# GB/T 5599 Dynamics

## 中文介绍

`gbt5599-dynamics` 是一个用于轨道车辆动力学结果分析与后处理的 Codex skill，评价框架以 **GB/T 5599-2019《机车车辆动力学性能评定及试验鉴定规范》** 为核心。它既可以帮助 Codex 规划动力学评价流程，也可以配合仓库中的参考脚本，对 SIMPACK 等软件导出的动力学结果进行自动化处理、统计、绘图和报告解释。

这个 skill 的目标不是把某一个固定项目的脚本简单搬过来，而是把“按 GB/T 5599 做动力学分析时应该如何检查数据、选择指标、处理信号、统计结果、判断限值和写报告”的经验沉淀下来，让后续不同车辆、不同速度、不同线路条件、不同仿真软件导出的结果都能有一套清晰的处理框架。

## 主要功能

### 1. 动力学评价流程规划

当你准备分析列车或车辆系统动力学结果时，这个 skill 可以帮助确认：

- 需要评价运行安全性、平稳性/舒适性，还是两者都需要；
- 仿真或试验数据是否包含必要通道；
- 需要哪些工况信息，例如速度、车辆编组、载荷状态、线路条件、曲线半径、轨道不平顺、稳定计算区间等；
- 哪些指标适合用于结果比较和报告撰写；
- 哪些限值需要来自 GB/T 5599、项目要求或用户补充说明。

### 2. 运行安全性指标处理

该 skill 支持围绕 GB/T 5599 常用安全性指标进行后处理和解释，包括：

- 脱轨系数；
- 轮重减载率；
- 轮轴横向力 / 轮对横向力；
- 轮轨横向力、垂向力；
- 静轮重、静轴重；
- 各指标的限值利用率；
- 最不利工况、最不利车厢、最不利轮位或轮轴识别。

参考处理逻辑包括：

- 根据稳定区间截取数据；
- 将时间序列按速度换算为空间位置；
- 按空间步长进行统计；
- 对安全性指标取指定百分位；
- 根据静轮重或静轴重计算相关评价量；
- 输出可追溯的原始值、评价值、限值和利用率。

### 3. 平稳性与舒适性指标处理

该 skill 可以处理车体振动响应和乘坐平稳性相关内容，包括：

- 车体横向加速度；
- 车体垂向加速度；
- 0.4-40 Hz 等频带滤波；
- 统计加速度；
- Sperling 平稳性指标；
- 横向/垂向平稳性对比；
- 车厢位置效应；
- 不同工况下舒适性变化规律。

参考脚本中默认采用 5 s 窗口计算 Sperling 指标，并可输出每个窗口的结果，便于追踪最不利时段。

### 4. 频域诊断与图表输出

除了表格评价，skill 还支持围绕频域和可视化结果开展分析，例如：

- 车体加速度功率谱密度；
- 横向/垂向频率成分对比；
- 不同工况频谱差异；
- 安全性指标折线图；
- 舒适性指标折线图；
- 工况-车厢热力图；
- 最不利加速度时程诊断图；
- Sperling 指标对比图。

这些图可以用于论文、技术报告或项目汇报中的结果展示。

### 5. 可配置工况体系

该 skill 不绑定固定工况。原项目中默认包含 `35m2`、`40m2_1`、`40m2_2`、`40m2_3`、`45m2` 等隧道工况，但这只是示例。

对于新的项目，可以通过 `references/case_config_example.json` 定义任意工况，例如：

- 不同速度；
- 不同曲线半径；
- 不同载荷状态；
- 不同隧道断面；
- 不同轨道不平顺；
- 不同悬挂参数；
- 不同气动载荷方案；
- 不同车辆编组或车厢数量。

配置文件可以指定工况编号、显示名称、绘图顺序、车厢顺序和对比组。

### 6. 可追溯结果输出

参考脚本可以生成一套比较完整的分析结果，包括：

- `analysis_config.json`：记录速度、静轮重、稳定区间、空间步长、滤波频带、限值等参数；
- `metric_summary.csv`：各工况、各车厢的主要评价指标；
- `GBT5599_analysis_summary.xlsx`：Excel 汇总表；
- `sperling_windows.csv`：平稳性指标窗口结果；
- `frequency_spectra.csv.gz`：频谱数据；
- `processed_data/`：每个工况、每节车的处理后时程数据；
- `figures/`：报告用图；
- `analysis_report.md`：简要分析报告。

这些输出便于复核，也方便后续写论文、报告或进行二次绘图。

## 适用数据

该 skill 可以指导处理多种来源的数据，包括：

- SIMPACK 导出的 TXT 结果；
- UM、VI-Rail 等多体动力学软件结果；
- MATLAB 或 Python 处理后的 CSV/TXT；
- Excel 或表格形式的动力学结果；
- 试验数据，只要包含必要的时间、速度、加速度和轮轨力通道。

仓库中的 `scripts/analyze_gbt5599.py` 目前最直接支持 SIMPACK 风格 TXT 文件。若你的数据列名、文件结构或单位不同，可以让 Codex 基于这个 skill 修改解析器或增加预处理脚本。

## 仓库结构

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

其中：

- `SKILL.md`：Codex 调用 skill 时读取的核心说明；
- `references/gbt5599_evaluation_guide.md`：通用 GB/T 5599 动力学评价指南；
- `references/workflow.md`：参考脚本对应的 SIMPACK TXT 工作流说明；
- `references/case_config_example.json`：自定义工况配置模板；
- `scripts/analyze_gbt5599.py`：可运行的参考后处理脚本。

## 安装为 Codex Skill

将本仓库下载或克隆到 Codex 的 skills 目录：

```text
C:\Users\<your-user-name>\.codex\skills\gbt5599-dynamics
```

