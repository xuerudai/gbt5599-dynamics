# GB/T 5599 Dynamics Evaluation Guide

Use this guide when a task requires a complete GB/T 5599-oriented dynamics analysis rather than only running the bundled script.

## First-pass questions

Before calculating, identify:

- Data source: simulation or test; SIMPACK, UM, VI-Rail, MATLAB, Python, CSV/TXT, or spreadsheet.
- Vehicle and operation: vehicle type, formation, axle arrangement, load case, speed, line condition, curve radius if applicable, track irregularity, and whether the model has reached steady operation.
- Evaluation scope: running safety only, ride quality only, or both.
- Available channels: time or distance, vehicle/car id, carbody lateral acceleration, carbody vertical acceleration, wheel vertical force, wheel lateral force, derailment coefficient, wheel unloading ratio, axle/wheelset lateral force, speed, and sampling rate.
- Standard basis: GB/T 5599-2019 plus any user-provided clauses, project-specific acceptance limits, or company rules.

If a required channel is missing, do not invent it. Derive it only when the raw physical channels are available and the sign convention is known.

## Indicator families

Running safety:

- Derailment coefficient or wheel-rail lateral/vertical force ratio.
- Wheel unloading ratio based on static wheel load and dynamic vertical wheel force.
- Axle lateral force or wheelset lateral force.
- Optional project indicators: wheel load, wheel-rail vertical force, guiding force, lateral displacement, yaw/roll response, or suspension travel when the user requests diagnostic analysis.

Ride quality and comfort:

- Carbody lateral acceleration.
- Carbody vertical acceleration.
- Statistical acceleration after standard-consistent filtering and spatial/time segmentation.
- Sperling ride index or project-specific comfort index.

Frequency diagnosis:

- PSD/Welch spectra for carbody acceleration.
- Dominant frequency, bandwidth, and case-to-case energy shifts.
- Connection between spectra and time-domain/Sperling results.

## Data preparation

Use structured parsing when possible:

- Read CSV/TXT/XLSX with column names preserved.
- Inspect units before calculation; common force units are N or kN, acceleration units are m/s2 or g.
- Convert time to distance using measured speed or a declared constant speed when no distance channel exists.
- Remove initialization or obvious transient segments using a documented stable interval.
- Use zero-phase filtering for post-processing; do not introduce phase lag into evaluation signals.
- Preserve raw data and write processed data separately.

## Safety processing logic

Derailment coefficient:

- If a derailment coefficient channel exists, confirm whether it is signed. Use absolute value for limit comparison when left/right signs are opposite by convention.
- If only lateral and vertical wheel forces exist, derive the coefficient as `Y / Q` only after confirming sign and unit conventions.
- Apply spatial statistics if the analysis represents running along track; document the spatial step and percentile.

Wheel unloading ratio:

- Use `Q0` from static equilibrium, model documentation, or measured static load.
- Compute unloading as `(Q0 - Q) / Q0`.
- Evaluate the positive unloading tail; increased load is not unloading.

Axle lateral force:

- Combine left/right lateral wheel forces belonging to the same wheelset according to the model's sign convention.
- Convert to kN before comparing with kN limits.
- Calculate the standard or project limit from static axle load when required.

## Ride quality processing logic

Acceleration:

- Use lateral and vertical carbody acceleration at the correct vehicle body location.
- Remove the unstable initial segment.
- Filter in the standard/project frequency band, commonly `0.4-40 Hz` for the present workflow.
- Segment by distance or time according to the evaluation plan.
- Report both the statistical value and raw/filtered peaks when useful for diagnostics.

Sperling index:

- Use stable, filtered acceleration.
- Segment with a documented window length, commonly `5 s` in this workflow.
- Apply the correct lateral or vertical frequency weighting.
- Report lateral and vertical indices separately plus the maximum when summarizing.

## Generalization rules

Do not assume the source project's cases are universal:

- Treat case names as metadata, not physics.
- Create a case config for each new project.
- Allow comparison groups to represent tunnel area, tunnel shape, speed, load state, track irregularity, suspension variant, crosswind condition, or any other experimental factor.
- If filenames do not follow `<condition>_che<car>.txt`, adapt the parser or create a preprocessing step that normalizes filenames and columns.

## Output checklist

A complete analysis should usually include:

- `analysis_config.json` with all assumptions and limits.
- Processed per-case/per-car data.
- Metric summary table with values, limits, utilization ratios, and critical wheel/axle/car.
- Sperling window table when ride index is calculated.
- Figures for safety, acceleration, ride index, heatmaps, and spectra when relevant.
- A short report section explaining method, assumptions, results, worst cases, and whether each requirement is satisfied.

## QA checks

Before final conclusions:

- Confirm sample rate is sufficient for the highest analyzed frequency.
- Confirm unit conversions by checking realistic force and acceleration ranges.
- Confirm static load and axle load values.
- Confirm the selected stable interval removes initialization response.
- Confirm the reported worst case is based on evaluated values, not accidental raw spikes unless the standard/project requires peak values.
- Confirm the same sign convention is used across all wheels, cars, and cases.
- Check that any limit changes caused by speed, curve radius, vehicle category, or project rules are documented.

## Report wording pattern

Use concise, auditable language:

1. State data source and operating condition.
2. State GB/T 5599-2019 as the evaluation framework and list any project-specific assumptions.
3. Describe safety indicators and statistical method.
4. Describe comfort/ride-quality indicators and filtering/windowing.
5. Present worst-case values and utilization ratios.
6. Explain physical trends without overstating causality.
7. Conclude compliance separately for safety and ride quality.
