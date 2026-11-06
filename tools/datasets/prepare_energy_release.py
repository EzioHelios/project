# ruff: noqa: T201, RUF001
"""Package validated energy data into self-contained, documented releases."""

import argparse
import csv
import fnmatch
import gzip
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from tools.datasets.energy_release_io import read_csv, read_sequence
from tools.datasets.verify_energy_release import sha256, verify

VERSION = "1.1.0"
NAMES = {
    "events": "仓储用能事件数据集",
    "forecast": "仓储短期负荷预测数据集",
    "inputs": "仓储短期负荷预测输入集",
}
RENAMES = {
    "activity_timing_usable_under_pilot_rule": "event_timing_eligible",
    "observed_increment_to_30min_dynamic_energy_ratio": "increment_to_window_dynamic_energy_ratio",
    "deduplicated_register_observations": "deduplicated_register_records",
}
# Descriptions define actual stored fields, including audit and optional review columns.
DESCRIPTIONS = dict(
    line.split("|", 1)
    for line in """
site_id|场站匿名编号
meter_id|电表匿名编号
sequence_id|序列唯一编号，沿用数据处理版本编号
step|序列内从0开始的行号
observed_at|源记录观测时间，按元数据时间规则转换
available_at|消息接收时间；源表未保存接收时间时为空
availability_status|message_received_time表示有接收时间；ingestion_time_unknown表示接收时间未知
cumulative_energy_kwh|系统单位映射后的累计电能示值
quality_status|源记录质量状态；历史档案无源质量标志时按数值有效性赋值
source_system|采集系统或历史档案来源
source_ref|源记录关联摘要，不包含原始设备地址
mapping_version|单位及点位映射版本
source_time_field|源表采用的时间列名
source_time_basis|观测时间转换依据或企业时间假设
legacy_quality_basis|历史档案质量标志判定依据
legacy_time_semantics_status|历史档案时区核实状态
duplicate_conflict|同表同记录时间是否存在数值冲突
valid_register|示值是否满足本处理版本的有效性检查
interval_start|计量区间起点，区间采用左闭右开约定
interval_end|计量区间终点
interval_end_exclusive|事件区间不包含的终点
start_source_ref|区间起点累计示值的源记录摘要
end_source_ref|区间终点累计示值的源记录摘要
history_source_start|历史输入第一计量区间的起点源摘要
history_source_end|历史输入最后计量区间的终点源摘要
duration_seconds|区间起止时间差
average_power_kw|区间电量除以区间小时数所得的平均功率
electricity_kwh|有效累计示值差分，或有效区间电量聚合值
quality_flag|区间质量状态，枚举定义见docs/data_description.md
is_valid_interval|区间能否按当前规则计算电量和平均功率
segment_id|同表连续区间分段号；缺口或无效区间触发分段
primary_evaluation_eligible|该目标行是否纳入主评测，时间对齐假设行不纳入
split|时间分区：train、validation、test；事件集另有boundary
month|序列归属月份，格式YYYY-MM
observations|事件序列观测行数
parent_first_row|序列在该电表原生区间表中的首行号，从0开始
parent_last_row|序列在该电表原生区间表中的末行号，包含该行
input_path|本包根目录下的序列输入相对目录
label_path|本包根目录下的事件标注相对目录
target_path|本包根目录下的未来实测派生目标相对目录
profile|预测任务配置编号
prediction_origin|预测发起时间；未来计量区间从该时刻开始
history_length|历史输入步数
forecast_horizon|未来预测步数
history_parent_start_row|历史输入在该电表15分钟底表中的首行号，从0开始
future_parent_start_row|未来目标在该电表15分钟底表中的首行号，从0开始
observation_lag_steps|预测发起前预留的历史可用性滞后步数
sequence_position_in_batch|序列在批文件中的位置，从0开始
hour|未来计量区间起点的本地小时，0至23
minute|未来计量区间起点的本地分钟，0至59
weekday|未来计量区间起点的星期序号，星期一为0，星期日为6
state|规则状态：unknown、low_load、active_load、high_load
smoothed_power_kw|按该表规则平滑窗口计算的平均功率
verification_level|标注核实等级；事件rule_candidate与逐点weak_rule_label均属规则标注
label_source|候选事件标注依据
label_quality|事件序列标注质量状态
label_type|请求中的候选事件输出类型
state_labels|逐点状态标注文件引用
event_id|事件唯一编号
event_type|候选类型：activity_above_background或charging_activity_candidate
candidate_tags|CSV中以竖线分隔的候选属性；JSON中为数组
duration_minutes|规则识别事件区间的持续分钟数
max_interval_average_power_kw|候选区间内最大区间平均功率
max_smoothed_power_kw|候选区间内最大平滑功率
boundary_resolution_seconds|候选事件边界的原生时间分辨率
boundary_semantics|边界解释，表示曲线阈值越限范围
rule_version|产生候选标注的规则处理版本
smoothing_window_minutes|该表采用的功率平滑窗口时长
reviewed_label|人工复核后的标签；未复核为空
independent_evidence|独立业务证据引用；未复核为空
reviewer|复核人员；未复核为空
reviewed_at|复核时间；未复核为空
boundary_review|边界复核结果；未复核为空
notes|复核备注；未复核为空
raw_source_records|源表记录数，含重复记录
deduplicated_register_records|按电表和记录时间去重后的累计示值行数
duplicate_records_removed|去重移除的记录数
duplicate_conflict_readings|被选留记录中存在同时间示值冲突的记录数
first_observed_at|最早的已记录观测时间
last_observed_at|最晚的已记录观测时间
invalid_register_readings|未通过有效性检查的累计示值记录数
native_interval_seconds|电表原生采样间隔
valid_native_intervals|有效原生计量区间数
invalid_or_gap_intervals|无效、首条或缺口区间数
maximum_observation_gap_hours|相邻观测最大间隔
register_decrease_intervals|累计示值下降区间数
candidate_events|规则候选事件数量
extended_activity_candidates|带extended_activity_review属性的候选数量
forecast_15min_intervals|可用于构造预测任务的15分钟区间数
forecast_sequences|已导出的预测序列数
time_alignment_assumption_intervals|依赖时间对齐假设的15分钟区间数
event_timing_eligible|该表是否通过当前事件时间识别的量化步进筛查
role_status|回路用途分类：负荷、发电或储能等
meter_purpose|平台设备清单登记的回路用途
meter_purpose_confirmation|回路用途证据等级
meter_scope|电表覆盖范围核实状态
timezone|时区标识
source_type|累计示值及派生区间数据的来源类型
energy_unit|电能单位
power_unit|功率单位
metering_semantics_status|单位映射、CT/PT及示值分辨率核实状态
physical_rated_power_verified|现场额定功率是否已独立核实
processing_version|源数值处理版本
release_version|目录、字段说明及包装版本
sampling_interval_seconds|预测区间长度
target_columns|模型应预测的数值列
archive_comparison_offset_hours|仅用于档案时间对照的偏移小时数
reading_time|重复冲突档案保留的源时间字符串，未经时区修正
normalized_value|重复冲突档案中经系统映射的累计示值
overlapping_numeric_pairs|时间对照中的共同有效数值对数量
equal_value_fraction|对照数值相同的比例
median_absolute_register_difference_kwh|对照累计示值绝对差的中位数
offset_applied_to_dataset|该对照时间偏移是否应用于发布数据
conclusion|时间对照结论
example_id|格式示例编号
example_path|本包根目录下的示例相对目录
eligible_nonoverlapping_target_windows|该表、配置、分区满足条件且目标不重叠的窗口数
exported_windows|实际导出窗口数
status|导出可用状态
sequences|预测窗口数
model|基线模型编号
scope|评测纳入范围
target_steps|该基线在评测范围内的有效目标步数
MAE_kw|平均绝对误差
RMSE_kw|均方根误差
WAPE_percent|绝对误差总和除以实测功率绝对值总和，分母为0时为空
last_observed_value|采用历史最后一步功率的恒值预测
previous_day|采用历史中同一时刻前一天的功率；历史无对应点时为空
previous_week|采用历史中同一时刻前一周的功率；历史无对应点时为空
source_name|规则或参数来源
standard_code|标准编号；企业曲线假设不对应标准时为null
confidence_level|规则候选可信度状态，未按独立真值校准
training_end_exclusive|标定训练期不包含的终点
calibration_observations|阈值标定使用的训练观测数量
minimum_activity_duration_minutes|候选活动最短持续分钟数
extended_activity_review_minutes|长时活动复核阈值
observed_min_positive_increment_kwh|训练示值最小正增量，不能等同于硬件分辨率
increment_is_verified_register_resolution|示值增量是否已被核实为电表硬件分辨率
active_threshold_kw|高于背景的活动功率阈值
high_threshold_kw|高负荷功率阈值
increment_to_window_dynamic_energy_ratio|观测最小正增量与训练动态范围对应窗口电量之比
quantization_screen_source|量化步进筛查的企业假设
threshold_derivation|训练阈值的推导规则
interpretation|事件标注含义
valid_from|参数有效起点
observed_native_interval_seconds|训练数据的原生区间长度
visible_start|该事件在当前月序列中可见的起点
visible_end_exclusive|该事件在当前月序列中可见的不包含终点
continues_before_sequence|该事件是否从当前序列之前延续
continues_after_sequence|该事件是否延续至当前序列之后
events|该月序列可见的候选事件数组
""".strip().splitlines()
)
INTEGER_FIELDS = {
    "step",
    "observations",
    "parent_first_row",
    "parent_last_row",
    "history_length",
    "forecast_horizon",
    "history_parent_start_row",
    "future_parent_start_row",
    "observation_lag_steps",
    "sequence_position_in_batch",
    "hour",
    "minute",
    "weekday",
    "raw_source_records",
    "deduplicated_register_records",
    "duplicate_records_removed",
    "duplicate_conflict_readings",
    "invalid_register_readings",
    "native_interval_seconds",
    "valid_native_intervals",
    "invalid_or_gap_intervals",
    "register_decrease_intervals",
    "candidate_events",
    "extended_activity_candidates",
    "forecast_15min_intervals",
    "forecast_sequences",
    "time_alignment_assumption_intervals",
    "archive_comparison_offset_hours",
    "overlapping_numeric_pairs",
    "eligible_nonoverlapping_target_windows",
    "exported_windows",
    "sequences",
    "target_steps",
    "boundary_resolution_seconds",
    "calibration_observations",
    "sampling_interval_seconds",
    "observed_native_interval_seconds",
    "segment_id",
}
BOOLEAN_FIELDS = {
    "duplicate_conflict",
    "valid_register",
    "is_valid_interval",
    "primary_evaluation_eligible",
    "event_timing_eligible",
    "offset_applied_to_dataset",
    "physical_rated_power_verified",
    "increment_is_verified_register_resolution",
    "continues_before_sequence",
    "continues_after_sequence",
}
NUMBER_FIELDS = {
    "duration_seconds",
    "duration_minutes",
    "smoothing_window_minutes",
    "maximum_observation_gap_hours",
    "equal_value_fraction",
    "WAPE_percent",
    "hour",
    "minute",
    "weekday",
}
NULLABLE_FIELDS = {
    "available_at",
    "interval_start",
    "start_source_ref",
    "duration_seconds",
    "electricity_kwh",
    "average_power_kw",
    "smoothed_power_kw",
    "reviewed_label",
    "independent_evidence",
    "reviewer",
    "reviewed_at",
    "boundary_review",
    "notes",
    "previous_day",
    "previous_week",
    "WAPE_percent",
    "standard_code",
    "observed_min_positive_increment_kwh",
    "active_threshold_kw",
    "high_threshold_kw",
    "increment_to_window_dynamic_energy_ratio",
    "valid_from",
    "cumulative_energy_kwh",
    "normalized_value",
}


