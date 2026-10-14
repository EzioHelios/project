"""Prepare traceable Xiangtai meter activities without inventing a purchase boundary.

Read-only by default. Apply requires a reviewed input fingerprint. All activities
remain draft/excluded until the electricity purchase boundary is established.
Never invokes demo initialization, publishes a boundary, or runs an inventory.
"""

# ruff: noqa: RUF001, T201 - maintenance audit output and Chinese business data.
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.domain.ghg_inventory import models as g
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

TEAM_ID = UUID("00000000-0000-7000-8000-000000000001")
ORGANIZATION_CODE = "XIANGTAI-METERED"
OWNER = "xiangtai_meter_preparation_v1"
CATEGORY = CATEGORY_BY_CODE["2.1"]
FACTOR = Decimal("0.5827")
PARAMETER_SET = "MEE-JS-2023-LOCATION"
PDF_URL = "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/W020251231726284332528.pdf"
PDF_HASH = "d43b60a3eaad9f3fe59ca37c204d3d0e1b6ea52742a092f0d856971a3f018e5a"
EVIDENCE_CODE = "MEE-2025-47-ELECTRICITY-2023"
# The legacy registry identifies this storage circuit but does not define charge/discharge registers.
HELD_CODES = {"432301227008": "储能充放电方向待核实"}


