"""GB/T 5599-2019 dynamics analysis for the municipal train tunnel cases.

The script parses the SIMPACK multi-block TXT exports, evaluates running safety
and ride quality, writes traceable processed data, and creates publication-ready
SVG/PDF/PNG figures.

Default assumptions (all exposed as CLI options):
* analysis starts at 5 s to conservatively exclude the visible 2-3 s transition
* constant speed: 160 km/h (needed because the exports have no distance column)
* static wheel load: 56,505.6 N
* derailment coefficient limit: 0.8 (straight / R > 400 m)
* wheel unloading ratio limit: 0.65 (v <= 160 km/h)
* carbody lateral/vertical acceleration limit: 2.5 m/s^2
* Sperling grade-1 reference: W = 2.5 for the present EMU-type train

Example
-------
python analyze_gbt5599.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt, welch
from matplotlib.ticker import FormatStrFormatter, MaxNLocator, ScalarFormatter


# Mandatory editable-text settings for publication SVG files.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "Arial",
    "DejaVu Sans",
    "Liberation Sans",
]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams.update(
    {
        # Report-ready typography: figures remain legible after insertion and
        # moderate down-scaling in Word/PDF reports.
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 11,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9.5,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


CASE_MAP = {
    "35m2": ("case1", "算例1", "35 m²", "面积"),
    "40m2_1": ("case2", "算例2", "40 m²-1", "形状"),
    "40m2_2": ("case3", "算例3", "40 m²-2", "面积/形状"),
    "40m2_3": ("case4", "算例4", "40 m²-3", "形状"),
    "45m2": ("case5", "算例5", "45 m²", "面积"),
}
AREA_CASES = ["case1", "case3", "case5"]
SHAPE_CASES = ["case2", "case3", "case4"]
CASE_ORDER = ["case1", "case2", "case3", "case4", "case5"]
CAR_ORDER = [f"car{i}" for i in range(1, 9)]
CASE_LABEL = {value[0]: value[1] for value in CASE_MAP.values()}
CASE_DETAIL = {value[0]: value[2] for value in CASE_MAP.values()}

COLORS = {
    "case1": "#0F4D92",
    "case2": "#42949E",
    "case3": "#B64342",
    "case4": "#9A4D8E",
    "case5": "#767676",
}
MARKERS = {"case1": "o", "case2": "s", "case3": "D", "case4": "^", "case5": "P"}
COLOR_CYCLE = ["#0F4D92", "#42949E", "#B64342", "#9A4D8E", "#767676", "#D08B2E", "#4F7D3A", "#5A5A5A"]
MARKER_CYCLE = ["o", "s", "D", "^", "P", "v", "X", "*"]


def color_for_case(case: str) -> str:
    if case not in COLORS:
        COLORS[case] = COLOR_CYCLE[len(COLORS) % len(COLOR_CYCLE)]
    return COLORS[case]


def marker_for_case(case: str) -> str:
    if case not in MARKERS:
        MARKERS[case] = MARKER_CYCLE[len(MARKERS) % len(MARKER_CYCLE)]
    return MARKERS[case]


def load_case_config(path: Path) -> None:
    """Override case mapping and comparison groups from a user JSON file."""
    global CASE_MAP, AREA_CASES, SHAPE_CASES, CASE_ORDER, CAR_ORDER, CASE_LABEL, CASE_DETAIL

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = data.get("cases")
    if not cases:
        raise ValueError("case config must contain a non-empty 'cases' list")

    parsed: dict[str, tuple[str, str, str, str]] = {}
    case_order: list[str] = []
    for index, case in enumerate(cases, start=1):
        condition = str(case.get("condition") or case.get("prefix") or "").strip()
        if not condition:
            raise ValueError(f"case config entry {index} is missing 'condition'")
        case_id = str(case.get("case_id") or case.get("id") or f"case{index}").strip()
        label = str(case.get("label") or case_id).strip()
        detail = str(case.get("detail") or condition).strip()
        group = str(case.get("group") or case.get("category") or "").strip()
        parsed[condition.lower()] = (case_id, label, detail, group)
        case_order.append(case_id)

    CASE_MAP = parsed
    CASE_ORDER = list(data.get("case_order") or case_order)
    CAR_ORDER = list(data.get("car_order") or data.get("cars") or CAR_ORDER)
    AREA_CASES = list(data.get("area_cases") or data.get("comparison_groups", {}).get("area", []))
    SHAPE_CASES = list(data.get("shape_cases") or data.get("comparison_groups", {}).get("shape", []))
    CASE_LABEL = {value[0]: value[1] for value in CASE_MAP.values()}
    CASE_DETAIL = {value[0]: value[2] for value in CASE_MAP.values()}


@dataclass(frozen=True)
class Config:
    input_dir: Path
    output_dir: Path
    speed_kmh: float
    static_wheel_load_n: float
    derailment_limit: float
    unloading_limit: float
    acceleration_limit: float
    sperling_grade1_limit: float
    analysis_start_s: float = 5.0
    spatial_step_m: float = 2.0
    percentile: float = 99.85
    filter_low_hz: float = 0.4
    filter_high_hz: float = 40.0
    sperling_window_s: float = 5.0

    @property
    def speed_ms(self) -> float:
        return self.speed_kmh / 3.6

    @property
    def static_axle_load_kn(self) -> float:
        return 2.0 * self.static_wheel_load_n / 1000.0

    @property
    def axle_lateral_limit_kn(self) -> float:
        return 15.0 + self.static_axle_load_kn / 3.0


def clean_header(text: str) -> str:
    return text.strip().strip('"')


def parse_numeric_rows(lines: list[str], start: int, ncols: int) -> np.ndarray:
    rows: list[list[float]] = []
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) != ncols:
            if rows:
                break
            continue
        try:
            row = [float(x) for x in parts]
        except ValueError:
            if rows:
                break
            continue
        rows.append(row)
    if not rows:
        raise ValueError(f"No numeric rows found after line {start + 1}")
    return np.asarray(rows, dtype=float)


def parse_simpack_txt(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_indices = [i for i, line in enumerate(lines) if line.startswith('"time"')]
    if len(header_indices) < 2:
        raise ValueError(f"{path.name}: expected two data blocks, found {len(header_indices)}")

    blocks: list[pd.DataFrame] = []
    for header_index in header_indices[:2]:
        headers = [clean_header(x) for x in lines[header_index].split("\t")]
        values = parse_numeric_rows(lines, header_index + 2, len(headers))
        blocks.append(pd.DataFrame(values, columns=headers))

    acc, safety = blocks
    if len(acc) != len(safety):
        raise ValueError(f"{path.name}: acceleration and safety row counts differ")
    return acc, safety


def identify_case(path: Path) -> tuple[str, str, str]:
    stem = path.stem.lower()
    match = re.match(r"(.+)_che(\d+)$", stem)
    if not match:
        raise ValueError(f"Unexpected filename: {path.name}")
    condition, car_number = match.groups()
    if condition not in CASE_MAP:
        raise ValueError(f"Unknown condition in {path.name}")
    case_id, case_label, _, _ = CASE_MAP[condition]
    return case_id, case_label, f"car{car_number}"


def find_column(df: pd.DataFrame, wheel: int, side: str, token: str) -> str:
    needle = f"ws{wheel}_{side}"
    matches = [column for column in df.columns if needle in column and token in column]
    if len(matches) != 1:
        raise KeyError(f"Expected one column for {needle!r} + {token!r}, found {matches}")
    return matches[0]


def bandpass(data: np.ndarray, fs: float, low: float, high: float) -> np.ndarray:
    high = min(high, 0.95 * fs / 2.0)
    sos = butter(4, [low, high], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, data)


def spatial_samples(time: np.ndarray, values: np.ndarray, speed_ms: float, step_m: float) -> np.ndarray:
    distance = (time - time[0]) * speed_ms
    target = np.arange(distance[0], distance[-1] + 1e-9, step_m)
    return np.interp(target, distance, values)


def spatial_window_peaks(
    time: np.ndarray, values: np.ndarray, speed_ms: float, step_m: float
) -> np.ndarray:
    distance = (time - time[0]) * speed_ms
    edges = np.arange(distance[0], distance[-1] + step_m, step_m)
    peaks: list[float] = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (distance >= left) & (distance < right)
        if np.any(mask):
            peaks.append(float(np.max(np.abs(values[mask]))))
    return np.asarray(peaks)


def statistical_acceleration(peaks: np.ndarray) -> float:
    if peaks.size < 2:
        return float(peaks.max(initial=0.0))
    return float(peaks.mean() + 2.2 * peaks.std(ddof=1))


def sperling_weight(frequency: np.ndarray, direction: str) -> np.ndarray:
    f = np.asarray(frequency, dtype=float)
    weight = np.ones_like(f)
    if direction == "vertical":
        low = (f >= 0.5) & (f < 5.9)
        mid = (f >= 5.9) & (f < 20.0)
        weight[low] = 0.325 * f[low] ** 2
        weight[mid] = 400.0 / f[mid] ** 2
    elif direction == "lateral":
        low = (f >= 0.5) & (f < 5.4)
        mid = (f >= 5.4) & (f < 26.0)
        weight[low] = 0.8 * f[low] ** 2
        weight[mid] = 650.0 / f[mid] ** 2
    else:
        raise ValueError(direction)
    return weight


def sperling_index(segment: np.ndarray, fs: float, direction: str) -> float:
    """Calculate W from discrete harmonic amplitudes following Annex E."""
    x = np.asarray(segment, dtype=float) - float(np.mean(segment))
    n = len(x)
    if n < 8:
        return float("nan")
    window = np.hanning(n)
    coherent_gain = window.mean()
    amplitude = 2.0 * np.abs(np.fft.rfft(x * window)) / (n * coherent_gain)
    frequency = np.fft.rfftfreq(n, 1.0 / fs)
    valid = (frequency >= 0.5) & (frequency <= 40.0)
    frequency = frequency[valid]
    amplitude = amplitude[valid]
    weight = sperling_weight(frequency, direction)
    # GB/T 5599-2019 Annex E: W_i = 3.57 * [(A_i^3 / f_i) F(f_i)]^(1/10).
    wi = 3.57 * np.power((amplitude**3 / frequency) * weight, 0.1)
    return float(np.sum(wi**10) ** 0.1)


def sperling_windows(
    time: np.ndarray, data: np.ndarray, fs: float, direction: str, window_s: float
) -> list[dict[str, float]]:
    nwin = int(round(window_s * fs))
    if nwin > len(data):
        nwin = len(data)
    # A 50% overlap improves time coverage while retaining the prescribed 5 s window.
    step = max(1, nwin // 2)
    records: list[dict[str, float]] = []
    for start in range(0, len(data) - nwin + 1, step):
        stop = start + nwin
        records.append(
            {
                "time_start_s": float(time[start]),
                "time_end_s": float(time[stop - 1]),
                "W": sperling_index(data[start:stop], fs, direction),
            }
        )
    return records


def evaluate_file(path: Path, cfg: Config) -> tuple[dict, pd.DataFrame, list[dict]]:
    case_id, case_label, car = identify_case(path)
    acc, safety = parse_simpack_txt(path)

    time_all = acc.iloc[:, 0].to_numpy(dtype=float)
    stable_mask = time_all >= cfg.analysis_start_s
    if stable_mask.sum() < 100:
        raise ValueError(f"{path.name}: insufficient samples after {cfg.analysis_start_s:g} s")
    acc = acc.loc[stable_mask].reset_index(drop=True)
    safety = safety.loc[stable_mask].reset_index(drop=True)
    time = acc.iloc[:, 0].to_numpy(dtype=float)
    dt = float(np.median(np.diff(time)))
    fs = 1.0 / dt
    ay_raw = acc.iloc[:, 1].to_numpy(dtype=float)
    az_raw = acc.iloc[:, 2].to_numpy(dtype=float)
    ay = bandpass(ay_raw, fs, cfg.filter_low_hz, cfg.filter_high_hz)
    az = bandpass(az_raw, fs, cfg.filter_low_hz, cfg.filter_high_hz)

    processed = pd.DataFrame(
        {
            "time_s": time,
            "distance_m": (time - time[0]) * cfg.speed_ms,
            "carbody_ay_raw_mps2": ay_raw,
            "carbody_az_raw_mps2": az_raw,
            "carbody_ay_filtered_mps2": ay,
            "carbody_az_filtered_mps2": az,
        }
    )

    derailment_by_wheel: dict[str, np.ndarray] = {}
    unloading_by_wheel: dict[str, np.ndarray] = {}
    lateral_by_wheel: dict[str, np.ndarray] = {}
    for wheel in range(1, 5):
        for side in ("L", "R"):
            wheel_id = f"ws{wheel}_{side}"
            yq = safety[find_column(safety, wheel, side, "Derailment coefficient")].to_numpy(float)
            lateral = safety[find_column(safety, wheel, side, "Lateral wheel force")].to_numpy(float)
            vertical = safety[find_column(safety, wheel, side, "Vertical wheel force")].to_numpy(float)
            unloading = (cfg.static_wheel_load_n - vertical) / cfg.static_wheel_load_n
            derailment_by_wheel[wheel_id] = yq
            unloading_by_wheel[wheel_id] = unloading
            lateral_by_wheel[wheel_id] = lateral
            processed[f"derailment_{wheel_id}"] = yq
            processed[f"unloading_{wheel_id}"] = unloading
            processed[f"Y_{wheel_id}_N"] = lateral
            processed[f"Q_{wheel_id}_N"] = vertical

    axle_lateral: dict[str, np.ndarray] = {}
    for wheel in range(1, 5):
        axle_id = f"ws{wheel}"
        h = lateral_by_wheel[f"ws{wheel}_L"] + lateral_by_wheel[f"ws{wheel}_R"]
        axle_lateral[axle_id] = h / 1000.0
        processed[f"H_{axle_id}_kN"] = h / 1000.0

    def percentile_by_channel(channels: dict[str, np.ndarray], absolute: bool) -> tuple[float, str, float]:
        evaluated: dict[str, float] = {}
        raw: dict[str, float] = {}
        for name, values in channels.items():
            sample = spatial_samples(time, values, cfg.speed_ms, cfg.spatial_step_m)
            if absolute:
                sample = np.abs(sample)
                raw[name] = float(np.max(np.abs(values)))
            else:
                raw[name] = float(np.max(values))
            evaluated[name] = float(np.percentile(sample, cfg.percentile))
        critical = max(evaluated, key=evaluated.get)
        return evaluated[critical], critical, raw[critical]

    derail_eval, derail_wheel, derail_peak = percentile_by_channel(derailment_by_wheel, True)
    unload_eval, unload_wheel, unload_peak = percentile_by_channel(unloading_by_wheel, False)
    axle_eval, axle_wheel, axle_peak = percentile_by_channel(axle_lateral, True)

    ay_peaks = spatial_window_peaks(time, ay, cfg.speed_ms, cfg.spatial_step_m)
    az_peaks = spatial_window_peaks(time, az, cfg.speed_ms, cfg.spatial_step_m)
    ay_stat = statistical_acceleration(ay_peaks)
    az_stat = statistical_acceleration(az_peaks)

    wy_windows = sperling_windows(time, ay, fs, "lateral", cfg.sperling_window_s)
    wz_windows = sperling_windows(time, az, fs, "vertical", cfg.sperling_window_s)
    w_records: list[dict] = []
    for direction, windows in (("lateral", wy_windows), ("vertical", wz_windows)):
        for record in windows:
            w_records.append({"case_id": case_id, "case_label": case_label, "car": car, "direction": direction, **record})
    wy = max((x["W"] for x in wy_windows), default=float("nan"))
    wz = max((x["W"] for x in wz_windows), default=float("nan"))

    summary = {
        "case_id": case_id,
        "case_label": case_label,
        "case_detail": CASE_DETAIL[case_id],
        "car": car,
        "source_file": path.name,
        "duration_s": float(time[-1] - time[0]),
        "sample_rate_hz": fs,
        "derailment_p99_85": derail_eval,
        "derailment_raw_peak": derail_peak,
        "derailment_critical_wheel": derail_wheel,
        "derailment_limit": cfg.derailment_limit,
        "derailment_utilization": derail_eval / cfg.derailment_limit,
        "unloading_p99_85": unload_eval,
        "unloading_raw_peak": unload_peak,
        "unloading_critical_wheel": unload_wheel,
        "unloading_limit": cfg.unloading_limit,
        "unloading_utilization": unload_eval / cfg.unloading_limit,
        "axle_lateral_p99_85_kN": axle_eval,
        "axle_lateral_raw_peak_kN": axle_peak,
        "axle_lateral_critical_axle": axle_wheel,
        "axle_lateral_limit_kN": cfg.axle_lateral_limit_kn,
        "axle_lateral_utilization": axle_eval / cfg.axle_lateral_limit_kn,
        "ay_stat_mps2": ay_stat,
        "az_stat_mps2": az_stat,
        "ay_raw_peak_mps2": float(np.max(np.abs(ay_raw))),
        "az_raw_peak_mps2": float(np.max(np.abs(az_raw))),
        "acceleration_limit_mps2": cfg.acceleration_limit,
        "ay_utilization": ay_stat / cfg.acceleration_limit,
        "az_utilization": az_stat / cfg.acceleration_limit,
        "sperling_Wy": wy,
        "sperling_Wz": wz,
        "sperling_Wmax": max(wy, wz),
        "sperling_grade1_limit": cfg.sperling_grade1_limit,
        "sperling_utilization": max(wy, wz) / cfg.sperling_grade1_limit,
    }
    return summary, processed, w_records


def add_panel_label(
    ax: plt.Axes, label: str, x: float = -0.14, y: float = 1.04
) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom")


def style_axis(ax: plt.Axes) -> None:
    ax.grid(axis="y", color="#D8D8D8", linewidth=0.5, alpha=0.7)
    ax.tick_params(direction="out", length=3)


def save_figure(fig: plt.Figure, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    # The current delivery contract requires PNG only. Remove obsolete vector
    # exports from earlier runs so that the output folder stays unambiguous.
    for suffix in (".svg", ".pdf"):
        obsolete = base.with_suffix(suffix)
        if obsolete.exists():
            obsolete.unlink()
    fig.savefig(base.with_suffix(".png"), dpi=400, bbox_inches="tight")
    plt.close(fig)


def comparison_panel(
    ax: plt.Axes,
    summary: pd.DataFrame,
    cases: list[str],
    metric: str,
    ylabel: str,
    limit: float | None,
    *,
    limit_text: str | None = None,
    y_decimals: int | None = None,
) -> None:
    x = np.arange(len(CAR_ORDER))
    for case in cases:
        values = [float(summary.query("case_id == @case and car == @car")[metric].iloc[0]) for car in CAR_ORDER]
        ax.plot(
            x,
            values,
            color=color_for_case(case),
            marker=marker_for_case(case),
            linewidth=1.6,
            markersize=4.5,
            label=CASE_LABEL[case],
        )
    plotted_max = max(
        float(summary.query("case_id in @cases")[metric].max()),
        np.finfo(float).eps,
    )
    if limit is not None:
        if limit_text is not None:
            ax.set_ylim(0, plotted_max * 1.25)
            ax.text(
                0.98,
                0.94,
                limit_text,
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=9,
                color="#4D4D4D",
            )
        elif limit > 3.0 * plotted_max:
            # Preserve visibility of differences when every result is far below the limit.
            ax.set_ylim(0, plotted_max * 1.25)
            ax.text(
                0.98,
                0.94,
                f"标准限值：{limit:.3g}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=9,
                color="#4D4D4D",
            )
        else:
            ax.axhline(limit, color="#272727", linestyle="--", linewidth=1.0, label="标准限值")
    ax.set_xticks(x, CAR_ORDER)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.035)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    if y_decimals is not None:
        ax.yaxis.set_major_formatter(FormatStrFormatter(f"%.{y_decimals}f"))
    style_axis(ax)


def make_safety_figure(summary: pd.DataFrame, cfg: Config, cases: list[str], title: str, output: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.4), constrained_layout=True)
    comparison_panel(
        axes[0], summary, cases, "derailment_p99_85", "脱轨系数", cfg.derailment_limit, y_decimals=3
    )
    comparison_panel(
        axes[1], summary, cases, "unloading_p99_85", "轮重减载率", cfg.unloading_limit, y_decimals=3
    )
    comparison_panel(
        axes[2],
        summary,
        cases,
        "axle_lateral_p99_85_kN",
        "轮轴横向力 (kN)",
        cfg.axle_lateral_limit_kn,
        y_decimals=3,
    )
    for label, ax in zip("abc", axes):
        add_panel_label(ax, label)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.10), ncol=len(labels))
    save_figure(fig, output)


def make_comfort_figure(summary: pd.DataFrame, cfg: Config, cases: list[str], title: str, output: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 6.2), constrained_layout=True)
    metrics = [
        ("ay_stat_mps2", "横向振动加速度 (m/s²)", cfg.acceleration_limit),
        ("az_stat_mps2", "垂向振动加速度 (m/s²)", cfg.acceleration_limit),
        ("sperling_Wy", "横向平稳性指标 $W_y$", cfg.sperling_grade1_limit),
        ("sperling_Wz", "垂向平稳性指标 $W_z$", cfg.sperling_grade1_limit),
    ]
    for label, ax, (metric, ylabel, limit) in zip("abcd", axes.flat, metrics):
        if metric.startswith("sperling_"):
            comparison_panel(ax, summary, cases, metric, ylabel, limit, limit_text="优良：2.5")
        else:
            comparison_panel(ax, summary, cases, metric, ylabel, limit)
        add_panel_label(ax, label)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.06), ncol=len(labels))
    save_figure(fig, output)


def make_heatmap(
    summary: pd.DataFrame,
    metric_specs: list[tuple[str, str]],
    output: Path,
) -> None:
    if len(metric_specs) != 3:
        raise ValueError("Each heatmap figure must contain exactly three indicators")
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.8), constrained_layout=True)
    for index, (ax, (metric, title)) in enumerate(zip(axes.flat, metric_specs)):
        matrix = np.asarray(
            [
                [
                    float(summary.query("case_id == @case and car == @car")[metric].iloc[0])
                    for car in CAR_ORDER
                ]
                for case in CASE_ORDER
            ]
        )
        im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd")
        ax.set_title(title, fontsize=13, pad=10)
        ax.set_xticks(np.arange(len(CAR_ORDER)), [str(i) for i in range(1, 9)])
        ax.set_xlabel("车厢编号")
        ax.set_yticks(np.arange(len(CASE_ORDER)))
        if index == 0:
            ax.set_yticklabels([CASE_LABEL[case] for case in CASE_ORDER])
            ax.set_ylabel("算例")
        else:
            ax.set_yticklabels([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
        cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.025)
        cbar.ax.tick_params(labelsize=9.5)
        add_panel_label(ax, "abc"[index], x=-0.10, y=1.04)
    save_figure(fig, output)


def make_critical_diagnostics(summary: pd.DataFrame, processed_dir: Path, output: Path) -> None:
    critical = summary.sort_values(["ay_utilization", "az_utilization"], ascending=False).iloc[0]
    csv_path = processed_dir / f"{critical.case_id}_{critical.car}_processed.csv.gz"
    data = pd.read_csv(csv_path)
    time = data["time_s"].to_numpy()
    fs = 1.0 / float(np.median(np.diff(time)))
    ay = data["carbody_ay_filtered_mps2"].to_numpy()
    az = data["carbody_az_filtered_mps2"].to_numpy()
    fy, pyy = welch(ay, fs=fs, nperseg=min(4096, len(ay)))
    fz, pzz = welch(az, fs=fs, nperseg=min(4096, len(az)))

    fig, axes = plt.subplots(2, 2, figsize=(8.8, 6.0), constrained_layout=True)
    axes[0, 0].plot(time, ay, color="#0F4D92", linewidth=0.65)
    axes[0, 1].plot(time, az, color="#B64342", linewidth=0.65)
    valid_y = (fy >= 0.5) & (fy <= 40.0)
    valid_z = (fz >= 0.5) & (fz <= 40.0)
    axes[1, 0].loglog(fy[valid_y], pyy[valid_y], color="#0F4D92", linewidth=1.0)
    axes[1, 1].loglog(fz[valid_z], pzz[valid_z], color="#B64342", linewidth=1.0)
    axes[0, 0].set_ylabel("横向加速度 (m/s²)")
    axes[0, 1].set_ylabel("垂向加速度 (m/s²)")
    axes[0, 0].set_xlabel("时间 (s)")
    axes[0, 1].set_xlabel("时间 (s)")
    axes[1, 0].set_ylabel("PSD ((m/s²)²/Hz)")
    axes[1, 1].set_ylabel("PSD ((m/s²)²/Hz)")
    axes[1, 0].set_xlabel("频率 (Hz)")
    axes[1, 1].set_xlabel("频率 (Hz)")
    axes[1, 0].set_xlim(0.4, 40)
    axes[1, 1].set_xlim(0.4, 40)
    axes[0, 0].set_xlim(6.0, 12.0)
    axes[0, 1].set_xlim(6.0, 12.0)
    for ax in axes[1, :]:
        ax.set_xscale("log")
        ax.set_xlim(0.5, 40.0)
        ax.set_xticks([0.5, 1, 2, 5, 10, 20, 40])
        ax.xaxis.set_major_formatter(ScalarFormatter())
    for label, ax in zip("abcd", axes.flat):
        style_axis(ax)
        add_panel_label(ax, label)
    save_figure(fig, output)


def build_frequency_spectra(summary: pd.DataFrame, processed_dir: Path) -> pd.DataFrame:
    """Build traceable 0.5-40 Hz Welch spectra for every case and car."""
    records: list[dict] = []
    for row in summary.itertuples(index=False):
        data = pd.read_csv(processed_dir / f"{row.case_id}_{row.car}_processed.csv.gz")
        time = data["time_s"].to_numpy()
        fs = 1.0 / float(np.median(np.diff(time)))
        ay = data["carbody_ay_filtered_mps2"].to_numpy()
        az = data["carbody_az_filtered_mps2"].to_numpy()
        fy, pyy = welch(ay, fs=fs, nperseg=min(2048, len(ay)), window="hann")
        fz, pzz = welch(az, fs=fs, nperseg=min(2048, len(az)), window="hann")
        valid_y = (fy >= 0.5) & (fy <= 40.0)
        valid_z = (fz >= 0.5) & (fz <= 40.0)
        if not np.array_equal(fy[valid_y], fz[valid_z]):
            raise RuntimeError("Lateral and vertical frequency grids differ")
        for frequency, psd_y, psd_z in zip(fy[valid_y], pyy[valid_y], pzz[valid_z]):
            records.append(
                {
                    "case_id": row.case_id,
                    "case_label": row.case_label,
                    "car": row.car,
                    "frequency_hz": frequency,
                    "lateral_psd_m2s4_per_hz": psd_y,
                    "vertical_psd_m2s4_per_hz": psd_z,
                }
            )
    return pd.DataFrame(records)


def make_frequency_figure(
    spectra: pd.DataFrame,
    cases: list[str],
    direction: str,
    output: Path,
) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(12.0, 6.4), sharex=True, constrained_layout=True)
    value_column = (
        "lateral_psd_m2s4_per_hz" if direction == "lateral" else "vertical_psd_m2s4_per_hz"
    )
    direction_label = "横向" if direction == "lateral" else "垂向"
    for ax, car in zip(axes.flat, CAR_ORDER):
        for case in cases:
            subset = spectra.query("case_id == @case and car == @car")
            frequency = subset["frequency_hz"].to_numpy()
            ax.loglog(
                frequency,
                subset[value_column].to_numpy(),
                color=COLORS[case],
                linewidth=1.0,
                label=CASE_LABEL[case],
            )
        ax.set_title(car, fontsize=11)
        ax.set_xlabel("频率 (Hz)")
        ax.set_xscale("log")
        ax.set_xlim(0.5, 40.0)
        ax.set_xticks([0.5, 1, 2, 5, 10, 20, 40])
        ax.xaxis.set_major_formatter(ScalarFormatter())
        style_axis(ax)
    axes[0, 0].set_ylabel(f"{direction_label}加速度PSD\n((m/s²)²/Hz)")
    axes[1, 0].set_ylabel(f"{direction_label}加速度PSD\n((m/s²)²/Hz)")
    for label, ax in zip("abcdefgh", axes.flat):
        add_panel_label(ax, label, x=-0.08, y=1.02)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.075), ncol=len(labels))
    save_figure(fig, output)


def make_sperling_figure(
    summary: pd.DataFrame, cfg: Config, cases: list[str], title: str, output: Path
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6), constrained_layout=True)
    comparison_panel(
        axes[0],
        summary,
        cases,
        "sperling_Wy",
        "横向平稳性指标 $W_y$",
        cfg.sperling_grade1_limit,
        limit_text="平稳性优：2.5",
    )
    comparison_panel(
        axes[1],
        summary,
        cases,
        "sperling_Wz",
        "垂向平稳性指标 $W_z$",
        cfg.sperling_grade1_limit,
        limit_text="平稳性优：2.5",
    )
    for label, ax in zip("ab", axes):
        add_panel_label(ax, label, x=-0.08, y=1.02)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.10), ncol=len(labels))
    save_figure(fig, output)


def write_readme(cfg: Config, summary: pd.DataFrame) -> None:
    worst = {
        "derailment": summary.loc[summary["derailment_utilization"].idxmax()],
        "unloading": summary.loc[summary["unloading_utilization"].idxmax()],
        "axle": summary.loc[summary["axle_lateral_utilization"].idxmax()],
        "acc": summary.loc[summary[["ay_utilization", "az_utilization"]].max(axis=1).idxmax()],
        "ride_quality": summary.loc[summary["sperling_utilization"].idxmax()],
    }
    lines = [
        "# GB/T 5599-2019 analysis output",
        "",
        "## Fixed mapping",
        "",
        "- Case 1 = 35 m²",
        "- Case 2 = 40 m²-1",
        "- Case 3 = 40 m²-2",
        "- Case 4 = 40 m²-3",
        "- Case 5 = 45 m²",
        "- Figure car labels: car1, car4, car8",
        "",
        "## Processing assumptions",
        "",
        f"- Constant speed: {cfg.speed_kmh:g} km/h (source TXT files do not contain distance/speed).",
        f"- Analysis starts at t = {cfg.analysis_start_s:g} s to exclude initialization/settling response.",
        f"- Static wheel load: {cfg.static_wheel_load_n:.1f} N; static axle load: {cfg.static_axle_load_kn:.4f} kN.",
        f"- Spatial statistical step: {cfg.spatial_step_m:g} m; safety percentile: {cfg.percentile:g}%.",
        f"- Carbody acceleration filter: {cfg.filter_low_hz:g}-{cfg.filter_high_hz:g} Hz.",
        f"- Derailment limit: {cfg.derailment_limit:g}; unloading limit: {cfg.unloading_limit:g}.",
        f"- Axle lateral force limit: {cfg.axle_lateral_limit_kn:.4f} kN.",
        f"- Carbody acceleration reference limit: {cfg.acceleration_limit:g} m/s².",
        f"- 平稳性指标采用5 s窗；优良参考值W = {cfg.sperling_grade1_limit:g}。",
        "",
        "## Important interpretation notes",
        "",
        "- Derailment coefficient uses the absolute value because left/right SIMPACK signs are opposite.",
        "- Wheel unloading uses (Q0-Q)/Q0 and retains the positive (unloading) tail.",
        "- Axle lateral force uses Y_L + Y_R; the initial equal/opposite contact components cancel.",
        "- The 0.8 derailment limit assumes straight track or curve radius R > 400 m. Use --derailment-limit 0.9 for R=250-400 m when applicable.",
        "- 平稳性指标按附录E频率权重和离散5 s谐波幅值计算。",
        "",
        "## Worst utilization records",
        "",
    ]
    for key, row in worst.items():
        lines.append(f"- {key}: {row.case_label} {row.car}")
    (cfg.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_analysis_report(cfg: Config, summary: pd.DataFrame) -> None:
    """Write a compact report that always reflects the current full consist."""
    metrics = {
        "脱轨系数": ("derailment_p99_85", "derailment_limit", "derailment_utilization"),
        "轮重减载率": ("unloading_p99_85", "unloading_limit", "unloading_utilization"),
        "轮轴横向力(kN)": (
            "axle_lateral_p99_85_kN",
            "axle_lateral_limit_kN",
            "axle_lateral_utilization",
        ),
        "横向振动加速度(m/s²)": ("ay_stat_mps2", "acceleration_limit_mps2", "ay_utilization"),
        "垂向振动加速度(m/s²)": ("az_stat_mps2", "acceleration_limit_mps2", "az_utilization"),
        "横向平稳性指标": ("sperling_Wy", "sperling_grade1_limit", "sperling_utilization"),
        "垂向平稳性指标": ("sperling_Wz", "sperling_grade1_limit", "sperling_utilization"),
    }
    lines = [
        "# 8节编组列车动力学分析报告",
        "",
        "## 处理设置",
        "",
        f"- 共处理5个算例×8节车=40组数据，分析区间从{cfg.analysis_start_s:g} s开始。",
        f"- 安全指标采用{cfg.spatial_step_m:g} m空间样本的{cfg.percentile:g}%分位统计值。",
        f"- 车体加速度采用{cfg.filter_low_hz:g}-{cfg.filter_high_hz:g} Hz带通滤波。",
        "- 平稳性指标采用5 s窗、50%重叠和GB/T 5599-2019附录E频率权重。",
        "",
        "## 全编组最不利指标",
        "",
        "| 指标 | 最不利算例/车厢 | 评价值 | 限值 | 限值利用率 |",
        "|---|---|---:|---:|---:|",
    ]
    for label, (value_col, limit_col, util_col) in metrics.items():
        row = summary.loc[summary[value_col].idxmax()]
        utilization = float(row[value_col]) / float(row[limit_col])
        lines.append(
            f"| {label} | {row.case_label} {row.car} | {row[value_col]:.4f} | "
            f"{row[limit_col]:.4f} | {utilization:.2%} |"
        )

    car_summary = (
        summary.groupby("car", observed=True)[["ay_stat_mps2", "az_stat_mps2", "sperling_Wmax"]]
        .mean()
        .reindex(CAR_ORDER)
    )
    lines.extend(
        [
            "",
            "## 编组位置效应",
            "",
            "下表为各车厢跨5个算例的平均响应，用于识别稳定的位置效应。",
            "",
            "| 车厢 | 横向加速度 | 垂向加速度 | 平稳性指标最大值 |",
            "|---|---:|---:|---:|",
        ]
    )
    for car, row in car_summary.iterrows():
        lines.append(
            f"| {car} | {row.ay_stat_mps2:.4f} | {row.az_stat_mps2:.4f} | {row.sperling_Wmax:.4f} |"
        )
    worst_car = car_summary["sperling_Wmax"].idxmax()
    lines.extend(
        [
            "",
            f"跨算例平均后，{worst_car}的平稳性指标最高，是当前编组中应优先关注的位置。",
            "",
            "## 说明",
            "",
            "图中车厢名称统一使用car1-car8；面积对比为算例1、3、5，形状对比为算例2、3、4。",
        ]
    )
    (cfg.output_dir / "analysis_report.md").write_text("\n".join(lines), encoding="utf-8")


def run(cfg: Config) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    for old_figure in figures_dir.iterdir():
        if old_figure.is_file() and old_figure.suffix.lower() in {".png", ".svg", ".pdf"}:
            old_figure.unlink()
    processed_dir = cfg.output_dir / "processed_data"
    processed_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(cfg.input_dir.glob("*.txt"))
    expected_files = len(CASE_ORDER) * len(CAR_ORDER)
    if len(files) != expected_files:
        raise RuntimeError(f"Expected {expected_files} TXT files, found {len(files)} in {cfg.input_dir}")

    summaries: list[dict] = []
    all_w_records: list[dict] = []
    for path in files:
        summary, processed, w_records = evaluate_file(path, cfg)
        summaries.append(summary)
        all_w_records.extend(w_records)
        processed.to_csv(
            processed_dir / f"{summary['case_id']}_{summary['car']}_processed.csv.gz",
            index=False,
            compression="gzip",
        )
        print(f"Processed {path.name}: {summary['case_label']} {summary['car']}")

    summary_df = pd.DataFrame(summaries)
    summary_df["case_id"] = pd.Categorical(summary_df["case_id"], CASE_ORDER, ordered=True)
    summary_df["car"] = pd.Categorical(summary_df["car"], CAR_ORDER, ordered=True)
    summary_df = summary_df.sort_values(["case_id", "car"]).reset_index(drop=True)
    w_df = pd.DataFrame(all_w_records)

    summary_df.to_csv(cfg.output_dir / "metric_summary.csv", index=False, encoding="utf-8-sig")
    w_df.to_csv(cfg.output_dir / "sperling_windows.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(cfg.output_dir / "GBT5599_analysis_summary.xlsx", engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="metric_summary", index=False)
        w_df.to_excel(writer, sheet_name="sperling_windows", index=False)

    config_record = {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in cfg.__dict__.items()
    }
    config_record["static_axle_load_kn"] = cfg.static_axle_load_kn
    config_record["axle_lateral_limit_kn"] = cfg.axle_lateral_limit_kn
    (cfg.output_dir / "analysis_config.json").write_text(
        json.dumps(config_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    make_safety_figure(summary_df, cfg, AREA_CASES, "不同隧道面积下的运行安全性", figures_dir / "fig01_safety_area")
    make_safety_figure(summary_df, cfg, SHAPE_CASES, "不同隧道形状下的运行安全性", figures_dir / "fig02_safety_shape")
    make_comfort_figure(summary_df, cfg, AREA_CASES, "不同隧道面积下的振动与平稳性", figures_dir / "fig03_comfort_area")
    make_comfort_figure(summary_df, cfg, SHAPE_CASES, "不同隧道形状下的振动与平稳性", figures_dir / "fig04_comfort_shape")
    safety_heatmaps = [
        ("derailment_p99_85", "脱轨系数"),
        ("unloading_p99_85", "轮重减载率"),
        ("axle_lateral_p99_85_kN", "轮轴横向力 (kN)"),
    ]
    comfort_heatmaps = [
        ("ay_stat_mps2", "横向振动加速度 (m/s²)"),
        ("az_stat_mps2", "垂向振动加速度 (m/s²)"),
        ("sperling_Wmax", "平稳性指标 $W$"),
    ]
    make_heatmap(summary_df, safety_heatmaps, figures_dir / "fig05a_safety_heatmaps")
    make_heatmap(summary_df, comfort_heatmaps, figures_dir / "fig05b_comfort_heatmaps")
    make_critical_diagnostics(summary_df, processed_dir, figures_dir / "fig06_critical_acceleration")
    spectra_df = build_frequency_spectra(summary_df, processed_dir)
    spectra_df.to_csv(cfg.output_dir / "frequency_spectra.csv.gz", index=False, compression="gzip")
    make_frequency_figure(
        spectra_df,
        AREA_CASES,
        "lateral",
        figures_dir / "fig07_frequency_area_lateral",
    )
    make_frequency_figure(
        spectra_df,
        AREA_CASES,
        "vertical",
        figures_dir / "fig08_frequency_area_vertical",
    )
    make_frequency_figure(
        spectra_df,
        SHAPE_CASES,
        "lateral",
        figures_dir / "fig09_frequency_shape_lateral",
    )
    make_frequency_figure(
        spectra_df,
        SHAPE_CASES,
        "vertical",
        figures_dir / "fig10_frequency_shape_vertical",
    )
    make_sperling_figure(
        summary_df,
        cfg,
        AREA_CASES,
        "不同隧道面积下的Sperling平稳性指标",
        figures_dir / "fig11_sperling_area",
    )
    make_sperling_figure(
        summary_df,
        cfg,
        SHAPE_CASES,
        "不同隧道形状下的Sperling平稳性指标",
        figures_dir / "fig12_sperling_shape",
    )
    write_readme(cfg, summary_df)
    write_analysis_report(cfg, summary_df)
    print(f"Analysis complete: {cfg.output_dir}")


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=here / "original_result")
    parser.add_argument("--output-dir", type=Path, default=here / "analysis_output")
    parser.add_argument(
        "--case-config",
        type=Path,
        help="JSON file that overrides case mapping, car order, and comparison groups.",
    )
    parser.add_argument("--speed-kmh", type=float, default=160.0)
    parser.add_argument("--static-wheel-load-n", type=float, default=56505.6)
    parser.add_argument("--derailment-limit", type=float, default=0.8)
    parser.add_argument("--unloading-limit", type=float, default=0.65)
    parser.add_argument("--acceleration-limit", type=float, default=2.5)
    parser.add_argument("--sperling-grade1-limit", type=float, default=2.5)
    parser.add_argument("--analysis-start-s", type=float, default=5.0)
    parser.add_argument("--spatial-step-m", type=float, default=2.0)
    parser.add_argument("--percentile", type=float, default=99.85)
    parser.add_argument("--filter-low-hz", type=float, default=0.4)
    parser.add_argument("--filter-high-hz", type=float, default=40.0)
    parser.add_argument("--sperling-window-s", type=float, default=5.0)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    if args.case_config:
        load_case_config(args.case_config)
    run(
        Config(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            speed_kmh=args.speed_kmh,
            static_wheel_load_n=args.static_wheel_load_n,
            derailment_limit=args.derailment_limit,
            unloading_limit=args.unloading_limit,
            acceleration_limit=args.acceleration_limit,
            sperling_grade1_limit=args.sperling_grade1_limit,
            analysis_start_s=args.analysis_start_s,
            spatial_step_m=args.spatial_step_m,
            percentile=args.percentile,
            filter_low_hz=args.filter_low_hz,
            filter_high_hz=args.filter_high_hz,
            sperling_window_s=args.sperling_window_s,
        )
    )