def write_json(path: Path, value: Any) -> None:
    """Write UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    """Write plain or gzip CSV with explicit column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def relocate(path: str) -> str:
    """Convert source task paths to release-relative paths."""
    return (
        path.replace("task1_events/inputs/", "sequences/")
        .replace("task1_events/evaluator_only/sequences/", "annotations/")
        .replace("task2_forecast/inputs/", "sequences/")
        .replace("task2_forecast/evaluator_only/", "targets/")
    )


def field_info(name: str) -> tuple[str, str]:  # noqa: PLR0911
    """Return the logical type and unit of a stored field."""
    if name in BOOLEAN_FIELDS:
        return "boolean", ""
    if name in INTEGER_FIELDS:
        return "integer", "s" if name.endswith("seconds") else "h" if name.endswith("hours") else ""
    if name.endswith("_kwh") or name == "normalized_value":
        return "number", "kWh"
    if name.endswith("_kw") or name in {"last_observed_value", "previous_day", "previous_week"}:
        return "number", "kW"
    if name in NUMBER_FIELDS or name == "increment_to_window_dynamic_energy_ratio":
        units = {"duration_seconds": "s", "WAPE_percent": "%"}
        return "number", units.get(name, "min" if name.endswith("minutes") else "h" if name.endswith("hours") else "")
    if name.endswith("_minutes"):
        return "number", "min"
    if name.endswith("_at") or name in {
        "interval_start",
        "interval_end",
        "interval_end_exclusive",
        "prediction_origin",
        "training_end_exclusive",
        "valid_from",
        "visible_start",
        "visible_end_exclusive",
    }:
        return "datetime", ""
    if name in {"events", "candidate_tags", "mapping_version", "target_columns"}:
        return "string_or_array", ""
    return "string", ""


