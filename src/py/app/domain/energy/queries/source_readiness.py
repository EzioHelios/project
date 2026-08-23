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
                            from ghg_activity_record
                            where team_id = :team_id and status = 'approved' and ghg_scope = 'scope1'
                        ) as scope1_activity_count,
                        (
                            select count(*)::int
                            from ghg_activity_record
                            where team_id = :team_id and status = 'approved' and ghg_scope = 'scope2'
                        ) as scope2_activity_count,
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
        scope1_activity_count = int(counts["scope1_activity_count"] or 0)
        scope2_activity_count = int(counts["scope2_activity_count"] or 0)
        production_output_count = int(counts["production_output_count"] or 0)
        inventory_activity_count = scope1_activity_count + scope2_activity_count

        analysis_status = "ready" if energy_interval_count > 0 else "source_missing"
        production_status = "ready" if production_output_count > 0 else "source_missing"
        inventory_energy_status = "ready" if inventory_activity_count > 0 else "source_missing"
        operations_status = (
            "ready" if energy_interval_count > 0 else "partial" if inventory_activity_count > 0 else "source_missing"
        )
        planning_status = (
            "ready"
            if energy_interval_count > 0 and production_output_count > 0
            else "partial"
            if energy_interval_count > 0 or production_output_count > 0 or inventory_activity_count > 0
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
                "ghg_inventory_energy": inventory_energy_status,
            },
            "items": [
                {
                    "key": "energy_interval_facts",
                    "label": "能源计量事实",
                    "count": energy_interval_count,
                    "status": analysis_status,
                },
                {
                    "key": "scope1_activities",
                    "label": "Scope 1 活动数据",
                    "count": scope1_activity_count,
                    "status": "ready" if scope1_activity_count else "source_missing",
                },
                {
                    "key": "scope2_activities",
                    "label": "Scope 2 活动数据",
                    "count": scope2_activity_count,
                    "status": "ready" if scope2_activity_count else "source_missing",
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
            "scope1_activity_count": 0,
            "scope2_activity_count": 0,
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
            "ghg_inventory_energy": "source_missing",
        },
        "items": [
            {"key": "energy_interval_facts", "label": "能源计量事实", "count": 0, "status": "source_missing"},
            {"key": "scope1_activities", "label": "Scope 1 活动数据", "count": 0, "status": "source_missing"},
            {"key": "scope2_activities", "label": "Scope 2 活动数据", "count": 0, "status": "source_missing"},
            {"key": "production_output_facts", "label": "产量分母事实", "count": 0, "status": "source_missing"},
        ],
    }
