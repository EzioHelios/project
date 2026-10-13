from __future__ import annotations

from pydantic import BaseModel, Field


class BigscreenNavItem(BaseModel):
    label: str
    path: str


class BigscreenMetric(BaseModel):
    id: str
    label: str
    value: float | int | None
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
    carbon_co2e: float | None = None
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
    company_gallery: list[BigscreenMediaItem] = Field(default_factory=list)
    company_facts: list[BigscreenInfoItem] = Field(default_factory=list)
    profile: BigscreenPublicProfile | None = None


class BigscreenPublicProfile(BaseModel):
    title: str
    summary: str
    features: list[BigscreenInfoItem] = Field(default_factory=list)
    source_name: str
    source_url: str
    published_on: str


class BigscreenCarbonPayload(BaseModel):
    period_facts: list[BigscreenInfoItem] = Field(default_factory=list)
    scope_distribution: list[BigscreenDistributionItem] = Field(default_factory=list)
    area_ranking: list[BigscreenDistributionItem] = Field(default_factory=list)
    hero_metrics: list[BigscreenMetric] = Field(default_factory=list)
    flow: BigscreenFlowData = Field(default_factory=lambda: BigscreenFlowData(title="组织碳流", unit="kgCO2e"))
    source_ranking: list[BigscreenDistributionItem] = Field(default_factory=list)
    activity_distribution: list[BigscreenDistributionItem] = Field(default_factory=list)
    factors: list[BigscreenInfoItem] = Field(default_factory=list)