class ReleaseBuilder:
    """Copy source data and validate each independent release."""

    def __init__(self, source: Path, output: Path) -> None:
        self.source = source / "package"
        self.output = output
        self.original = json.loads((self.source / "manifest.json").read_text(encoding="utf-8"))
        self.validation = json.loads((source / "validation_report.json").read_text(encoding="utf-8"))
        if self.validation["status"] != "passed":
            msg = "The source release must pass numeric validation first."
            raise ValueError(msg)
        self.source_hashes = {r["path"]: r["sha256"] for r in read_csv(source / "checksums.csv")}
        self.schemas: dict[str, dict[str, list[str]]] = {}
        self.preserved: list[dict[str, str]] = []
        self.roots = {key: output / f"{name}_v{VERSION}" for key, name in NAMES.items()}
        self.event_index: list[dict[str, str]] = []
        self.forecast_index: list[dict[str, str]] = []

    def copy(self, source: Path, destination: Path, *, pattern: str | None = None) -> None:
        """Copy a file and prove unchanged bytes against its source inventory."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = sha256(destination)
        if self.source in source.parents:
            origin = str(source.relative_to(self.source))
            if digest != self.source_hashes[origin]:
                msg = f"Source preservation failed: {origin}"
                raise ValueError(msg)
            self.preserved.append(
                {"source_path": origin, "release_path": str(destination.relative_to(self.output)), "sha256": digest}
            )
        elif digest != sha256(source):
            msg = f"Copy mismatch: {source}"
            raise ValueError(msg)
        if pattern:
            self.register(destination, pattern)

    def register(self, path: Path, pattern: str) -> None:
        """Register and check CSV schemas for all copied table families."""
        root = next(root for root in self.roots.values() if root in path.parents)
        schemas = self.schemas.setdefault(str(root), {})
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            columns = next(csv.reader(stream))
        if pattern in schemas and schemas[pattern] != columns:
            msg = f"Inconsistent table schema: {pattern}"
            raise ValueError(msg)
        schemas[pattern] = columns
        if missing := set(columns) - DESCRIPTIONS.keys():
            msg = f"Undefined fields: {missing}"
            raise ValueError(msg)

    def common(self, key: str) -> None:
        """Prepare common documentation, task metadata and local tools."""
        root = self.roots[key]
        root.mkdir(parents=True, exist_ok=False)
        tools_dir = Path(__file__).parent
        self.copy(tools_dir / "energy_release_io.py", root / "scripts/read_sequence.py")
        self.copy(tools_dir / "verify_energy_release.py", root / "scripts/verify_checksums.py")
        meters = json.loads((self.source / "base/meter_metadata.json").read_text(encoding="utf-8"))
        write_json(root / "metadata/meters.json", meters)
        write_json(root / "metadata/splits.json", self.original["time_splits"])
        task_path = self.source / ("task1_events" if key == "events" else "task2_forecast") / "task_spec.json"
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["release_version"] = VERSION
        task["processing_version"] = task.pop("version")
        write_json(root / "metadata/task.json", task)
        self.write_docs(key)

    def base(self, key: str) -> None:
        """Copy cumulative and derived tables with their quality reports."""
        root = self.roots[key]
        groups = ["registers", "native_intervals"] + (["forecast_15min"] if key == "forecast" else [])
        for group in groups:
            for source in sorted((self.source / "base" / group).glob("*.csv.gz")):
                self.copy(source, root / "data" / group / source.name, pattern=f"data/{group}/*.csv.gz")
        for source in sorted((self.source / "quality/duplicate_conflicts").glob("*.csv.gz")):
            self.copy(
                source,
                root / "reports/duplicate_conflicts" / source.name,
                pattern="reports/duplicate_conflicts/*.csv.gz",
            )
        self.copy(
            self.source / "quality/legacy_time_alignment_audit.csv",
            root / "reports/time_alignment.csv",
            pattern="reports/time_alignment.csv",
        )
        quality = read_csv(self.source / "quality/meter_quality_report.csv")
        quality = [{RENAMES.get(k, k): v for k, v in row.items()} for row in quality]
        write_csv(root / "reports/meter_quality.csv", quality)
        self.register(root / "reports/meter_quality.csv", "reports/meter_quality.csv")

    def events(self) -> None:
        """Prepare full event observations, weak annotations and review examples."""
        root = self.roots["events"]
        self.common("events")
        self.base("events")
        self.event_index = read_csv(self.source / "task1_events/sequence_index.csv")
        for row in self.event_index:
            old_input, old_label = row["input_path"], row["label_path"]
            row["input_path"], row["label_path"] = relocate(old_input), relocate(old_label)
            self.copy(
                self.source / old_input / "observations.csv.gz",
                root / row["input_path"] / "observations.csv.gz",
                pattern="sequences/**/observations.csv.gz",
            )
            metadata = json.loads((self.source / old_input / "metadata.json").read_text(encoding="utf-8"))
            metadata["release_version"] = VERSION
            write_json(root / row["input_path"] / "metadata.json", metadata)
            for name in ("state_labels.csv.gz", "annotations.json"):
                self.copy(
                    self.source / old_label / name,
                    root / row["label_path"] / name,
                    pattern="annotations/**/state_labels.csv.gz" if name.endswith(".gz") else None,
                )
        write_csv(root / "sequence_index.csv", self.event_index)
        self.register(root / "sequence_index.csv", "sequence_index.csv")
        self.copy(
            self.source / "task1_events/evaluator_only/all_candidate_events.csv",
            root / "annotations/events.csv",
            pattern="annotations/events.csv",
        )
        self.copy(
            self.source / "task1_events/review_template.csv",
            root / "annotations/review_template.csv",
            pattern="annotations/review_template.csv",
        )
        for source in sorted((self.source / "task1_events/evaluator_only/calibration").glob("*.json")):
            rule = json.loads(source.read_text(encoding="utf-8"))
            write_json(root / "annotations/rules" / source.name, {RENAMES.get(k, k): v for k, v in rule.items()})
        self.metadata("events")
        selections = []
        for meter in ("S01_M01", "S01_M15", "S02_M08"):
            choices = [r for r in self.event_index if r["meter_id"] == meter and r["split"] == "test"]
            if not choices:
                choices = [r for r in self.event_index if r["meter_id"] == meter and r["split"] != "boundary"]
            best = max(
                choices,
                key=lambda r: len(json.loads((root / r["label_path"] / "annotations.json").read_text())["events"]),
            )
            selections.append(best)
        self.examples("events", selections)

    def forecast(self) -> None:
        """Prepare forecast inputs, targets and separately identified baselines."""
        root = self.roots["forecast"]
        self.common("forecast")
        self.base("forecast")
        self.forecast_index = read_csv(self.source / "task2_forecast/sequence_index.csv.gz")
        batches = {}
        for row in self.forecast_index:
            old_input, old_target = row["input_path"], row["target_path"]
            row["input_path"], row["target_path"] = relocate(old_input), relocate(old_target)
            batches[old_input] = old_target
        for old_input, old_target in sorted(batches.items()):
            destination = root / relocate(old_input)
            for name in ("history.csv.gz", "future_covariates.csv.gz"):
                self.copy(self.source / old_input / name, destination / name, pattern=f"sequences/**/{name}")
            with (
                gzip.open(self.source / old_input / "metadata.jsonl.gz", "rt", encoding="utf-8") as source,
                gzip.open(destination / "metadata.jsonl.gz", "wt", encoding="utf-8") as target,
            ):
                for line in source:
                    metadata = json.loads(line)
                    metadata["input_path"] = relocate(metadata["input_path"])
                    metadata["release_version"] = VERSION
                    target.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            self.copy(
                self.source / old_target / "future.csv.gz",
                root / relocate(old_target) / "future.csv.gz",
                pattern="targets/**/future.csv.gz",
            )
            baseline_path = old_target.replace("task2_forecast/evaluator_only/", "benchmarks/predictions/")
            self.copy(
                self.source / old_target / "baseline_predictions.csv.gz",
                root / baseline_path / "baseline_predictions.csv.gz",
                pattern="benchmarks/predictions/**/baseline_predictions.csv.gz",
            )
        write_csv(root / "sequence_index.csv.gz", self.forecast_index)
        self.register(root / "sequence_index.csv.gz", "sequence_index.csv.gz")
        for old, new in (
            ("baseline_metrics.csv", "benchmarks/metrics.csv"),
            ("eligibility_report.csv", "reports/eligibility.csv"),
            ("sequence_counts.csv", "reports/sequence_counts.csv"),
        ):
            self.copy(self.source / "task2_forecast" / old, root / new, pattern=new)
        self.metadata("forecast")
        selections = []
        for site, profile in (
            ("S01", "next_hour"),
            ("S01", "next_day"),
            ("S01", "next_day_short_history"),
            ("S02", "next_hour"),
            ("S02", "next_day_short_history"),
        ):
            choices = [
                r
                for r in self.forecast_index
                if r["site_id"] == site and r["profile"] == profile and r["split"] == "test"
            ]
            selections.append(choices[len(choices) // 2])
        self.examples("forecast", selections)
        self.inputs(selections)

    def inputs(self, selections: list[dict[str, str]]) -> None:
        """Create an input edition with no future values or derived target summaries."""
        root, full = self.roots["inputs"], self.roots["forecast"]
        self.common("inputs")
        for source in sorted((full / "sequences").rglob("*")):
            if source.is_file():
                self.copy(
                    source,
                    root / source.relative_to(full),
                    pattern=f"sequences/**/{source.name}" if source.name.endswith(".csv.gz") else None,
                )
        rows = [
            {k: v for k, v in row.items() if k not in {"target_path", "future_parent_start_row"}}
            for row in self.forecast_index
        ]
        write_csv(root / "sequence_index.csv.gz", rows)
        self.register(root / "sequence_index.csv.gz", "sequence_index.csv.gz")
        self.copy(
            full / "reports/sequence_counts.csv",
            root / "reports/sequence_counts.csv",
            pattern="reports/sequence_counts.csv",
        )
        self.metadata("inputs")
        self.examples("inputs", selections)

    def metadata(self, key: str) -> None:
        """Write edition-specific metadata with precise count semantics."""
        original = self.original
        value = {
            "dataset_id": "warehouse_energy_events" if key == "events" else "warehouse_load_forecast",
            "title": NAMES[key],
            "release_version": VERSION,
            "release_date": "2026-09-28",
            "processing_version": original["processing_version"],
            "task": "energy_events" if key == "events" else "load_forecast",
            "edition": "inputs_only" if key == "inputs" else "full",
            "timezone": "Asia/Shanghai",
            "sites": original["sites"],
            "source_meters": original["meters_with_observations"],
            "recorded_time_range": {
                "start": original["first_observed_at"],
                "end": original["last_observed_at"],
                "continuous_coverage": False,
            },
            "sequences": original["event_review_sequences"] if key == "events" else original["forecast_sequences"],
            "included_deduplicated_register_records": 0
            if key == "inputs"
            else original["independent_register_observations"],
            "underlying_deduplicated_register_records": original["independent_register_observations"],
            "underlying_source_records": original["source_observations"],
            "source_snapshot_sha256": original["source_snapshot_sha256"],
            "synthetic_observations": original["synthetic_observations"],
            "imputed_intervals": original["imputed_intervals"],
            "source_policy": "tenant-scoped database snapshot; pseudonymous site and meter identifiers",
            "units": {"electricity": "kWh", "average_power": "kW"},
            "metering_status": original["metering_semantics_status"],
            "time_semantics_status": original["legacy_time_semantics_status"],
            "availability_status": "S01 measurement-time backtest; S02 received-time check with one-step history lag",
            "distribution_status": "customer_review; competition_distribution_authorization_pending",
            "checksum_scope": "all files except checksums.csv; file_manifest.csv lists content files excluding both inventories",
        }
        if key == "events":
            value.update(
                candidate_events=original["candidate_events"], verified_business_events=0, label_level="rule_candidate"
            )
        else:
            value.update(
                eligible_forecast_meters=20, sampling_interval_seconds=900, contains_future_values=key == "forecast"
            )
        write_json(self.roots[key] / "dataset.json", value)

    def examples(self, key: str, selections: list[dict[str, str]]) -> None:
        """Export real indexed sequences and concrete request/response examples."""
        root = self.roots[key]
        index = []
        for number, row in enumerate(selections, start=1):
            directory = root / "examples" / f"sequence{number:04d}"
            values = read_sequence(root, row["sequence_id"], with_targets=key != "inputs", index_row=row)
            for name, records in values.items():
                if isinstance(records, list) and records:
                    write_csv(directory / f"{name}.csv", records)
                    self.register(directory / f"{name}.csv", f"examples/*/{name}.csv")
                elif isinstance(records, dict):
                    write_json(directory / f"{name}.json", records)
            index.append(
                {
                    "example_id": directory.name,
                    "sequence_id": row["sequence_id"],
                    "site_id": row["site_id"],
                    "meter_id": row["meter_id"],
                    "split": row["split"],
                    "example_path": str(directory.relative_to(root)),
                }
            )
            if key == "events":
                request = {
                    "request_id": row["sequence_id"],
                    "observations_csv": "observations.csv",
                    "metadata_json": "metadata.json",
                    "label_type": "rule_candidate_events",
                }
            else:
                request = {
                    "request_id": row["sequence_id"],
                    "history_csv": "history.csv",
                    "future_covariates_csv": "future_covariates.csv",
                    "metadata_json": "metadata.json",
                    "history_length": int(row["history_length"]),
                    "forecast_horizon": int(row["forecast_horizon"]),
                    "sampling_interval_seconds": 900,
                    "target_columns": ["average_power_kw"],
                    "prediction_origin": row["prediction_origin"],
                }
                predictions = [
                    {"step": i, "average_power_kw": float(values["history"][-1]["average_power_kw"])}
                    for i in range(int(row["forecast_horizon"]))
                ]
                write_json(
                    directory / "sample_response.json",
                    {"request_id": row["sequence_id"], "model": "last_observed_value", "predictions": predictions},
                )
                if key == "forecast":
                    write_json(
                        directory / "ground_truth.json",
                        {
                            "sequence_id": row["sequence_id"],
                            "future_csv": "future.csv",
                            "target_columns": ["average_power_kw"],
                            "forecast_horizon": int(row["forecast_horizon"]),
                            "primary_mask_column": "primary_evaluation_eligible",
                            "source": "cumulative_register_derived_intervals",
                        },
                    )
            write_json(directory / "sample_request.json", request)
        write_csv(root / "examples/example_index.csv", index)
        self.register(root / "examples/example_index.csv", "examples/example_index.csv")
        # This JSON Schema is an actual schema, not a response object filled with zero values.
        if key != "events":
            write_json(
                root / "examples/response.schema.json",
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "Load forecast response",
                    "type": "object",
                    "required": ["request_id", "predictions"],
                    "additionalProperties": False,
                    "properties": {
                        "request_id": {"type": "string"},
                        "model": {"type": "string"},
                        "predictions": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["step", "average_power_kw"],
                                "additionalProperties": False,
                                "properties": {
                                    "step": {"type": "integer", "minimum": 0},
                                    "average_power_kw": {"type": "number"},
                                },
                            },
                        },
                    },
                },
            )

    def write_docs(self, key: str) -> None:
        """Write concise dataset documentation matched to actual files."""
        root = self.roots[key]
        common = """# 数据说明

