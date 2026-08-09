# GB/T 5599 Dynamics

Reusable Codex skill and reference scripts for railway vehicle dynamics analysis using **GB/T 5599-2019** as the evaluation framework.

This repository is intended for train dynamics post-processing tasks such as running safety evaluation, ride quality analysis, wheel-rail force statistics, and report-ready result interpretation.

## What This Skill Does

- Plans and audits GB/T 5599-oriented vehicle dynamics evaluations.
- Processes SIMPACK-style TXT exports with a bundled Python script.
- Supports configurable operating cases, vehicle/car order, and comparison groups.
- Evaluates typical indicators such as:
  - derailment coefficient
  - wheel unloading ratio
  - axle lateral force
  - carbody lateral and vertical acceleration
  - Sperling ride index
- Produces traceable outputs including processed data, summary tables, figures, and analysis configuration files.

The bundled script is a practical reference implementation. The skill itself is broader: it can guide adaptation to SIMPACK, UM, VI-Rail, MATLAB, Python, CSV/TXT, and spreadsheet workflows when the required channels are available.

## Repository Structure

```text
gbt5599-dynamics/
  SKILL.md
  README.md
  agents/
    openai.yaml
  references/
    gbt5599_evaluation_guide.md
    workflow.md
    case_config_example.json
  scripts/
    analyze_gbt5599.py
```

## Install As A Codex Skill

Clone or download this repository into your Codex skills directory:

```text
C:\Users\<your-user-name>\.codex\skills\gbt5599-dynamics
```

Then restart Codex. You can invoke it with:

```text
$gbt5599-dynamics
```

Example prompt:

```text
Use $gbt5599-dynamics to analyze these SIMPACK vehicle dynamics TXT exports according to GB/T 5599.
```

## Run The Reference Script

The script expects SIMPACK-style TXT exports similar to:

```text
<condition>_che<car-number>.txt
```

Example:

```text
35m2_che1.txt
35m2_che2.txt
40m2_1_che1.txt
```

Basic command:

```bash
python scripts/analyze_gbt5599.py ^
  --input-dir path/to/original_result ^
  --output-dir path/to/analysis_output
```

Common options:

```bash
python scripts/analyze_gbt5599.py ^
  --input-dir result_analysis/original_result ^
  --output-dir result_analysis/analysis_output ^
  --speed-kmh 160 ^
  --static-wheel-load-n 56505.6 ^
  --analysis-start-s 5 ^
  --spatial-step-m 2 ^
  --percentile 99.85 ^
  --filter-low-hz 0.4 ^
  --filter-high-hz 40 ^
  --sperling-window-s 5
```

## Configure New Operating Cases

For projects that do not use the original `35m2`, `40m2_1`, `40m2_2`, `40m2_3`, `45m2` naming, create a case configuration JSON based on:

```text
references/case_config_example.json
```

Run with:

```bash
python scripts/analyze_gbt5599.py ^
  --input-dir path/to/original_result ^
  --output-dir path/to/analysis_output ^
  --case-config path/to/case_config.json
```

Important fields:

- `condition`: filename prefix before `_che<car-number>`.
- `case_id`: stable internal ID used in output tables.
- `label`: label shown in figures and reports.
- `detail`: human-readable condition description.
- `case_order`: plotting and table order.
- `car_order`: expected vehicle/car labels.
- `area_cases` and `shape_cases`: optional comparison groups. They can represent any factor, such as speed, tunnel area, load state, track irregularity, or suspension variant.

## Main Outputs

The reference script writes outputs such as:

- `analysis_config.json`
- `metric_summary.csv`
- `GBT5599_analysis_summary.xlsx`
- `sperling_windows.csv`
- `frequency_spectra.csv.gz`
- processed per-case/per-car CSV files
- report-ready figures under `figures/`
- a short Markdown analysis report

## Notes And Limitations

- The script is not a replacement for reading GB/T 5599-2019 or project-specific acceptance rules.
- Always confirm units, sign conventions, static wheel load, stable time interval, speed, curve radius, and applicable limits before judging compliance.
- If your export column names or file structure differ from the SIMPACK-style reference format, adapt the parser or create a preprocessing step.
- Do not treat the example tunnel case mapping as fixed. It is only the default example from the source project.

## References Inside The Skill

- `references/gbt5599_evaluation_guide.md`: broad GB/T 5599 evaluation workflow, required channels, QA checks, and report pattern.
- `references/workflow.md`: details for the bundled SIMPACK TXT workflow.
- `references/case_config_example.json`: template for custom case mappings.
