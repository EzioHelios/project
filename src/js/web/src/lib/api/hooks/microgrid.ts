import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  microgridApplyBindingTemplate,
  microgridBootstrapXiangtaiDemo,
  microgridCreateDispatchBatch,
  microgridCreateWorkingCopy,
  microgridDiscardScenarioDraft,
  microgridGetAssetSeries,
  microgridGetBindingTemplate,
  microgridGetDataReadiness,
  microgridGetDispatchBatch,
  microgridGetEconomicInputOptions,
  microgridGetForecastRun,
  microgridGetOptimizationComparison,
  microgridGetOptimizationRun,
  microgridGetOverview,
  microgridGetTopology,
  microgridListAssets,
  microgridListDispatchBatches,
  microgridListFlexibilityContracts,
  microgridListForecastRuns,
  microgridListMeterBindings,
  microgridListOptimizationRuns,
  microgridListScenarios,
  microgridPublishScenario,
  microgridReplaceMeterBindings,
  microgridRestoreScenario,
  microgridRunForecast,
  microgridRunOptimization,
  microgridUpdateFlexibilityContract,
  microgridUpdateScenario,
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
  qualityStatus: "pass" | "warning" | "failed"
  qualityChecks: Array<{ code: string; status: string; message: string }>
  historySourceKind: string
  historyCoveragePct: number | null
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
  purpose: "trial" | "operational"
  baselinePeakKw: number | null
  optimizedPeakKw: number | null
  peakChangeKw: number | null
  evCompletionPct: number | null
  schedule?: SchedulePoint[]
}

