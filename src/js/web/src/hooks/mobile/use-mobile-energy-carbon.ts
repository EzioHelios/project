import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo } from "react"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { useAuthStore } from "@/lib/auth"
import { listTeams, type Team, type User } from "@/lib/generated/api"

export type AlertSummary = {
  total: number
  unhandled: number
  high_risk: number
  today_added: number
  avg_handle_hours: number | null
  by_source: { name: string; value: number }[]
  by_severity: { name: string; value: number }[]
  by_status: { name: string; value: number }[]
  by_area: { name: string; value: number }[]
}

export type AlertTrend = {
  series: { period: string; alerts_count: number; handled_count: number; energy_kwh?: number; carbon_co2e?: number }[]
}

export type AlertRow = {
  id: string
  source: string
  record_id: number
  record_type?: string
  alert_type: string
  severity: string
  title: string
  area_name?: string
  object_name?: string
  status: string
  occurred_at?: string | null
  description?: string | null
}

export type AlertDetail = AlertRow & {
  history: { label: string; value: string | null | undefined }[]
}

export type MonitorArea = {
  id: number
  name: string
  status: string
  health_ratio: number
  equipment_total: number
  equipment_online: number
  equipment_fault: number
  video_total: number
  video_online: number
  alert_unhandled: number
}

export type MonitorDevice = {
  id: number
  name: string
  code?: string | null
  category?: number | null
  sector_id?: number | null
  sector_name?: string | null
  status?: number | null
  trip_state?: number | null
  location?: string | null
  protocol?: string | null
  alert_unhandled?: number
}

export type MonitorDeviceDetail = {
  device: MonitorDevice & { install_time?: string | null }
  meter_samples: { id?: number; point_code?: string | null; normalized_value?: number | null; reading_time?: string | null; quality_status?: string | null }[]
  alerts: Record<string, unknown>[]
}

export type MonitorDeviceTimeseries = {
  series: { period: string; energy_kwh: number; carbon_co2e: number }[]
}

export type EnergySummary = {
  period: string
  total_kwh: number
  meter_count: number
  sample_count: number
  invalid_meter_count: number
  calc_status: string
}

export type EnergyTrend = {
  items: { period: string; total_kwh: number; sample_count: number }[]
  granularity: string
}

export type EnergyRankingRow = {
  id: string
  name: string
  total_kwh: number
  sample_count: number
}

export type MobileWorkOrder = {
  id: string
  source_alert_id: string
  source: string
  record_id: number
  task_type: string
  priority: string
  title: string
  area_name?: string | null
  object_name?: string | null
  status: string
  occurred_at?: string | null
  due_at?: string | null
  assignee: string
  description?: string | null
  actions: string[]
  history?: { label: string; value: string | null | undefined }[]
}

export type MobileEnergyFilters = {
  period?: string
  granularity?: string
  groupBy?: "area" | "equipment"
  areaId?: string
}

export type MobileEnergyCarbonOptions = {
  selectedDeviceId?: number | null
  selectedAlertId?: string | null
  selectedWorkOrderId?: string | null
  energy?: MobileEnergyFilters
}

export type MobileEnergyCarbonData = {
  currentUser: User | null
  teams: Team[]
  currentTeam: Team | null
  setCurrentTeam: (team: Team) => void
  energySummary?: EnergySummary
  energyTrend?: EnergyTrend
  energyRanking: EnergyRankingRow[]
  summary?: AlertSummary
  trend?: AlertTrend
  alerts: AlertRow[]
  alertDetail?: AlertDetail
  devices: MonitorDevice[]
  areas: MonitorArea[]
  deviceDetail?: MonitorDeviceDetail
  deviceTimeseries?: MonitorDeviceTimeseries
  deviceAlerts: AlertRow[]
  deviceVideos: Record<string, unknown>[]
  workOrders: MobileWorkOrder[]
  workOrderDetail?: MobileWorkOrder
  acknowledgeAlert: (alertId: string, note?: string) => Promise<void>
  transferAlertToWorkOrder: (alertId: string, note?: string) => Promise<string | null>
  acceptWorkOrder: (workOrderId: string) => Promise<void>
  submitWorkOrder: (workOrderId: string, result: string, attachments: string[]) => Promise<void>
  isTeamsLoading: boolean
  isBusinessLoading: boolean
  isActionPending: boolean
  isError: boolean
  errorMessage: string
}

