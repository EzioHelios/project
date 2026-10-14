"""Correct the existing Anfang inventory from measured facts and a verified MEE factor.

Default is read-only. Apply requires the reviewed plan fingerprint. This operation
does not initialize tenants, infer meter boundaries, or create sample activities.
"""

# ruff: noqa: RUF001, T201 - Chinese audit metadata and explicit maintenance output.

import argparse
import asyncio
import hashlib
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import pairwise
from uuid import UUID

import httpx
from sqlalchemy import select

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.domain.ghg_inventory import models as g
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.reports import CreateInventoryReport, TransitionInventoryReport
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

TEAM_ID = UUID("00000000-0000-7000-8000-000000000002")
INVENTORY = "ANFANG-2026"
EXPECTED_ACTIVITY_COUNT = 8
PERIOD_ID = 10
BOUNDARY_ID = 10
FACTOR = Decimal("0.5827")
PARAMETER_SET = "MEE-JS-2023-LOCATION"
VALUE_CODE = f"{INVENTORY}:{PARAMETER_SET}:ENERGY_FACTOR"
EVIDENCE_CODE = "MEE-2025-47-ELECTRICITY-2023"
PDF_URL = "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/W020251231726284332528.pdf"
PDF_HASH = "d43b60a3eaad9f3fe59ca37c204d3d0e1b6ea52742a092f0d856971a3f018e5a"


