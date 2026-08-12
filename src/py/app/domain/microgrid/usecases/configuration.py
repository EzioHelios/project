"""Versioned scenario and flexibility configuration use cases."""

from __future__ import annotations

# ruff: noqa: EM101, PLR2004, TRY003
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.microgrid.domain.entities import FlexibilityWindow, Scenario
from app.domain.microgrid.domain.exceptions import ScenarioNotReadyError
from app.domain.microgrid.domain.value_objects import ScenarioStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CreateScenario:
    """Create the next editable version of a site scenario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        site_id: int,
        code: str,
        name: str,
        parameters: dict[str, Any],
        source_name: str,
        confidence_level: float,
    ) -> m.MicrogridScenario:
        site = await self._session.get(m.MicrogridSite, site_id)
        if site is None:
            raise ScenarioNotReadyError("microgrid site not found")
        latest = await self._session.scalar(
            select(func.max(m.MicrogridScenario.version)).where(
                m.MicrogridScenario.site_id == site.id, m.MicrogridScenario.code == code
            )
        )
        row = m.MicrogridScenario(
            team_id=site.team_id,
            site_id=site.id,
            code=code,
            name=name,
            version=int(latest or 0) + 1,
            status="draft",
            parameters=parameters,
            asset_snapshot=[],
            source_kind="enterprise_assumption",
            source_name=source_name,
            confidence_level=Decimal(str(confidence_level)),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row


class PublishScenario:
    """Validate and freeze a draft, archiving the previously published version."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, scenario_id: int) -> m.MicrogridScenario:
        row = await self._session.get(m.MicrogridScenario, scenario_id)
        if row is None:
            raise ScenarioNotReadyError("scenario not found")
        if row.status != ScenarioStatus.DRAFT.value:
            raise ScenarioNotReadyError("only a draft scenario can be published")
        aggregate = Scenario(code=row.code, version=row.version, parameters=row.parameters)
        aggregate.publish()
        previous = (
            (
                await self._session.execute(
                    select(m.MicrogridScenario).where(
                        m.MicrogridScenario.site_id == row.site_id,
                        m.MicrogridScenario.status == ScenarioStatus.PUBLISHED.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        for item in previous:
            item.status = ScenarioStatus.ARCHIVED.value
        assets = (
            (
                await self._session.execute(
                    select(m.MicrogridAsset).where(
                        m.MicrogridAsset.site_id == row.site_id, m.MicrogridAsset.enabled.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        row.asset_snapshot = [
            {
                "code": asset.code,
                "type": asset.asset_type,
                "ratedPowerKw": float(asset.rated_power_kw or 0),
                "ratedEnergyKwh": float(asset.rated_energy_kwh or 0),
                "parameters": asset.parameters,
            }
            for asset in assets
        ]
        row.status = aggregate.status.value
        row.published_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(row)
        return row


class UpsertFlexibilityContract:
    """Maintain a validated flexible-resource contract on a draft scenario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, *, contract_id: int | None = None, **data: Any) -> m.FlexibilityContract:
        scenario = await self._session.get(m.MicrogridScenario, int(data["scenario_id"]))
        if scenario is None or scenario.status != "draft":
            raise ScenarioNotReadyError("flexibility contracts can only be changed on a draft scenario")
        FlexibilityWindow(
            start=_minute_to_time(int(data["start_minute"])),
            end=_minute_to_time(int(data["end_minute"])),
            minimum_power_kw=float(data["minimum_power_kw"]),
            maximum_power_kw=float(data["maximum_power_kw"]),
            target_energy_kwh=(float(data["target_energy_kwh"]) if data.get("target_energy_kwh") is not None else None),
            priority=int(data["priority"]),
        )
        row = await self._session.get(m.FlexibilityContract, contract_id) if contract_id else None
        if row is None:
            row = m.FlexibilityContract(
                team_id=scenario.team_id, scenario_id=scenario.id, asset_id=int(data["asset_id"])
            )
            self._session.add(row)
        for field in (
            "contract_type",
            "start_minute",
            "end_minute",
            "priority",
            "enabled",
        ):
            setattr(row, field, data[field])
        for field in ("minimum_power_kw", "maximum_power_kw", "target_energy_kwh", "penalty_cny_per_kwh"):
            value = data.get(field)
            setattr(row, field, Decimal(str(value)) if value is not None else None)
        await self._session.commit()
        await self._session.refresh(row)
        return row


def _minute_to_time(minute: int) -> time:
    if not 0 <= minute <= 1440:
        msg = "minute must be between 0 and 1440"
        raise ValueError(msg)
    minute = min(minute, 1439)
    return time(hour=minute // 60, minute=minute % 60)
