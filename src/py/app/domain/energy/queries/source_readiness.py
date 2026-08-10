from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergySourceReadinessQueryService:
    """Read model for tenant-scoped source-data readiness."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self) -> dict[str, Any]:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return _empty_summary()
        row = (
            (
                await self._session.execute(
                    text(
                        """
                    select
                        (
                            select count(*)::int
                            from dataapp_energyintervalfact
                            where team_id = :team_id and is_current = true
                        ) as energy_interval_count,
                        (
                            select count(*)::int
                            from dataapp_scope1stationarycombustion
                            where team_id = :team_id and status = 'approved' and record_usage <> 'reference'
                        ) as scope1_stationary_count,
                        (
                            select count(*)::int
                            from dataapp_scope2electricitybill
                            where team_id = :team_id and status = 'approved' and record_usage <> 'reference'
                        ) as scope2_electricity_count,
                        (
                            select count(*)::int
                            from dataapp_productionoutputfact
                            where team_id = :team_id and record_status = 'confirmed'
                        ) as production_output_count
                    """
                    ),
                    {"team_id": str(team_id)},
                )
            )
            .mappings()
            .one()
        )
        counts = jsonable_mapping(dict(row))
        energy_interval_count = int(counts["energy_interval_count"] or 0)
        scope1_stationary_count = int(counts["scope1_stationary_count"] or 0)
        scope2_electricity_count = int(counts["scope2_electricity_count"] or 0)
        production_output_count = int(counts["production_output_count"] or 0)
        scope_count = scope1_stationary_count + scope2_electricity_count

        analysis_status = "ready" if energy_interval_count > 0 else "source_missing"
        production_status = "ready" if production_output_count > 0 else "source_missing"
        accounting_energy_status = "ready" if scope_count > 0 else "source_missing"
        operations_status = "ready" if energy_interval_count > 0 else "partial" if scope_count > 0 else "source_missing"
        planning_status = (
            "ready"
            if energy_interval_count > 0 and production_output_count > 0
            else "partial"
            if energy_interval_count > 0 or production_output_count > 0 or scope_count > 0
            else "source_missing"
        )

        return {
            "counts": counts,
            "statuses": {
                "energy_consumption": operations_status,
                "energy_intensity": planning_status,
                "energy_operations": operations_status,
                "energy_analysis": analysis_status,
                "energy_flow": analysis_status,
                "production_denominator": production_status,
                "budget_planning": planning_status,
                "benchmarking": planning_status,
                "carbon_accounting_energy": accounting_energy_status,
            },
            "items": [
                {
                    "key": "energy_interval_facts",
                    "label": "能源计量事实",
                    "count": energy_interval_count,
                    "status": analysis_status,
                },
                {
                    "key": "scope1_stationary_combustion",
                    "label": "Scope1 固定燃烧",
                    "count": scope1_stationary_count,
                    "status": "ready" if scope1_stationary_count else "source_missing",
                },
                {
                    "key": "scope2_electricity_bills",
                    "label": "Scope2 电力账单",
                    "count": scope2_electricity_count,
                    "status": "ready" if scope2_electricity_count else "source_missing",
                },
                {
                    "key": "production_output_facts",
                    "label": "产量分母事实",
                    "count": production_output_count,
                    "status": production_status,
                },
            ],
        }


def _empty_summary() -> dict[str, Any]:
    return {
        "counts": {
            "energy_interval_count": 0,
            "scope1_stationary_count": 0,
            "scope2_electricity_count": 0,
            "production_output_count": 0,
        },
        "statuses": {
            "energy_consumption": "source_missing",
            "energy_intensity": "source_missing",
            "energy_operations": "source_missing",
            "energy_analysis": "source_missing",
            "energy_flow": "source_missing",
            "production_denominator": "source_missing",
            "budget_planning": "source_missing",
            "benchmarking": "source_missing",
            "carbon_accounting_energy": "source_missing",
        },
        "items": [
            {"key": "energy_interval_facts", "label": "能源计量事实", "count": 0, "status": "source_missing"},
            {"key": "scope1_stationary_combustion", "label": "Scope1 固定燃烧", "count": 0, "status": "source_missing"},
            {"key": "scope2_electricity_bills", "label": "Scope2 电力账单", "count": 0, "status": "source_missing"},
            {"key": "production_output_facts", "label": "产量分母事实", "count": 0, "status": "source_missing"},
        ],
    }