## 数据来源与计量

数据取自两个仓储场站的电表记录及历史档案。场站和电表以S01、S02及匿名电表编号表示，回路用途采用平台设备清单。累计示值按现有系统映射使用kWh；有效区间电量为相邻累计示值差，平均功率为区间电量除以区间小时数。CT/PT、硬件示值分辨率和回路成员尚待现场核实，数值适用范围以metadata/meters.json为准。

记录时间范围为2023-03-21至2026-09-27，各表实际范围和缺口不同。累计记录数按电表和已记录时间去重计算；滑窗复用历史行不增加源记录数。原生间隔包括300、900和3600秒。无效区间和缺口保留，不插值补齐，不将小时计量上采样为15分钟观测。

## 时间与可用性

时间字符串含+08:00偏移。S01历史档案的无时区时间暂按场站本地时间解释；部分档案存在8小时偏移对照证据，未取得采集依据前未对档案进行8小时修正。时间对照结果保存在完整数据集reports/time_alignment.csv。观测时间范围是记录范围，并非已认证的完整物理采样时间范围。

S01未保存消息接收时间，预测采用按观测时间的回溯评测；S02按MQTT UTC时间合同转换，并检查接收时间，历史末点预留1个15分钟区间的滞后。available_at为空表示接收时间未知。时间分区边界见metadata/splits.json；起止边界为左闭右开。

