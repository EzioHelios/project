# ruff: noqa: RUF001
from __future__ import annotations

import hashlib
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

USER_AGENT = "Mozilla/5.0 energy-benchmark-policy-sync"
DEFAULT_CACHE_DIR = Path(tempfile.gettempdir()) / "litestar-fullstack-energy-benchmark-policy"


@dataclass(frozen=True, slots=True)
class PolicySource:
    key: str
    name: str
    profile_name: str
    library_type: str
    source_name: str
    page_url: str
    fallback_pdf_url: str
    standard_code: str
    industry_name: str
    scenario: str
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True, slots=True)
class PolicyBenchmarkRow:
    target_type: str
    target_code: str | None
    target_name: str
    metric_code: str
    metric_name: str
    benchmark_value: Decimal
    unit: str
    metric_direction: str
    applicable_industry: str
    applicable_category: str
    applicable_condition: str
    reference_standard: str
    advanced_value: Decimal | None = None
    saving_value: Decimal | None = None
    access_value: Decimal | None = None
    baseline_value: Decimal | None = None
    advanced_level: str | None = None
    saving_level: str | None = None
    access_level: str | None = None
    standard_level: str | None = None
    warning_threshold_pct: Decimal = Decimal(10)
    severe_threshold_pct: Decimal = Decimal(25)
    confidence_level: str = "high"
    remark: str | None = None


@dataclass(slots=True)
class PolicySyncResult:
    requested_sources: list[str]
    downloaded_files: list[dict[str, str]]
    profiles_upserted: int = 0
    items_upserted: int = 0
    dry_run: bool = True


POLICY_SOURCES = {
    "ndrc-2023": PolicySource(
        key="ndrc-2023",
        name="工业重点领域能效标杆水平和基准水平（2023年版）",
        profile_name="政策库-工业重点领域能效标杆水平和基准水平（2023年版）",
        library_type="policy_industry",
        source_name="国家发展改革委等部门",
        page_url="https://www.ndrc.gov.cn/xxgk/zcfb/tz/202307/t20230704_1358113.html",
        fallback_pdf_url="https://www.ndrc.gov.cn/xxgk/zcfb/tz/202307/P020230704381062435004.pdf",
        standard_code="发改产业〔2023〕723号",
        industry_name="工业重点领域",
        scenario="重点行业单位产品综合能耗标杆与基准",
        valid_from=date(2023, 6, 6),
        valid_to=None,
    ),
    "ndrc-equipment-2024": PolicySource(
        key="ndrc-equipment-2024",
        name="重点用能产品设备能效先进水平、节能水平和准入水平（2024年版）",
        profile_name="政策库-重点用能产品设备能效水平（2024年版）",
        library_type="equipment_efficiency",
        source_name="国家发展改革委等部门",
        page_url="https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/202402/t20240207_1364001.html",
        fallback_pdf_url="https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/202402/P020240207565694124092.pdf",
        standard_code="发改环资规〔2024〕127号",
        industry_name="重点用能产品设备",
        scenario="设备能效先进、节能、准入水平",
        valid_from=date(2024, 4, 1),
        valid_to=None,
    ),
}


def available_policy_sources() -> list[dict[str, str]]:
    return [
        {
            "key": source.key,
            "name": source.name,
            "page_url": source.page_url,
            "fallback_pdf_url": source.fallback_pdf_url,
            "standard_code": source.standard_code,
        }
        for source in POLICY_SOURCES.values()
    ]


async def sync_policy_benchmark_library(
    session: AsyncSession,
    source_keys: list[str],
    *,
    apply: bool,
    cache_dir: Path | None = None,
) -> PolicySyncResult:
    require_session_tenant_id(session)
    selected = [POLICY_SOURCES[key] for key in source_keys if key in POLICY_SOURCES]
    if not selected:
        selected = list(POLICY_SOURCES.values())
    result = PolicySyncResult(requested_sources=[source.key for source in selected], downloaded_files=[], dry_run=not apply)

    for source in selected:
        downloaded = _download_policy_pdf(source, cache_dir or DEFAULT_CACHE_DIR)
        result.downloaded_files.append(downloaded)
        rows = _policy_rows(source.key)
        if not apply:
            result.profiles_upserted += 1
            result.items_upserted += len(rows)
            continue
        profile = await _upsert_profile(session, source, downloaded)
        result.profiles_upserted += 1
        for row in rows:
            await _upsert_item(session, profile, source, row, downloaded)
            result.items_upserted += 1
    if apply:
        await session.commit()
    return result