def digest(value: object) -> str:
    """Hash reviewed business inputs, excluding generated database IDs."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def monthly_plan(facts: list[dict[str, Any]], devices: dict[int, dict], areas: dict[int, dict]) -> dict:
    """Only aggregate disjoint, measured hourly facts for the same meter/month."""
    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    held: dict[str, int] = defaultdict(int)
    for fact in facts:
        device = devices.get(fact["equipment_id"])
        require(device is not None, "Fact has no tenant-owned device")
        code = device["code"]
        if device["category"] != 0 or code in HELD_CODES or not device["is_enable"]:
            held[code] += 1
            continue
        area = areas.get(device["sector_id"])
        require(area is not None and area["code"] == fact["area_id"], f"Area mapping mismatch: {code}")
        require(fact["equipment_code"] == code, f"Equipment mapping mismatch: {code}")
        require(
            fact["source_system"] == "meter_projection"
            and fact["granularity"] == "hour"
            and fact["data_quality"] == "measured"
            and fact["unit"] == "kWh"
            and fact["is_current"]
            and fact["energy_type_code"] == "purchased_electricity"
            and fact["amount"].is_finite()
            and fact["amount"] >= 0,
            f"Unverified hourly fact: {fact['id']}",
        )
        require(
            (fact["source_snapshot"] or {}).get("reading_source_system") in {"yunji", "yunji_legacy"},
            f"Unverified raw reading origin: {fact['id']}",
        )
        require(fact["period_end"] - fact["period_start"] == timedelta(hours=1), "Not a one-hour interval")
        grouped[(device["id"], fact["period_start"].strftime("%Y-%m"))].append(fact)
    items = []
    for (device_id, month), values in sorted(grouped.items()):
        values.sort(key=lambda row: (row["period_start"], row["id"]))
        require(all(a["period_end"] <= b["period_start"] for a, b in pairwise(values)), "Overlapping hourly facts")
        device = devices[device_id]
        area = areas[device["sector_id"]]
        month_start = datetime.fromisoformat(f"{month}-01")
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        require(all(v["period_end"] <= month_end for v in values), "Fact crosses monthly boundary")
        items.append(
            {
                "inventory_code": f"XIANGTAI-METER-{month[:4]}",
                "record_code": f"XT-METER-{device['code']}-{month}",
                "equipment_id": device_id,
                "equipment_code": device["code"],
                "equipment_name": device["name"],
                "area_id": area["id"],
                "area_code": area["code"],
                "area_name": area["name"],
                "month": month,
                "period_start": str(values[0]["period_start"].date()),
                "period_end": str((values[-1]["period_end"] - timedelta(microseconds=1)).date()),
                "kwh": str(sum((v["amount"] for v in values), Decimal(0))),
                "fact_count": len(values),
                "missing_hours": int((month_end - month_start).total_seconds() / 3600) - len(values),
                "fact_hash": digest(values),
                "fact_ids": [v["id"] for v in values],
                "projection_run_ids": sorted({v["projection_run_id"] for v in values}),
                "source_system": "energy_fact",
                "boundary_status": "excluded",
                "status": "draft",
            }
        )
    return {"items": items, "held_fact_counts": dict(held), "factor_pdf_hash": PDF_HASH, "factor": str(FACTOR)}


async def ensure(session: Any, model: Any, key: dict, values: dict) -> Any:
    """Create an exact owned record or reject a conflicting existing record."""
    row = await session.scalar(select(model).filter_by(**key))
    if row is None:
        row = model(**key, **values)
        session.add(row)
        await session.flush()
    else:
        require(
            all(getattr(row, k) == v for k, v in values.items()), f"Existing {model.__name__} differs; review required"
        )
    return row


async def apply_plan(session: Any, plan: dict) -> dict:
    """Atomically prepare existing canonical entities; do not authorize calculation."""
    organization = await ensure(
        session,
        m.ReportingOrganization,
        {"code": ORGANIZATION_CODE},
        {
            "name": "祥泰仓库计量数据",
            "organization_type": "facility",
            "status": "draft",
            "source_name": OWNER,
            "remark": "按现有设备区域登记整理；组织控制关系及外购电边界待确认。",
        },
    )
    evidence = await ensure(
        session,
        g.GhgEvidenceFile,
        {"evidence_code": EVIDENCE_CODE},
        {
            "file_name": "2023年电力二氧化碳排放因子.pdf",
            "document_type": "emission_factor",
            "document_no": "生态环境部、国家统计局公告2025年第47号",
            "issuer": "生态环境部、国家统计局",
            "storage_key": PDF_URL,
            "sha256": PDF_HASH,
            "confidentiality": "public",
            "verification_status": "verified",
        },
    )
    periods = {}
    for inventory in sorted({v["inventory_code"] for v in plan["items"]}):
        year = int(inventory[-4:])
        periods[inventory] = await ensure(
            session,
            m.ReportingPeriod,
            {"code": inventory},
            {
                "reporting_org_id": organization.id,
                "name": f"祥泰仓库{year}年计量活动整理",
                "period_type": "annual",
                "period_start": date(year, 1, 1),
                "period_end": date(year, 12, 31),
                "status": "draft",
                "source_name": OWNER,
            },
        )
        value_code = f"{inventory}:{PARAMETER_SET}:ENERGY_FACTOR"
        await ensure(
            session,
            g.GhgParameterValue,
            {"value_code": value_code, "version": 1},
            {
                "parameter_code": "ENERGY_FACTOR",
                "parameter_name": "江苏省电力平均二氧化碳排放因子（2023年）",
                "parameter_role": "emission_factor",
                "value": FACTOR,
                "unit": "kgCO2/kWh",
                "source_mode": "authority_published",
                "source_name": "生态环境部、国家统计局《2023年电力二氧化碳排放因子》",
                "source_version": "2023",
                "standard_code": "公告2025年第47号",
                "table_reference": "表3：江苏",
                "reference_year": 2023,
                "geography": "江苏",
                "fuel_or_material": "外购电力",
                "evidence_code": EVIDENCE_CODE,
                "approval_status": "approved",
                "status": "active",
            },
        )
        await ensure(
            session,
            g.GhgEvidenceLink,
            {"link_code": f"{inventory}-FACTOR"},
            {
                "record_type": "parameter",
                "record_code": value_code,
                "evidence_id": evidence.id,
                "evidence_role": "factor_source",
                "page_or_cell_reference": "第1页，表3，江苏",
                "review_status": "verified",
            },
        )
    created = reused = 0
    for item in plan["items"]:
        inventory = item["inventory_code"]
        source_code = f"METER-{item['equipment_code']}"
        source = await ensure(
            session,
            g.GhgEmissionSource,
            {"inventory_code": inventory, "source_code": source_code},
            {
                "reporting_period_id": periods[inventory].id,
                "organization_code": ORGANIZATION_CODE,
                "facility_code": item["area_code"],
                "source_name": f"{item['equipment_name']}计量活动",
                "iso_category_code": "2.1",
                "source_mechanism": CATEGORY.source_mechanism,
                "origin_kind": "internal",
                "default_area_id": item["area_id"],
                "default_equipment_id": item["equipment_id"],
                "default_allocation_role": "energy_consumption",
                "source_system": "energy_fact",
                "source_payload": {"prepared_by": OWNER, "purchase_boundary_status": "unconfirmed"},
                "status": "active",
            },
        )
        old = await session.scalar(
            select(g.GhgActivityRecord).filter_by(inventory_code=inventory, record_code=item["record_code"])
        )
        values = {
            "reporting_period_id": periods[inventory].id,
            "organization_boundary_id": None,
            "emission_source_id": source.id,
            "organization_code": ORGANIZATION_CODE,
            "facility_code": item["area_code"],
            "source_code": source_code,
            "activity_code": item["record_code"],
            "activity_name": f"{item['equipment_name']} {item['month']}计量电量",
            "period_start": date.fromisoformat(item["period_start"]),
            "period_end": date.fromisoformat(item["period_end"]),
            "iso_category_code": "2.1",
            "ghg_scope": CATEGORY.ghg_scope,
            "source_mechanism": CATEGORY.source_mechanism,
            "value_chain_position": CATEGORY.value_chain_position,
            "boundary_status": "excluded",
            "activity_amount": Decimal(item["kwh"]),
            "activity_unit": "kWh",
            "data_source_type": "measured",
            "measurement_method": "逐表有效小时电量按月归集",
            "quality_status": "warning",
            "parameter_set_code": PARAMETER_SET,
            "source_system": "energy_fact",
            "source_record_type": "meter_month",
            "source_record_id": item["equipment_id"],
            "status": "draft",
            "source_payload": {
                "prepared_by": OWNER,
                "method_code": "F08_PURCHASED_ENERGY",
                "energy_type": "electricity",
                "meter_point": item["equipment_code"],
                "scope2_method": "location",
                "supplier_name": "",
                "purchase_boundary_status": "unconfirmed",
                "fact_hash": item["fact_hash"],
                "fact_ids": item["fact_ids"],
                "projection_run_ids": item["projection_run_ids"],
                "fact_count": item["fact_count"],
                "missing_hours": item["missing_hours"],
                "organization_total_eligible": False,
            },
            "remarks": f"计量活动待确认：供电方、购电范围及总分表关系。已归集{item['fact_count']}个小时区间，"
            f"当月未覆盖{item['missing_hours']}小时；未覆盖时段未补值。未纳入组织排放核算。",
        }
        activity = await ensure(
            session, g.GhgActivityRecord, {"inventory_code": inventory, "record_code": item["record_code"]}, values
        )
        if old is None:
            await ReplaceActivityAllocations(session).execute(
                inventory_code=inventory,
                record_code=activity.record_code,
                allocations=[
                    {
                        "area_id": item["area_id"],
                        "equipment_id": item["equipment_id"],
                        "allocation_role": "energy_consumption",
                        "allocation_ratio": Decimal(1),
                        "source_kind": "measured",
                    }
                ],
                commit=False,
            )
            created += 1
        else:
            allocations = list(
                (await session.scalars(select(g.GhgActivityAllocation).filter_by(activity_id=activity.id))).all()
            )
            require(
                len(allocations) == 1
                and allocations[0].equipment_id == item["equipment_id"]
                and allocations[0].area_id == item["area_id"]
                and allocations[0].allocation_ratio == 1,
                "Existing allocation changed; review required",
            )
            reused += 1
    return {"created": created, "reused": reused, "formal_runs_created": 0}


async def main(*, apply: bool, expected_fingerprint: str | None, through_month: str) -> None:
    cutoff = datetime.fromisoformat(f"{through_month}-01")
    end = (cutoff.replace(day=28) + timedelta(days=4)).replace(day=1)
    require(end.date() <= datetime.now(UTC).date(), "Only closed months may be prepared")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, trust_env=False) as client:
        response = await client.get(PDF_URL)
        response.raise_for_status()
        require(hashlib.sha256(response.content).hexdigest() == PDF_HASH, "Official PDF changed; review required")
    async with provide_services(provide_users_service) as (users,):
        session = users.repository.session
        session.info.update({TENANT_ID_SESSION_KEY: TEAM_ID, TENANT_BYPASS_SESSION_KEY: False})
        team = await session.get(m.Team, TEAM_ID)
        require(team is not None and team.name == "祥泰仓库", "Tenant mismatch")
        await session.execute(select(func.pg_advisory_xact_lock(7131013)))
        devices = {
            v.id: {c.key: getattr(v, c.key) for c in v.__table__.columns}
            for v in (await session.scalars(select(m.MonitorEquipment))).all()
        }
        areas = {
            v.id: {"id": v.id, "code": v.code, "name": v.name}
            for v in (await session.scalars(select(m.MonitorSector))).all()
        }
        f = m.EnergyIntervalFact
        columns = [
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
        facts = [
            dict(v)
            for v in (
                await session.execute(
                    select(*columns).where(
                        f.is_current.is_(True),
                        f.source_system == "meter_projection",
                        f.granularity == "hour",
                        f.period_end <= end,
                    )
                )
            ).mappings()
        ]
        plan = monthly_plan(facts, devices, areas)
        require(bool(plan["items"]), "No verified monthly meter data")
        existing = list(
            (
                await session.scalars(
                    select(g.GhgActivityRecord).where(
                        g.GhgActivityRecord.inventory_code.in_({item["inventory_code"] for item in plan["items"]}),
                        g.GhgActivityRecord.period_end < end.date(),
                    )
                )
            ).all()
        )
        expected_codes = {item["record_code"] for item in plan["items"]}
        require(
            all(row.record_code in expected_codes for row in existing),
            "Previously prepared activity lost its source facts; review required",
        )
        fingerprint = digest({"tenant": TEAM_ID, "plan": plan})
        print(
            json.dumps(
                {"apply": apply, "fingerprint": fingerprint, "through_month": through_month, "plan": plan},
                ensure_ascii=False,
                default=str,
            ),
            flush=True,
        )
        if not apply:
            await session.rollback()
            return
        require(expected_fingerprint == fingerprint, "Reviewed fingerprint mismatch; nothing applied")
        result = await apply_plan(session, plan)
        await session.commit()
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--through-month", required=True)
    options = parser.parse_args()
    asyncio.run(
        main(
            apply=options.apply, expected_fingerprint=options.expected_fingerprint, through_month=options.through_month
        )
    )
