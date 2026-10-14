"""Correct metadata on the two unpublished Xiangtai metered-scope reports only.

The enterprise fields are matched to the supplied legacy SQL, not invented.
No calculations, activity amounts, review states or published reports are changed.
"""

# ruff: noqa: T201 - business metadata and explicit maintenance output.
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

TEAM_ID = UUID("00000000-0000-7000-8000-000000000001")
ORGANIZATION_ID = 7
SQL_HASH = "d120cb53e46a78d5d52fa0ab1362861f5f77508dd9761710c493dcf7ae61b94f"
RANGES = {
    "XIANGTAI-METER-2025": (date(2025, 7, 1), date(2025, 12, 31)),
    "XIANGTAI-METER-2026": (date(2026, 1, 1), date(2026, 9, 30)),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


async def main(*, apply: bool, expected_fingerprint: str | None) -> None:
    async with provide_services(provide_users_service) as (users,):
        s = users.repository.session
        s.info.update({TENANT_ID_SESSION_KEY: TEAM_ID, TENANT_BYPASS_SESSION_KEY: False})
        enterprise = await s.get(m.EnterpriseInfo, 1)
        org = await s.scalar(select(m.ReportingOrganization).where(m.ReportingOrganization.code == "XIANGTAI-METERED"))
        require(
            enterprise is not None
            and enterprise.name == "祥泰仓库"
            and enterprise.unify_code == "91321200834792016A"
            and enterprise.belong_unit == "国网江苏省电力有限公司泰州供电分公司",
            "Legacy enterprise identity changed",
        )
        require(
            org is not None
            and org.id == ORGANIZATION_ID
            and org.enterprise_id in {None, enterprise.id}
            and org.name in {"祥泰仓库计量数据", "祥泰仓库"},
            "Reporting organization changed",
        )
        periods, reports = [], []
        for inventory, (start, end) in RANGES.items():
            period = await s.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
            report = await s.scalar(
                select(m.GhgInventoryReport).where(m.GhgInventoryReport.inventory_code == inventory)
            )
            require(
                period is not None and period.reporting_org_id == org.id and period.status == "draft",
                "Period is not editable",
            )
            require(
                report is not None
                and report.status == "draft"
                and report.version == 1
                and report.reporting_period_id == period.id
                and report.reporting_org_id == org.id,
                "Report is not an owned draft",
            )
            require(
                period.period_start in {date(start.year, 1, 1), start}
                and period.period_end in {date(end.year, 12, 31), end},
                "Period was manually changed",
            )
            activities = (
                await s.scalars(select(m.GhgActivityRecord).where(m.GhgActivityRecord.inventory_code == inventory))
            ).all()
            require(
                bool(activities)
                and min(v.period_start for v in activities) == start
                and max(v.period_end for v in activities) == end,
                "Actual data coverage changed",
            )
            periods.append(period)
            reports.append(report)
        plan = {
            "organization": {"id": org.id, "name": enterprise.name, "enterprise_id": enterprise.id},
            "enterprise": {
                "name": enterprise.name,
                "unify_code": enterprise.unify_code,
                "belong_unit": enterprise.belong_unit,
                "location": enterprise.location,
            },
            "periods": [
                {
                    "id": p.id,
                    "code": p.code,
                    "start": str(RANGES[p.code][0]),
                    "end": str(RANGES[p.code][1]),
                    "period_type": "custom",
                }
                for p in periods
            ],
            "reports": [
                {
                    "id": r.id,
                    "code": r.report_code,
                    "version": r.version,
                    "status": r.status,
                    "run_id": r.run_id,
                    "metrics": r.metrics_snapshot,
                }
                for r in reports
            ],
            "legacy_sql_sha256": SQL_HASH,
        }
        fingerprint = hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()
        print(
            json.dumps({"apply": apply, "fingerprint": fingerprint, "plan": plan}, ensure_ascii=False, default=str),
            flush=True,
        )
        if not apply:
            await s.rollback()
            return
        require(fingerprint == expected_fingerprint, "Plan changed; nothing applied")
        org.name, org.enterprise_id = enterprise.name, enterprise.id
        for period in periods:
            period.period_start, period.period_end = RANGES[period.code]
            period.period_type = "custom"
        await s.commit()
        print(
            json.dumps(
                {
                    "organization_id": org.id,
                    "period_ids": [p.id for p in periods],
                    "report_ids": [r.id for r in reports],
                    "all_reports_remain_draft": True,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-fingerprint")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, expected_fingerprint=args.expected_fingerprint))
