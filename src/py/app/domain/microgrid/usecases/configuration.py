"""Versioned scenario and flexibility configuration use cases."""

from __future__ import annotations

# ruff: noqa: EM101, EM102, PLR2004, TRY003
from copy import deepcopy
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

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


class CreateWorkingCopy:
    """Return the site's existing draft or clone a scenario and all flexibility contracts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, source_scenario_id: int, *, change_summary: str | None = None) -> m.MicrogridScenario:
        source = await self._session.get(m.MicrogridScenario, source_scenario_id)
        if source is None:
            raise ScenarioNotReadyError("scenario not found")
        existing = await self._session.scalar(
            select(m.MicrogridScenario)
            .where(
                m.MicrogridScenario.site_id == source.site_id,
                m.MicrogridScenario.code == source.code,
                m.MicrogridScenario.status == "draft",
            )
            .order_by(m.MicrogridScenario.version.desc())
        )
        if existing is not None:
            return existing
        latest = await self._session.scalar(
            select(func.max(m.MicrogridScenario.version)).where(
                m.MicrogridScenario.site_id == source.site_id,
                m.MicrogridScenario.code == source.code,
            )
        )
        row = m.MicrogridScenario(
            team_id=source.team_id,
            site_id=source.site_id,
            code=source.code,
            name=source.name,
            version=int(latest or 0) + 1,
            status="draft",
            parameters=deepcopy(source.parameters),
            asset_snapshot=deepcopy(source.asset_snapshot),
            source_kind=source.source_kind,
            source_name=source.source_name,
            confidence_level=source.confidence_level,
            valid_from=datetime.now(UTC),
            tariff_plan_id=source.tariff_plan_id,
            grid_emission_factor_id=source.grid_emission_factor_id,
            based_on_scenario_id=source.id,
            change_summary=change_summary or "基于当前场景自动创建工作草稿",
        )
        self._session.add(row)
        await self._session.flush()
        contracts = (
            await self._session.scalars(
                select(m.FlexibilityContract).where(m.FlexibilityContract.scenario_id == source.id)
            )
        ).all()
        self._session.add_all(
            [
                m.FlexibilityContract(
                    team_id=source.team_id,
                    scenario_id=row.id,
                    asset_id=contract.asset_id,
                    contract_type=contract.contract_type,
                    start_minute=contract.start_minute,
                    end_minute=contract.end_minute,
                    minimum_power_kw=contract.minimum_power_kw,
                    maximum_power_kw=contract.maximum_power_kw,
                    target_energy_kwh=contract.target_energy_kwh,
                    priority=contract.priority,
                    penalty_cny_per_kwh=contract.penalty_cny_per_kwh,
                    recovery_constraints=deepcopy(contract.recovery_constraints),
                    enabled=contract.enabled,
                )
                for contract in contracts
            ]
        )
        await self._session.commit()
        await self._session.refresh(row)
        return row


class UpdateWorkingScenario:
    """Update a draft or transparently create one from a published scenario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        scenario_id: int,
        *,
        parameters: dict[str, Any],
        name: str | None = None,
        tariff_plan_id: int | None = None,
        grid_emission_factor_id: int | None = None,
        change_summary: str | None = None,
    ) -> m.MicrogridScenario:
        scenario = await self._session.get(m.MicrogridScenario, scenario_id)
        if scenario is None:
            raise ScenarioNotReadyError("scenario not found")
        if scenario.status != "draft":
            scenario = await CreateWorkingCopy(self._session).execute(scenario.id, change_summary=change_summary)
        validate_strategy_parameters(parameters)
        scenario.parameters = deepcopy(parameters)
        if name is not None:
            scenario.name = name
        if tariff_plan_id is not None:
            tariff = await self._session.get(m.EnergyTariffPlan, tariff_plan_id)
            if tariff is None or not tariff.is_enabled:
                raise ScenarioNotReadyError("selected tariff plan is unavailable")
            scenario.tariff_plan_id = tariff.id
        if grid_emission_factor_id is not None:
            factor = await self._session.get(m.EmissionFactor, grid_emission_factor_id)
            if factor is None or not factor.is_active:
                raise ScenarioNotReadyError("selected grid emission factor is unavailable")
            scenario.grid_emission_factor_id = factor.id
        scenario.change_summary = change_summary
        await self._session.commit()
        await self._session.refresh(scenario)
        return scenario


