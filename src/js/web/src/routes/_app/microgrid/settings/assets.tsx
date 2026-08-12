import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, RefreshCw } from "lucide-react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getAssetTypeLabel, MicrogridSettingsTabs, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useMicrogridAssets, useMicrogridScenarios } from "@/lib/api/hooks/microgrid"

export const Route = createFileRoute("/_app/microgrid/settings/assets")({ component: MicrogridAssetSettingsPage })

function MicrogridAssetSettingsPage() {
  const assets = useMicrogridAssets()
  const scenarios = useMicrogridScenarios()
  const published = scenarios.data?.find((scenario) => scenario.status === "published")
  const assumed = assets.data?.filter((asset) => asset.sourceKind === "enterprise_assumption").length ?? 0

  return (
    <AdminPageScaffold
      title="设备与场景"
      status={<RunStatusBadge status={published?.status === "published" ? "completed" : "queued"} />}
      meta={published ? `${published.name} v${published.version} · ${published.sourceName}` : "尚无已发布场景"}
      topActions={
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/microgrid/operations">
              <ArrowLeft />
              返回监控
            </Link>
          </Button>
          <Button disabled={assets.isFetching || scenarios.isFetching} onClick={() => void Promise.all([assets.refetch(), scenarios.refetch()])} size="sm" variant="outline">
            <RefreshCw className={assets.isFetching || scenarios.isFetching ? "animate-spin" : ""} />
            刷新
          </Button>
        </div>
      }
      tabs={<MicrogridSettingsTabs />}
      filters={
        <ContextBar>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">场景状态</span>
            <div className="font-medium text-sm">{published ? "已发布 / 不可修改" : "未发布"}</div>
          </div>
          <div className="min-w-64">
            <span className="text-muted-foreground text-xs">参数来源</span>
            <div className="truncate font-medium text-sm">{published?.sourceName ?? "-"}</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="资源总数" value={assets.data?.length ?? 0} unit="个" />
          <MetricTile label="可调资源" value={assets.data?.filter((asset) => asset.controllable).length ?? 0} unit="个" />
          <MetricTile label="演示假设" value={assumed} unit="项" />
          <MetricTile label="场景版本" value={published?.version ?? "-"} unit={published ? "版" : ""} />
        </MetricStrip>
      }
    >
      {!assets.isLoading && (assets.data?.length ?? 0) === 0 ? (
        <AdminEmptyState title="尚无设备配置" description="请先从运行总览初始化祥泰演示场景。" />
      ) : (
        <AdminPanel title="资源参数与来源" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>资源</TableHead>
                <TableHead>类型</TableHead>
                <TableHead className="text-right">额定功率</TableHead>
                <TableHead className="text-right">额定容量</TableHead>
                <TableHead>可调</TableHead>
                <TableHead>来源</TableHead>
                <TableHead className="text-right">置信度</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(assets.data ?? []).map((asset) => (
                <TableRow key={asset.id}>
                  <TableCell>
                    <div className="font-medium">{asset.name}</div>
                    <div className="text-muted-foreground text-xs">{asset.code}</div>
                  </TableCell>
                  <TableCell>{getAssetTypeLabel(asset.assetType)}</TableCell>
                  <TableCell className="text-right">{formatNumber(asset.ratedPowerKw)} kW</TableCell>
                  <TableCell className="text-right">{asset.ratedEnergyKwh ? `${formatNumber(asset.ratedEnergyKwh)} kWh` : "-"}</TableCell>
                  <TableCell>{asset.controllable ? "是" : "否"}</TableCell>
                  <TableCell>{asset.sourceName}</TableCell>
                  <TableCell className="text-right">{formatNumber((asset.confidenceLevel ?? 0) * 100, 0)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminPanel>
      )}
    </AdminPageScaffold>
  )
}
