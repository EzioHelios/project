"""Tenant carbon-asset reference-data provisioning."""

from __future__ import annotations

# ruff: noqa: RUF001 - official Chinese standard titles and document numbers are exact audit fields.
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_assets.domain.policies import validate_instrument

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


REFERENCE_INSTRUMENTS: tuple[dict[str, Any], ...] = (
    {
        "code": "CEA-NATIONAL",
        "name": "全国碳排放配额",
        "instrument_class": "CEA",
        "native_unit": "tCO2e",
        "market": "national",
        "registry": "全国碳排放权注册登记系统",
        "region": "CN",
        "currency": "CNY",
        "compliance_eligible": True,
        "status": "active",
        "source_name": "全国碳市场制度",
        "standard_code": "全国碳市场",
        "source_url": "https://www.mee.gov.cn/",
    },
    {
        "code": "CCER-NATIONAL",
        "name": "国家核证自愿减排量",
        "instrument_class": "CCER",
        "native_unit": "tCO2e",
        "market": "national_ccer",
        "registry": "全国温室气体自愿减排注册登记系统",
        "region": "CN",
        "currency": "CNY",
        "compliance_eligible": True,
        "status": "active",
        "source_name": "温室气体自愿减排交易管理办法（试行）",
        "standard_code": "生态环境部令第31号",
        "source_url": "https://www.gov.cn/zhengce/zhengceku/202310/content_6910691.htm",
    },
    {
        "code": "GREEN-CERTIFICATE-CN",
        "name": "可再生能源绿色电力证书",
        "instrument_class": "GREEN_CERTIFICATE",
        "native_unit": "certificate",
        "market": "green_certificate_cn",
        "registry": "国家能源局绿证核发交易体系",
        "region": "CN",
        "currency": "CNY",
        "compliance_eligible": False,
        "status": "active",
        "source_name": "可再生能源绿色电力证书核发和交易规则",
        "standard_code": "国能发新能规〔2024〕67号",
        "source_url": "https://www.nea.gov.cn/2024-09/05/c_1310785828.htm",
    },
)

REFERENCE_COMPLIANCE_RULE: dict[str, Any] = {
    "rule_code": "NATIONAL-ETS-2023-2024",
    "rule_name": "全国碳市场2023、2024年度履约规则",
    "version": 1,
    "market": "national",
    "eligible_instrument_classes": ["CEA", "CCER"],
    "max_offset_ratio": 0.05,
    "parameters": {"offsetInstrumentClass": "CCER"},
    "effective_from": date(2023, 1, 1),
    "effective_to": date(2024, 12, 31),
    "status": "published",
    "source_name": "2023、2024年度全国碳排放权交易发电行业配额总量和分配方案",
    "standard_code": "环办气候〔2024〕22号",
    "source_url": "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk03/202410/t20241021_1089750.html",
}


async def ensure_carbon_asset_reference_data(
    session: AsyncSession,
) -> tuple[dict[str, m.CarbonAssetInstrument], m.CarbonComplianceRuleVersion]:
    """Create or refresh the reference catalog inside the active tenant."""
    instruments: dict[str, m.CarbonAssetInstrument] = {}
    for payload in REFERENCE_INSTRUMENTS:
        validate_instrument(
            str(payload["instrument_class"]),
            str(payload["native_unit"]),
            bool(payload["compliance_eligible"]),
        )
        row = await session.scalar(
            select(m.CarbonAssetInstrument).where(m.CarbonAssetInstrument.code == payload["code"])
        )
        if row is None:
            row = m.CarbonAssetInstrument(**payload)
            session.add(row)
        else:
            for field, value in payload.items():
                setattr(row, field, value)
        await session.flush()
        instruments[row.code] = row

    rule = await session.scalar(
        select(m.CarbonComplianceRuleVersion).where(
            m.CarbonComplianceRuleVersion.rule_code == REFERENCE_COMPLIANCE_RULE["rule_code"],
            m.CarbonComplianceRuleVersion.version == REFERENCE_COMPLIANCE_RULE["version"],
        )
    )
    if rule is None:
        rule = m.CarbonComplianceRuleVersion(**REFERENCE_COMPLIANCE_RULE)
        session.add(rule)
    else:
        for field, value in REFERENCE_COMPLIANCE_RULE.items():
            setattr(rule, field, value)
    await session.flush()
    return instruments, rule
