---
name: gbt5599-dynamics
description: Perform railway vehicle dynamics analysis and post-processing with GB/T 5599-2019 as the governing evaluation framework. Use when Codex needs to plan, audit, or execute train dynamics evaluation from SIMPACK/UM/VI-Rail/MATLAB/Python/CSV/TXT outputs, including running safety, wheel-rail force statistics, derailment coefficient, wheel unloading ratio, axle lateral force, carbody acceleration, Sperling ride index, stability/comfort figures, configurable operating cases, traceable tables, and report-ready interpretation.
---

# GB/T 5599 Dynamics

## Overview

Use this skill to evaluate railway vehicle dynamics results using GB/T 5599-2019 as the analysis framework. It supports both hands-on post-processing and higher-level work: choosing indicators, checking whether data channels are sufficient, adapting scripts to new simulation exports, judging compliance, and writing a defensible methods/results section.

The bundled `scripts/analyze_gbt5599.py` is a runnable reference implementation for SIMPACK-style TXT exports. Treat it as a reusable starting point, not as the only supported workflow.

## Workflow

1. Identify the evaluation task and required indicators.
   - Read `references/gbt5599_evaluation_guide.md` before designing or auditing an analysis plan.
   - Separate running safety, ride quality/comfort, and frequency-domain diagnosis.
   - Confirm vehicle type, speed, line condition, simulation/test source, stable interval, static wheel load, and required GB/T 5599 clauses or tables if the user provides them.

2. Identify the available dynamics result files.
   - Accept SIMPACK, UM, VI-Rail, MATLAB, Python, CSV, TXT, XLSX, or other exports if required channels are present.
   - Prefer data containing time/distance, vehicle/car id, carbody lateral/vertical acceleration, vertical wheel force, lateral wheel force, derailment coefficient or raw Y/Q channels, wheelset/axle identifiers, speed, and sampling rate.
   - For the bundled script, expect filenames like `35m2_che1.txt`, `40m2_1_che8.txt`, or generally `<condition>_che<car>.txt`.
   - Confirm or create a case mapping before interpreting figures or writing report text.

3. Check assumptions before calculation.
   - Start analysis at `t >= 5 s` unless the user specifies a different stable interval.
   - Use constant speed `160 km/h` when exports do not include distance.
   - Use static wheel load `56505.6 N` unless the model or static balance result gives another value.
   - Use spatial step `2 m` and percentile `99.85%` for safety metrics unless a different standard/project requirement is provided.
   - Filter carbody acceleration with a zero-phase `0.4-40 Hz` bandpass unless the selected evaluation item requires another band.
   - Use a `5 s` Sperling window with documented overlap for the present workflow.

4. Evaluate running safety.
   - Derailment coefficient: use absolute value when left/right signs are opposite by convention; evaluate the documented spatial statistic.
   - Wheel unloading ratio: compute `(Q0 - Q) / Q0`; retain the positive unloading tail; evaluate the documented spatial statistic.
   - Axle lateral force: combine left and right lateral wheel forces for each wheelset/axle according to sign convention; convert to kN; evaluate the documented spatial statistic.
   - Default limits in the reference workflow: derailment coefficient `0.8`, unloading ratio `0.65`, axle lateral force `15 + P0/3`, where `P0` is static axle load in kN.
   - If speed, curve radius, vehicle category, or project rules differ, ask for or set the applicable limits before judging compliance.

5. Evaluate ride quality and comfort.
   - Compute lateral and vertical carbody acceleration after filtering.
   - Use spatial or time windows as required by the chosen evaluation item; the bundled script uses `2 m` windows and `mean(peaks) + 2.2 * std(peaks)` for statistical acceleration.
   - Default acceleration reference limit in the reference workflow: `2.5 m/s^2`.
   - Compute lateral and vertical Sperling ride indices using GB/T 5599-oriented frequency weighting over `0.5-40 Hz`.
   - Use `W = 2.5` as the grade-1 reference for the present EMU-style workflow unless the user provides another classification.

6. Produce traceable outputs.
   - Write processed per-case/per-car data with time, distance, raw/filtered acceleration, wheel forces, unloading ratios, derailment coefficients, and axle lateral forces.
   - Write summary tables with values, critical wheel/axle, limits, and utilization ratios.
   - Export a machine-readable config recording all assumptions.
   - Create report-ready figures for selected comparison groups, heatmaps, critical acceleration, frequency spectra, and Sperling comparisons when enough cases exist.

7. Interpret results conservatively.
   - Report the worst case and car for each metric.
   - Compare all metrics to limits through utilization ratios, not only raw magnitudes.
   - Separate safety conclusions from comfort/ride-quality conclusions.
   - Mention whether high values are local to a car/case or systematic across the train.
   - For reports, state the stable-time cutoff, spatial statistics, filter band, static wheel load, and limit assumptions so the result is auditable.

## Running The Script

Use the bundled script when the user's data layout matches the reference workflow:

```bash
python scripts/analyze_gbt5599.py --input-dir path/to/original_result --output-dir path/to/analysis_output
```

Common options:

```bash
python scripts/analyze_gbt5599.py \
  --input-dir result_analysis/original_result \
  --output-dir result_analysis/analysis_output \
  --speed-kmh 160 \
  --static-wheel-load-n 56505.6 \
  --analysis-start-s 5 \
  --spatial-step-m 2 \
  --percentile 99.85 \
  --filter-low-hz 0.4 \
  --filter-high-hz 40 \
  --sperling-window-s 5
```

For new projects with different tunnel conditions, car counts, or case names, create a JSON case config based on `references/case_config_example.json` and run:

```bash
python scripts/analyze_gbt5599.py \
  --input-dir path/to/original_result \
  --output-dir path/to/analysis_output \
  --case-config path/to/case_config.json
```

The `condition` field must match the filename prefix before `_che<car number>`, such as `mycase_che1.txt`. The script defaults to the original five-case tunnel study when `--case-config` is not supplied.

If the script does not match the user's TXT block structure or column names, patch a copy of the script in the working project rather than changing the skill resource itself.

## References

Read `references/gbt5599_evaluation_guide.md` for the broad GB/T 5599 analysis framework, required data channels, indicator logic, QA checks, and report structure.

Read `references/workflow.md` when working with the original SIMPACK TXT workflow or adapting that script to new data. Use `references/case_config_example.json` as the template for non-default case mappings.