def _download_policy_pdf(source: PolicySource, cache_dir: Path) -> dict[str, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    page_html = _fetch_text(source.page_url)
    pdf_url = _find_pdf_url(source.page_url, page_html) or source.fallback_pdf_url
    content = _fetch_bytes(pdf_url)
    digest = hashlib.sha256(content).hexdigest()
    file_name = f"{source.key}-{digest[:12]}.pdf"
    path = cache_dir / file_name
    path.write_bytes(content)
    return {"source_key": source.key, "page_url": source.page_url, "pdf_url": pdf_url, "sha256": digest, "path": str(path)}


def _fetch_text(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8", errors="ignore")


def _fetch_bytes(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        msg = f"不支持的政策资料地址: {url}"
        raise ValueError(msg)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _find_pdf_url(page_url: str, page_html: str) -> str | None:
    for match in re.finditer(r"href=[\"']([^\"']+\.pdf)[\"']", page_html, flags=re.IGNORECASE):
        candidate = urljoin(page_url, match.group(1))
        if "P020" in candidate or "附件" in candidate:
            return candidate
    match = re.search(r"https?://[^\"]+?\.pdf", page_html, flags=re.IGNORECASE)
    return match.group(0) if match else None


async def _upsert_profile(session: AsyncSession, source: PolicySource, downloaded: dict[str, str]) -> m.EnergyBenchmarkProfile:
    profile = await session.scalar(
        select(m.EnergyBenchmarkProfile).where(
            m.EnergyBenchmarkProfile.name == source.profile_name,
            m.EnergyBenchmarkProfile.standard_code == source.standard_code,
        )
    )
    if profile is None:
        profile = m.EnergyBenchmarkProfile(name=source.profile_name)
        session.add(profile)
        await session.flush()
    profile.industry_name = source.industry_name
    profile.scenario = source.scenario
    profile.library_type = source.library_type
    profile.source_name = source.source_name
    profile.source_url = downloaded["pdf_url"]
    profile.source_hash = downloaded["sha256"]
    profile.source_file_name = Path(downloaded["path"]).name
    profile.standard_code = source.standard_code
    profile.version_status = "active"
    profile.valid_from = source.valid_from
    profile.valid_to = source.valid_to
    profile.is_enabled = True
    profile.remark = source.page_url
    return profile


async def _upsert_item(
    session: AsyncSession,
    profile: m.EnergyBenchmarkProfile,
    source: PolicySource,
    row: PolicyBenchmarkRow,
    downloaded: dict[str, str],
) -> m.EnergyBenchmarkItem:
    item = await session.scalar(
        select(m.EnergyBenchmarkItem).where(
            m.EnergyBenchmarkItem.profile_id == profile.id,
            m.EnergyBenchmarkItem.target_type == row.target_type,
            m.EnergyBenchmarkItem.target_code == row.target_code,
            m.EnergyBenchmarkItem.metric_code == row.metric_code,
            m.EnergyBenchmarkItem.applicable_condition == row.applicable_condition,
        )
    )
    if item is None:
        item = m.EnergyBenchmarkItem(
            profile_id=profile.id,
            target_type=row.target_type,
            target_code=row.target_code,
            metric_code=row.metric_code,
            metric_name=row.metric_name,
            benchmark_value=row.benchmark_value,
            unit=row.unit,
        )
        session.add(item)
    item.target_name = row.target_name
    item.metric_name = row.metric_name
    item.benchmark_value = row.benchmark_value
    item.unit = row.unit
    item.standard_code = source.standard_code
    item.source_url = downloaded["pdf_url"]
    item.source_hash = downloaded["sha256"]
    item.applicable_industry = row.applicable_industry
    item.applicable_category = row.applicable_category
    item.applicable_condition = row.applicable_condition
    item.metric_direction = row.metric_direction
    item.advanced_value = row.advanced_value
    item.saving_value = row.saving_value
    item.access_value = row.access_value
    item.baseline_value = row.baseline_value
    item.advanced_level = row.advanced_level
    item.saving_level = row.saving_level
    item.access_level = row.access_level
    item.standard_level = row.standard_level
    item.version_status = "active"
    item.reference_standard = row.reference_standard
    item.excellent_value = row.advanced_value
    item.warning_threshold_pct = row.warning_threshold_pct
    item.severe_threshold_pct = row.severe_threshold_pct
    item.source_name = source.source_name
    item.confidence_level = row.confidence_level
    item.is_enabled = True
    item.remark = row.remark
    return item


def _policy_rows(source_key: str) -> list[PolicyBenchmarkRow]:
    if source_key == "ndrc-equipment-2024":
        return [
            _equipment_row("motor", "三相异步电动机", "效率等级", "电动机能效限定值及能效等级（GB 18613-2020）"),
            _equipment_row("transformer", "电力变压器", "空载损耗、负载损耗等级", "电力变压器能效限定值及能效等级（GB 20052-2020）"),
            _equipment_row("industrial_boiler", "工业锅炉", "热效率等级", "工业锅炉能效限定值及能效等级（GB 24500-2020）"),
            _equipment_row("air_compressor", "容积式空气压缩机", "机组比功率等级", "容积式空气压缩机能效限定值及能效等级（GB 19153-2019）"),
            _equipment_row("ventilator", "通风机", "效率等级", "通风机能效限定值及能效等级（GB 19761-2020）"),
            _equipment_row("ev_charger", "充电桩", "充电效率、功率因数、待机功耗等级", "电动汽车充电设备能效评价指标及试验规范（T/CECA-G 0208-2022）"),
            _equipment_row("multi_split_ac", "多联式空调（热泵）机组", "全年能源消耗效率等级", "多联式空调（热泵）机组能效限定值及能效等级（GB 21454-2021）"),
            _equipment_row("chiller", "冷水机组", "综合部分负荷性能系数等级", "冷水机组能效限定值及能效等级（GB 19577-2015）"),
            _equipment_row("pv_inverter", "光伏并网逆变器", "平均加权效率等级", "质量分级及领跑者评价要求 光伏并网逆变器（T/CPIA 0050-2023、T/CSTE 0215-2023）"),
        ]
    return [
        PolicyBenchmarkRow(
            target_type="product",
            target_code="cement_clinker",
            target_name="水泥熟料",
            metric_code="kgce_per_unit",
            metric_name="单位产品综合能耗",
            benchmark_value=Decimal(100),
            baseline_value=Decimal(117),
            unit="kgce/t",
            metric_direction="lower_is_better",
            applicable_industry="水泥制造",
            applicable_category="水泥熟料",
            applicable_condition="水泥熟料单位产品综合能耗",
            reference_standard="GB 16780",
            advanced_value=Decimal(100),
            access_value=Decimal(117),
            standard_level="benchmark",
            remark="取自《工业重点领域能效标杆水平和基准水平（2023年版）》附件。",
        ),
        PolicyBenchmarkRow(
            target_type="product",
            target_code="flat_glass_gt_800",
            target_name="平板玻璃（生产能力>800吨/天）",
            metric_code="kgce_per_unit",
            metric_name="单位产品综合能耗",
            benchmark_value=Decimal(8),
            baseline_value=Decimal(12),
            unit="kgce/weight_box",
            metric_direction="lower_is_better",
            applicable_industry="玻璃制造",
            applicable_category="平板玻璃",
            applicable_condition="生产能力>800吨/天",
            reference_standard="平板玻璃单位产品能源消耗限额",
            advanced_value=Decimal(8),
            access_value=Decimal(12),
            standard_level="benchmark",
            remark="取自《工业重点领域能效标杆水平和基准水平（2023年版）》附件。",
        ),
        PolicyBenchmarkRow(
            target_type="product",
            target_code="truck_radial_tire",
            target_name="全钢子午线轮胎",
            metric_code="kgce_per_unit",
            metric_name="单位产品综合能耗",
            benchmark_value=Decimal(235),
            baseline_value=Decimal(340),
            unit="kgce/t",
            metric_direction="lower_is_better",
            applicable_industry="轮胎制造",
            applicable_category="全钢子午线轮胎",
            applicable_condition="全钢子午线轮胎单位产品综合能耗",
            reference_standard="轮胎单位产品能源消耗限额相关标准",
            advanced_value=Decimal(235),
            access_value=Decimal(340),
            standard_level="benchmark",
            remark="取自《工业重点领域能效标杆水平和基准水平（2023年版）》附件。",
        ),
    ]


def _equipment_row(target_code: str, target_name: str, metric_name: str, reference_standard: str) -> PolicyBenchmarkRow:
    return PolicyBenchmarkRow(
        target_type="device_type",
        target_code=target_code,
        target_name=target_name,
        metric_code="energy_efficiency_level",
        metric_name=metric_name,
        benchmark_value=Decimal(1),
        unit="级",
        metric_direction="level_rank",
        applicable_industry="重点用能产品设备",
        applicable_category=target_name,
        applicable_condition="同能效标准分类",
        reference_standard=reference_standard,
        advanced_value=Decimal(1),
        saving_value=Decimal(2),
        access_value=Decimal(3),
        advanced_level="能效1级",
        saving_level="能效2级",
        access_level="能效3级",
        standard_level="advanced",
        remark="取自《重点用能产品设备能效先进水平、节能水平和准入水平（2024年版）》附件。",
    )
