import { createFileRoute } from "@tanstack/react-router"
import { RefreshCw, Sparkles } from "lucide-react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getAssetTypeLabel, RunStatusBadge, ShadowModeBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useMicrogridActions, useMicrogridOverview } from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/overview")({ component: MicrogridOverviewPage })

function MicrogridOverviewPage() {
  const chartTheme = useAdminChartTheme("energy")
  const overview = useMicrogridOverview()
  const actions = useMicrogridActions()
  const data = overview.data
  const trend = (data?.trend ?? []).map((point) => ({ ...point, period: formatMicrogridDateTime(point.period) }))
  const trendOption = createTrendChartOption(
    chartTheme,
    trend,
    [
      { key: "loadKw", label: "负荷预测", colorKey: "energy" },
      { key: "pvKw", label: "光伏预测", colorKey: "carbon" },
      { key: "gridImportKw", label: "计划购电", colorKey: "cost" },
    ],
    { periodKey: "period", includeZeroSeries: true },
  )

  if (!overview.isLoading && !data?.configured) {
    return (
      <AdminPageScaffold title="运行总览" status={<ShadowModeBadge />}>
        <AdminEmptyState
          title="祥泰微电网演示尚未初始化"
          description="创建祥泰演示场景并生成首轮预测与优化结果。"
          actions={
            <Button disabled={actions.bootstrap.isPending} onClick={() => actions.bootstrap.mutate()}>
              <Sparkles />
              {actions.bootstrap.isPending ? "正在初始化" : "初始化祥泰演示"}
            </Button>
          }
        />
      </AdminPageScaffold>
    )
  }

  const metrics = data?.metrics
  return (
    <AdminPageScaffold
      title="运行总览"
      status={<ShadowModeBadge />}
      meta={data?.site ? `${data.site.name} · 场景 ${data.scenario?.name ?? "-"} v${data.scenario?.version ?? "-"}` : undefined}
      topActions={
        <Button disabled={overview.isFetching} onClick={() => void overview.refetch()} size="sm" variant="outline">
          <RefreshCw className={overview.isFetching ? "animate-spin" : ""} />
          刷新
        </Button>
      }
      filters={
        <ContextBar>
          <div className="min-w-44">
            <span className="text-muted-foreground text-xs">站点</span>
            <div className="font-medium text-sm">{data?.site?.name ?? "-"}</div>
          </div>
          <div className="min-w-40">
            <span className="text-muted-foreground text-xs">数据模式</span>
            <div className="font-medium text-sm">影子运行</div>
          </div>
          <div className="min-w-56">
            <span className="text-muted-foreground text-xs">参数来源</span>
            <div className="truncate font-medium text-sm">{data?.scenario?.sourceName ?? "-"}</div>
          </div>
          <div className="min-w-40">
            <span className="text-muted-foreground text-xs">时间基准</span>
            <div className="font-medium text-sm">站点时间 UTC+8</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip className="xl:grid-cols-6">
          <MetricTile label="PCC功率" value={formatNumber(metrics?.pccPowerKw)} unit="kW" meta="模拟状态投影" />
          <MetricTile label="光伏功率" value={formatNumber(metrics?.pvPowerKw)} unit="kW" />
          <MetricTile label="储能SOC" value={formatNumber(metrics?.socPct)} unit="%" />
          <MetricTile label="优化节省" value={formatNumber(metrics?.savingsCny, 2)} unit="元/日" tone="success" />
          <MetricTile label="削减峰值" value={formatNumber(metrics?.peakReductionKw)} unit="kW" />
          <MetricTile label="减排" value={formatNumber(metrics?.carbonReductionKg)} unit="kgCO₂e" />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <ChartPanel
          title="未来24小时功率计划"
          unit="kW"
          source="负荷/PV预测与MILP计划"
          updatedAt={formatMicrogridDateTime(data?.optimizationRun?.completedAt ?? data?.forecastRun?.completedAt)}
          option={trendOption}
          height={330}
        />
        <AdminPanel title="计算链状态" contentClassName="divide-y divide-border/60 p-0">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-sm">负荷与光伏预测</span>
            <RunStatusBadge status={data?.forecastRun?.status} />
          </div>
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-sm">滚动优化</span>
            <RunStatusBadge status={data?.optimizationRun?.status} />
          </div>
          <div className="grid grid-cols-2 gap-3 px-4 py-3 text-sm">
            <div>
              <div className="text-muted-foreground text-xs">求解器</div>
              <div className="mt-1 font-medium">{data?.optimizationRun?.solver ?? "HiGHS"}</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">求解耗时</div>
              <div className="mt-1 font-medium tabular-nums">{formatNumber(data?.optimizationRun?.solverSeconds, 3)} s</div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">在线资源</div>
              <div className="mt-1 font-medium tabular-nums">
                {metrics?.onlineAssets ?? 0}/{metrics?.totalAssets ?? 0}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">告警</div>
              <div className="mt-1 font-medium tabular-nums">{metrics?.alarmCount ?? 0}</div>
            </div>
          </div>
        </AdminPanel>
      </div>
      <AdminPanel title="资源运行状态" contentClassName="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>资源</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">当前功率</TableHead>
              <TableHead className="text-right">额定功率</TableHead>
              <TableHead>数据来源</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.assets ?? []).map((asset) => (
              <TableRow key={asset.id}>
                <TableCell className="font-medium">{asset.name}</TableCell>
                <TableCell>{getAssetTypeLabel(asset.assetType)}</TableCell>
                <TableCell>{asset.online ? "在线" : "离线"}</TableCell>
                <TableCell className="text-right">{formatNumber(asset.activePowerKw)} kW</TableCell>
                <TableCell className="text-right">{formatNumber(asset.ratedPowerKw)} kW</TableCell>
                <TableCell>{asset.sourceKind === "enterprise_assumption" ? "企业演示假设" : asset.sourceKind}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminPanel>
    </AdminPageScaffold>
  )
}
