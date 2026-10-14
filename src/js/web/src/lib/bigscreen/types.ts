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
  value: number | null
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
  energy_kwh: number | null
  carbon_co2e: number | null
  value: number | null
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
  id?: string | null
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
  city?: string | null
  show_weather: boolean
  promo_video_url?: string | null
  nav_items: BigscreenNavItem[]
}

export type BigscreenIntroResponse = {
  hero_title: string
  company_gallery: BigscreenMediaItem[]
  company_facts: BigscreenInfoItem[]
  profile: BigscreenPublicProfile | null
}

export type BigscreenPublicProfile = {
  title: string
  summary: string
  features: BigscreenInfoItem[]
  source_name: string
  source_url: string
  published_on: string
}

export type BigscreenOperationsResponse = {
  period_start: string
  period_end: string
  grain: string
  available_start: string | null
  available_end: string | null
  observed_at: string | null
  areas: Array<{ value: string; label: string }>
  energy_kpis: BigscreenMetric[]
  energy_flow: BigscreenFlowData
  profile: BigscreenPublicProfile | null
  presentation: { overview_focus?: "business" | "sampling"; monitor_focus?: "safety" | "sampling"; carbon_focus?: "commute" | "inventory" }
  energy_calendar: Array<{ id: string; label: string; value: number | null; unit: string; start: string; end: string; recorded_days: number; calendar_days: number }>
  ledger: {
    trend: Array<{ period: string; inbound: number | null; outbound: number | null }>
    coverage: Array<{ kind: string; records: number; dated_records: number; undated_records: number; missing_amount: number }>
  }
  commute_power: BigscreenDistributionItem[]
  trend: Array<{ period: string; value: number | null }>
  area_ranking: Array<{ id: string | null; name: string; value: number }>
  equipment_ranking: Array<{ id: string; name: string; value: number }>
  company_name: string | null
  company_facts: BigscreenInfoItem[]
  devices: Array<{
    id: string
    name: string
    category: number | null
    status: number | null
    area: string | null
    area_id: string | null
    last_reading: string | null
    register_value: number | null
    register_unit: string | null
  }>
  alarms: BigscreenEventSummary
  safety: BigscreenEventSummary
  carbon_alarms: BigscreenEventSummary
  power_alarms: BigscreenEventSummary
  business: Array<{ label: string; value: number | null; unit: string; detail: string }>
}

export type BigscreenEventSummary = {
  page: number
  page_size: number
  total: number
  start: string | null
  end: string | null
  distribution: BigscreenDistributionItem[]
  region_distribution: BigscreenDistributionItem[]
  status_distribution: BigscreenDistributionItem[]
  recent: Array<{ id: string; title: string; type: string; time: string | null; status: string; area: string; device: string; level: string | null; handle_note: string | null }>
}

export type BigscreenPeriod = { start?: string; end?: string; grain?: string; area?: string }

export type BigscreenEventCategory = "all" | "power" | "carbon" | "video"
export type BigscreenEventFilters = { category: BigscreenEventCategory; start?: string; end?: string; status?: string; area?: string; page?: number }

export type BigscreenCarbonResponse = {
  period_facts: BigscreenInfoItem[]
  scope_distribution: BigscreenDistributionItem[]
  area_ranking: BigscreenDistributionItem[]
  hero_metrics: BigscreenMetric[]
  flow: BigscreenFlowData
  source_ranking: BigscreenDistributionItem[]
  activity_distribution: BigscreenDistributionItem[]
  factors: BigscreenInfoItem[]
}