## CSV、空值与枚举

CSV采用UTF-8，可带BOM；csv.gz为gzip压缩CSV。数值列采用小数文本，布尔列为True或False。空数值表示无法计算或不存在，不能默认替换为0。hour、minute、weekday以小数形式存储整数日历值。

| quality_flag | 含义 |
|---|---|
| measured | 有效累计示值差分 |
| measured_irregular_duration | 满足容差但非名义时长的有效区间 |
| measured_3x5min_aggregate | 三个连续5分钟有效区间合成15分钟区间 |
| day_boundary_time_alignment_assumption | 在允许的60秒范围内对齐15分钟网格，主评测排除此类目标 |
| first_reading_no_interval | 首个示值无前序区间 |
| invalid_endpoint_or_conflict | 端点无效或同时间存在冲突 |
| register_decrease_review | 累计示值下降，待复核 |
| data_gap_or_cadence_change | 时间缺口或采样间隔变化 |

逐列类型、单位、可空性和定义见field_dictionary.csv。预测示例中的sample_response.json采用历史末值基线，仅用于接口读取；future.csv为源示值派生目标。二者用途不同。

## 版本与使用范围

发布版本1.1.0负责目录、字段说明和示例组织，数值处理版本保持full-1.0.0。源累计值、输入曲线、未来目标、状态和候选事件未因目录调整改变。对外分发授权状态见dataset.json；本地审阅材料不包含企业原始身份映射或数据库访问凭据。
"""
        if key == "events":
            common = common.replace(
                "预测示例中的sample_response.json采用历史末值基线，仅用于接口读取；future.csv为源示值派生目标。二者用途不同。",
                "事件示例的annotations.json和state_labels.csv来自本数据集规则标注。",
            )
        elif key == "inputs":
            common = common.replace("future.csv为源示值派生目标", "未来实测派生目标只在完整预测数据集中提供")
        self.text(root / "docs/data_description.md", common)
        if key == "events":
            task_doc = """# 用能事件标注

本任务面向电表曲线中的高于背景持续用能、活动中的高负荷和充电回路持续用能候选。28块电表的全部原生区间按电表、月份和时间分区组织为793段序列；无效观测仍在序列中保留。boundary分区保存跨时间分区边界的区间，不用于训练期阈值标定或独立分区评测。

annotations/events.csv含8532个规则候选，独立业务确认事件数为0。charging_activity_candidate结合充电回路清单与曲线规则形成，不能直接等同于充电订单；activity_above_background表示高于本回路背景的持续活动。extended_activity_review表示持续跨度达到120分钟，high_load_within_activity表示活动段内累计高负荷时间达到30分钟。

