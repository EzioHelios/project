export type BigscreenApiEnvelope<T> = {
  code: number
  msg?: string
  data: T
}

export type BigscreenNavItem = {
  label: string
  path: string
}

export type BigscreenMetric = {
  id: string
  label: string
  value: number
  unit?: string | null
  ratio?: number | null
  emphasis?: string | null
}

export type BigscreenMediaItem = {
  id: string
  title: string
  description?: string | null
  image_url?: string | null
}

export type BigscreenInfoItem = {
  label: string
  value: string
}

export type BigscreenAlertItem = {
  id: string
  title: string
  detail?: string | null
  occurred_at?: string | null
  severity: "info" | "warning" | "critical" | string
}

export type BigscreenTrendPoint = {
  period: string
  energy_kwh: number
  carbon_co2e: number
  value: number
}

export type BigscreenFlowNode = {
  id: string
  name: string
  value?: number | null
  category?: string | null
}

export type BigscreenFlowLink = {
  source: string
  target: string
  value: number
}

export type BigscreenFlowData = {
  title: string
  unit?: string | null
  nodes: BigscreenFlowNode[]
  links: BigscreenFlowLink[]
}

export type BigscreenDistributionItem = {
  name: string
  value: number
}

export type BigscreenComparisonItem = {
  name: string
  current: number
  baseline?: number | null
  unit?: string | null
}

export type BigscreenMetaResponse = {
  title: string
  short_name: string
  description: string
  default_path: string
  show_weather: boolean
  promo_video_url?: string | null
  nav_items: BigscreenNavItem[]
}

export type BigscreenIntroResponse = {
  hero_title: string
  hero_description: string
  company_gallery: BigscreenMediaItem[]
  project_spotlights: BigscreenMediaItem[]
  success_cases: BigscreenMediaItem[]
  promo_video_url?: string | null
  company_facts: BigscreenInfoItem[]
}

export type BigscreenOverviewResponse = {
  energy_kpis: BigscreenMetric[]
  carbon_kpis: BigscreenMetric[]
  energy_flow: BigscreenFlowData
  production_trend: BigscreenTrendPoint[]
  filters: Record<string, Array<{ label: string; value: string }>>
}

export type BigscreenPowerResponse = {
  alerts: BigscreenAlertItem[]
  energy_structure: BigscreenDistributionItem[]
  energy_ranking: BigscreenDistributionItem[]
  energy_flow: BigscreenFlowData
  energy_timeseries: BigscreenTrendPoint[]
  hero_metrics: BigscreenMetric[]
}

export type BigscreenCarbonResponse = {
  carbon_compare: BigscreenComparisonItem[]
  production_share: BigscreenDistributionItem[]
  carbon_flow: BigscreenFlowData
  carbon_alerts: BigscreenAlertItem[]
  carbon_price_trend: BigscreenTrendPoint[]
  commentary: string[]
  hero_metrics: BigscreenMetric[]
}