def digest(value: object) -> str:
    """Hash a stable, JSON-serializable review input."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


async def main(*, apply: bool, expected_fingerprint: str | None) -> None:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, trust_env=False) as client:
        pdf = await client.get(PDF_URL)
        pdf.raise_for_status()
        require(hashlib.sha256(pdf.content).hexdigest() == PDF_HASH, "Official PDF hash changed; review required")
    async with provide_services(provide_users_service) as (users,):
        s = users.repository.session
        s.info.update({TENANT_ID_SESSION_KEY: TEAM_ID, TENANT_BYPASS_SESSION_KEY: False})
        team = await s.get(m.Team, TEAM_ID)
        require(team is not None and team.name == "安方中心库", "Tenant mismatch")
        activities = list(
            (
                await s.scalars(
                    select(g.GhgActivityRecord)
                    .where(
                        g.GhgActivityRecord.inventory_code == INVENTORY,
                    )
                    .order_by(g.GhgActivityRecord.record_code)
                )
            ).all()
        )
        require(len(activities) == EXPECTED_ACTIVITY_COUNT, "Expected exactly the eight reviewed activities")
        plan = []
        for activity in activities:
            require(
                activity.source_system == "energy_fact" and activity.data_source_type == "measured",
                "Unverified activity origin",
            )
            require(
                activity.iso_category_code == "2.1" and activity.activity_unit == "kWh", "Unexpected category or unit"
            )
            require(
                activity.reporting_period_id == PERIOD_ID and activity.organization_boundary_id == BOUNDARY_ID,
                "Inventory context changed",
            )
            require(activity.source_payload.get("method_code") == "F08_PURCHASED_ENERGY", "Unexpected method")
            allocations = list(
                (
                    await s.scalars(
                        select(g.GhgActivityAllocation).where(
                            g.GhgActivityAllocation.activity_id == activity.id,
                        )
                    )
                ).all()
            )
            require(len(allocations) == 1 and allocations[0].allocation_ratio == Decimal(1), "Allocation changed")
            allocation = allocations[0]
            boundary = await s.get(m.MeasurementBoundary, allocation.measurement_boundary_id)
            require(
                boundary is not None
                and boundary.status == "active"
                and boundary.include_in_scope2
                and boundary.energy_direction == "import"
                and boundary.meter_equipment_id == allocation.equipment_id,
                "Missing explicit import boundary",
            )
            require(
                boundary.valid_from is None or boundary.valid_from <= activity.period_start, "Boundary starts too late"
            )
            require(boundary.valid_to is None or boundary.valid_to >= activity.period_end, "Boundary expires too early")
            f = m.EnergyIntervalFact
            facts = list(
                (
                    await s.scalars(
                        select(f)
                        .where(
                            f.is_current.is_(True),
                            f.granularity == "hour",
                            f.energy_type_code == "purchased_electricity",
                            f.equipment_id == allocation.equipment_id,
                            f.period_start >= datetime.combine(activity.period_start, time.min),
                            f.period_end <= datetime.combine(activity.period_end + timedelta(days=1), time.min),
                        )
                        .order_by(f.period_start, f.id)
                    )
                ).all()
            )
            require(bool(facts), f"No measured facts for {activity.record_code}")
            require(
                all(
                    v.data_quality == "measured"
                    and v.source_system == "meter_projection"
                    and v.unit == "kWh"
                    and v.measurement_boundary_id == boundary.id
                    and v.amount >= 0
                    for v in facts
                ),
                "Unverified or mismatched fact",
            )
            require(all(a.period_end <= b.period_start for a, b in pairwise(facts)), "Overlapping hourly facts")
            amount = sum((v.amount for v in facts), Decimal(0))
            plan.append(
                {
                    "activity_id": activity.id,
                    "record_code": activity.record_code,
                    "old_kwh": str(activity.activity_amount),
                    "kwh": str(amount),
                    "start": str(activity.period_start),
                    "end": str(activity.period_end),
                    "equipment_id": allocation.equipment_id,
                    "boundary_id": boundary.id,
                    "fact_count": len(facts),
                    "fact_hash": digest([(v.id, v.revision_no, v.period_start, v.period_end, v.amount) for v in facts]),
                }
            )
        desired = [{k: v for k, v in item.items() if k != "old_kwh"} for item in plan]
        fingerprint = digest(
            {"team": TEAM_ID, "inventory": INVENTORY, "factor_pdf": PDF_HASH, "factor": FACTOR, "activities": desired}
        )
        expected_total = sum((Decimal(v["kwh"]) * FACTOR for v in plan), Decimal(0))
        print(
            json.dumps(
                {
                    "apply": apply,
                    "fingerprint": fingerprint,
                    "activities": plan,
                    "total_kwh": str(sum((Decimal(v["kwh"]) for v in plan), Decimal(0))),
                    "total_co2_kg": str(expected_total),
                    "factor": str(FACTOR),
                    "factor_year": 2023,
                    "coverage": "Existing eight metered circuits, not a full-warehouse declaration",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if not apply:
            await s.rollback()
            return
        require(expected_fingerprint == fingerprint, "Plan changed or fingerprint missing; no writes applied")
        evidence = await s.scalar(select(g.GhgEvidenceFile).where(g.GhgEvidenceFile.evidence_code == EVIDENCE_CODE))
        if evidence is None:
            evidence = g.GhgEvidenceFile(
                evidence_code=EVIDENCE_CODE,
                file_name="2023年电力二氧化碳排放因子.pdf",
                document_type="emission_factor",
                document_no="生态环境部、国家统计局公告2025年第47号",
                issuer="生态环境部、国家统计局",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                storage_key=PDF_URL,
                sha256=PDF_HASH,
                confidentiality="public",
                verification_status="verified",
                valid_from=date(2025, 12, 31),
            )
            s.add(evidence)
            await s.flush()
        require(evidence.sha256 == PDF_HASH and evidence.storage_key == PDF_URL, "Evidence mismatch")
        factor = await s.scalar(select(g.GhgParameterValue).where(g.GhgParameterValue.value_code == VALUE_CODE))
        if factor is None:
            factor = g.GhgParameterValue(
                value_code=VALUE_CODE,
                version=1,
                parameter_code="ENERGY_FACTOR",
                parameter_name="江苏省电力平均二氧化碳排放因子（2023年）",
                parameter_role="emission_factor",
                value=FACTOR,
                unit="kgCO2/kWh",
                source_mode="authority_published",
                source_name="生态环境部、国家统计局《2023年电力二氧化碳排放因子》",
                source_version="2023",
                standard_code="公告2025年第47号",
                table_reference="表3：江苏",
                reference_year=2023,
                geography="江苏",
                fuel_or_material="外购电力",
                valid_from=date(2025, 12, 31),
                evidence_code=EVIDENCE_CODE,
                measurement_method="省级电力平均二氧化碳排放因子；地点法",
                approval_status="approved",
                status="active",
            )
            s.add(factor)
        require(factor.value == FACTOR and factor.evidence_code == EVIDENCE_CODE, "Factor mismatch")
        previous_factor = await s.get(g.GhgParameterValue, 833)
        require(
            previous_factor is not None
            and previous_factor.value == Decimal("0.5703")
            and previous_factor.value_code == "ANFANG-2026:ANFANG-ELEC-GRID-2026:ENERGY_FACTOR",
            "Old factor changed",
        )
        previous_factor.status = "archived"
        link_code = "MEE-JS-2023-PARAMETER"
        if await s.scalar(select(g.GhgEvidenceLink).where(g.GhgEvidenceLink.link_code == link_code)) is None:
            s.add(
                g.GhgEvidenceLink(
                    link_code=link_code,
                    record_type="parameter",
                    record_code=VALUE_CODE,
                    evidence_id=evidence.id,
                    evidence_role="factor_source",
                    page_or_cell_reference="第1页，表3，江苏",
                    review_status="verified",
                )
            )
        for activity, item in zip(activities, desired, strict=True):
            activity.activity_amount = Decimal(item["kwh"])
            activity.parameter_set_code = PARAMETER_SET
            activity.source_payload = {
                **activity.source_payload,
                "energy_fact_evidence": item,
                "factor_reference_year": 2023,
                "factor_source_url": PDF_URL,
            }
        await s.flush()
        runs = list(
            (
                await s.scalars(
                    select(g.GhgCalculationRun)
                    .where(
                        g.GhgCalculationRun.inventory_code == INVENTORY,
                        g.GhgCalculationRun.status == "completed",
                    )
                    .order_by(g.GhgCalculationRun.id.desc())
                )
            ).all()
        )
        run = next((r for r in runs if (r.input_snapshot or {}).get("maintenanceFingerprint") == fingerprint), None)
        if run is None:
            run = await RunInventoryCalculation(s).execute(
                inventory_code=INVENTORY,
                reporting_profile_code="CORPORATE_ISO14064_GHGP",
                reporting_period_id=PERIOD_ID,
                reporting_org_id=6,
                organization_boundary_id=BOUNDARY_ID,
                default_scope2_method="location",
            )
            run.input_snapshot = {
                **run.input_snapshot,
                "maintenanceFingerprint": fingerprint,
                "energyFactEvidence": desired,
                "factorSourceUrl": PDF_URL,
                "factorSha256": PDF_HASH,
            }
        require(run.total_co2e_kg == expected_total, "Calculation total mismatch")
        await s.commit()
        old_report = await s.get(g.GhgInventoryReport, 14)
        require(old_report is not None and old_report.report_code == "ANFANG-INV-2026", "Old report changed")
        if old_report.status == "published":
            await TransitionInventoryReport(s).execute(
                report_code=old_report.report_code,
                version=old_report.version,
                action="archive",
                actor="运维维护（用户授权）",
                comment="原报告使用演示因子且活动量已被能源事实重建修正；保留历史版本，新核算采用正式江苏因子。",
            )
        report = await s.scalar(select(g.GhgInventoryReport).where(g.GhgInventoryReport.run_id == run.id))
        if report is None:
            report = await CreateInventoryReport(s).execute(
                run_code=run.run_code,
                title="安方中心库已接入计量回路外购电力排放计算记录（2026年7月至8月）",
                change_summary="按既有8个计量回路及原记录期间更新小时级实测电量；采用公告2025年第47号表3江苏2023年因子0.5827 kgCO2/kWh。仅覆盖已有计量回路，不代表全仓完整盘查。",
            )
        print(
            json.dumps(
                {
                    "run_id": run.id,
                    "run_code": run.run_code,
                    "kg": str(run.total_co2e_kg),
                    "report_id": report.id,
                    "report_status": report.status,
                    "fingerprint": fingerprint,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-fingerprint")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, expected_fingerprint=args.expected_fingerprint))