class RestoreScenario:
    """Restore a historical version into a new editable version."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, scenario_id: int) -> m.MicrogridScenario:
        source = await self._session.get(m.MicrogridScenario, scenario_id)
        if source is None:
            raise ScenarioNotReadyError("scenario not found")
        draft = await self._session.scalar(
            select(m.MicrogridScenario).where(
                m.MicrogridScenario.site_id == source.site_id,
                m.MicrogridScenario.code == source.code,
                m.MicrogridScenario.status == "draft",
            )
        )
        if draft is not None:
            await self._session.execute(
                delete(m.FlexibilityContract).where(m.FlexibilityContract.scenario_id == draft.id)
            )
            await self._session.delete(draft)
            await self._session.commit()
        return await CreateWorkingCopy(self._session).execute(source.id, change_summary=f"从 v{source.version} 恢复")


class DiscardScenarioDraft:
    """Delete a draft and its dependent flexibility contracts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, scenario_id: int) -> None:
        row = await self._session.get(m.MicrogridScenario, scenario_id)
        if row is None or row.status != "draft":
            raise ScenarioNotReadyError("only a draft scenario can be discarded")
        await self._session.delete(row)
        await self._session.commit()


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
        asset = await self._session.get(m.MicrogridAsset, int(data["asset_id"]))
        if asset is None or asset.site_id != scenario.site_id:
            raise ScenarioNotReadyError("flexibility asset must belong to the scenario site")
        hard_constraint = bool(data.get("hard_constraint", True))
        penalty = float(data.get("penalty_cny_per_kwh") or 0)
        if asset.asset_type == "lighting" and not hard_constraint:
            raise ScenarioNotReadyError("lighting safety minimum must remain a hard constraint")
        if not hard_constraint and penalty <= 0:
            raise ScenarioNotReadyError("soft flexibility contracts require a positive penalty")
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
        row.recovery_constraints = {
            **row.recovery_constraints,
            "hard_constraint": hard_constraint,
        }
        await self._session.commit()
        await self._session.refresh(row)
        return row


def _minute_to_time(minute: int) -> time:
    if not 0 <= minute <= 1440:
        msg = "minute must be between 0 and 1440"
        raise ValueError(msg)
    minute = min(minute, 1439)
    return time(hour=minute // 60, minute=minute % 60)


def validate_strategy_parameters(parameters: dict[str, Any]) -> None:
    """Validate P0 strategy controls before they become an auditable draft."""
    required = {"grid", "pv", "storage", "tariff"}
    missing = required.difference(parameters)
    if missing:
        raise ScenarioNotReadyError(f"missing scenario sections: {', '.join(sorted(missing))}")
    weights = parameters.get("objective_weights", {})
    values = [float(weights.get(key, default)) for key, default in (("energy", 1), ("peak", 1), ("carbon", 1))]
    if any(value < 0 or value > 10 for value in values) or not any(value > 0 for value in values):
        raise ScenarioNotReadyError("objective weights must be within 0-10 and at least one must be positive")
    storage = parameters["storage"]
    minimum = float(storage.get("minimum_soc_pct", 15))
    maximum = float(storage.get("maximum_soc_pct", 90))
    terminal = float(storage.get("terminal_soc_pct", storage.get("initial_soc_pct", 50)))
    if not 0 <= minimum < maximum <= 100 or not minimum <= terminal <= maximum:
        raise ScenarioNotReadyError("storage SOC bounds or terminal target are invalid")
    reserve_margin = float(parameters.get("reserve_margin_pct", 8))
    if not 0 <= reserve_margin <= 100:
        raise ScenarioNotReadyError("reserve margin must be within 0-100 percent")
    economics = parameters.get("economics", {})
    if float(economics.get("battery_degradation_cny_per_kwh", 0.08)) < 0:
        raise ScenarioNotReadyError("battery degradation cost cannot be negative")
    if float(economics.get("carbon_cny_per_kg", 0.08)) < 0:
        raise ScenarioNotReadyError("carbon price cannot be negative")
