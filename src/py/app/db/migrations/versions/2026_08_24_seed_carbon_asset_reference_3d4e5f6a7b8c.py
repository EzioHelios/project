"""seed traceable carbon asset instruments and compliance rule

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-08-24
"""

from __future__ import annotations

# ruff: noqa: RUF001
from datetime import date

import sqlalchemy as sa
from alembic import op

from app.domain.carbon_assets import models

revision = "3d4e5f6a7b8c"
down_revision = "2c3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    team = sa.table("team", sa.column("id"))
    instrument = models.CarbonAssetInstrument.__table__
    rule = models.CarbonComplianceRuleVersion.__table__
    for team_id in bind.scalars(sa.select(team.c.id)):
        bind.execute(
            instrument.insert(),
            [
                {
                    "team_id": team_id, "code": "CEA-NATIONAL", "name": "全国碳排放配额", "instrument_class": "CEA",
                    "native_unit": "tCO2e", "market": "national", "registry": "全国碳排放权注册登记系统",
                    "region": "CN", "currency": "CNY", "compliance_eligible": True, "status": "active",
                    "source_name": "全国碳市场制度", "standard_code": "全国碳市场", "source_url": "https://www.mee.gov.cn/",
                },
                {
                    "team_id": team_id, "code": "CCER-NATIONAL", "name": "国家核证自愿减排量", "instrument_class": "CCER",
                    "native_unit": "tCO2e", "market": "national_ccer", "registry": "全国温室气体自愿减排注册登记系统",
                    "region": "CN", "currency": "CNY", "compliance_eligible": True, "status": "active",
                    "source_name": "温室气体自愿减排交易管理办法（试行）", "standard_code": "生态环境部令第31号",
                    "source_url": "https://www.gov.cn/zhengce/zhengceku/202310/content_6910691.htm",
                },
                {
                    "team_id": team_id, "code": "GREEN-CERTIFICATE-CN", "name": "可再生能源绿色电力证书",
                    "instrument_class": "GREEN_CERTIFICATE", "native_unit": "certificate", "market": "green_certificate_cn",
                    "registry": "国家能源局绿证核发交易体系", "region": "CN", "currency": "CNY",
                    "compliance_eligible": False, "status": "active", "source_name": "可再生能源绿色电力证书核发和交易规则",
                    "standard_code": "国能发新能规〔2024〕67号", "source_url": "https://www.nea.gov.cn/2024-09/05/c_1310785828.htm",
                },
            ],
        )
        bind.execute(
            rule.insert().values(
                team_id=team_id, rule_code="NATIONAL-ETS-2023-2024", rule_name="全国碳市场2023、2024年度履约规则",
                version=1, market="national", eligible_instrument_classes=["CEA", "CCER"], max_offset_ratio=0.05,
                parameters={"offsetInstrumentClass": "CCER"}, effective_from=date(2023, 1, 1), effective_to=date(2024, 12, 31),
                status="published", source_name="2023、2024年度全国碳排放权交易发电行业配额总量和分配方案",
                standard_code="环办气候〔2024〕22号", source_url="https://www.mee.gov.cn/xxgk2018/xxgk/xxgk03/202410/t20241021_1089750.html",
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.delete(models.CarbonComplianceRuleVersion.__table__).where(models.CarbonComplianceRuleVersion.__table__.c.rule_code == "NATIONAL-ETS-2023-2024"))
    bind.execute(sa.delete(models.CarbonAssetInstrument.__table__).where(models.CarbonAssetInstrument.__table__.c.code.in_(("CEA-NATIONAL", "CCER-NATIONAL", "GREEN-CERTIFICATE-CN"))))
