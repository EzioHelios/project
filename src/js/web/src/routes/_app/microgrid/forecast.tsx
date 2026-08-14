import { createFileRoute } from "@tanstack/react-router"
import { Play } from "lucide-react"
import { useMemo, useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTabsList, ChartPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getForecastModelLabel, RunStatusBadge } from "@/components/microgrid/microgrid-page"
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
      status={<RunStatusBadge status={run.data?.qualityStatus ?? run.data?.status} />}
      meta={run.data ? `${getForecastModelLabel(run.data.modelVersion)} · ${run.data.intervalMinutes}分钟` : "尚无预测运行"}
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
            <span className="text-muted-foreground text-xs">时间基准</span>
            <div className="font-medium text-sm">站点时间 UTC+8</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile
            label={seriesCode === "load" ? "MAE" : "预测点数"}
            value={seriesCode === "load" ? formatNumber(run.data?.metrics.mae_kw, 2) : points.length}
            unit={seriesCode === "load" ? "kW" : "点"}
          />
          <MetricTile
            label={seriesCode === "load" ? "RMSE" : "预测算法"}
            value={seriesCode === "load" ? formatNumber(run.data?.metrics.rmse_kw, 2) : seriesCode === "pv" ? "pvlib ModelChain" : "状态转移模型"}
            unit={seriesCode === "load" ? "kW" : ""}
          />
          <MetricTile
            label={seriesCode === "load" ? "MAPE" : "质量状态"}
            value={seriesCode === "load" ? formatNumber(run.data?.metrics.mape_pct, 2) : getForecastAvailability(run.data?.qualityStatus)}
            unit={seriesCode === "load" ? "%" : ""}
            tone={run.data?.qualityStatus === "pass" ? "success" : "warning"}
          />
          <MetricTile
            label={seriesCode === "load" ? "区间覆盖率" : "数据完整率"}
            value={formatNumber(seriesCode === "load" ? (run.data?.metrics.coverage ?? 0) * 100 : run.data?.historyCoveragePct, 1)}
            unit="%"
          />
        </MetricStrip>
      }
    >
      {!run.data && !run.isLoading ? (
        <AdminEmptyState
          title="尚无预测结果"
          description="完成站点配置后即可运行24小时预测。"
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
            source={seriesCode === "load" ? getForecastModelLabel(run.data?.modelVersion) : seriesCode === "pv" ? "pvlib ModelChain / PVWatts" : "储能物理状态转移模型"}
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
                      <TableCell>{getForecastModelLabel(item.modelVersion)}</TableCell>
                      <TableCell>24h / {item.intervalMinutes}min</TableCell>
                      <TableCell>
                        <RunStatusBadge status={item.qualityStatus ?? item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            <AdminPanel title="预测模型" contentClassName="space-y-3 p-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">负荷预测</span>
                <span className="text-right">{getForecastModelLabel(run.data?.modelVersion)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">光伏预测</span>
                <span>pvlib ModelChain / PVWatts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">SOC预测</span>
                <span>物理状态转移模型</span>
              </div>
            </AdminPanel>
          </div>
        </>
      )}
    </AdminPageScaffold>
  )
}

function getForecastAvailability(status?: string | null) {
  if (status === "pass") return "可用"
  if (status === "failed") return "不可用"
  return status ? "需关注" : "-"
}
