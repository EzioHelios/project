"""Calculate the user-selected Xiangtai metered scope with the existing GHG engine.

No synthetic activities, inferred electrical topology or photovoltaic deductions.
Read-only by default. Application requires an exact reviewed input fingerprint.
Reports stay draft; electrical-boundary uncertainty is preserved in audit metadata.
"""

# ruff: noqa: RUF001, T201 - Chinese business metadata and maintenance output.
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.domain.ghg_inventory import models as g
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.reports import CreateInventoryReport
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

TEAM_ID = UUID("00000000-0000-7000-8000-000000000001")
PREPARED_BY = "xiangtai_meter_preparation_v1"
OWNER = "xiangtai_meter_inventory_v1"
FACTOR = Decimal("0.5827")
FACTOR_YEAR = 2023
EXPECTED_COUNT = 156
PDF_HASH = "d43b60a3eaad9f3fe59ca37c204d3d0e1b6ea52742a092f0d856971a3f018e5a"
INVENTORIES = ("XIANGTAI-METER-2025", "XIANGTAI-METER-2026")
SCOPE_NOTE = (
    "按用户指定的现有区域设备计量范围汇总；仅覆盖所列电表和实际采集期间。"
    "电力按江苏2023年平均因子折算，不扣减光伏，不补值。"
    "区域归属不作为总分表电气关系证明；未声明全仓覆盖或总分表无重叠。"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def validate_activity(activity: Any, allocation: Any, device: Any, area: Any) -> dict:
    """Require actual owned meter records and retain all existing quality flags."""
    payload = activity.source_payload or {}
    require(activity.inventory_code in INVENTORIES, "Unexpected inventory")
    require(payload.get("prepared_by") == PREPARED_BY, "Activity was not prepared from verified facts")
    require(activity.source_system == "energy_fact" and activity.data_source_type == "measured", "Not measured data")
    require(activity.iso_category_code == "2.1" and activity.activity_unit == "kWh", "Unexpected activity type")
    require(payload.get("method_code") == "F08_PURCHASED_ENERGY", "Unexpected method")
    require(activity.status in {"draft", "approved"}, "Activity has a conflicting state")
    require(activity.activity_amount.is_finite() and activity.activity_amount >= 0, "Invalid amount")
    require(device is not None and area is not None, "Missing tenant-owned device or area")
    require(device.is_enable and device.category == 0 and device.code != "432301227008", "Excluded equipment")
    require(allocation.allocation_ratio == 1, "Allocation must cover exactly one meter")
    require(
        allocation.equipment_id == device.id and allocation.area_id == device.sector_id == area.id, "Binding changed"
    )
    require(payload.get("meter_point") == device.code and activity.facility_code == area.code, "Code binding changed")
    ids = payload.get("fact_ids", [])
    require(bool(ids) and len(ids) == len(set(ids)) == payload.get("fact_count"), "Invalid source facts")
    return {
        "id": activity.id,
        "record_code": activity.record_code,
        "inventory_code": activity.inventory_code,
        "period_id": activity.reporting_period_id,
        "start": str(activity.period_start),
        "end": str(activity.period_end),
        "kwh": str(activity.activity_amount),
        "equipment_id": device.id,
        "equipment_code": device.code,
        "equipment_name": device.name,
        "area_id": area.id,
        "area_code": area.code,
        "area_name": area.name,
        "fact_hash": payload["fact_hash"],
        "fact_count": len(ids),
        "missing_hours": payload["missing_hours"],
    }


async def inspect(session: Any) -> tuple[list, dict]:
    activities = list(
        (
            await session.scalars(
                select(g.GhgActivityRecord)
                .where(
                    g.GhgActivityRecord.inventory_code.in_(INVENTORIES),
                )
                .order_by(g.GhgActivityRecord.record_code)
            )
        ).all()
    )
    require(len(activities) == EXPECTED_COUNT, "Reviewed batch must contain exactly 156 activities")
    devices = {v.id: v for v in (await session.scalars(select(m.MonitorEquipment))).all()}
    areas = {v.id: v for v in (await session.scalars(select(m.MonitorSector))).all()}
    allocations = defaultdict(list)
    for row in (
        await session.scalars(
            select(g.GhgActivityAllocation).where(
                g.GhgActivityAllocation.activity_id.in_([v.id for v in activities]),
            )
        )
    ).all():
        allocations[row.activity_id].append(row)
    items = []
    seen_facts: set[int] = set()
    f = m.EnergyIntervalFact
    fields = [
        f.id,
        f.equipment_id,
        f.equipment_code,
        f.area_id,
        f.period_start,
        f.period_end,
        f.amount,
        f.source_system,
        f.granularity,
        f.data_quality,
        f.unit,
        f.is_current,
        f.energy_type_code,
        f.source_snapshot,
        f.projection_run_id,
        f.revision_no,
    ]
    for activity in activities:
        require(len(allocations[activity.id]) == 1, "Expected one area/device allocation")
        allocation = allocations[activity.id][0]
        item = validate_activity(
            activity, allocation, devices.get(allocation.equipment_id), areas.get(allocation.area_id)
        )
        ids = activity.source_payload["fact_ids"]
        require(not seen_facts.intersection(ids), "Source facts assigned to multiple activities")
        seen_facts.update(ids)
        facts = [
            dict(v)
            for v in (
                await session.execute(select(*fields).where(f.id.in_(ids)).order_by(f.period_start, f.id))
            ).mappings()
        ]
        require(len(facts) == len(ids) and all(v["is_current"] for v in facts), "Source facts missing or retired")
        require(digest(facts) == item["fact_hash"], "Source facts changed since preparation")
        require(
            sum((v["amount"] for v in facts), Decimal(0)) == activity.activity_amount, "Activity differs from facts"
        )
        items.append(item)
    factors = []
    for inventory in INVENTORIES:
        factor = await session.scalar(
            select(g.GhgParameterValue).where(
                g.GhgParameterValue.value_code == f"{inventory}:MEE-JS-2023-LOCATION:ENERGY_FACTOR",
            )
        )
        require(
            factor is not None
            and factor.value == FACTOR
            and factor.status == "active"
            and factor.approval_status == "approved"
            and factor.reference_year == FACTOR_YEAR,
            "Factor changed",
        )
        evidence = await session.scalar(
            select(g.GhgEvidenceFile).where(
                g.GhgEvidenceFile.evidence_code == factor.evidence_code,
            )
        )
        require(evidence is not None and evidence.sha256 == PDF_HASH, "Factor evidence changed")
        factors.append({"id": factor.id, "code": factor.value_code, "value": str(factor.value), "hash": PDF_HASH})
    plan = {"team_id": str(TEAM_ID), "items": items, "factors": factors, "scope": SCOPE_NOTE}
    return activities, plan


async def calculate_inventory(session: Any, activities: list, plan: dict, inventory: str, fingerprint: str) -> dict:
    selected = [v for v in activities if v.inventory_code == inventory]
    items = [v for v in plan["items"] if v["inventory_code"] == inventory]
    require(len({v.reporting_period_id for v in selected}) == 1, "Mixed reporting periods")
    period = await session.get(m.ReportingPeriod, selected[0].reporting_period_id)
    organization = await session.get(m.ReportingOrganization, period.reporting_org_id)
    require(period.code == inventory and organization.code == "XIANGTAI-METERED", "Context mismatch")
    require(period.status in {"draft", "active"}, "Reporting period is locked or changed")
    organization.status = "active"
    organization.remark = SCOPE_NOTE
    period.name = f"祥泰仓库{inventory[-4:]}年已接入设备电力核算"
    period.remark = SCOPE_NOTE
    boundary_no = f"{inventory}-METERED"
    boundary = await session.scalar(
        select(m.OrganizationBoundary).where(m.OrganizationBoundary.boundary_no == boundary_no)
    )
    device_items = {v["equipment_id"]: v for v in items}
    if boundary is None:
        boundary = m.OrganizationBoundary(
            reporting_org_id=organization.id,
            period_id=period.id,
            boundary_no=boundary_no,
            boundary_name=f"祥泰{inventory[-4:]}年已接入设备计量范围",
            boundary_type="organization",
            boundary_method="operational_control",
            version=1,
            status="published",
            published_at=datetime.now().astimezone().replace(tzinfo=None),
            source_name="用户指定现有区域设备范围",
            confidence_level="medium",
            remark=SCOPE_NOTE,
            operational_boundary={
                "scope2": True,
                "calculation_basis": "configured_metered_scope",
                "purchase_boundary_status": "unconfirmed",
                "full_inventory_verified": False,
                "equipment_codes": sorted(v["equipment_code"] for v in device_items.values()),
                "maintenance_owner": OWNER,
            },
        )
        session.add(boundary)
        await session.flush()
        for item in device_items.values():
            session.add(
                m.BoundaryFacility(
                    boundary_id=boundary.id,
                    facility_type="equipment",
                    area_id=item["area_id"],
                    equipment_id=item["equipment_id"],
                    facility_code=item["equipment_code"],
                    facility_name=item["equipment_name"],
                    facility_role="energy_consumption",
                    included=True,
                    valid_from=period.period_start,
                    valid_to=period.period_end,
                    source_name="既有设备区域登记",
                )
            )
    else:
        require(
            boundary.status == "published"
            and boundary.period_id == period.id
            and (boundary.operational_boundary or {}).get("maintenance_owner") == OWNER,
            "Boundary changed",
        )
        members = (
            await session.scalars(select(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == boundary.id))
        ).all()
        require(
            len(members) == len(device_items)
            and {v.equipment_id for v in members} == device_items.keys()
            and all(v.included and v.area_id == device_items[v.equipment_id]["area_id"] for v in members),
            "Boundary membership changed",
        )
    for activity in selected:
        require(activity.organization_boundary_id in {None, boundary.id}, "Conflicting activity boundary")
        activity.organization_boundary_id = boundary.id
        activity.boundary_status = "included"
        activity.status = "approved"
        activity.source_payload = {
            **activity.source_payload,
            "calculated_by": OWNER,
            "calculation_basis": "configured_metered_scope",
        }
        activity.remarks = (
            f"按现有区域设备计量范围核算；{activity.source_payload['fact_count']}个小时区间，"
            f"当月未覆盖{activity.source_payload['missing_hours']}小时，未补值。{SCOPE_NOTE}"
        )
        source = await session.get(g.GhgEmissionSource, activity.emission_source_id)
        require(source is not None and source.inventory_code == inventory, "Source mismatch")
        require(source.organization_boundary_id in {None, boundary.id}, "Conflicting source boundary")
        source.organization_boundary_id = boundary.id
    await session.flush()
    runs = (
        await session.scalars(
            select(g.GhgCalculationRun).where(
                g.GhgCalculationRun.inventory_code == inventory,
                g.GhgCalculationRun.status == "completed",
            )
        )
    ).all()
    run = next((v for v in runs if (v.input_snapshot or {}).get("maintenanceFingerprint") == fingerprint), None)
    if run is None:
        require(not runs, "Existing completed calculation needs review before recalculation")
        run = await RunInventoryCalculation(session).execute(
            inventory_code=inventory,
            reporting_profile_code="CORPORATE_ISO14064_GHGP",
            reporting_period_id=period.id,
            reporting_org_id=organization.id,
            organization_boundary_id=boundary.id,
        )
        run.input_snapshot = {
            **run.input_snapshot,
            "maintenanceFingerprint": fingerprint,
            "calculationBasis": "configured_metered_scope",
            "scopeNote": SCOPE_NOTE,
            "fullInventoryVerified": False,
            "energyFactEvidence": items,
            "factorSha256": PDF_HASH,
        }
        await session.commit()
    expected = sum((Decimal(v["kwh"]) * FACTOR for v in items), Decimal(0))
    require(abs(run.total_co2e_kg - expected) <= Decimal("0.000001"), "Calculation total differs from inputs")
    report = await session.scalar(select(g.GhgInventoryReport).where(g.GhgInventoryReport.run_id == run.id))
    report_summary = (
        f"{min(v['start'] for v in items)}至{max(v['end'] for v in items)}；"
        f"{len(device_items)}个电表，{len(selected)}条月度活动；江苏2023年电力因子0.5827 kgCO2/kWh。"
    )
    if report is None:
        report = await CreateInventoryReport(session).execute(
            run_code=run.run_code,
            title=f"祥泰仓库{inventory[-4:]}年已接入设备电力排放核算报告",
            change_summary=report_summary,
        )
    elif report.status == "draft" and report.change_summary == SCOPE_NOTE:
        report.change_summary = report_summary
    await session.commit()
    return {
        "inventory": inventory,
        "run_code": run.run_code,
        "report_id": report.id,
        "report_status": report.status,
        "activity_count": len(selected),
        "meters": len(device_items),
        "kwh": str(sum((Decimal(v["kwh"]) for v in items), Decimal(0))),
        "co2_kg": str(run.total_co2e_kg),
    }


async def main(*, apply: bool, expected_fingerprint: str | None) -> None:
    async with provide_services(provide_users_service) as (users,):
        session = users.repository.session
        session.info.update({TENANT_ID_SESSION_KEY: TEAM_ID, TENANT_BYPASS_SESSION_KEY: False})
        team = await session.get(m.Team, TEAM_ID)
        require(team is not None and team.name == "祥泰仓库", "Wrong tenant")
        activities, plan = await inspect(session)
        fingerprint = digest(plan)
        print(json.dumps({"apply": apply, "fingerprint": fingerprint, "plan": plan}, ensure_ascii=False), flush=True)
        if not apply:
            await session.rollback()
            return
        require(fingerprint == expected_fingerprint, "Reviewed fingerprint mismatch; no changes applied")
        for inventory in INVENTORIES:
            result = await calculate_inventory(session, activities, plan, inventory, fingerprint)
            print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-fingerprint")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, expected_fingerprint=args.expected_fingerprint))
