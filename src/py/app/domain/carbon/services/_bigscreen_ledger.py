"""Read-only presentation of dated warehouse ledger amounts, without estimating missing values."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


def parse_ledger_date(value: str | None) -> date | None:
    """Accept the two numeric year-first formats observed in the imported ledgers."""
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()  # noqa: DTZ007 - date-only source.
        except ValueError:
            continue
    return None


async def ledger_overview(session: AsyncSession) -> dict[str, Any]:
    months: dict[str, dict[str, Any]] = {}
    coverage = []
    for key, model, date_field, amount in (
        ("inbound", m.InMoney, m.InMoney.rkrq, m.InMoney.shje),
        ("outbound", m.OutMoney, m.OutMoney.gzrq, m.OutMoney.je),
    ):
        rows = (
            await session.execute(
                select(
                    date_field,
                    func.count(),
                    func.count(amount),
                    func.sum(amount),
                )
                .select_from(model)
                .group_by(date_field)
            )
        ).all()
        counts: dict[str, Any] = {
            "kind": key,
            "records": 0,
            "dated_records": 0,
            "undated_records": 0,
            "missing_amount": 0,
        }
        for raw_date, count, valid_amount, total in rows:
            counts["records"] += count
            counts["missing_amount"] += count - valid_amount
            day = parse_ledger_date(raw_date)
            if day is None:
                counts["undated_records"] += count
                continue
            counts["dated_records"] += count
            period = day.strftime("%Y-%m")
            month = months.setdefault(period, {"period": period, "inbound": None, "outbound": None})
            if valid_amount:
                month[key] = (month[key] or 0) + float(total) / 10000
        coverage.append(counts)
    if months:
        cursor = parse_ledger_date(f"{min(months)}-01")
        last = parse_ledger_date(f"{max(months)}-01")
        while cursor and last and cursor <= last:
            period = cursor.strftime("%Y-%m")
            months.setdefault(period, {"period": period, "inbound": None, "outbound": None})
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"trend": [months[key] for key in sorted(months)], "coverage": coverage}