export type MicrogridOverview = {
  configured: boolean
  mode: string
  site?: {
    id: number
    code: string
    name: string
    pccCapacityKw: number
    status: string
    sourceName: string
    bindingTemplateAvailable: boolean
  }
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
  dataReadiness?: DataReadiness
  dispatchBatch?: DispatchBatch | null
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
  siteId?: number
  scenarioId?: number
  scenarioName?: string
  scenarioVersion?: number
  purpose?: string
  receipts?: Array<{
    commandKey: string
    assetCode: string
    scheduledAt: string
    targetPowerKw: number
    executedPowerKw: number | null
    status: string
    reason: string | null
  }>
  assetSummaries?: Array<{
    assetCode: string
    commandCount: number
    executedCount: number
    clippedCount: number
    rejectedCount: number
    absoluteDeviationKwh: number
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
  tariffPlanId: number | null
  gridEmissionFactorId: number | null
  basedOnScenarioId: number | null
  changeSummary: string | null
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
  recoveryConstraints?: Record<string, unknown>
  hardConstraint?: boolean
}

export type DataReadiness = {
  ready: boolean
  validIntervals: number
  expectedIntervals: number
  coveragePct: number
  latestAt: string | null
  stale: boolean
  bindingCount: number
  equipmentIds: number[]
  reasons: string[]
  sourceKind: string
}

export type MeterBinding = {
  id?: number
  siteId?: number
  assetId: number
  assetCode: string
  assetName: string
  equipmentId: number
  equipmentCode: string
  equipmentName: string
  role: string
  pointCode: string
  direction: string
  sign: number
  sourceKind?: string
  sourceName?: string
  enabled?: boolean
}

export type BindingTemplate = {
  siteId: number
  monitorSectorId: number | null
  monitorSectorName: string | null
  templateCode: string
  items: MeterBinding[]
  unavailableCodes: string[]
  derivedPcc: boolean
}

export type EconomicInputOptions = {
  tariffPlans: Array<{ id: number; code: string; name: string; effectiveFrom: string | null }>
  emissionFactors: Array<{ id: number; code: string; value: number; unit: string; year: number; source: string }>
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

export function useMicrogridAssets(siteId?: number) {
  return useQuery({
    queryKey: ["microgrid", "assets", siteId],
    queryFn: async () => ((await microgridListAssets({ query: { site_id: siteId }, throwOnError: true })).data as { items: MicrogridAsset[] }).items,
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

export function useMicrogridScenarios(siteId?: number) {
  return useQuery({
    queryKey: ["microgrid", "scenarios", siteId],
    queryFn: async () => ((await microgridListScenarios({ query: { site_id: siteId }, throwOnError: true })).data as { items: MicrogridScenario[] }).items,
  })
}

export function useMicrogridFlexibilityContracts(scenarioId?: number) {
  return useQuery({
    queryKey: ["microgrid", "flexibility-contracts", scenarioId],
    enabled: Boolean(scenarioId),
    queryFn: async () => ((await microgridListFlexibilityContracts({ query: { scenario_id: scenarioId }, throwOnError: true })).data as { items: FlexibilityContract[] }).items,
  })
}

export function useMicrogridDataReadiness(siteId?: number) {
  return useQuery({
    queryKey: ["microgrid", "data-readiness", siteId],
    enabled: Boolean(siteId),
    queryFn: async () => (await microgridGetDataReadiness({ path: { site_id: siteId as number }, throwOnError: true })).data as DataReadiness,
  })
}

export function useMicrogridMeterBindings(siteId?: number) {
  return useQuery({
    queryKey: ["microgrid", "meter-bindings", siteId],
    enabled: Boolean(siteId),
    queryFn: async () => ((await microgridListMeterBindings({ path: { site_id: siteId as number }, throwOnError: true })).data as { items: MeterBinding[] }).items,
  })
}

export function useMicrogridBindingTemplate(siteId?: number, enabled = true) {
  return useQuery({
    queryKey: ["microgrid", "binding-template", siteId],
    enabled: Boolean(siteId) && enabled,
    queryFn: async () => (await microgridGetBindingTemplate({ path: { site_id: siteId as number }, throwOnError: true })).data as BindingTemplate,
  })
}

export function useMicrogridEconomicInputs() {
  return useQuery({
    queryKey: ["microgrid", "economic-input-options"],
    queryFn: async () => (await microgridGetEconomicInputOptions({ throwOnError: true })).data as EconomicInputOptions,
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

export function useMicrogridOptimizationComparison(runIds: number[]) {
  return useQuery({
    queryKey: ["microgrid", "optimization-comparison", runIds],
    enabled: runIds.length >= 2,
    queryFn: async () =>
      (await microgridGetOptimizationComparison({ query: { run_ids: runIds.join(",") }, throwOnError: true })).data as {
        siteId: number
        horizonStart: string
        horizonEnd: string
        runs: OptimizationRun[]
      },
  })
}

export function useMicrogridDispatchBatches() {
  return useQuery({
    queryKey: ["microgrid", "dispatch-batches"],
    queryFn: async () => ((await microgridListDispatchBatches({ throwOnError: true })).data as { items: DispatchBatch[] }).items,
    refetchInterval: 15_000,
  })
}

export function useMicrogridDispatchBatch(batchId?: number) {
  return useQuery({
    queryKey: ["microgrid", "dispatch-batch", batchId],
    enabled: Boolean(batchId),
    queryFn: async () => (await microgridGetDispatchBatch({ path: { batch_id: batchId as number }, throwOnError: true })).data as DispatchBatch,
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
    ...mutationOptions("祥泰微电网站点已就绪"),
  })
  const runForecast = useMutation({
    mutationFn: (payload: { siteId: number; scenarioId?: number }) => microgridRunForecast({ body: payload, throwOnError: true }).then((response) => response.data as ForecastRun),
    ...mutationOptions("预测运行已完成"),
  })
  const runOptimization = useMutation({
    mutationFn: (payload: { forecastRunId: number; scenarioId?: number; purpose: "trial" | "operational"; acknowledgeQualityWarning?: boolean }) =>
      microgridRunOptimization({ body: payload, throwOnError: true }).then((response) => response.data as OptimizationRun),
    ...mutationOptions("策略计算已完成"),
  })
  const dispatch = useMutation({
    mutationFn: (optimizationRunId: number) => microgridCreateDispatchBatch({ body: { optimizationRunId }, throwOnError: true }).then((response) => response.data as DispatchBatch),
    ...mutationOptions("优化计划已提交调度"),
  })
  const applyBindingTemplate = useMutation({
    mutationFn: (siteId: number) => microgridApplyBindingTemplate({ path: { site_id: siteId }, body: { confirm: true }, throwOnError: true }),
    ...mutationOptions("祥泰电表映射已应用并完成历史投影"),
  })
  const replaceMeterBindings = useMutation({
    mutationFn: (payload: { siteId: number; bindings: MeterBinding[] }) =>
      microgridReplaceMeterBindings({
        path: { site_id: payload.siteId },
        body: {
          bindings: payload.bindings.map((item) => ({
            assetId: item.assetId,
            equipmentId: item.equipmentId,
            role: item.role,
            pointCode: item.pointCode,
            direction: item.direction,
            sign: item.sign,
            enabled: item.enabled ?? true,
          })),
        },
        throwOnError: true,
      }),
    ...mutationOptions("设备绑定已保存并重新投影历史数据"),
  })
  const saveScenario = useMutation({
    mutationFn: (payload: { scenarioId: number; parameters: Record<string, unknown>; tariffPlanId?: number; gridEmissionFactorId?: number; changeSummary?: string }) =>
      microgridUpdateScenario({
        path: { scenario_id: payload.scenarioId },
        body: payload,
        throwOnError: true,
      }).then((response) => response.data as MicrogridScenario),
    ...mutationOptions("策略草稿已保存"),
  })
  const createWorkingCopy = useMutation({
    mutationFn: (scenarioId: number) =>
      microgridCreateWorkingCopy({ path: { scenario_id: scenarioId }, throwOnError: true }).then((response) => response.data as MicrogridScenario),
    ...mutationOptions("待发布版本已创建"),
  })
  const publishScenario = useMutation({
    mutationFn: (scenarioId: number) => microgridPublishScenario({ path: { scenario_id: scenarioId }, throwOnError: true }).then((response) => response.data as MicrogridScenario),
    ...mutationOptions("策略版本已发布"),
  })
  const restoreScenario = useMutation({
    mutationFn: (scenarioId: number) => microgridRestoreScenario({ path: { scenario_id: scenarioId }, throwOnError: true }).then((response) => response.data as MicrogridScenario),
    ...mutationOptions("历史版本已恢复为草稿"),
  })
  const discardDraft = useMutation({
    mutationFn: (scenarioId: number) => microgridDiscardScenarioDraft({ path: { scenario_id: scenarioId }, throwOnError: true }),
    ...mutationOptions("策略草稿已放弃"),
  })
  const updateContract = useMutation({
    mutationFn: (contract: FlexibilityContract) =>
      microgridUpdateFlexibilityContract({
        path: { contract_id: contract.id },
        body: {
          scenarioId: contract.scenarioId,
          assetId: contract.assetId,
          contractType: contract.contractType,
          startMinute: contract.startMinute,
          endMinute: contract.endMinute,
          minimumPowerKw: contract.minimumPowerKw,
          maximumPowerKw: contract.maximumPowerKw,
          targetEnergyKwh: contract.targetEnergyKwh,
          priority: contract.priority,
          penaltyCnyPerKwh: contract.penaltyCnyPerKwh,
          hardConstraint: contract.hardConstraint ?? Boolean(contract.recoveryConstraints?.hard_constraint ?? true),
          enabled: contract.enabled,
        },
        throwOnError: true,
      }),
    ...mutationOptions("柔性契约已保存"),
  })
  return {
    bootstrap,
    runForecast,
    runOptimization,
    dispatch,
    applyBindingTemplate,
    replaceMeterBindings,
    saveScenario,
    createWorkingCopy,
    publishScenario,
    restoreScenario,
    discardDraft,
    updateContract,
  }
}
