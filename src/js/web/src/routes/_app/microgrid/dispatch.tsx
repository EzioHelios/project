import { createFileRoute } from "@tanstack/react-router"
import { RefreshCw } from "lucide-react"
import { useMemo, useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useMicrogridDispatchBatch, useMicrogridDispatchBatches } from "@/lib/api/hooks/microgrid"
import { formatMicrogridDateTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/dispatch")({ component: MicrogridDispatchPage })

function MicrogridDispatchPage() {
  const chartTheme = useAdminChartTheme("energy")
  const batches = useMicrogridDispatchBatches()
  const [selectedId, setSelectedId] = useState<number>()
  const batch = useMicrogridDispatchBatch(selectedId)
  const items = batches.data ?? []
  const executed = items.reduce((total, item) => total + item.acceptedCount, 0)
  const rejected = items.reduce((total, item) => total + item.rejectedCount, 0)
  const curve = useMemo(
    () =>
      (batch.data?.receipts ?? []).map((item) => ({
        period: formatMicrogridDateTime(item.scheduledAt),
        targetKw: item.targetPowerKw,
        executedKw: item.executedPowerKw,
      })),
    [batch.data?.receipts],
  )
  const option = createTrendChartOption(
    chartTheme,
    curve,
    [
      { key: "targetKw", label: "目标功率", colorKey: "energy" },
      { key: "executedKw", label: "反馈功率", colorKey: "carbon" },
    ],
    { periodKey: "period", includeZeroSeries: true },
  )

  return (
    <AdminPageScaffold
      title="调度记录"
      status={<RunStatusBadge status={items[0]?.status} />}
      meta={items[0]?.completedAt ? `最近更新 ${formatMicrogridDateTime(items[0].completedAt)}` : undefined}
      topActions={
        <Button disabled={batches.isFetching} onClick={() => void batches.refetch()} size="sm" variant="outline">
          <RefreshCw className={batches.isFetching ? "animate-spin" : ""} />
          刷新
        </Button>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="调度批次" value={items.length} unit="批" />
          <MetricTile label="指令总数" value={items.reduce((total, item) => total + item.commandCount, 0)} unit="条" />
          <MetricTile label="已接收" value={executed} unit="条" tone="success" />
          <MetricTile label="拒绝" value={rejected} unit="条" tone={rejected > 0 ? "warning" : "default"} />
        </MetricStrip>
      }
    >
      {items.length === 0 && !batches.isLoading ? (
        <AdminEmptyState title="尚无调度记录" description="优化计划提交后，调度记录将在此更新。" />
      ) : (
        <AdminPanel title="调度批次台账" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>批次</TableHead>
                <TableHead>策略版本</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">指令</TableHead>
                <TableHead className="text-right">已接收</TableHead>
                <TableHead className="text-right">拒绝</TableHead>
                <TableHead>完成时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow className="cursor-pointer" key={item.id} onClick={() => setSelectedId(item.id)}>
                  <TableCell className="font-medium">#{item.id}</TableCell>
                  <TableCell>{item.scenarioVersion ? `策略 v${item.scenarioVersion}` : "-"}</TableCell>
                  <TableCell>
                    <RunStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{item.commandCount}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.acceptedCount}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.rejectedCount}</TableCell>
                  <TableCell>{formatMicrogridDateTime(item.completedAt)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminPanel>
      )}
      <Sheet open={Boolean(selectedId)} onOpenChange={(open) => !open && setSelectedId(undefined)}>
        <SheetContent className="sm:max-w-3xl">
          <SheetHeader>
            <SheetTitle>调度批次 #{selectedId}</SheetTitle>
          </SheetHeader>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 pb-6">
            <ChartPanel title="目标与反馈偏差" unit="kW" source="调度执行记录" option={option} height={260} />
            <AdminPanel title="资源执行汇总" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>资源</TableHead>
                    <TableHead className="text-right">指令</TableHead>
                    <TableHead className="text-right">裁剪</TableHead>
                    <TableHead className="text-right">拒绝</TableHead>
                    <TableHead className="text-right">偏差</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(batch.data?.assetSummaries ?? []).map((item) => (
                    <TableRow key={item.assetCode}>
                      <TableCell>{item.assetCode}</TableCell>
                      <TableCell className="text-right">{item.commandCount}</TableCell>
                      <TableCell className="text-right">{item.clippedCount}</TableCell>
                      <TableCell className="text-right">{item.rejectedCount}</TableCell>
                      <TableCell className="text-right">{formatNumber(item.absoluteDeviationKwh, 3)} kWh</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
          </div>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}
