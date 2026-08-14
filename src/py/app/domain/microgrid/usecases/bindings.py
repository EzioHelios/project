"""Application workflows for explicit microgrid meter bindings."""

from __future__ import annotations

# ruff: noqa: EM101, EM102, PERF401, TRY003
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from app.db import models as m
from app.domain.microgrid.domain.exceptions import ScenarioNotReadyError
from app.domain.microgrid.infrastructure.metering import MicrogridMeterProjection
from app.lib.tenancy import DEFAULT_TENANT_ID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

XIANGTAI_BINDING_TEMPLATE: dict[str, tuple[str, ...]] = {
    "pv": ("001559274638", "001559274637", "001553926808"),
    "charger": ("001559275531", "001559275528", "432301227007"),
    "storage": ("432301227008",),
    "lighting": ("432206212781", "432301226885"),
}
XIANGTAI_ASSET_BY_ROLE = {
    "pv": "PV-01",
    "charger": "EVSE-GROUP",
    "storage": "BESS-01",
    "lighting": "LIGHTING",
    "fixed_load": "WAREHOUSE",
}


class BindingTemplate:
    """Build a preview-only Xiangtai mapping from exact equipment codes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, site_id: int) -> dict[str, Any]:
        site = await self._session.get(m.MicrogridSite, site_id)
        if site is None:
            raise ScenarioNotReadyError("microgrid site not found")
        if site.code != "xiangtai-taizhou" or site.team_id != DEFAULT_TENANT_ID:
            raise ScenarioNotReadyError("the Xiangtai binding template only applies to the Xiangtai site")
        assets = {
            row.code: row
            for row in (
                await self._session.scalars(select(m.MicrogridAsset).where(m.MicrogridAsset.site_id == site.id))
            ).all()
        }
        equipment = (
            await self._session.scalars(
                select(m.MonitorEquipment)
                .where(m.MonitorEquipment.team_id == site.team_id)
                .order_by(m.MonitorEquipment.id)
            )
        ).all()
        by_code = {row.code: row for row in equipment}
        explicit_codes = {code for codes in XIANGTAI_BINDING_TEMPLATE.values() for code in codes}
        items: list[dict[str, Any]] = []
        for role, codes in XIANGTAI_BINDING_TEMPLATE.items():
            asset = assets.get(XIANGTAI_ASSET_BY_ROLE[role])
            if asset is None:
                continue
            for code in codes:
                row = by_code.get(code)
                if row is not None:
                    items.append(_template_item(asset=asset, equipment=row, role=role))
        load_asset = assets.get(XIANGTAI_ASSET_BY_ROLE["fixed_load"])
        if load_asset is not None:
            for row in equipment:
                if row.code not in explicit_codes:
                    items.append(_template_item(asset=load_asset, equipment=row, role="fixed_load"))
        root = await self._session.scalar(
            select(m.MonitorSector).where(
                m.MonitorSector.team_id == site.team_id,
                m.MonitorSector.code == "ROOT",
            )
        )
        return {
            "siteId": site.id,
            "monitorSectorId": root.id if root else None,
            "monitorSectorName": root.name if root else None,
            "templateCode": "xiangtai-manual-v1",
            "items": items,
            "unavailableCodes": sorted(explicit_codes.difference(by_code)),
            "derivedPcc": True,
        }


class ReplaceMeterBindings:
    """Replace the explicitly confirmed binding set and rebuild measured history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        site_id: int,
        bindings: list[dict[str, Any]],
        monitor_sector_id: int | None = None,
        source_name: str = "管理员手工绑定",
    ) -> list[m.MicrogridAssetMeterBinding]:
        site = await self._session.get(m.MicrogridSite, site_id)
        if site is None:
            raise ScenarioNotReadyError("microgrid site not found")
        if monitor_sector_id is not None:
            sector = await self._session.get(m.MonitorSector, monitor_sector_id)
            if sector is None or sector.team_id != site.team_id:
                raise ScenarioNotReadyError("monitor sector must belong to the site tenant")
            site.monitor_sector_id = sector.id
        assets = {
            row.id: row
            for row in (
                await self._session.scalars(select(m.MicrogridAsset).where(m.MicrogridAsset.site_id == site.id))
            ).all()
        }
        equipment_ids = {int(item["equipment_id"]) for item in bindings}
        equipment = {
            row.id: row
            for row in (
                await self._session.scalars(select(m.MonitorEquipment).where(m.MonitorEquipment.id.in_(equipment_ids)))
            ).all()
        }
        allowed_roles = {"fixed_load", "pv", "storage", "charger", "lighting", "pcc"}
        rows: list[m.MicrogridAssetMeterBinding] = []
        seen: set[tuple[int, str, str]] = set()
        for item in bindings:
            asset = assets.get(int(item["asset_id"]))
            meter = equipment.get(int(item["equipment_id"]))
            role = str(item["role"])
            if asset is None or meter is None or meter.team_id != site.team_id:
                raise ScenarioNotReadyError("asset and equipment must belong to the site tenant")
            if role not in allowed_roles:
                raise ScenarioNotReadyError(f"unsupported meter binding role: {role}")
            direction = str(item.get("direction", "import"))
            if direction not in {"import", "export"}:
                raise ScenarioNotReadyError("binding direction must be import or export")
            point_code = str(item.get("point_code", "forward_active_total")).strip()
            sign = Decimal(str(item.get("sign", 1)))
            if not point_code:
                raise ScenarioNotReadyError("binding point code is required")
            if sign == 0:
                raise ScenarioNotReadyError("binding sign cannot be zero")
            key = (
                meter.id,
                point_code,
                direction,
            )
            if key in seen:
                raise ScenarioNotReadyError("duplicate meter binding")
            seen.add(key)
            rows.append(
                m.MicrogridAssetMeterBinding(
                    team_id=site.team_id,
                    site_id=site.id,
                    asset_id=asset.id,
                    equipment_id=meter.id,
                    role=role,
                    point_code=key[1],
                    direction=key[2],
                    sign=sign,
                    valid_from=datetime.now(UTC),
                    source_kind="manual_configuration",
                    source_name=source_name,
                    enabled=bool(item.get("enabled", True)),
                )
            )
        await self._session.execute(
            delete(m.MicrogridAssetMeterBinding).where(m.MicrogridAssetMeterBinding.site_id == site.id)
        )
        self._session.add_all(rows)
        await self._session.commit()
        await MicrogridMeterProjection(self._session).project(site_id=site.id)
        return rows


