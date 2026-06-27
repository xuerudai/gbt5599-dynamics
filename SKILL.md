---
name: gbt5599-dynamics
description: Process railway vehicle dynamics results against GB/T 5599-2019. Use when Codex needs to analyze SIMPACK or similar multi-block TXT exports for train running safety and ride quality, including derailment coefficient, wheel unloading ratio, axle lateral force, carbody lateral/vertical acceleration, Sperling ride index, tunnel-condition comparisons, processed CSV/XLSX tables, figures, and report-ready interpretation.
---

# GB/T 5599 Dynamics

## Overview

Use this skill to reproduce the user's GB/T 5599-2019 vehicle dynamics post-processing workflow for municipal/intercity EMU tunnel cases. The reference implementation is `scripts/analyze_gbt5599.py`; read or run it when the task involves actual SIMPACK TXT exports or when exact formulas, defaults, or output columns matter.

## Workflow

1. Identify the available dynamics result files.
   - Prefer SIMPACK multi-block `.txt` exports containing a carbody acceleration block and a wheel-rail safety block.
   - Expect filenames like `35m2_che1.txt`, `40m2_1_che8.txt`, or generally `<condition>_che<car>.txt`.
   - Confirm the case-to-condition mapping before interpreting figures or writing report text.

2. Check assumptions before calculation.
   - Start analysis at `t >= 5 s` unless the user specifies a different stable interval.
   - Use constant speed `160 km/h` when exports do not include distance.
   - Use static wheel load `56505.6 N` unless the model or static balance result gives another value.
   - Use spatial step `2 m` and percentile `99.85%` for safety metrics.
   - Filter carbody acceleration with a zero-phase `0.4-40 Hz` bandpass.
   - Use a `5 s` Sperling window with 50% overlap.

3. Evaluate safety metrics.
   - Derailment coefficient: use absolute value because left/right SIMPACK signs can be opposite; evaluate the `99.85%` spatial percentile.
   - Wheel unloading ratio: compute `(Q0 - Q) / Q0`; retain the positive unloading tail; evaluate the `99.85%` spatial percentile.
   - Axle lateral force: combine left and right lateral wheel forces for each wheelset/axle as `Y_L + Y_R`; convert to kN; evaluate the absolute `99.85%` spatial percentile.
   - Default limits: derailment coefficient `0.8`, unloading ratio `0.65`, axle lateral force `15 + P0/3`, where `P0` is static axle load in kN.
   - If the line condition differs from straight track or `R > 400 m`, ask or set the applicable derailment limit before judging compliance.

4. Evaluate comfort and ride quality.
   - Compute lateral and vertical carbody acceleration after filtering.
   - Use spatial `2 m` windows and the GB/T-style statistical acceleration `mean(peaks) + 2.2 * std(peaks)`.
   - Default acceleration reference limit: `2.5 m/s^2`.
   - Compute lateral and vertical Sperling ride indices using GB/T 5599-2019 Annex E frequency weighting over `0.5-40 Hz`.
   - Use `W = 2.5` as the grade-1/优秀 reference for the present EMU-style vehicle unless the user provides another classification.

5. Produce traceable outputs.
   - Write processed per-case/per-car data with time, distance, raw/filtered acceleration, wheel forces, unloading ratios, derailment coefficients, and axle lateral forces.
   - Write summary tables with values, critical wheel/axle, limits, and utilization ratios.
   - Export a machine-readable config recording all assumptions.
   - Create report-ready figures for area comparisons, shape comparisons, heatmaps, critical acceleration, frequency spectra, and Sperling comparisons when enough cases exist.

6. Interpret results conservatively.
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
  --percentile 99.85
```

For new projects with different tunnel conditions, car counts, or case names, create a JSON case config based on `references/case_config_example.json` and run:

```bash
python scripts/analyze_gbt5599.py \
  --input-dir path/to/original_result \
  --output-dir path/to/analysis_output \
  --case-config path/to/case_config.json
```

The `condition` field must match the filename prefix before `_che<car number>`, such as `mycase_che1.txt`. The script still defaults to the original five-case tunnel study when `--case-config` is not supplied.

If the script does not match the user's TXT block structure or column names, patch a copy of the script in the working project rather than changing the skill resource itself.

## References

Read `references/workflow.md` when writing report text, adapting the method to new data, or explaining why each metric is processed this way. Use `references/case_config_example.json` as the template for non-default case mappings.
