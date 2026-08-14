import { createFileRoute } from "@tanstack/react-router"
import { GitCompareArrows, Play, Send, Settings2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getOptimizationAlgorithmLabel, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import {
  useMicrogridActions,
  useMicrogridEconomicInputs,
  useMicrogridForecastRuns,
  useMicrogridOptimizationComparison,
  useMicrogridOptimizationRun,
  useMicrogridOptimizationRuns,
  useMicrogridScenarios,
} from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/optimization")({ component: MicrogridOptimizationPage })

function MicrogridOptimizationPage() {
  const chartTheme = useAdminChartTheme("energy")
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [strategyOpen, setStrategyOpen] = useState(false)
  const [comparisonOpen, setComparisonOpen] = useState(false)
  const [selectedRunIds, setSelectedRunIds] = useState<number[]>([])
  const [preset, setPreset] = useState<keyof typeof strategyPresets>("balanced")
  const [weights, setWeights] = useState<StrategyWeights>({ energy: 1, peak: 1.5, carbon: 1.5 })
  const [socMinimum, setSocMinimum] = useState(15)
  const [socMaximum, setSocMaximum] = useState(90)
  const [terminalSoc, setTerminalSoc] = useState(52)
  const [reserveMargin, setReserveMargin] = useState(8)
  const [degradationCost, setDegradationCost] = useState(0.08)
  const [carbonPrice, setCarbonPrice] = useState(0.08)
  const [tariffPlanId, setTariffPlanId] = useState<number>()
  const [emissionFactorId, setEmissionFactorId] = useState<number>()
  const forecastRuns = useMicrogridForecastRuns()
  const runs = useMicrogridOptimizationRuns()
  const scenarios = useMicrogridScenarios(forecastRuns.data?.[0]?.siteId)
  const economics = useMicrogridEconomicInputs()
  const published = scenarios.data?.find((item) => item.status === "published")
  const draft = scenarios.data?.find((item) => item.status === "draft")
  const strategySource = draft ?? published
  const latestRunId = runs.data?.[0]?.id
  const run = useMicrogridOptimizationRun(latestRunId)
  const actions = useMicrogridActions()
  const comparison = useMicrogridOptimizationComparison(selectedRunIds)
  const comparisonRuns = comparison.data?.runs ?? []
  const schedule = run.data?.schedule ?? []
  const powerPoints = useMemo(
    () =>
      schedule.map((point) => ({
        period: formatMicrogridDateTime(point.validAt),
        loadKw: point.loadKw,
        pvKw: point.pvKw,
        gridImportKw: point.gridImportKw,
        batteryKw: point.batteryDischargeKw - point.batteryChargeKw,
        chargerKw: point.chargerKw,
      })),
    [schedule],
  )
  const socPoints = useMemo(() => schedule.map((point) => ({ period: formatMicrogridDateTime(point.validAt), socPct: point.socPct })), [schedule])
  const powerOption = createTrendChartOption(
    chartTheme,
    powerPoints,
    [
      { key: "loadKw", label: "固定负荷", colorKey: "energy" },
      { key: "pvKw", label: "光伏", colorKey: "carbon" },
      { key: "gridImportKw", label: "电网购电", colorKey: "cost" },
      { key: "batteryKw", label: "储能(+放电)", colorKey: "scope3" },
      { key: "chargerKw", label: "充电桩", colorKey: "warning" },
    ],
    { periodKey: "period", includeZeroSeries: true },
  )
  const socOption = createTrendChartOption(chartTheme, socPoints, [{ key: "socPct", label: "SOC", colorKey: "energy" }], {
    periodKey: "period",
    includeZeroSeries: true,
  })
  const comparisonPoints = useMemo(() => {
    const byPeriod = new Map<string, Record<string, unknown>>()
    for (const item of comparisonRuns) {
      for (const point of item.schedule ?? []) {
        const period = formatMicrogridDateTime(point.validAt)
        const row = byPeriod.get(period) ?? { period }
        row[`grid-${item.id}`] = point.gridImportKw
        row[`soc-${item.id}`] = point.socPct
        byPeriod.set(period, row)
      }
    }
    return [...byPeriod.values()]
  }, [comparisonRuns])
  const comparisonColors = ["energy", "cost", "carbon"] as const
  const comparisonGridOption = createTrendChartOption(
    chartTheme,
    comparisonPoints,
    comparisonRuns.map((item, index) => ({ key: `grid-${item.id}`, label: `方案 #${item.id}`, colorKey: comparisonColors[index] })),
    { periodKey: "period", includeZeroSeries: true },
  )
  const comparisonSocOption = createTrendChartOption(
    chartTheme,
    comparisonPoints,
    comparisonRuns.map((item, index) => ({ key: `soc-${item.id}`, label: `方案 #${item.id}`, colorKey: comparisonColors[index] })),
    { periodKey: "period", includeZeroSeries: true },
  )
  const latestForecastId = forecastRuns.data?.find((item) => item.status === "completed")?.id
  const latestForecast = forecastRuns.data?.find((item) => item.id === latestForecastId)
  const isFeasible = run.data?.status === "optimal" || run.data?.status === "feasible"
  const isDispatchable = isFeasible && run.data?.purpose === "operational" && latestForecast?.qualityStatus === "pass"

  useEffect(() => {
    if (!strategySource) return
    const parameters = strategySource.parameters
    const objectiveWeights = (parameters.objective_weights as Partial<StrategyWeights> | undefined) ?? {}
    const storage = (parameters.storage as Record<string, unknown> | undefined) ?? {}
    const economicParameters = (parameters.economics as Record<string, unknown> | undefined) ?? {}
    setWeights({
      energy: Number(objectiveWeights.energy ?? 1),
      peak: Number(objectiveWeights.peak ?? 1.5),
      carbon: Number(objectiveWeights.carbon ?? 1.5),
    })
    setSocMinimum(Number(storage.minimum_soc_pct ?? 15))
    setSocMaximum(Number(storage.maximum_soc_pct ?? 90))
    setTerminalSoc(Number(storage.terminal_soc_pct ?? storage.initial_soc_pct ?? 52))
    setReserveMargin(Number(parameters.reserve_margin_pct ?? 8))
    setDegradationCost(Number(economicParameters.battery_degradation_cny_per_kwh ?? 0.08))
    setCarbonPrice(Number(economicParameters.carbon_cny_per_kg ?? 0.08))
    setTariffPlanId(strategySource.tariffPlanId ?? economics.data?.tariffPlans[0]?.id)
    setEmissionFactorId(strategySource.gridEmissionFactorId ?? economics.data?.emissionFactors[0]?.id)
  }, [economics.data, strategySource])

  const saveStrategy = () => {
    const source = strategySource
    if (!source) return
    const parameters = structuredClone(source.parameters)
    parameters.objective_weights = weights
    parameters.reserve_margin_pct = reserveMargin
    parameters.storage = {
      ...((parameters.storage as Record<string, unknown>) ?? {}),
      minimum_soc_pct: socMinimum,
      maximum_soc_pct: socMaximum,
      terminal_soc_pct: terminalSoc,
    }
    parameters.economics = {
      ...((parameters.economics as Record<string, unknown>) ?? {}),
      battery_degradation_cny_per_kwh: degradationCost,
      carbon_cny_per_kg: carbonPrice,
    }
    actions.saveScenario.mutate({
      scenarioId: source.id,
      parameters,
      tariffPlanId,
      gridEmissionFactorId: emissionFactorId,
      changeSummary: `策略预设：${strategyPresets[preset].label}`,
    })
    setStrategyOpen(false)
  }

  const runTrial = () => {
    if (!latestForecastId || !(draft ?? published)) return
    actions.runOptimization.mutate({
      forecastRunId: latestForecastId,
      scenarioId: (draft ?? published)?.id,
      purpose: "trial",
      acknowledgeQualityWarning: latestForecast?.qualityStatus === "warning",
    })
  }

  const runOperational = () => {
    if (!latestForecastId || !published || latestForecast?.qualityStatus !== "pass") return
    actions.runOptimization.mutate({ forecastRunId: latestForecastId, scenarioId: published.id, purpose: "operational" })
  }

  return (
    <AdminPageScaffold
      title="智能优化"
      status={<RunStatusBadge status={run.data?.status} />}
      meta={run.data ? `${getOptimizationAlgorithmLabel(run.data.solver)} · ${formatNumber((run.data.mipGap ?? 0) * 100, 2)}% Gap · 24小时计划` : "尚无优化运行"}
      topActions={
        <div className="flex gap-2">
          <Button disabled={!latestForecastId || actions.runOptimization.isPending} onClick={runTrial} size="sm" variant="outline">
            <Play />
            {actions.runOptimization.isPending ? "求解中" : "运行试算"}
          </Button>
          <Button disabled={!published || latestForecast?.qualityStatus !== "pass" || actions.runOptimization.isPending} onClick={runOperational} size="sm" variant="outline">
            正式优化
          </Button>
          <Button onClick={() => setStrategyOpen(true)} size="sm" variant="outline">
            <Settings2 />
            策略参数
          </Button>
          <Button disabled={(runs.data?.length ?? 0) < 2} onClick={() => setComparisonOpen(true)} size="sm" variant="outline">
            <GitCompareArrows />
            方案比较
          </Button>
          <Button disabled={!isDispatchable || actions.dispatch.isPending} onClick={() => setConfirmOpen(true)} size="sm">
            <Send />
            提交计划
          </Button>
        </div>
      }
      filters={
        <ContextBar>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">优化范围</span>
            <div className="font-medium text-sm">未来24小时 / 15分钟</div>
          </div>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">目标</span>
            <div className="font-medium text-sm">费用 + 峰值 + 碳排</div>
          </div>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">时间基准</span>
            <div className="font-medium text-sm">站点时间 UTC+8</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip className="xl:grid-cols-6">
          <MetricTile label="基线费用" value={formatNumber(run.data?.baselineCostCny, 2)} unit="元/日" />
          <MetricTile label="优化费用" value={formatNumber(run.data?.objectiveCny, 2)} unit="元/日" />
          <MetricTile
            label={(run.data?.savingsCny ?? 0) >= 0 ? "节省" : "费用增加"}
            value={formatNumber(Math.abs(run.data?.savingsCny ?? 0), 2)}
            unit="元/日"
            tone={(run.data?.savingsCny ?? 0) >= 0 ? "success" : "warning"}
          />
          <MetricTile
            label={(run.data?.peakChangeKw ?? 0) <= 0 ? "峰值下降" : "峰值增加"}
            value={formatNumber(Math.abs(run.data?.peakChangeKw ?? 0))}
            unit="kW"
            tone={(run.data?.peakChangeKw ?? 0) <= 0 ? "success" : "warning"}
          />
          <MetricTile
            label={(run.data?.carbonReductionKg ?? 0) >= 0 ? "减排" : "排放增加"}
            value={formatNumber(Math.abs(run.data?.carbonReductionKg ?? 0))}
            unit="kgCO₂e"
            tone={(run.data?.carbonReductionKg ?? 0) >= 0 ? "success" : "warning"}
          />
          <MetricTile label="求解耗时" value={formatNumber(run.data?.solverSeconds, 3)} unit="s" />
        </MetricStrip>
      }
    >
      {!run.data && !run.isLoading ? (
        <AdminEmptyState
          title="尚无优化结果"
          description="先完成负荷与光伏预测，再运行24小时滚动优化。"
          actions={
            <Button disabled={!latestForecastId} onClick={runTrial}>
              运行优化
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <ChartPanel title="资源调度计划" unit="kW" source="Pyomo + HiGHS MILP" updatedAt={formatMicrogridDateTime(run.data?.completedAt)} option={powerOption} height={360} />
            <ChartPanel title="储能SOC轨迹" unit="%" source="储能物理状态转移模型" updatedAt={formatMicrogridDateTime(run.data?.completedAt)} option={socOption} height={360} />
          </div>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <AdminPanel title="调度计划明细（前12时段）" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>时刻</TableHead>
                    <TableHead className="text-right">负荷</TableHead>
                    <TableHead className="text-right">光伏</TableHead>
                    <TableHead className="text-right">购电</TableHead>
                    <TableHead className="text-right">储能</TableHead>
                    <TableHead className="text-right">SOC</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schedule.slice(0, 12).map((point) => (
                    <TableRow key={point.validAt}>
                      <TableCell>{formatMicrogridDateTime(point.validAt)}</TableCell>
                      <TableCell className="text-right">{formatNumber(point.loadKw)}</TableCell>
                      <TableCell className="text-right">{formatNumber(point.pvKw)}</TableCell>
                      <TableCell className="text-right">{formatNumber(point.gridImportKw)}</TableCell>
                      <TableCell className="text-right">{formatNumber(point.batteryDischargeKw - point.batteryChargeKw)}</TableCell>
                      <TableCell className="text-right">{formatNumber(point.socPct)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            <AdminPanel title="目标函数分解" contentClassName="space-y-3 p-4 text-sm">
              {Object.entries(run.data?.costBreakdown ?? {}).map(([key, value]) => (
                <div className="flex justify-between" key={key}>
                  <span className="text-muted-foreground">{costLabel[key] ?? key}</span>
                  <span className="tabular-nums">¥ {formatNumber(value, 2)}</span>
                </div>
              ))}
              <div className="border-border/70 border-t pt-3">
                <div className="flex justify-between font-medium">
                  <span>目标值</span>
                  <span className="tabular-nums">¥ {formatNumber(run.data?.objectiveCny, 2)}</span>
                </div>
              </div>
            </AdminPanel>
          </div>
          {(run.data?.diagnostics.length ?? 0) > 0 && (
            <AdminPanel title="约束诊断" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>约束</TableHead>
                    <TableHead>级别</TableHead>
                    <TableHead>诊断</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {run.data?.diagnostics.map((item) => (
                    <TableRow key={item.constraint}>
                      <TableCell>{item.constraint}</TableCell>
                      <TableCell>{item.severity}</TableCell>
                      <TableCell>{item.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
          )}
          {actions.dispatch.data && (
            <AdminPanel title="最近调度回执" contentClassName="grid gap-3 p-4 md:grid-cols-4">
              <MetricTile label="指令数" value={actions.dispatch.data.commandCount} />
              <MetricTile label="接受/执行" value={actions.dispatch.data.acceptedCount} tone="success" />
              <MetricTile label="拒绝" value={actions.dispatch.data.rejectedCount} />
              <MetricTile label="调度通道" value="调度服务" />
            </AdminPanel>
          )}
        </>
      )}
      <Dialog onOpenChange={setConfirmOpen} open={confirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>提交调度计划</DialogTitle>
            <DialogDescription>确认提交当前24小时调度计划？</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setConfirmOpen(false)} variant="outline">
              取消
            </Button>
            <Button
              onClick={() => {
                if (run.data?.id) actions.dispatch.mutate(run.data.id)
                setConfirmOpen(false)
              }}
            >
              确认提交
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Sheet open={strategyOpen} onOpenChange={setStrategyOpen}>
        <SheetContent className="sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>策略参数</SheetTitle>
          </SheetHeader>
          <div className="flex-1 space-y-5 overflow-y-auto px-4">
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(strategyPresets).map(([key, item]) => (
                <Button
                  key={key}
                  variant={preset === key ? "default" : "outline"}
                  onClick={() => {
                    setPreset(key as keyof typeof strategyPresets)
                    setWeights({ energy: item.energy, peak: item.peak, carbon: item.carbon })
                  }}
                >
                  {item.label}
                </Button>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <NumberField label="电费权重" max={10} value={weights.energy} onChange={(energy) => setWeights({ ...weights, energy })} />
              <NumberField label="峰值权重" max={10} value={weights.peak} onChange={(peak) => setWeights({ ...weights, peak })} />
              <NumberField label="碳成本权重" max={10} value={weights.carbon} onChange={(carbon) => setWeights({ ...weights, carbon })} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <NumberField label="SOC下限" value={socMinimum} onChange={setSocMinimum} />
              <NumberField label="SOC上限" value={socMaximum} onChange={setSocMaximum} />
              <NumberField label="期末SOC" value={terminalSoc} onChange={setTerminalSoc} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <NumberField label="备用裕度 %" value={reserveMargin} onChange={setReserveMargin} />
              <NumberField label="储能退化 元/kWh" max={10} value={degradationCost} onChange={setDegradationCost} />
              <NumberField label="碳价 元/kg" max={10} value={carbonPrice} onChange={setCarbonPrice} />
            </div>
            <div className="grid gap-3 border-border border-t pt-4">
              <div className="space-y-1.5">
                <Label>分时电价方案</Label>
                <Select value={tariffPlanId ? String(tariffPlanId) : undefined} onValueChange={(value) => setTariffPlanId(Number(value))}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择分时电价" />
                  </SelectTrigger>
                  <SelectContent>
                    {(economics.data?.tariffPlans ?? []).map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>电网排放因子</Label>
                <Select value={emissionFactorId ? String(emissionFactorId) : undefined} onValueChange={(value) => setEmissionFactorId(Number(value))}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择排放因子" />
                  </SelectTrigger>
                  <SelectContent>
                    {(economics.data?.emissionFactors ?? []).map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.value} {item.unit} · {item.year}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <SheetFooter>
            <Button onClick={saveStrategy}>保存为待发布版本</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
      <Sheet open={comparisonOpen} onOpenChange={setComparisonOpen}>
        <SheetContent className="sm:max-w-4xl">
          <SheetHeader>
            <SheetTitle>策略方案比较</SheetTitle>
          </SheetHeader>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 pb-6">
            <div className="flex flex-wrap gap-2">
              {(runs.data ?? []).slice(0, 8).map((item) => (
                <Button
                  key={item.id}
                  size="sm"
                  variant={selectedRunIds.includes(item.id) ? "default" : "outline"}
                  onClick={() =>
                    setSelectedRunIds((current) => (current.includes(item.id) ? current.filter((id) => id !== item.id) : current.length < 3 ? [...current, item.id] : current))
                  }
                >
                  #{item.id} {item.purpose === "trial" ? "试算" : "正式"}
                </Button>
              ))}
            </div>
            <AdminPanel title="同窗口指标对比" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>方案</TableHead>
                    <TableHead className="text-right">费用</TableHead>
                    <TableHead className="text-right">节省</TableHead>
                    <TableHead className="text-right">峰值</TableHead>
                    <TableHead className="text-right">减排</TableHead>
                    <TableHead className="text-right">EV完成率</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(comparison.data?.runs ?? []).map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        #{item.id} {item.purpose}
                      </TableCell>
                      <TableCell className="text-right">¥ {formatNumber(item.objectiveCny, 2)}</TableCell>
                      <TableCell className="text-right">¥ {formatNumber(item.savingsCny, 2)}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.optimizedPeakKw)} kW</TableCell>
                      <TableCell className="text-right">{formatNumber(item.carbonReductionKg)} kg</TableCell>
                      <TableCell className="text-right">{item.evCompletionPct == null ? "—" : `${formatNumber(item.evCompletionPct)}%`}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            {comparisonRuns.length >= 2 ? (
              <div className="grid gap-3 xl:grid-cols-2">
                <ChartPanel title="方案购电曲线" unit="kW" source="同一预测窗口" option={comparisonGridOption} height={300} />
                <ChartPanel title="方案SOC轨迹" unit="%" source="同一预测窗口" option={comparisonSocOption} height={300} />
              </div>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

const costLabel: Record<string, string> = {
  energy_cost_cny: "购售电费用",
  demand_cost_cny: "需量费用",
  battery_degradation_cny: "储能退化",
  carbon_cost_cny: "碳成本",
  curtailment_cost_cny: "弃光成本",
  generator_cost_cny: "备用机组",
  flexibility_penalty_cny: "柔性违约成本",
}

type StrategyWeights = { energy: number; peak: number; carbon: number }

const strategyPresets = {
  cost: { label: "费用优先", energy: 1, peak: 1, carbon: 0.5 },
  balanced: { label: "综合平衡", energy: 1, peak: 1.5, carbon: 1.5 },
  carbon: { label: "减碳优先", energy: 0.7, peak: 0.7, carbon: 4 },
  peak: { label: "削峰优先", energy: 0.7, peak: 4, carbon: 1 },
} as const

function NumberField({ label, value, onChange, max = 100 }: { label: string; value: number; onChange: (value: number) => void; max?: number }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input max={max} min={0} step={0.1} type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  )
}