class ApplyXiangtaiBindingTemplate:
    """Apply the previewed mapping only after explicit confirmation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, site_id: int, *, confirm: bool) -> list[m.MicrogridAssetMeterBinding]:
        if not confirm:
            raise ScenarioNotReadyError("binding template confirmation is required")
        preview = await BindingTemplate(self._session).execute(site_id)
        return await ReplaceMeterBindings(self._session).execute(
            site_id=site_id,
            monitor_sector_id=preview["monitorSectorId"],
            bindings=[
                {
                    "asset_id": item["assetId"],
                    "equipment_id": item["equipmentId"],
                    "role": item["role"],
                    "point_code": item["pointCode"],
                    "direction": item["direction"],
                    "sign": item["sign"],
                    "enabled": True,
                }
                for item in preview["items"]
            ],
            source_name="祥泰人工确认映射模板V1",
        )


def _template_item(*, asset: m.MicrogridAsset, equipment: m.MonitorEquipment, role: str) -> dict[str, Any]:
    return {
        "assetId": asset.id,
        "assetCode": asset.code,
        "assetName": asset.name,
        "equipmentId": equipment.id,
        "equipmentCode": equipment.code,
        "equipmentName": equipment.name,
        "role": role,
        "pointCode": "forward_active_total",
        "direction": "import",
        "sign": 1,
    }


__all__ = ("ApplyXiangtaiBindingTemplate", "BindingTemplate", "ReplaceMeterBindings")