export function useMobileEnergyCarbonData(options: MobileEnergyCarbonOptions = {}): MobileEnergyCarbonData {
  const queryClient = useQueryClient()
  const { isAuthenticated, user, teams, currentTeam, setTeams, setCurrentTeam } = useAuthStore()

  const teamsQuery = useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const response = await listTeams()
      return response.data?.items ?? []
    },
    enabled: isAuthenticated,
  })

  const loadedTeams = teamsQuery.data ?? teams
  const effectiveTeam = useMemo(() => {
    if (currentTeam && loadedTeams.some((team) => team.id === currentTeam.id)) return currentTeam
    return loadedTeams[0] ?? null
  }, [currentTeam, loadedTeams])

  useEffect(() => {
    if (!teamsQuery.data) return
    const nextCurrentTeam = effectiveTeam
    const changedTeam = nextCurrentTeam?.id !== currentTeam?.id
    setTeams(teamsQuery.data)
    if (nextCurrentTeam && changedTeam) {
      setCurrentTeam(nextCurrentTeam)
      void queryClient.invalidateQueries()
    }
  }, [currentTeam?.id, effectiveTeam, queryClient, setCurrentTeam, setTeams, teamsQuery.data])

  const enabled = isAuthenticated && Boolean(effectiveTeam)
  const tenantKey = effectiveTeam?.id ?? "no-team"
  const energy = options.energy ?? {}
  const period = energy.period ?? "month"
  const granularity = energy.granularity ?? "day"
  const groupBy = energy.groupBy ?? "equipment"
  const areaQuery = energy.areaId && energy.areaId !== "all" ? `&area_id=${encodeURIComponent(energy.areaId)}` : ""

  const energySummaryQuery = useQuery<ApiEnvelope<EnergySummary>>({
    queryKey: ["mobile", tenantKey, "energy-summary", period, energy.areaId],
    queryFn: () => fetchCarbonApi<EnergySummary>(`/api/metering/energy/summary?period=${period}${areaQuery}`),
    enabled,
  })
  const energyTrendQuery = useQuery<ApiEnvelope<EnergyTrend>>({
    queryKey: ["mobile", tenantKey, "energy-trend", granularity, energy.areaId],
    queryFn: () => fetchCarbonApi<EnergyTrend>(`/api/metering/energy/trend?granularity=${granularity}${areaQuery}`),
    enabled,
  })
  const energyRankingQuery = useQuery<ApiEnvelope<{ items: EnergyRankingRow[] }>>({
    queryKey: ["mobile", tenantKey, "energy-ranking", groupBy, period, energy.areaId],
    queryFn: () => fetchCarbonApi<{ items: EnergyRankingRow[] }>(`/api/metering/energy/ranking?period=${period}&group_by=${groupBy}&limit=10${areaQuery}`),
    enabled,
  })

  const summaryQuery = useQuery<ApiEnvelope<AlertSummary>>({
    queryKey: ["mobile", tenantKey, "alert-summary"],
    queryFn: () => fetchCarbonApi<AlertSummary>("/api/energy-carbon/alerts/summary"),
    enabled,
  })
  const trendQuery = useQuery<ApiEnvelope<AlertTrend>>({
    queryKey: ["mobile", tenantKey, "alert-trend"],
    queryFn: () => fetchCarbonApi<AlertTrend>("/api/energy-carbon/alerts/trend?months=12"),
    enabled,
  })
  const alertsQuery = useQuery<ApiEnvelope<{ items: AlertRow[]; total: number; limit: number; offset: number }>>({
    queryKey: ["mobile", tenantKey, "alerts"],
    queryFn: () => fetchCarbonApi<{ items: AlertRow[]; total: number; limit: number; offset: number }>("/api/energy-carbon/alerts?limit=30"),
    enabled,
  })
  const devicesQuery = useQuery<ApiEnvelope<{ items: MonitorDevice[]; total: number }>>({
    queryKey: ["mobile", tenantKey, "devices"],
    queryFn: () => fetchCarbonApi<{ items: MonitorDevice[]; total: number }>("/api/energy-carbon/monitor/devices?limit=120"),
    enabled,
  })
  const areasQuery = useQuery<ApiEnvelope<{ items: MonitorArea[]; total: number }>>({
    queryKey: ["mobile", tenantKey, "areas"],
    queryFn: () => fetchCarbonApi<{ items: MonitorArea[]; total: number }>("/api/energy-carbon/monitor/areas"),
    enabled,
  })

  const alerts = alertsQuery.data?.data.items ?? []
  const selectedAlertId = options.selectedAlertId ?? alerts[0]?.id
  const selectedDeviceId = options.selectedDeviceId ?? devicesQuery.data?.data.items?.[0]?.id
  const alertDetailQuery = useQuery<ApiEnvelope<AlertDetail>>({
    queryKey: ["mobile", tenantKey, "alert-detail", selectedAlertId],
    queryFn: () => fetchCarbonApi<AlertDetail>(`/api/energy-carbon/alerts/${selectedAlertId}`),
    enabled: enabled && Boolean(selectedAlertId),
  })
  const deviceDetailQuery = useQuery<ApiEnvelope<MonitorDeviceDetail>>({
    queryKey: ["mobile", tenantKey, "device-detail", selectedDeviceId],
    queryFn: () => fetchCarbonApi<MonitorDeviceDetail>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}`),
    enabled: enabled && Boolean(selectedDeviceId),
  })
  const deviceTimeseriesQuery = useQuery<ApiEnvelope<MonitorDeviceTimeseries>>({
    queryKey: ["mobile", tenantKey, "device-timeseries", selectedDeviceId],
    queryFn: () => fetchCarbonApi<MonitorDeviceTimeseries>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}/timeseries`),
    enabled: enabled && Boolean(selectedDeviceId),
  })
  const deviceAlertsQuery = useQuery<ApiEnvelope<{ items: AlertRow[] }>>({
    queryKey: ["mobile", tenantKey, "device-alerts", selectedDeviceId],
    queryFn: () => fetchCarbonApi<{ items: AlertRow[] }>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}/alerts`),
    enabled: enabled && Boolean(selectedDeviceId),
  })
  const deviceVideosQuery = useQuery<ApiEnvelope<{ items: Record<string, unknown>[] }>>({
    queryKey: ["mobile", tenantKey, "device-videos", selectedDeviceId],
    queryFn: () => fetchCarbonApi<{ items: Record<string, unknown>[] }>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}/videos`),
    enabled: enabled && Boolean(selectedDeviceId),
  })
  const workOrdersQuery = useQuery<ApiEnvelope<{ items: MobileWorkOrder[]; total: number }>>({
    queryKey: ["mobile", tenantKey, "work-orders"],
    queryFn: () => fetchCarbonApi<{ items: MobileWorkOrder[]; total: number }>("/api/mobile/work-orders?limit=30"),
    enabled,
  })
  const workOrders = workOrdersQuery.data?.data.items ?? []
  const selectedWorkOrderId = options.selectedWorkOrderId ?? workOrders[0]?.id
  const workOrderDetailQuery = useQuery<ApiEnvelope<MobileWorkOrder>>({
    queryKey: ["mobile", tenantKey, "work-order-detail", selectedWorkOrderId],
    queryFn: () => fetchCarbonApi<MobileWorkOrder>(`/api/mobile/work-orders/${selectedWorkOrderId}`),
    enabled: enabled && Boolean(selectedWorkOrderId),
  })

  const mutation = useMutation({
    mutationFn: ({ url, body }: { url: string; body?: Record<string, unknown> }) => postMobileApi<{ work_order_id?: string }>(url, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mobile", tenantKey] })
    },
  })

  const isBusinessLoading = [
    teamsQuery,
    energySummaryQuery,
    energyTrendQuery,
    energyRankingQuery,
    summaryQuery,
    trendQuery,
    alertsQuery,
    devicesQuery,
    areasQuery,
    alertDetailQuery,
    deviceDetailQuery,
    deviceTimeseriesQuery,
    deviceAlertsQuery,
    deviceVideosQuery,
    workOrdersQuery,
    workOrderDetailQuery,
  ].some((query) => query.isLoading)
  const errors = [
    teamsQuery.error,
    energySummaryQuery.error,
    energyTrendQuery.error,
    energyRankingQuery.error,
    summaryQuery.error,
    trendQuery.error,
    alertsQuery.error,
    devicesQuery.error,
    areasQuery.error,
    alertDetailQuery.error,
    deviceDetailQuery.error,
    deviceTimeseriesQuery.error,
    deviceAlertsQuery.error,
    deviceVideosQuery.error,
    workOrdersQuery.error,
    workOrderDetailQuery.error,
    mutation.error,
  ].filter(Boolean)

  return {
    currentUser: user,
    teams: loadedTeams,
    currentTeam: effectiveTeam,
    setCurrentTeam,
    energySummary: energySummaryQuery.data?.data,
    energyTrend: energyTrendQuery.data?.data,
    energyRanking: energyRankingQuery.data?.data.items ?? [],
    summary: summaryQuery.data?.data,
    trend: trendQuery.data?.data,
    alerts,
    alertDetail: alertDetailQuery.data?.data,
    devices: devicesQuery.data?.data.items ?? [],
    areas: areasQuery.data?.data.items ?? [],
    deviceDetail: deviceDetailQuery.data?.data,
    deviceTimeseries: deviceTimeseriesQuery.data?.data,
    deviceAlerts: deviceAlertsQuery.data?.data.items ?? [],
    deviceVideos: deviceVideosQuery.data?.data.items ?? [],
    workOrders,
    workOrderDetail: workOrderDetailQuery.data?.data,
    acknowledgeAlert: async (alertId, note) => {
      await mutation.mutateAsync({ url: `/api/mobile/alerts/${alertId}/acknowledge`, body: { note } })
    },
    transferAlertToWorkOrder: async (alertId, note) => {
      const result = await mutation.mutateAsync({ url: `/api/mobile/alerts/${alertId}/transfer-work-order`, body: { note } })
      return result.data.work_order_id ?? null
    },
    acceptWorkOrder: async (workOrderId) => {
      await mutation.mutateAsync({ url: `/api/mobile/work-orders/${workOrderId}/accept` })
    },
    submitWorkOrder: async (workOrderId, result, attachments) => {
      await mutation.mutateAsync({ url: `/api/mobile/work-orders/${workOrderId}/submit`, body: { result, attachments } })
    },
    isTeamsLoading: teamsQuery.isLoading,
    isBusinessLoading,
    isActionPending: mutation.isPending,
    isError: errors.length > 0,
    errorMessage: errors.map((error) => (error instanceof Error ? error.message : String(error))).join("；"),
  }
}

async function postMobileApi<T>(url: string, body: Record<string, unknown> = {}) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const payload = (await response.json().catch(() => ({}))) as ApiEnvelope<T>
  if (!response.ok || payload.code >= 400) {
    throw new Error(payload.msg || `HTTP ${response.status}`)
  }
  return payload
}
