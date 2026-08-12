import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  microgridBootstrapXiangtaiDemo,
  microgridCreateDispatchBatch,
  microgridGetAssetSeries,
  microgridGetForecastRun,
  microgridGetOptimizationRun,
  microgridGetOverview,
  microgridGetTopology,
  microgridListAssets,
  microgridListFlexibilityContracts,
  microgridListForecastRuns,
  microgridListOptimizationRuns,
  microgridListScenarios,
  microgridRunForecast,
  microgridRunOptimization,
} from "@/lib/generated/api"

export type MicrogridAsset = {
  id: number
  siteId: number
  code: string
  name: string
  assetType: "grid" | "pv" | "storage" | "charger" | "lighting" | "load" | "generator"
  ratedPowerKw: number | null
  ratedEnergyKwh: number | null
  controllable: boolean
  parameters: Record<string, unknown>
  sourceKind: string
  sourceName: string
  confidenceLevel: number | null
  online: boolean
  operatingMode: string
  activePowerKw: number | null
  socPct: number | null
  temperatureC: number | null
  alarmLevel: string
  observedAt: string | null
  stateSourceKind: string
}

export type ForecastPoint = {
  seriesCode: "load" | "pv" | "soc"
  validAt: string
  p10: number
  p50: number
  p90: number
  unit: string
}

export type MicrogridSeriesPoint = {
  observedAt: string
  value: number
  unit: string
  sourceKind: string
  quality: string
}

export type ForecastRun = {
  id: number
  siteId: number
  scenarioId: number
  status: string
  horizonStart: string
  horizonEnd: string
  intervalMinutes: number
  modelVersion: string
  metrics: { mae_kw?: number; rmse_kw?: number; mape_pct?: number; coverage?: number; model?: string }
  inputSnapshot: Record<string, unknown>
  completedAt: string | null
  errorMessage: string | null
  points?: ForecastPoint[]
}

export type SchedulePoint = {
  validAt: string
  loadKw: number
  pvKw: number
  gridImportKw: number
  gridExportKw: number
  batteryChargeKw: number
  batteryDischargeKw: number
  chargerKw: number
  lightingKw: number
  generatorKw: number
  curtailedPvKw: number
  socPct: number
  tariffCnyPerKwh: number
  intervalCostCny: number
}

export type OptimizationRun = {
  id: number
  siteId: number
  scenarioId: number
  forecastRunId: number
  status: string
  solver: string
  solverSeconds: number | null
  mipGap: number | null
  objectiveCny: number | null
  baselineCostCny: number | null
  savingsCny: number | null
  peakReductionKw: number | null
  carbonReductionKg: number | null
  costBreakdown: Record<string, number>
  diagnostics: Array<{ constraint: string; severity: string; message: string }>
  inputSnapshot: Record<string, unknown>
  completedAt: string | null
  errorMessage: string | null
  schedule?: SchedulePoint[]
}

export type MicrogridOverview = {
  configured: boolean
  mode: string
  site?: { id: number; code: string; name: string; pccCapacityKw: number; status: string; sourceName: string }
  scenario?: { id: number; name: string; version: number; sourceKind: string; sourceName: string; confidenceLevel: number } | null
  metrics?: {
    pccPowerKw: number
    pvPowerKw: number
    socPct: number
    onlineAssets: number
    totalAssets: number
    savingsCny: number
    peakReductionKw: number
    carbonReductionKg: number
    alarmCount: number
  }
  trend?: Array<{ period: string; loadKw?: number; pvKw?: number; gridImportKw?: number; socPct?: number }>
  assets?: MicrogridAsset[]
  forecastRun?: ForecastRun | null
  optimizationRun?: OptimizationRun | null
}

export type MicrogridTopology = {
  configured: boolean
  mode?: string
  schemaVersion?: number
  topologyVersion?: number
  canvas?: { width: number; height: number }
  layout?: {
    algorithm: "dagre"
    direction: "TB" | "LR"
    rankSeparation?: number
    nodeSeparation?: number
    edgeSeparation?: number
  }
  site?: MicrogridOverview["site"]
  nodes: Array<{
    id: string
    kind?: string
    assetCode?: string
    label: string
    meta?: string
    x?: number
    y?: number
    ports?: Array<{
      id: string
      side: "top" | "right" | "bottom" | "left"
      direction: "input" | "output"
      offset?: number
      offsetByLayout?: Partial<Record<"TB" | "LR", number>>
      voltageLevel?: string | null
    }>
  }>
  edges: Array<{
    id?: string
    source: string
    target: string
    sourceHandle?: string
    targetHandle?: string
    assetCode?: string
    kind?: string
    voltageLevel?: string
  }>
  assets?: MicrogridAsset[]
}

export type DispatchBatch = {
  id: number
  optimizationRunId: number
  status: string
  adapterCode: string
  expiresAt: string
  commandCount: number
  acceptedCount: number
  rejectedCount: number
  completedAt: string | null
  receipts: Array<{
    commandKey: string
    assetCode: string
    scheduledAt: string
    targetPowerKw: number
    executedPowerKw: number | null
    status: string
    reason: string | null
  }>
}

