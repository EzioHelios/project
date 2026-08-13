import { createFileRoute } from "@tanstack/react-router"
import { Play } from "lucide-react"
import { useMemo, useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTabsList, ChartPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsTrigger } from "@/components/ui/tabs"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useMicrogridActions, useMicrogridForecastRun, useMicrogridForecastRuns, useMicrogridOverview } from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/forecast")({ component: MicrogridForecastPage })

function MicrogridForecastPage() {
  const chartTheme = useAdminChartTheme("energy")
  const [seriesCode, setSeriesCode] = useState<"load" | "pv" | "soc">("load")
  const overview = useMicrogridOverview()
  const runs = useMicrogridForecastRuns()
  const latestRunId = runs.data?.[0]?.id
  const run = useMicrogridForecastRun(latestRunId)
  const actions = useMicrogridActions()
  const points = useMemo(
    () =>
      (run.data?.points ?? [])
        .filter((point) => point.seriesCode === seriesCode)
        .map((point) => ({ period: formatMicrogridDateTime(point.validAt), p10: point.p10, p50: point.p50, p90: point.p90 })),
    [run.data?.points, seriesCode],
  )
  const option = createTrendChartOption(
    chartTheme,
    points,
    [
      { key: "p10", label: "P10", colorKey: "neutral" },
      { key: "p50", label: "P50", colorKey: "energy" },
      { key: "p90", label: "P90", colorKey: "warning" },
    ],
    { periodKey: "period", includeZeroSeries: true },
  )
  const unit = seriesCode === "soc" ? "%" : "kW"
  const siteId = overview.data?.site?.id
  const scenarioId = overview.data?.scenario?.id

  return (
    <AdminPageScaffold
      title="预测分析"
      status={<RunStatusBadge status={run.data?.status} />}
      meta={run.data ? `${run.data.modelVersion} · 预测间隔 ${run.data.intervalMinutes} 分钟` : "尚无预测运行"}
      topActions={
        <Button disabled={!siteId || actions.runForecast.isPending} onClick={() => siteId && actions.runForecast.mutate({ siteId, scenarioId: scenarioId ?? undefined })} size="sm">
          <Play />
          {actions.runForecast.isPending ? "计算中" : "重新预测"}
        </Button>
      }
      filters={
        <ContextBar>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">预测范围</span>
            <div className="font-medium text-sm">未来24小时 / 96点</div>
          </div>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">天气来源</span>
            <div className="font-medium text-sm">Open-Meteo / 模拟回退</div>
          </div>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">数据模式</span>
            <div className="font-medium text-sm">实测负荷优先</div>
          </div>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">时间基准</span>
            <div className="font-medium text-sm">站点时间 UTC+8</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="MAE" value={formatNumber(run.data?.metrics.mae_kw, 2)} unit="kW" />
          <MetricTile label="RMSE" value={formatNumber(run.data?.metrics.rmse_kw, 2)} unit="kW" />
          <MetricTile label="MAPE" value={formatNumber(run.data?.metrics.mape_pct, 2)} unit="%" />
          <MetricTile label="区间覆盖率" value={formatNumber((run.data?.metrics.coverage ?? 0) * 100, 1)} unit="%" />
        </MetricStrip>
      }
    >
      {!run.data && !run.isLoading ? (
        <AdminEmptyState
          title="尚无预测结果"
          description="初始化祥泰场景后运行首个24小时预测。"
          actions={
            <Button disabled={!siteId} onClick={() => siteId && actions.runForecast.mutate({ siteId, scenarioId: scenarioId ?? undefined })}>
              运行预测
            </Button>
          }
        />
      ) : (
        <>
          <Tabs value={seriesCode} onValueChange={(value) => setSeriesCode(value as typeof seriesCode)}>
            <AdminTabsList className="max-w-xl">
              <TabsTrigger value="load">负荷预测</TabsTrigger>
              <TabsTrigger value="pv">光伏预测</TabsTrigger>
              <TabsTrigger value="soc">SOC预测</TabsTrigger>
            </AdminTabsList>
          </Tabs>
          <ChartPanel
            title={seriesCode === "load" ? "仓库负荷分位数预测" : seriesCode === "pv" ? "光伏出力分位数预测" : "储能SOC预测包络"}
            unit={unit}
            source={run.data?.inputSnapshot.weatherProvider ? String(run.data.inputSnapshot.weatherProvider) : "模型输入快照"}
            updatedAt={formatMicrogridDateTime(run.data?.completedAt)}
            option={option}
            height={360}
          />
          <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <AdminPanel title="预测运行记录" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>运行时间</TableHead>
                    <TableHead>模型</TableHead>
                    <TableHead>范围</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(runs.data ?? []).slice(0, 8).map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{formatMicrogridDateTime(item.completedAt)}</TableCell>
                      <TableCell>{item.modelVersion}</TableCell>
                      <TableCell>24h / {item.intervalMinutes}min</TableCell>
                      <TableCell>
                        <RunStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            <AdminPanel title="模型输入快照" contentClassName="space-y-3 p-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">场景版本</span>
                <span>v{String(run.data?.inputSnapshot.scenarioVersion ?? "-")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">负荷模型</span>
                <span className="max-w-52 truncate">{run.data?.metrics.model ?? run.data?.modelVersion ?? "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">PV模型</span>
                <span>pvlib / PVWatts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">SOC模型</span>
                <span>物理状态方程</span>
              </div>
            </AdminPanel>
          </div>
        </>
      )}
    </AdminPageScaffold>
  )
}
