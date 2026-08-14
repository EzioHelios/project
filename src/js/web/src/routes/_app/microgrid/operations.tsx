import { createFileRoute, Link } from "@tanstack/react-router"
import { RefreshCw, Settings2 } from "lucide-react"
import { useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getAssetTypeLabel, MicrogridOperatingBadge } from "@/components/microgrid/microgrid-page"
import { AssetFaceplate, ScadaRuntime, type ScadaSelection } from "@/components/microgrid/scada"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type MicrogridAsset, useMicrogridTopology } from "@/lib/api/hooks/microgrid"
import { formatMicrogridTime } from "@/lib/microgrid-time"

export const Route = createFileRoute("/_app/microgrid/operations")({ component: MicrogridOperationsPage })

function MicrogridOperationsPage() {
  const [selection, setSelection] = useState<ScadaSelection | null>(null)
  const query = useMicrogridTopology()
  const topology = query.data
  const assets = topology?.assets ?? []
  const storage = assets.find((asset) => asset.assetType === "storage")
  const controllable = assets.filter((asset) => asset.controllable)

  return (
    <AdminPageScaffold
      title="运行监控"
      status={<MicrogridOperatingBadge />}
      meta={topology?.site?.name}
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
        <AdminEmptyState title="尚未配置微电网站点" description="请先完成站点与设备配置。" />
      ) : (
        <div className="space-y-3">
          <AdminPanel title="一次系统运行图" contentClassName="p-0">
            <ScadaRuntime onSelect={setSelection} topology={topology} />
          </AdminPanel>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <AdminPanel title="设备状态" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>设备</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>模式</TableHead>
                    <TableHead className="text-right">功率</TableHead>
                    <TableHead className="text-right">数据时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assets.map((asset) => (
                    <TableRow key={asset.id}>
                      <TableCell>
                        <div className="font-medium">{asset.name}</div>
                        <div className="text-muted-foreground text-xs">{getAssetTypeLabel(asset.assetType)}</div>
                      </TableCell>
                      <TableCell>
                        <span className={asset.online ? "text-[hsl(var(--status-success))]" : "text-muted-foreground"}>{asset.online ? "在线" : "离线"}</span>
                      </TableCell>
                      <TableCell>{getAssetOperatingMode(asset)}</TableCell>
                      <TableCell className="text-right">
                        {formatNumber(asset.activePowerKw)} kW
                        {asset.socPct !== null && <div className="text-muted-foreground text-xs">SOC {formatNumber(asset.socPct)}%</div>}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground text-xs">{formatMicrogridTime(asset.observedAt)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            <AdminPanel title="可调资源边界" contentClassName="divide-y p-0">
              {controllable.map((asset) => (
                <div className="flex items-center justify-between gap-3 px-4 py-3" key={asset.id}>
                  <div>
                    <div className="font-medium text-sm">{asset.name}</div>
                    <div className="mt-1 text-muted-foreground text-xs">{asset.assetType === "storage" ? "功率目标与SOC边界" : "有功功率目标"}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-sm tabular-nums">0–{formatNumber(asset.ratedPowerKw)} kW</div>
                  </div>
                </div>
              ))}
            </AdminPanel>
          </div>
          <AssetFaceplate onOpenChange={(open) => !open && setSelection(null)} selection={selection} />
        </div>
      )}
    </AdminPageScaffold>
  )
}

function getAssetOperatingMode(asset: MicrogridAsset) {
  if (!asset.online) return "离线"
  if (asset.assetType === "storage") {
    if ((asset.activePowerKw ?? 0) < -0.1) return "充电"
    if ((asset.activePowerKw ?? 0) > 0.1) return "放电"
    return "待机"
  }
  if (asset.assetType === "pv") return "并网"
  if (asset.assetType === "grid") return "供电"
  if (asset.assetType === "charger") return "充电"
  if (asset.assetType === "generator") return "待机"
  return "运行"
}
