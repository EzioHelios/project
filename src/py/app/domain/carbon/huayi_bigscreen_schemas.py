from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.carbon.bigscreen_schemas import (
    BigscreenAlertItem,
    BigscreenDistributionItem,
    BigscreenMetaPayload,
    BigscreenTrendPoint,
)


class HuayiBigscreenKeyValue(BaseModel):
    label: str
    value: float | int | str
    unit: str | None = None
    tone: str = "cyan"
    detail: str | None = None


class HuayiBigscreenMetricGroup(BaseModel):
    id: str
    title: str
    metrics: list[HuayiBigscreenKeyValue] = Field(default_factory=list)


class HuayiBigscreenListSection(BaseModel):
    id: str
    title: str
    items: list[HuayiBigscreenKeyValue] = Field(default_factory=list)


class HuayiBigscreenOverviewPayload(BaseModel):
    park_name: str
    photovoltaic_metrics: list[HuayiBigscreenKeyValue] = Field(default_factory=list)
    charger_metrics: list[HuayiBigscreenKeyValue] = Field(default_factory=list)
    load_groups: list[HuayiBigscreenMetricGroup] = Field(default_factory=list)
    carbon_stats: list[HuayiBigscreenKeyValue] = Field(default_factory=list)
    resource_cards: list[HuayiBigscreenMetricGroup] = Field(default_factory=list)
    device_status: list[HuayiBigscreenKeyValue] = Field(default_factory=list)
    benefit_items: list[HuayiBigscreenKeyValue] = Field(default_factory=list)
    lifestyle_sections: list[HuayiBigscreenListSection] = Field(default_factory=list)
    alerts: list[BigscreenAlertItem] = Field(default_factory=list)
    carbon_trend: list[BigscreenTrendPoint] = Field(default_factory=list)
    area_distribution: list[BigscreenDistributionItem] = Field(default_factory=list)
    storage_status: HuayiBigscreenKeyValue | None = None


__all__ = [
    "BigscreenMetaPayload",
    "HuayiBigscreenKeyValue",
    "HuayiBigscreenListSection",
    "HuayiBigscreenMetricGroup",
    "HuayiBigscreenOverviewPayload",
]