逐表阈值仅用训练期有效观测标定。平滑窗口为max(30分钟，原生间隔)，活动阈值为max(训练p90，训练中位数+max(10⁻⁶ kW，最小正增量/平滑小时数))，高负荷阈值为max(训练p99，活动阈值+max(10⁻⁶ kW，最小正增量/平滑小时数))。量化步进筛查比值为最小正增量/[(训练p99−中位平滑功率)×平滑小时数]，达到0.5或动态范围不存在时不输出活动时长候选。上述参数是企业曲线假设，逐表依据保存在annotations/rules，standard_code为null，不作为行业标准阈值。

逐点state采用unknown、low_load、active_load、high_load。low_load表示未达到活动阈值的有效平滑区间。unknown表示未满足有效曲线或阈值条件。候选边界由平滑曲线越限确定，小时表只能提供小时分辨率的候选跨度。跨月候选在annotations.json中保留可见区间及前后延续标记；统计事件总数时按event_id去重。

review_template.csv为独立证据复核表，复核字段当前为空。缺少设备工时、充电订单或现场记录时，不据规则候选计算作业识别准确率、设备工时或节能收益。
"""
            tree = """data/registers/、data/native_intervals/  累计示值与原生计量区间
sequences/<split>/<sequence_id>/         observations.csv.gz、metadata.json
annotations/<split>/<sequence_id>/       state_labels.csv.gz、annotations.json
annotations/events.csv                  全部候选事件清单
annotations/rules/                      逐表规则参数
annotations/review_template.csv         复核记录模板
sequence_index.csv                      793段序列索引
reports/                                逐表质量、时间对照及重复冲突记录"""
            example = "S01_M01_2026-09_test"
            scope = "包含28块电表的1,696,280条去重累计记录、793段月度序列及8,532个规则候选事件。适用于曲线事件检索、候选复核和规则结果对照。"
            task_file = "event_labels.md"
        else:
            task_doc = """# 短期负荷预测任务

目标列为average_power_kw，单位kW，步长900秒。仅对连续、有效的15分钟负荷区间构造窗口；发电和储能回路不作为用电负荷目标。小时表不拆分为15分钟观测。累计底表保留28块电表，其中20块具备可导出预测窗口。

| profile | 历史步数 | 预测步数 | 移动步长 |
|---|---:|---:|---:|
| next_hour | 96 | 4 | 4 |
| next_day | 672 | 96 | 96 |
| next_day_short_history | 96 | 96 | 96 |

共264109个序列，包含29537952行历史输入及2636444行未来目标。上述行数包含历史窗口复用。同一电表、配置内未来目标不重叠；不同配置不能合并为互相独立的目标样本。日预测为预测发起时间之后的滚动24小时，不要求起点为零时。

完整数据集sequence_index.csv.gz给出输入、目标相对目录及sequence_position_in_batch。每批最多500段，CSV以sequence_id和step区分序列，metadata.jsonl.gz每行对应一段。scripts/read_sequence.py按索引提取完整窗口。输入版使用相同索引和读取方式，省略目标目录和目标底表行号。

future_covariates.csv.gz仅包含未来日历字段；输入元数据不包含未来功率或未来源记录摘要。训练、验证、测试按目标时间划分，跨边界窗口丢弃，历史允许使用预测发起前已知区间。分区日期见metadata/splits.json。

主评测使用primary_evaluation_eligible=True的目标行。完整集benchmarks提供历史末值、前日、前周基线与MAE、RMSE、WAPE结果；历史长度不足时对应基线为空。MAE为绝对误差均值，RMSE为平方误差均值开方，WAPE为绝对误差总和/实测功率绝对值总和×100%，分母为0时不计算。它们是误差统计指标，不作为能效基准或节能量。

完整数据集包含所有分区未来目标及完整底表，适合数据审阅和训练。若用于隐藏测试，需要由评测方另行确定公开训练目标及隐藏测试范围。输入版省略全部未来目标、底表和目标统计，覆盖同一组264109个预测请求，独立包含读取工具和5段格式示例。

examples下的sample_request.json约定CSV路径相对于该示例目录。sample_response.json为历史末值基线响应；response.schema.json为JSON Schema。predictions长度应等于forecast_horizon，step应按0至horizon−1连续排列；此跨文件约束由调用方检查。接口约定用于本数据集读取，未声明与比赛平台正式API兼容。
"""
            if key == "inputs":
                task_doc = task_doc.replace(
                    "共264109个序列，包含29537952行历史输入及2636444行未来目标。",
                    "本输入版含264109个序列和29537952行历史输入，未来日历输入共2636444行；不含未来功率目标。",
                )
                task_doc = task_doc.replace("主评测使用", "完整集的主评测使用")
                scope = "包含264,109个预测请求的历史输入和未来日历字段，以及对应元数据。适用于读取验证和模型输入，不含未来实测目标、完整底表或基线评测统计。"
                tree = """sequences/<split>/<meter_id>/<profile>/<batch>/
  history.csv.gz                        历史功率输入
  future_covariates.csv.gz              未来日历输入
  metadata.jsonl.gz                     逐序列元数据
sequence_index.csv.gz                   264109个序列索引
reports/sequence_counts.csv             分区与配置数量"""
            else:
                scope = "包含28块电表的累计与区间底表，20块电表的264,109个预测序列，分区输入、未来目标和独立基线结果。适用于负荷预测训练、评测和来源复核。"
                tree = """data/registers/、data/native_intervals/、data/forecast_15min/  底表
sequences/<split>/<meter_id>/<profile>/<batch>/
  history.csv.gz、future_covariates.csv.gz、metadata.jsonl.gz
 targets/<split>/<meter_id>/<profile>/<batch>/future.csv.gz  未来目标
benchmarks/predictions/                 基线预测，非实测目标
benchmarks/metrics.csv                  基线误差汇总
sequence_index.csv.gz                   264109个序列索引
reports/                               质量、可用性及分区数量""".replace("\n targets/", "\ntargets/")
            example = "S01_M01_next_hour_train_0000001"
            task_file = "forecast_task.md"
        self.text(root / "docs" / task_file, task_doc)
        readme = f"""# {NAMES[key]}

版本：{VERSION}　发布日期：2026-09-28　数值处理版本：full-1.0.0

## 用途与范围

{scope}

## 文件组织

```text
{tree}
metadata/                              电表、任务与时间分区元数据
docs/                                  数据与任务说明
examples/                              从本集提取的单序列示例
scripts/                               Python读取与校验工具
field_dictionary.csv                   逐字段定义
dataset.json                           数据集版本、来源与数量信息
file_manifest.csv                      内容文件目录与字节数
checksums.csv                          除自身外全部文件的SHA256
reports/release_validation.json        本次发布核查结果
```

