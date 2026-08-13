import { createFileRoute } from "@tanstack/react-router"
import { Play, Send } from "lucide-react"
import { useMemo, useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useMicrogridActions, useMicrogridForecastRuns, useMicrogridOptimizationRun, useMicrogridOptimizationRuns } from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/optimization")({ component: MicrogridOptimizationPage })

function MicrogridOptimizationPage() {
  const chartTheme = useAdminChartTheme("energy")
  const [confirmOpen, setConfirmOpen] = useState(false)
  const forecastRuns = useMicrogridForecastRuns()
  const runs = useMicrogridOptimizationRuns()
  const latestRunId = runs.data?.[0]?.id
  const run = useMicrogridOptimizationRun(latestRunId)
  const actions = useMicrogridActions()
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
  const latestForecastId = forecastRuns.data?.find((item) => item.status === "completed")?.id
  const isFeasible = run.data?.status === "optimal" || run.data?.status === "feasible"

  return (
    <AdminPageScaffold
      title="智能优化"
      status={<RunStatusBadge status={run.data?.status} />}
      meta={run.data ? `${run.data.solver} · ${formatNumber((run.data.mipGap ?? 0) * 100, 2)}% Gap · 96点计划` : "尚无优化运行"}
      topActions={
        <div className="flex gap-2">
          <Button
            disabled={!latestForecastId || actions.runOptimization.isPending}
            onClick={() => latestForecastId && actions.runOptimization.mutate(latestForecastId)}
            size="sm"
            variant="outline"
          >
            <Play />
            {actions.runOptimization.isPending ? "求解中" : "重新优化"}
          </Button>
          <Button disabled={!isFeasible || actions.dispatch.isPending} onClick={() => setConfirmOpen(true)} size="sm">
            <Send />
            模拟下发
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
            <span className="text-muted-foreground text-xs">执行模式</span>
            <div className="font-medium text-sm">模拟闭环</div>
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
          <MetricTile label="节省" value={formatNumber(run.data?.savingsCny, 2)} unit="元/日" tone="success" />
          <MetricTile label="削峰" value={formatNumber(run.data?.peakReductionKw)} unit="kW" />
          <MetricTile label="减排" value={formatNumber(run.data?.carbonReductionKg)} unit="kgCO₂e" />
          <MetricTile label="求解耗时" value={formatNumber(run.data?.solverSeconds, 3)} unit="s" />
        </MetricStrip>
      }
    >
      {!run.data && !run.isLoading ? (
        <AdminEmptyState
          title="尚无优化结果"
          description="先完成负荷与光伏预测，再运行24小时滚动优化。"
          actions={
            <Button disabled={!latestForecastId} onClick={() => latestForecastId && actions.runOptimization.mutate(latestForecastId)}>
              运行优化
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <ChartPanel title="资源调度计划" unit="kW" source="Pyomo / HiGHS" updatedAt={formatMicrogridDateTime(run.data?.completedAt)} option={powerOption} height={360} />
            <ChartPanel title="储能SOC轨迹" unit="%" source="物理状态方程" updatedAt={formatMicrogridDateTime(run.data?.completedAt)} option={socOption} height={360} />
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
            <AdminPanel title="最近模拟调度回执" contentClassName="grid gap-3 p-4 md:grid-cols-4">
              <MetricTile label="指令数" value={actions.dispatch.data.commandCount} />
              <MetricTile label="接受/执行" value={actions.dispatch.data.acceptedCount} tone="success" />
              <MetricTile label="拒绝" value={actions.dispatch.data.rejectedCount} />
              <MetricTile label="调度通道" value="模拟调度" />
            </AdminPanel>
          )}
        </>
      )}
      <Dialog onOpenChange={setConfirmOpen} open={confirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>提交模拟调度</DialogTitle>
            <DialogDescription>本操作仅生成影子控制指令和执行回执，不触达现场断路器、保护或并离网控制。</DialogDescription>
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
              确认模拟下发
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
}
