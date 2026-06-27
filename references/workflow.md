# GB/T 5599 Dynamics Workflow Notes

## Input data shape

The reference workflow was created for SIMPACK text exports with two data blocks:

- Block 1: time, carbody lateral acceleration, carbody vertical acceleration.
- Block 2: time plus wheel-rail safety channels for four wheelsets, left/right wheels.

The parser expects two header lines beginning with `"time"` and tab-separated numeric data. If the export format changes, first inspect headers and update the parser or column matching logic.

## Fixed case mapping from the source project

- `35m2` -> `case1`, 35 m2, area comparison.
- `40m2_1` -> `case2`, 40 m2-1, shape comparison.
- `40m2_2` -> `case3`, 40 m2-2, area and shape baseline.
- `40m2_3` -> `case4`, 40 m2-3, shape comparison.
- `45m2` -> `case5`, 45 m2, area comparison.

Use `case1`, `case3`, `case5` for tunnel-area comparisons and `case2`, `case3`, `case4` for tunnel-shape comparisons unless the user provides a different experimental design.

For a new project, do not hard-code these names in prose or code. Create a config JSON following `case_config_example.json`:

- `cases[].condition`: filename prefix before `_che<car number>`.
- `cases[].case_id`: stable internal identifier used in tables and processed filenames.
- `cases[].label`: label shown in figures and reports.
- `cases[].detail`: human-readable condition description.
- `case_order`: plotting and table order.
- `car_order`: expected car labels and plotting order.
- `area_cases` and `shape_cases`: optional comparison groups reused by the bundled plotting functions. They can contain any `case_id` values, not only area or shape studies.

## Default processing assumptions

- Constant speed: 160 km/h.
- Stable interval: discard data before 5 s.
- Static wheel load: 56505.6 N.
- Static axle load: 113.0112 kN.
- Spatial statistics step: 2 m.
- Safety percentile: 99.85%.
- Carbody acceleration filter: zero-phase 0.4-40 Hz bandpass.
- Sperling window: 5 s, 50% overlap.

## Default limits

- Derailment coefficient: 0.8 for straight track or curve radius greater than 400 m.
- Wheel unloading ratio: 0.65 for speeds up to 160 km/h.
- Axle lateral force: `15 + P0/3`, where `P0` is static axle load in kN. With the source project's static wheel load, this is 52.6704 kN.
- Carbody acceleration reference limit: 2.5 m/s2.
- Sperling grade-1/优秀 reference: W = 2.5 for the current EMU-type use case.

## Metric details

Derailment coefficient:

- Use the absolute value for left/right channels because SIMPACK signs can be opposite.
- Convert time to distance using constant speed when no distance column exists.
- Interpolate to 2 m spatial samples and take the 99.85th percentile.

Wheel unloading ratio:

- Compute `(Q0 - Q) / Q0`, where `Q0` is static wheel load and `Q` is dynamic vertical wheel force.
- Preserve positive unloading; do not use the absolute value because increased wheel load is not unloading.
- Interpolate to 2 m spatial samples and take the 99.85th percentile.

Axle lateral force:

- For each wheelset, combine left and right lateral wheel forces as `Y_L + Y_R`.
- Convert N to kN.
- Use absolute values for evaluation.
- Interpolate to 2 m spatial samples and take the 99.85th percentile.

Carbody acceleration:

- Apply 0.4-40 Hz zero-phase bandpass filtering before statistical evaluation.
- Split the stable interval into 2 m spatial windows.
- For each spatial window, take the absolute peak.
- Compute `mean(peaks) + 2.2 * std(peaks)` as the statistical acceleration.

Sperling index:

- Remove the mean from each 5 s segment.
- Use a Hanning window and coherent-gain correction.
- Compute discrete harmonic amplitudes from the FFT.
- Keep 0.5-40 Hz components.
- Apply lateral or vertical Annex E frequency weighting.
- Combine harmonic contributions as the tenth-root sum used by the bundled script.

## Reporting pattern

When writing a report section:

1. State the SIMPACK source, speed, stable interval, static wheel load, and GB/T 5599-2019 basis.
2. Describe safety processing: 2 m spatial statistics and 99.85% percentile for derailment, unloading, and axle lateral force.
3. Describe comfort processing: 0.4-40 Hz filtered accelerations and 5 s Sperling windows.
4. Present worst-case values and utilization ratios.
5. Distinguish tunnel-area effects from tunnel-shape effects.
6. Identify controlling cars only when the pattern is consistent enough to support the conclusion.
