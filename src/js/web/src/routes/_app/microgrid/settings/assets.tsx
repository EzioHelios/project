import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, DatabaseZap, Pencil, RefreshCw } from "lucide-react"
import { useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, getAssetTypeLabel, MicrogridSettingsTabs, RunStatusBadge } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  type MeterBinding,
  useMicrogridActions,
  useMicrogridAssets,
  useMicrogridBindingTemplate,
  useMicrogridDataReadiness,
  useMicrogridMeterBindings,
  useMicrogridOverview,
  useMicrogridScenarios,
} from "@/lib/api/hooks/microgrid"

export const Route = createFileRoute("/_app/microgrid/settings/assets")({ component: MicrogridAssetSettingsPage })

function MicrogridAssetSettingsPage() {
  const overview = useMicrogridOverview()
  const siteId = overview.data?.site?.id
  const assets = useMicrogridAssets(siteId)
  const scenarios = useMicrogridScenarios(siteId)
  const readiness = useMicrogridDataReadiness(siteId)
  const bindings = useMicrogridMeterBindings(siteId)
  const template = useMicrogridBindingTemplate(siteId, overview.data?.site?.bindingTemplateAvailable)
  const actions = useMicrogridActions()
  const [editingBinding, setEditingBinding] = useState<MeterBinding>()
  const published = scenarios.data?.find((scenario) => scenario.status === "published")
  const pendingReview = assets.data?.filter((asset) => asset.sourceKind === "enterprise_assumption").length ?? 0

  return (
    <AdminPageScaffold
      title="设备与场景"
      status={<RunStatusBadge status={published?.status === "published" ? "completed" : "queued"} />}
      meta={published ? `祥泰仓库策略 v${published.version}` : "尚无已发布策略"}
      topActions={
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/microgrid/operations">
              <ArrowLeft />
              返回监控
            </Link>
          </Button>
          <Button
            disabled={assets.isFetching || scenarios.isFetching || readiness.isFetching || bindings.isFetching}
            onClick={() =>
              void Promise.all([
                assets.refetch(),
                scenarios.refetch(),
                readiness.refetch(),
                bindings.refetch(),
                ...(overview.data?.site?.bindingTemplateAvailable ? [template.refetch()] : []),
              ])
            }
            size="sm"
            variant="outline"
          >
            <RefreshCw className={assets.isFetching || scenarios.isFetching || readiness.isFetching || bindings.isFetching ? "animate-spin" : ""} />
            刷新
          </Button>
          {overview.data?.site?.bindingTemplateAvailable && (
            <Button disabled={!siteId || actions.applyBindingTemplate.isPending} onClick={() => siteId && actions.applyBindingTemplate.mutate(siteId)} size="sm">
              <DatabaseZap />
              {actions.applyBindingTemplate.isPending ? "同步中" : bindings.data?.length ? "同步设备映射" : "应用设备映射"}
            </Button>
          )}
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
            <span className="text-muted-foreground text-xs">策略版本</span>
            <div className="truncate font-medium text-sm">{published ? `v${published.version}` : "-"}</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="资源总数" value={assets.data?.length ?? 0} unit="个" />
          <MetricTile label="可调资源" value={assets.data?.filter((asset) => asset.controllable).length ?? 0} unit="个" />
          <MetricTile label="待复核参数" value={pendingReview} unit="项" />
          <MetricTile label="数据完整率" value={formatNumber(readiness.data?.coveragePct, 1)} unit="%" tone={readiness.data?.ready ? "success" : "warning"} />
        </MetricStrip>
      }
    >
      {!assets.isLoading && (assets.data?.length ?? 0) === 0 ? (
        <AdminEmptyState title="尚无设备配置" description="请先完成站点初始化与设备配置。" />
      ) : (
        <>
          <AdminPanel title="设备绑定与数据就绪" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>平台设备</TableHead>
                  <TableHead>微电网资源</TableHead>
                  <TableHead>角色</TableHead>
                  <TableHead>测点</TableHead>
                  <TableHead>方向</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead className="w-16" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(bindings.data ?? template.data?.items ?? []).map((binding) => (
                  <TableRow key={`${binding.equipmentId}-${binding.assetId}`}>
                    <TableCell>
                      <div className="font-medium">{binding.equipmentName}</div>
                      <div className="text-muted-foreground text-xs">{binding.equipmentCode}</div>
                    </TableCell>
                    <TableCell>{binding.assetName}</TableCell>
                    <TableCell>{bindingRoleLabel[binding.role] ?? binding.role}</TableCell>
                    <TableCell>{binding.pointCode}</TableCell>
                    <TableCell>{binding.direction === "export" ? "反向" : "正向"}</TableCell>
                    <TableCell>{getBindingSourceLabel(binding.sourceName)}</TableCell>
                    <TableCell>
                      <Button disabled={!binding.id} onClick={() => setEditingBinding(binding)} size="icon" variant="ghost">
                        <Pencil />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!readiness.data?.ready && (readiness.data?.reasons.length ?? 0) > 0 && (
              <div className="border-border/70 border-t px-4 py-3 text-muted-foreground text-sm">{readiness.data?.reasons.map(getReadinessReasonLabel).join("；")}</div>
            )}
          </AdminPanel>
          <Sheet open={Boolean(editingBinding)} onOpenChange={(open) => !open && setEditingBinding(undefined)}>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>调整设备绑定</SheetTitle>
              </SheetHeader>
              {editingBinding && (
                <div className="flex-1 space-y-4 px-4">
                  <div className="space-y-1.5">
                    <Label>平台设备</Label>
                    <div className="rounded-md border border-border px-3 py-2 text-sm">
                      {editingBinding.equipmentName} · {editingBinding.equipmentCode}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label>微电网资源</Label>
                    <Select
                      value={String(editingBinding.assetId)}
                      onValueChange={(value) => {
                        const asset = assets.data?.find((item) => item.id === Number(value))
                        if (asset) setEditingBinding({ ...editingBinding, assetId: asset.id, assetCode: asset.code, assetName: asset.name })
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(assets.data ?? []).map((asset) => (
                          <SelectItem key={asset.id} value={String(asset.id)}>
                            {asset.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>绑定角色</Label>
                    <Select value={editingBinding.role} onValueChange={(role) => setEditingBinding({ ...editingBinding, role })}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(bindingRoleLabel).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>累计量测点</Label>
                    <Input value={editingBinding.pointCode} onChange={(event) => setEditingBinding({ ...editingBinding, pointCode: event.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>能流方向</Label>
                      <Select value={editingBinding.direction} onValueChange={(direction) => setEditingBinding({ ...editingBinding, direction })}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="import">正向</SelectItem>
                          <SelectItem value="export">反向</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>符号系数</Label>
                      <Input type="number" step="1" value={editingBinding.sign} onChange={(event) => setEditingBinding({ ...editingBinding, sign: Number(event.target.value) })} />
                    </div>
                  </div>
                </div>
              )}
              <SheetFooter>
                <Button
                  disabled={!editingBinding || !siteId || actions.replaceMeterBindings.isPending}
                  onClick={() => {
                    if (!editingBinding || !siteId) return
                    actions.replaceMeterBindings.mutate({
                      siteId,
                      bindings: (bindings.data ?? []).map((item) => (item.id === editingBinding.id ? editingBinding : item)),
                    })
                    setEditingBinding(undefined)
                  }}
                >
                  保存并重新投影
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <AdminPanel title="资源参数" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>资源</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="text-right">额定功率</TableHead>
                  <TableHead className="text-right">额定容量</TableHead>
                  <TableHead>可调</TableHead>
                  <TableHead>配置方式</TableHead>
                  <TableHead>参数状态</TableHead>
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
                    <TableCell>{asset.sourceKind === "enterprise_assumption" ? "项目配置" : "设备台账"}</TableCell>
                    <TableCell>{(asset.confidenceLevel ?? 0) >= 0.8 ? "已确认" : "待复核"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminPanel>
        </>
      )}
    </AdminPageScaffold>
  )
}

const bindingRoleLabel: Record<string, string> = {
  fixed_load: "固定负荷",
  pv: "光伏",
  storage: "储能",
  charger: "充电桩",
  lighting: "照明",
  pcc: "PCC",
}

function getBindingSourceLabel(sourceName?: string | null) {
  if (!sourceName) return "待配置"
  if (sourceName.includes("模板") || sourceName.includes("演示")) return "人工配置"
  return sourceName
}

function getReadinessReasonLabel(reason: string) {
  return reason.replace("最近21天覆盖率", "最近21天数据完整率").replace("最新固定负荷数据", "最新负荷数据")
}