然后重启 Codex，即可通过下面的方式调用：

```text
$gbt5599-dynamics
```

示例：

```text
使用 $gbt5599-dynamics，按照 GB/T 5599 分析这些 SIMPACK 动力学结果，并输出安全性、平稳性和主要图表。
```

## 运行参考脚本

参考脚本默认适用于类似下面命名的 SIMPACK TXT 文件：

```text
<condition>_che<car-number>.txt
```

例如：

```text
35m2_che1.txt
35m2_che2.txt
40m2_1_che1.txt
```

基础命令：

```bash
python scripts/analyze_gbt5599.py ^
  --input-dir path/to/original_result ^
  --output-dir path/to/analysis_output
```

常用参数：

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

## 配置新工况

如果新项目不使用原始隧道工况名称，可以参考：

```text
references/case_config_example.json
```

运行时指定：

```bash
python scripts/analyze_gbt5599.py ^
  --input-dir path/to/original_result ^
  --output-dir path/to/analysis_output ^
  --case-config path/to/case_config.json
```

关键字段：

- `condition`：文件名前缀，即 `_che<car-number>` 前面的部分；
- `case_id`：输出表格中的稳定工况编号；
- `label`：图表和报告中的显示名称；
- `detail`：工况说明；
- `case_order`：表格和绘图顺序；
- `car_order`：车辆/车厢顺序；
- `area_cases`、`shape_cases`：对比组名称，实际可以用于任意对比因素。

## 注意事项

- 本 skill 不能替代 GB/T 5599 标准原文，也不能替代项目验收条款；
- 进行合规判断前，必须确认单位、符号约定、静轮重、速度、曲线半径、稳定区间和适用限值；
- 如果数据格式与参考脚本不一致，应先修改解析逻辑或进行数据预处理；
- 示例工况映射只是原项目默认示例，不是固定要求；
- 若涉及正式试验鉴定或工程验收，应由具备资质的专业人员复核。

---

## English Introduction

`gbt5599-dynamics` is a Codex skill for railway vehicle dynamics analysis and post-processing using **GB/T 5599-2019** as the evaluation framework. It helps Codex plan, audit, execute, and explain vehicle dynamics evaluations for running safety, ride quality, wheel-rail force statistics, and report-ready interpretation.

The skill is broader than a single project script. It captures a reusable workflow for checking available channels, selecting indicators, processing signals, computing statistics, comparing limits, and writing defensible analysis text.

## Key Capabilities

### 1. Evaluation Planning

The skill helps identify:

- whether the task involves running safety, ride quality, or both;
- whether the available data channels are sufficient;
- vehicle type, speed, formation, load case, line condition, curve radius, track irregularity, and stable analysis interval;
- which metrics and comparison groups are appropriate;
- which limits must come from GB/T 5599, project requirements, or user-provided rules.

### 2. Running Safety Post-processing

Supported indicators include:

- derailment coefficient;
- wheel unloading ratio;
- axle or wheelset lateral force;
- wheel-rail lateral and vertical forces;
- static wheel load and static axle load;
- utilization ratios;
- worst case, worst car, critical wheel, or critical axle identification.

The reference workflow supports stable-interval selection, time-to-distance conversion, spatial statistics, percentile evaluation, and traceable output of evaluated values, raw peaks, limits, and utilization ratios.

### 3. Ride Quality And Comfort Analysis

The skill supports:

- carbody lateral acceleration;
- carbody vertical acceleration;
- bandpass filtering such as 0.4-40 Hz;
- statistical acceleration;
- Sperling ride index;
- lateral and vertical ride-quality comparison;
- car-position effects and operating-condition effects.

### 4. Frequency-domain Diagnosis And Figures

The workflow can guide or generate:

- acceleration PSD / Welch spectra;
- dominant-frequency comparison;
- safety metric plots;
- comfort metric plots;
- case-car heatmaps;
- critical acceleration diagnostics;
- Sperling index comparison figures.

### 5. Configurable Operating Cases

The skill is not limited to the source tunnel cases. New projects can define arbitrary cases through `references/case_config_example.json`, such as speed cases, curve-radius cases, load states, tunnel sections, track irregularity levels, suspension variants, aerodynamic load cases, or different train formations.

### 6. Traceable Outputs

The bundled reference script can generate:

- `analysis_config.json`;
- `metric_summary.csv`;
- `GBT5599_analysis_summary.xlsx`;
- `sperling_windows.csv`;
- `frequency_spectra.csv.gz`;
- processed per-case/per-car CSV files;
- figures under `figures/`;
- a short Markdown analysis report.

## Supported Data Sources

The skill can guide work with:

- SIMPACK TXT exports;
- UM, VI-Rail, or other multibody dynamics exports;
- MATLAB/Python CSV or TXT outputs;
- Excel/spreadsheet results;
- test data with sufficient time, speed, acceleration, and wheel-rail force channels.

The bundled `scripts/analyze_gbt5599.py` directly targets SIMPACK-style TXT files. For different formats, adapt the parser or add a preprocessing step.

## Install As A Codex Skill

Clone or download this repository into:

```text
C:\Users\<your-user-name>\.codex\skills\gbt5599-dynamics
```

Restart Codex and invoke:

```text
$gbt5599-dynamics
```

Example prompt:

```text
Use $gbt5599-dynamics to analyze these vehicle dynamics results according to GB/T 5599.
```

## Notes

- This skill does not replace the GB/T 5599 standard text or project acceptance rules.
- Always confirm units, sign conventions, static wheel load, speed, curve radius, stable interval, and applicable limits.
- If the export format differs from the reference SIMPACK TXT workflow, adapt the parser before running compliance calculations.
