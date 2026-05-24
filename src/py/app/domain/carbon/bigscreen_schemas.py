from __future__ import annotations

from pydantic import BaseModel, Field


class BigscreenNavItem(BaseModel):
    label: str
    path: str


class BigscreenMetric(BaseModel):
    id: str
    label: str
    value: float | int
    unit: str | None = None
    ratio: float | None = None
    emphasis: str | None = None


class BigscreenMediaItem(BaseModel):
    id: str
    title: str
    description: str | None = None
    image_url: str | None = None


class BigscreenInfoItem(BaseModel):
    label: str
    value: str


class BigscreenAlertItem(BaseModel):
    id: str
    title: str
    detail: str | None = None
    occurred_at: str | None = None
    severity: str = "info"


class BigscreenTrendPoint(BaseModel):
    period: str
    energy_kwh: float = 0
    carbon_co2e: float = 0
    value: float = 0


class BigscreenFlowNode(BaseModel):
    id: str
    name: str
    value: float | None = None
    category: str | None = None


class BigscreenFlowLink(BaseModel):
    source: str
    target: str
    value: float


class BigscreenFlowData(BaseModel):
    title: str
    unit: str | None = None
    nodes: list[BigscreenFlowNode] = Field(default_factory=list)
    links: list[BigscreenFlowLink] = Field(default_factory=list)


class BigscreenDistributionItem(BaseModel):
    name: str
    value: float


class BigscreenComparisonItem(BaseModel):
    name: str
    current: float
    baseline: float | None = None
    unit: str | None = None


class BigscreenMetaPayload(BaseModel):
    title: str
    short_name: str
    description: str
    default_path: str
    city: str | None = None
    show_weather: bool = False
    promo_video_url: str | None = None
    nav_items: list[BigscreenNavItem] = Field(default_factory=list)


class BigscreenIntroPayload(BaseModel):
    hero_title: str
    hero_description: str
    company_gallery: list[BigscreenMediaItem] = Field(default_factory=list)
    project_spotlights: list[BigscreenMediaItem] = Field(default_factory=list)
    success_cases: list[BigscreenMediaItem] = Field(default_factory=list)
    promo_video_url: str | None = None
    company_facts: list[BigscreenInfoItem] = Field(default_factory=list)


class BigscreenOverviewPayload(BaseModel):
    energy_kpis: list[BigscreenMetric] = Field(default_factory=list)
    carbon_kpis: list[BigscreenMetric] = Field(default_factory=list)
    energy_flow: BigscreenFlowData
    production_trend: list[BigscreenTrendPoint] = Field(default_factory=list)
    filters: dict[str, list[dict[str, str]]] = Field(default_factory=dict)


class BigscreenPowerPayload(BaseModel):
    alerts: list[BigscreenAlertItem] = Field(default_factory=list)
    energy_structure: list[BigscreenDistributionItem] = Field(default_factory=list)
    energy_ranking: list[BigscreenDistributionItem] = Field(default_factory=list)
    energy_flow: BigscreenFlowData
    energy_timeseries: list[BigscreenTrendPoint] = Field(default_factory=list)
    hero_metrics: list[BigscreenMetric] = Field(default_factory=list)


class BigscreenCarbonPayload(BaseModel):
    carbon_compare: list[BigscreenComparisonItem] = Field(default_factory=list)
    production_share: list[BigscreenDistributionItem] = Field(default_factory=list)
    carbon_flow: BigscreenFlowData
    carbon_alerts: list[BigscreenAlertItem] = Field(default_factory=list)
    carbon_price_trend: list[BigscreenTrendPoint] = Field(default_factory=list)
    commentary: list[str] = Field(default_factory=list)
    hero_metrics: list[BigscreenMetric] = Field(default_factory=list)