export type MicrogridScenario = {
  id: number
  siteId: number
  code: string
  name: string
  version: number
  status: string
  sourceKind: string
  sourceName: string
  confidenceLevel: number
  validFrom: string
  publishedAt: string | null
  parameters: Record<string, unknown>
}

export type FlexibilityContract = {
  id: number
  scenarioId: number
  assetId: number
  assetCode: string
  assetName: string
  assetType: string
  contractType: string
  startMinute: number
  endMinute: number
  minimumPowerKw: number
  maximumPowerKw: number
  targetEnergyKwh: number | null
  priority: number
  penaltyCnyPerKwh: number
  enabled: boolean
}

export function useMicrogridOverview() {
  return useQuery({
    queryKey: ["microgrid", "overview"],
    queryFn: async () => (await microgridGetOverview({ throwOnError: true })).data as MicrogridOverview,
    refetchInterval: 15_000,
  })
}

export function useMicrogridTopology() {
  return useQuery({
    queryKey: ["microgrid", "topology"],
    queryFn: async () => (await microgridGetTopology({ throwOnError: true })).data as MicrogridTopology,
    refetchInterval: 15_000,
  })
}

export function useMicrogridAssets() {
  return useQuery({
    queryKey: ["microgrid", "assets"],
    queryFn: async () => ((await microgridListAssets({ throwOnError: true })).data as { items: MicrogridAsset[] }).items,
  })
}

export function useMicrogridAssetSeries(assetId: number | null) {
  return useQuery({
    queryKey: ["microgrid", "asset-series", assetId],
    enabled: assetId !== null,
    queryFn: async () => {
      if (assetId === null) return []
      const response = await microgridGetAssetSeries({ path: { asset_id: assetId }, query: { limit: 96 }, throwOnError: true })
      return (response.data as { items: MicrogridSeriesPoint[] }).items
    },
  })
}

export function useMicrogridScenarios() {
  return useQuery({
    queryKey: ["microgrid", "scenarios"],
    queryFn: async () => ((await microgridListScenarios({ throwOnError: true })).data as { items: MicrogridScenario[] }).items,
  })
}

export function useMicrogridFlexibilityContracts() {
  return useQuery({
    queryKey: ["microgrid", "flexibility-contracts"],
    queryFn: async () => ((await microgridListFlexibilityContracts({ throwOnError: true })).data as { items: FlexibilityContract[] }).items,
  })
}

export function useMicrogridForecastRuns() {
  return useQuery({
    queryKey: ["microgrid", "forecast-runs"],
    queryFn: async () => ((await microgridListForecastRuns({ throwOnError: true })).data as { items: ForecastRun[] }).items,
    refetchInterval: 60_000,
  })
}

export function useMicrogridForecastRun(runId?: number) {
  return useQuery({
    queryKey: ["microgrid", "forecast-run", runId],
    queryFn: async () => (await microgridGetForecastRun({ path: { run_id: runId as number }, throwOnError: true })).data as ForecastRun,
    enabled: Boolean(runId),
  })
}

export function useMicrogridOptimizationRuns() {
  return useQuery({
    queryKey: ["microgrid", "optimization-runs"],
    queryFn: async () => ((await microgridListOptimizationRuns({ throwOnError: true })).data as { items: OptimizationRun[] }).items,
    refetchInterval: 60_000,
  })
}

export function useMicrogridOptimizationRun(runId?: number) {
  return useQuery({
    queryKey: ["microgrid", "optimization-run", runId],
    queryFn: async () => (await microgridGetOptimizationRun({ path: { run_id: runId as number }, throwOnError: true })).data as OptimizationRun,
    enabled: Boolean(runId),
  })
}

export function useMicrogridActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => queryClient.invalidateQueries({ queryKey: ["microgrid"] })
  const mutationOptions = (success: string) => ({
    onSuccess: async () => {
      await invalidate()
      toast.success(success)
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const bootstrap = useMutation({
    mutationFn: async () => (await microgridBootstrapXiangtaiDemo({ body: { siteCode: "xiangtai-taizhou" }, throwOnError: true })).data as { siteId: number },
    ...mutationOptions("祥泰微电网演示场景已就绪"),
  })
  const runForecast = useMutation({
    mutationFn: (payload: { siteId: number; scenarioId?: number }) => microgridRunForecast({ body: payload, throwOnError: true }).then((response) => response.data as ForecastRun),
    ...mutationOptions("预测运行已完成"),
  })
  const runOptimization = useMutation({
    mutationFn: (forecastRunId: number) => microgridRunOptimization({ body: { forecastRunId }, throwOnError: true }).then((response) => response.data as OptimizationRun),
    ...mutationOptions("优化运行已完成"),
  })
  const dispatch = useMutation({
    mutationFn: (optimizationRunId: number) => microgridCreateDispatchBatch({ body: { optimizationRunId }, throwOnError: true }).then((response) => response.data as DispatchBatch),
    ...mutationOptions("优化计划已提交模拟调度"),
  })
  return { bootstrap, runForecast, runOptimization, dispatch }
}
