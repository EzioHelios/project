import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminFilterBar, AdminPageScaffold, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useCarbonAssetInstruments, useCarbonAssetLots, useCarbonCompliance, useCreateComplianceCycle, useCreateSettlement, usePostSettlement } from "@/lib/api/hooks/carbon-assets"
import type { ComplianceCycleRequest, SettlementRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/compliance")({ component: CarbonCompliancePage })

function CarbonCompliancePage() {
  const [cycleId, setCycleId] = useState<number>()
  const compliance = useCarbonCompliance(cycleId)
  const instruments = useCarbonAssetInstruments()
  const lots = useCarbonAssetLots()
  const createCycle = useCreateComplianceCycle()
  const createSettlement = useCreateSettlement()
  const postSettlement = usePostSettlement()
  const positionEnvelope = (compliance.position.data ?? {}) as AssetRow
  const position = (positionEnvelope.position ?? {}) as AssetRow
  const cycles = (compliance.cycles.data?.items ?? []) as AssetRow[]
  const rules = (compliance.rules.data?.items ?? []) as AssetRow[]
  const lotRows = (lots.data?.items ?? []) as AssetRow[]
  const instrumentRows = (instruments.data?.items ?? []) as AssetRow[]
  const classByInstrument = useMemo(() => new Map(instrumentRows.map((row) => [Number(row.id), textOf(row, "instrumentClass")])), [instrumentRows])
  const eligibleLots = lotRows.filter((row) => ["CEA", "CCER"].includes(classByInstrument.get(Number(row.instrumentId)) ?? ""))
  const refresh = () => void Promise.all([compliance.cycles.refetch(), compliance.rules.refetch(), compliance.position.refetch(), compliance.settlements.refetch(), lots.refetch()])
  return (
    <AdminPageScaffold
      title="碳履约管理"
      topActions={
        <div className="flex items-center gap-2">
          <CycleDialog rules={rules} pending={createCycle.isPending} onSubmit={(body, close) => createCycle.mutate(body, { onSuccess: close })} />
          <SettlementDialog
            cycles={cycles}
            lots={eligibleLots}
            classByInstrument={classByInstrument}
            pending={createSettlement.isPending}
            onSubmit={(body, close) => createSettlement.mutate(body, { onSuccess: close })}
          />
        </div>
      }
      filters={
        <AdminFilterBar
          fields={[
            {
              key: "cycle",
              node: (
                <Select value={cycleId ? String(cycleId) : "active"} onValueChange={(value) => setCycleId(value === "active" ? undefined : Number(value))}>
                  <SelectTrigger aria-label="履约周期">
                    <SelectValue placeholder="当前履约周期" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">当前履约周期</SelectItem>
                    {cycles.map((row) => (
                      <SelectItem key={String(row.id)} value={String(row.id)}>
                        {textOf(row, "cycleName")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={<RefreshButton onClick={refresh} loading={compliance.position.isFetching} />}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="应清缴量" value={formatNumber(position.obligation_tco2e)} unit="tCO₂e" />
          <MetricTile label="CEA可用量" value={formatNumber(position.cea_available_tco2e)} unit="tCO₂e" />
          <MetricTile label="CCER可用量" value={formatNumber(position.ccer_available_tco2e)} unit="tCO₂e" />
          <MetricTile label="履约缺口" value={formatNumber(position.gap_tco2e)} unit="tCO₂e" tone={Number(position.gap_tco2e ?? 0) > 0 ? "warning" : "success"} />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-[0.9fr_1.4fr]">
        <AssetTable
          title="履约周期"
          rows={cycles}
          columns={[
            { key: "cycleCode", label: "周期编号" },
            { key: "cycleName", label: "周期" },
            { key: "requiredSurrenderTco2e", label: "应清缴量", align: "right", render: (row) => formatNumber(row.requiredSurrenderTco2e) },
            { key: "status", label: "状态" },
          ]}
        />
        <AssetTable
          title="履约结算"
          rows={(compliance.settlements.data?.items ?? []) as AssetRow[]}
          columns={[
            { key: "settlementNo", label: "结算编号" },
            { key: "totalCeaTco2e", label: "CEA", align: "right", render: (row) => formatNumber(row.totalCeaTco2e) },
            { key: "totalCcerTco2e", label: "CCER", align: "right", render: (row) => formatNumber(row.totalCcerTco2e) },
            { key: "status", label: "状态" },
            {
              key: "action",
              label: "操作",
              render: (row) =>
                row.status === "draft" ? (
                  <Button size="sm" variant="outline" disabled={postSettlement.isPending} onClick={() => postSettlement.mutate(Number(row.id))}>
                    提交入账
                  </Button>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </div>
      <div className="mt-3">
        <AssetTable
          title="履约规则版本"
          rows={rules}
          columns={[
            { key: "ruleCode", label: "规则编号" },
            { key: "ruleName", label: "规则" },
            { key: "version", label: "版本" },
            { key: "maxOffsetRatio", label: "抵销上限", align: "right", render: (row) => `${formatNumber(Number(row.maxOffsetRatio ?? 0) * 100)}%` },
            { key: "effectiveFrom", label: "生效日期" },
            { key: "sourceName", label: "规则来源" },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}

function CycleDialog({ rules, pending, onSubmit }: { rules: AssetRow[]; pending: boolean; onSubmit: (body: ComplianceCycleRequest, close: () => void) => void }) {
  const [open, setOpen] = useState(false)
  const [ruleId, setRuleId] = useState("")
  const [cycleCode, setCycleCode] = useState("")
  const [cycleName, setCycleName] = useState("")
  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [covered, setCovered] = useState("")
  const [required, setRequired] = useState("")
  const [sourceName, setSourceName] = useState("")
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          新建周期
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建履约周期</DialogTitle>
          <DialogDescription className="sr-only">按已发布规则登记覆盖排放量与应清缴量。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>规则版本</Label>
            <Select value={ruleId} onValueChange={setRuleId}>
              <SelectTrigger>
                <SelectValue placeholder="选择规则" />
              </SelectTrigger>
              <SelectContent>
                {rules.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "ruleName")} · V{textOf(row, "version")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>周期编号</Label>
              <Input value={cycleCode} onChange={(event) => setCycleCode(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>周期名称</Label>
              <Input value={cycleName} onChange={(event) => setCycleName(event.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-2">
              <Label>开始日期</Label>
              <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>结束日期</Label>
              <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>清缴期限</Label>
              <Input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>覆盖排放量</Label>
              <Input type="number" min="0" value={covered} onChange={(event) => setCovered(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>应清缴量</Label>
              <Input type="number" min="0" value={required} onChange={(event) => setRequired(event.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>义务数据来源</Label>
            <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!ruleId || !cycleCode || !cycleName || !periodStart || !periodEnd || !required || !sourceName || pending}
            onClick={() =>
              onSubmit(
                {
                  cycleCode,
                  cycleName,
                  market: "national",
                  periodStart,
                  periodEnd,
                  surrenderDueDate: dueDate || undefined,
                  ruleVersionId: Number(ruleId),
                  coveredEmissionsTco2E: Number(covered || required),
                  requiredSurrenderTco2E: Number(required),
                  obligationSource: "manual",
                  sourceName,
                },
                () => setOpen(false),
              )
            }
          >
            保存周期
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SettlementDialog({
  cycles,
  lots,
  classByInstrument,
  pending,
  onSubmit,
}: {
  cycles: AssetRow[]
  lots: AssetRow[]
  classByInstrument: Map<number, string>
  pending: boolean
  onSubmit: (body: SettlementRequest, close: () => void) => void
}) {
  const [open, setOpen] = useState(false)
  const [cycleId, setCycleId] = useState("")
  const [lotId, setLotId] = useState("")
  const [quantity, setQuantity] = useState("")
  const [sourceName, setSourceName] = useState("")
  const lot = lots.find((row) => String(row.id) === lotId)
  const instrumentClass = classByInstrument.get(Number(lot?.instrumentId)) ?? "CEA"
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus />
          新建结算
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建履约结算</DialogTitle>
          <DialogDescription className="sr-only">选择资产批次生成待提交的清缴或抵销结算。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>履约周期</Label>
            <Select value={cycleId} onValueChange={setCycleId}>
              <SelectTrigger>
                <SelectValue placeholder="选择周期" />
              </SelectTrigger>
              <SelectContent>
                {cycles.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "cycleName")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>资产批次</Label>
            <Select value={lotId} onValueChange={setLotId}>
              <SelectTrigger>
                <SelectValue placeholder="选择CEA或CCER批次" />
              </SelectTrigger>
              <SelectContent>
                {lots.map((row) => (
                  <SelectItem key={String(row.id)} value={String(row.id)}>
                    {textOf(row, "lotNo")} · {classByInstrument.get(Number(row.instrumentId))}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label>结算数量</Label>
              <Input type="number" min="0" step="0.001" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>数据来源</Label>
              <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!cycleId || !lotId || !quantity || !sourceName || pending}
            onClick={() =>
              onSubmit(
                {
                  cycleId: Number(cycleId),
                  lines: [{ lotId: Number(lotId), quantity: Number(quantity), purpose: instrumentClass === "CCER" ? "offset" : "surrender" }],
                  sourceName,
                },
                () => setOpen(false),
              )
            }
          >
            保存草稿
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
