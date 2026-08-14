import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Pencil, RefreshCw, Trash2, Upload } from "lucide-react"
import { useState } from "react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, MicrogridSettingsTabs } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type FlexibilityContract, useMicrogridActions, useMicrogridFlexibilityContracts, useMicrogridScenarios } from "@/lib/api/hooks/microgrid"

export const Route = createFileRoute("/_app/microgrid/settings/flexibility")({ component: MicrogridFlexibilitySettingsPage })

function MicrogridFlexibilitySettingsPage() {
  const scenarios = useMicrogridScenarios()
  const actions = useMicrogridActions()
  const [editing, setEditing] = useState<FlexibilityContract>()
  const draft = scenarios.data?.find((item) => item.status === "draft")
  const published = scenarios.data?.find((item) => item.status === "published")
  const activeScenario = draft ?? published
  const contracts = useMicrogridFlexibilityContracts(activeScenario?.id)
  const active = contracts.data?.filter((contract) => contract.enabled) ?? []

  return (
    <AdminPageScaffold
      title="柔性契约"
      meta={`${active.length} 项生效`}
      topActions={
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/microgrid/operations">
              <ArrowLeft />
              返回监控
            </Link>
          </Button>
          <Button disabled={contracts.isFetching} onClick={() => void contracts.refetch()} size="sm" variant="outline">
            <RefreshCw className={contracts.isFetching ? "animate-spin" : ""} />
            刷新
          </Button>
          {draft && (
            <>
              <Button disabled={actions.discardDraft.isPending} onClick={() => actions.discardDraft.mutate(draft.id)} size="sm" variant="outline">
                <Trash2 />
                放弃草稿
              </Button>
              <Button disabled={actions.publishScenario.isPending} onClick={() => actions.publishScenario.mutate(draft.id)} size="sm">
                <Upload />
                发布策略
              </Button>
            </>
          )}
        </div>
      }
      tabs={<MicrogridSettingsTabs />}
      filters={
        <ContextBar>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">执行原则</span>
            <div className="font-medium text-sm">安全下限优先</div>
          </div>
          <div className="min-w-56">
            <span className="text-muted-foreground text-xs">配置作用域</span>
            <div className="font-medium text-sm">{draft ? `待发布 v${draft.version}` : published ? `已发布 v${published.version}` : "尚无策略"}</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="契约总数" value={contracts.data?.length ?? 0} unit="项" />
          <MetricTile label="生效契约" value={active.length} unit="项" />
          <MetricTile label="充电任务" value={active.filter((item) => item.contractType === "energy_deadline").length} unit="项" />
          <MetricTile label="最低服务" value={active.filter((item) => item.contractType === "minimum_service").length} unit="项" />
        </MetricStrip>
      }
    >
      {!contracts.isLoading && active.length === 0 ? (
        <AdminEmptyState title="尚无柔性契约" description="请先配置可调资源并发布场景。" />
      ) : (
        <AdminPanel title="调度边界" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>资源</TableHead>
                <TableHead>契约类型</TableHead>
                <TableHead>允许时窗</TableHead>
                <TableHead className="text-right">功率范围</TableHead>
                <TableHead className="text-right">目标电量</TableHead>
                <TableHead className="text-right">优先级</TableHead>
                <TableHead className="text-right">违约成本</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {active.map((contract) => (
                <TableRow key={contract.id}>
                  <TableCell>
                    <div className="font-medium">{contract.assetName}</div>
                    <div className="text-muted-foreground text-xs">{contract.assetCode}</div>
                  </TableCell>
                  <TableCell>{contract.contractType === "energy_deadline" ? "截止电量" : "最低服务"}</TableCell>
                  <TableCell>
                    {formatMinute(contract.startMinute)}–{formatMinute(contract.endMinute)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatNumber(contract.minimumPowerKw)}–{formatNumber(contract.maximumPowerKw)} kW
                  </TableCell>
                  <TableCell className="text-right">{contract.targetEnergyKwh ? `${formatNumber(contract.targetEnergyKwh)} kWh` : "-"}</TableCell>
                  <TableCell className="text-right">{contract.priority}</TableCell>
                  <TableCell className="text-right">{contract.hardConstraint ? "硬约束" : `¥ ${formatNumber(contract.penaltyCnyPerKwh, 2)}/kWh`}</TableCell>
                  <TableCell>
                    <Button disabled={!draft || contract.scenarioId !== draft.id} onClick={() => setEditing(contract)} size="icon" variant="ghost">
                      <Pencil />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminPanel>
      )}
      <Sheet open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(undefined)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>编辑柔性契约</SheetTitle>
          </SheetHeader>
          {editing && (
            <div className="flex-1 space-y-4 px-4">
              <div className="grid grid-cols-2 gap-3">
                <ContractField label="开始分钟" value={editing.startMinute} onChange={(value) => setEditing({ ...editing, startMinute: value })} />
                <ContractField label="结束分钟" value={editing.endMinute} onChange={(value) => setEditing({ ...editing, endMinute: value })} />
                <ContractField label="最小功率 kW" value={editing.minimumPowerKw} onChange={(value) => setEditing({ ...editing, minimumPowerKw: value })} />
                <ContractField label="最大功率 kW" value={editing.maximumPowerKw} onChange={(value) => setEditing({ ...editing, maximumPowerKw: value })} />
                {editing.assetType === "charger" && (
                  <ContractField label="目标电量 kWh" value={editing.targetEnergyKwh ?? 0} onChange={(value) => setEditing({ ...editing, targetEnergyKwh: value })} />
                )}
                {!editing.hardConstraint && (
                  <ContractField label="违约成本 元/kWh" value={editing.penaltyCnyPerKwh} onChange={(value) => setEditing({ ...editing, penaltyCnyPerKwh: value })} />
                )}
              </div>
              {editing.assetType !== "lighting" && (
                <Button variant="outline" onClick={() => setEditing({ ...editing, hardConstraint: !editing.hardConstraint })}>
                  {editing.hardConstraint ? "切换为软约束" : "切换为硬约束"}
                </Button>
              )}
            </div>
          )}
          <SheetFooter>
            <Button
              disabled={!editing}
              onClick={() => {
                if (editing) actions.updateContract.mutate(editing)
                setEditing(undefined)
              }}
            >
              保存契约
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function ContractField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  )
}

function formatMinute(value: number) {
  if (value === 1440) return "24:00"
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`
}