## 读取

使用Python 3.10或以上版本，无第三方依赖。在本数据集根目录执行：

```bash
python3 scripts/verify_checksums.py .
python3 scripts/read_sequence.py . {example} --output ../extracted_sequence
```

完整数据集读取标注或未来目标时添加`--with-targets`；预测输入版不接受该选项。examples/example_index.csv列出可直接查看的示例及原始sequence_id。CSV路径均相对于本数据集根目录；示例请求中的CSV路径相对于该示例目录。

## 数据解释

详细字段见field_dictionary.csv；来源、单位、时间和空值见docs/data_description.md；任务定义见docs/{task_file}。候选标注的核实等级、采集时间与计量映射状态以数据字段为准。文件清单与校验文件覆盖本包，不引用其他数据集目录。
"""
        if key == "inputs":
            readme = readme.replace(
                "完整数据集读取标注或未来目标时添加`--with-targets`；预测输入版不接受该选项。",
                "本版不提供未来目标，不接受`--with-targets`选项。",
            )
        elif key == "events":
            readme = readme.replace(
                "完整数据集读取标注或未来目标时添加`--with-targets`；预测输入版不接受该选项。",
                "读取对应规则标注时添加`--with-targets`选项。",
            )
        else:
            readme = readme.replace(
                "完整数据集读取标注或未来目标时添加`--with-targets`；预测输入版不接受该选项。",
                "读取对应未来目标时添加`--with-targets`选项。",
            )
        if key != "events":
            readme = readme.replace("候选标注的核实等级、采集时间与计量映射状态", "采集时间、历史可用性与计量映射状态")
        self.text(root / "README.md", readme)

    @staticmethod
    def text(path: Path, value: str) -> None:
        """Write a UTF-8 document."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def dictionary(self, key: str) -> None:
        """Document all CSV columns and operational metadata JSON keys."""
        root = self.roots[key]
        schemas = self.schemas[str(root)]
        rows = []
        for pattern, columns in sorted(schemas.items()):
            for column in columns:
                kind, unit = field_info(column)
                if kind == "string_or_array":
                    kind = "string"
                rows.append(
                    {
                        "file_pattern": pattern,
                        "field": column,
                        "logical_type": kind,
                        "unit": unit,
                        "nullable": column in NULLABLE_FIELDS,
                        "description": DESCRIPTIONS[column],
                    }
                )
        json_families = {
            "metadata/meters.json": [root / "metadata/meters.json"],
            "sequences/**/metadata.json" if key == "events" else "sequences/**/metadata.jsonl.gz": sorted(
                (root / "sequences").rglob("metadata.json" if key == "events" else "metadata.jsonl.gz")
            )[:1],
        }
        if key == "events":
            json_families["annotations/rules/*.json"] = sorted((root / "annotations/rules").glob("*.json"))
            json_families["annotations/**/annotations.json"] = sorted((root / "annotations").rglob("annotations.json"))
        for pattern, paths in json_families.items():
            keys = set()
            event_keys = set()
            for path in paths:
                if path.suffix == ".gz":
                    with gzip.open(path, "rt", encoding="utf-8") as stream:
                        obj = json.loads(stream.readline())
                else:
                    obj = json.loads(path.read_text(encoding="utf-8"))
                objects = obj if isinstance(obj, list) else [obj]
                for item in objects:
                    keys.update(item)
                    for event in item.get("events", []):
                        event_keys.update(event)
            for column in sorted(keys | event_keys):
                if column not in DESCRIPTIONS:
                    msg = f"Undefined JSON field: {pattern}/{column}"
                    raise ValueError(msg)
                kind, unit = field_info(column)
                if kind == "string_or_array":
                    kind = "array"
                rows.append(
                    {
                        "file_pattern": pattern,
                        "field": f"events[].{column}" if column in event_keys else column,
                        "logical_type": kind,
                        "unit": unit,
                        "nullable": column in NULLABLE_FIELDS,
                        "description": DESCRIPTIONS[column],
                    }
                )
        write_csv(root / "field_dictionary.csv", rows)
        for path in root.rglob("*.csv*"):
            if path.name in {"field_dictionary.csv", "example_index.csv"}:
                continue
            relative = str(path.relative_to(root))
            if not any(fnmatch.fnmatch(relative, pattern) for pattern in schemas):
                msg = f"Table is absent from field dictionary: {relative}"
                raise ValueError(msg)

    def validate(self, key: str) -> dict[str, Any]:  # noqa: C901
        """Validate every index, input metadata row and selected batch extraction."""
        root = self.roots[key]
        rows = self.event_index if key == "events" else self.forecast_index
        seen = set()
        batches: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            if row["sequence_id"] in seen:
                msg = "Duplicate sequence identifier."
                raise ValueError(msg)
            seen.add(row["sequence_id"])
            for name in ("input_path", "label_path", "target_path"):
                if name in row and not (key == "inputs" and name == "target_path") and not (root / row[name]).is_dir():
                    msg = f"Missing sequence directory: {row[name]}"
                    raise ValueError(msg)
            batches.setdefault(row["input_path"], []).append(row)
        metadata_count = 0
        loader_count = 0
        for directory, members in batches.items():
            if key == "events":
                metadata = json.loads((root / directory / "metadata.json").read_text(encoding="utf-8"))
                if metadata["sequence_id"] != members[0]["sequence_id"]:
                    msg = "Event metadata mismatch."
                    raise ValueError(msg)
                metadata_count += 1
            else:
                members = sorted(members, key=lambda row: int(row["sequence_position_in_batch"]))
                with gzip.open(root / directory / "metadata.jsonl.gz", "rt", encoding="utf-8") as stream:
                    lines = list(stream)
                if len(lines) != len(members):
                    msg = "Batch metadata count mismatch."
                    raise ValueError(msg)
                for position, (line, row) in enumerate(zip(lines, members, strict=True)):
                    meta = json.loads(line)
                    if (
                        meta["sequence_id"] != row["sequence_id"]
                        or meta["input_path"] != directory
                        or int(row["sequence_position_in_batch"]) != position
                    ):
                        msg = "Batch index mismatch."
                        raise ValueError(msg)
                    if {
                        "future_parent_start_row",
                        "target_path",
                        "future_source_start",
                        "future_source_end",
                    } & meta.keys():
                        msg = "Target identifiers present in input metadata."
                        raise ValueError(msg)
                    metadata_count += 1
        # First and last batch positions exercise extraction offsets for each site/profile/split.
        choices = {}
        for row in rows:
            group = (row["site_id"], row.get("profile", row["meter_id"]), row["split"])
            choices.setdefault(group, [row, row])[1] = row
        for pair in choices.values():
            for row in pair:
                read_sequence(root, row["sequence_id"], with_targets=key != "inputs", index_row=row)
                loader_count += 1
        for row in read_csv(root / "examples/example_index.csv"):
            folder = root / row["example_path"]
            original_row = next(r for r in rows if r["sequence_id"] == row["sequence_id"])
            result = read_sequence(root, row["sequence_id"], with_targets=key != "inputs", index_row=original_row)
            for name, value in result.items():
                if isinstance(value, list) and value and read_csv(folder / f"{name}.csv") != value:
                    msg = "Example values differ from the indexed sequence."
                    raise ValueError(msg)
            if key != "events":
                request = json.loads((folder / "sample_request.json").read_text())
                response = json.loads((folder / "sample_response.json").read_text())
                if (
                    len(response["predictions"]) != request["forecast_horizon"]
                    or response["request_id"] != request["request_id"]
                ):
                    msg = "Example response shape mismatch."
                    raise ValueError(msg)
                for step, prediction in enumerate(response["predictions"]):
                    if prediction["step"] != step or prediction["average_power_kw"] != float(
                        result["history"][-1]["average_power_kw"]
                    ):
                        msg = "Example baseline mismatch."
                        raise ValueError(msg)
        if key == "inputs":
            forbidden = {"future.csv", "future.csv.gz", "ground_truth.json", "baseline_predictions.csv.gz"}
            if (
                any(path.name in forbidden for path in root.rglob("*"))
                or (root / "data").exists()
                or (root / "targets").exists()
            ):
                msg = "Input edition contains target files."
                raise ValueError(msg)
            if {"future_parent_start_row", "target_path"} & read_csv(root / "sequence_index.csv.gz")[0].keys():
                msg = "Input edition contains target index fields."
                raise ValueError(msg)
        return {
            "status": "passed",
            "release_version": VERSION,
            "indexed_sequences_checked": len(rows),
            "metadata_records_checked": metadata_count,
            "reader_extractions_checked": loader_count,
            "example_sequences_checked": len(read_csv(root / "examples/example_index.csv")),
            "numeric_validation_basis": "full-1.0.0 complete parent-series validation; unchanged source CSV bytes verified by SHA256 during packaging",
            "previous_numeric_validation": self.validation
            if key != "inputs"
            else {
                "status": "passed",
                "forecast_sequences_checked": self.validation["forecast_sequences_checked"],
                "materialized_history_rows_checked": self.validation["materialized_history_rows_checked"],
            },
            "independent_business_label_verification": False,
            "checks": [
                "sequence paths and unique identifiers",
                "all sequence metadata and batch positions",
                "CSV field dictionary coverage",
                "real examples round-trip",
                "request and baseline response consistency",
            ]
            + (
                ["absence of future values and target files"]
                if key == "inputs"
                else ["copied numerical files unchanged"]
            ),
        }

    def finish(self, key: str) -> dict[str, Any]:
        """Create package inventories, validate the release, and verify ZIP content."""
        root = self.roots[key]
        self.dictionary(key)
        report = self.validate(key)
        write_json(root / "reports/release_validation.json", report)
        files = sorted(path for path in root.rglob("*") if path.is_file())
        inventory = [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "format": "csv.gz" if path.name.endswith(".csv.gz") else path.suffix.lstrip("."),
            }
            for path in files
        ]
        write_csv(root / "file_manifest.csv", inventory)
        files.append(root / "file_manifest.csv")
        hashes = [
            {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(files)
        ]
        write_csv(root / "checksums.csv", hashes)
        count = verify(root)
        archive = self.output / f"{root.name}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    target.write(path, arcname=str(path.relative_to(self.output)))
        with zipfile.ZipFile(archive) as source:
            if source.testzip() is not None:
                msg = "ZIP CRC check failed."
                raise ValueError(msg)
            expected = {f"{root.name}/{row['path']}" for row in hashes} | {f"{root.name}/checksums.csv"}
            if set(source.namelist()) != expected:
                msg = "ZIP member mismatch."
                raise ValueError(msg)
        print(f"{key}: {count} checked files, {archive.stat().st_size / 1024**2:.1f} MiB", flush=True)
        return {
            "dataset": NAMES[key],
            "root": root.name,
            "archive": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "sequences": report["indexed_sequences_checked"],
            "status": "passed",
        }

    def build(self) -> None:
        """Build three release editions without changing earlier deliverables."""
        self.output.mkdir(parents=True, exist_ok=False)
        print("Preparing event release...", flush=True)
        self.events()
        print("Preparing forecast release and input edition...", flush=True)
        self.forecast()
        releases = []
        for key in NAMES:
            print(f"Validating and archiving {key}...", flush=True)
            releases.append(self.finish(key))
        write_json(self.output / "release_summary.json", releases)
        write_csv(self.output / "internal/numeric_file_preservation.csv", self.preserved)
        self.text(
            self.output / "整改记录.md",
            """# 数据集交付整改记录

日期：2026-09-28。规范版1.1.0以全量数值处理版本full-1.0.0为基础，源累计值、曲线输入、未来实测派生目标和规则候选保持不变。

整改包括独立数据集根目录、各自说明、输入与标注或目标分目录、基线单列、批次序列读取工具、真实单序列示例、请求与响应结构、逐字段字典、包内文件清单和SHA256。事件集3段示例；预测完整集和输入版各5段示例。示例是原序列副本，不计入额外源数据或任务序列。

旧版字段activity_timing_usable_under_pilot_rule改名event_timing_eligible，observed_increment_to_30min_dynamic_energy_ratio改名increment_to_window_dynamic_energy_ratio，去重示值统计使用deduplicated_register_records。字段更名未改变参数或阈值。目录版与数值处理版分开记录。

所有复制数值文件与旧包校验清单逐文件比对SHA256；序列索引、逐行元数据、读取示例、输入版无目标文件、包内校验和ZIP CRC均通过核查。内部数值保留清单见internal/numeric_file_preservation.csv。发布清单及ZIP摘要见release_summary.json。

本次文档与整理代码由AI助手协助编写。这属于制作方式，不能宣称制作过程未使用AI；本次未生成或补造电量观测。源计量映射、历史时区和候选标签核实状态继续保留在各包的数据说明和元数据中。原版数据集、示例和自检报告均保留。
""",
        )


def main() -> None:
    """Build a formal release from the previously validated full dataset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("outputs/工业互联网能耗数据集_全量版_20260928"))
    parser.add_argument("--output", type=Path, default=Path("outputs/工业互联网能耗数据集_规范版_20260928"))
    args = parser.parse_args()
    ReleaseBuilder(args.source, args.output).build()


if __name__ == "__main__":
    main()
