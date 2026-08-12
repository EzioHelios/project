import { createFileRoute, Link } from "@tanstack/react-router"
import { RefreshCw, Settings2 } from "lucide-react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getAssetTypeLabel, MicrogridSingleLine, ShadowModeBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useMicrogridTopology } from "@/lib/api/hooks/microgrid"

export const Route = createFileRoute("/_app/microgrid/operations")({ component: MicrogridOperationsPage })

function MicrogridOperationsPage() {
  const query = useMicrogridTopology()
  const topology = query.data
  const assets = topology?.assets ?? []
  const storage = assets.find((asset) => asset.assetType === "storage")
  const controllable = assets.filter((asset) => asset.controllable)

  return (
    <AdminPageScaffold
      title="运行监控"
      status={<ShadowModeBadge />}
      meta={topology?.site ? `${topology.site.name} · 10–15秒状态轮询` : undefined}
      topActions={
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/microgrid/settings/assets">
              <Settings2 />
              资源配置
            </Link>
          </Button>
          <Button disabled={query.isFetching} onClick={() => void query.refetch()} size="sm" variant="outline">
            <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
            刷新状态
          </Button>
        </div>
      }
      filters={
        <ContextBar>
          <div className="min-w-44">
            <span className="text-muted-foreground text-xs">控制边界</span>
            <div className="font-medium text-sm">功率/SOC目标</div>
          </div>
          <div className="min-w-44">
            <span className="text-muted-foreground text-xs">现场系统</span>
            <div className="font-medium text-sm">模拟调度</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="在线设备" value={assets.filter((asset) => asset.online).length} unit={`/ ${assets.length}`} />
          <MetricTile label="可调资源" value={controllable.length} unit="个" />
          <MetricTile label="储能SOC" value={formatNumber(storage?.socPct)} unit="%" />
          <MetricTile label="活动告警" value={assets.filter((asset) => asset.alarmLevel !== "normal").length} tone="success" />
        </MetricStrip>
      }
    >
      {!topology?.configured ? (
        <AdminEmptyState title="尚未配置微电网站点" description="请先在运行总览初始化祥泰演示。" />
      ) : (
        <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
          <AdminPanel title="一次系统拓扑" contentClassName="p-0">
            <MicrogridSingleLine topology={topology} />
          </AdminPanel>
          <AdminPanel title="设备状态与中控边界" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>设备</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">功率</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assets.map((asset) => (
                  <TableRow key={asset.id}>
                    <TableCell>
                      <div className="font-medium">{asset.name}</div>
                      <div className="text-muted-foreground text-xs">
                        {getAssetTypeLabel(asset.assetType)} · {asset.code}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={asset.online ? "text-[hsl(var(--status-success))]" : "text-muted-foreground"}>{asset.online ? "在线" : "离线"}</span>
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(asset.activePowerKw)} kW{asset.socPct !== null && <div className="text-muted-foreground text-xs">SOC {formatNumber(asset.socPct)}%</div>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminPanel>
        </div>
      )}
      <AdminPanel title="可控操作范围" contentClassName="grid gap-3 p-4 md:grid-cols-3">
        {controllable.map((asset) => (
          <div className="rounded-md border border-border/70 bg-muted/20 p-3" key={asset.id}>
            <div className="font-medium text-sm">{asset.name}</div>
            <div className="mt-2 text-muted-foreground text-xs">允许目标：有功功率{asset.assetType === "storage" ? "与SOC边界" : ""}</div>
            <div className="mt-1 font-medium text-sm tabular-nums">0–{formatNumber(asset.ratedPowerKw)} kW</div>
            <div className="mt-2 text-muted-foreground text-xs">保护、断路器和并离网控制不在本层执行</div>
          </div>
        ))}
      </AdminPanel>
    </AdminPageScaffold>
  )
}
