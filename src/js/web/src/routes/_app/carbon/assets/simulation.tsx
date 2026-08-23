import { createFileRoute } from "@tanstack/react-router"
import { Calculator, Plus } from "lucide-react"
import { useState } from "react"

import { AdminPageScaffold, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type AssetRow, AssetTable, formatNumber, RefreshButton, textOf } from "@/components/carbon/carbon-assets-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useCarbonCompliance, useCarbonCostScenarios, useCreateCostScenario, useRunCostScenario } from "@/lib/api/hooks/carbon-assets"
import type { CostScenarioRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/assets/simulation")({ component: CarbonCostSimulationPage })

function CarbonCostSimulationPage() {
  const data = useCarbonCostScenarios()
  const compliance = useCarbonCompliance()
  const createScenario = useCreateCostScenario()
  const runScenario = useRunCostScenario()
  const [open, setOpen] = useState(false)
  const runs = (data.runs.data?.items ?? []) as AssetRow[]
  const latest = runs[0]
  const summary = (latest?.resultSummary ?? {}) as AssetRow
  const refresh = () => void Promise.all([data.scenarios.refetch(), data.runs.refetch(), compliance.cycles.refetch()])
  return (
    <AdminPageScaffold
      title="碳成本测算"
      topActions={
        <ScenarioDialog
          open={open}
          onOpenChange={setOpen}
          cycles={(compliance.cycles.data?.items ?? []) as AssetRow[]}
          pending={createScenario.isPending}
          onSubmit={(body) => createScenario.mutate(body, { onSuccess: () => setOpen(false) })}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="测算情景" value={data.scenarios.data?.total ?? 0} unit="个" />
          <MetricTile label="测算运行" value={data.runs.data?.total ?? 0} unit="次" />
          <MetricTile label="建议采购 CEA" value={formatNumber(summary.ceaPurchaseTco2e)} unit="tCO₂e" />
          <MetricTile label="预计成本" value={formatNumber(summary.totalCostCny)} unit="元" />
        </MetricStrip>
      }
    >
      <div className="grid gap-3 xl:grid-cols-[0.9fr_1.4fr]">
        <AssetTable
          title="成本情景"
          rows={(data.scenarios.data?.items ?? []) as AssetRow[]}
          actions={<RefreshButton onClick={refresh} loading={data.scenarios.isFetching || data.runs.isFetching} />}
          columns={[
            { key: "scenarioCode", label: "情景编号" },
            { key: "scenarioName", label: "情景名称" },
            { key: "status", label: "状态" },
            {
              key: "action",
              label: "操作",
              render: (row) => (
                <Button size="sm" variant="outline" disabled={runScenario.isPending} onClick={() => runScenario.mutate(Number(row.id))}>
                  <Calculator />
                  运行测算
                </Button>
              ),
            },
          ]}
        />
        <AssetTable
          title="冻结测算结果"
          rows={runs}
          columns={[
            { key: "runNo", label: "运行编号" },
            { key: "completedAt", label: "完成时间" },
            { key: "resultSummary", label: "CEA采购", align: "right", render: (row) => formatNumber((row.resultSummary as AssetRow | undefined)?.ceaPurchaseTco2e) },
            { key: "cost", label: "预计成本", align: "right", render: (row) => formatNumber((row.resultSummary as AssetRow | undefined)?.totalCostCny) },
          ]}
        />
      </div>
    </AdminPageScaffold>
  )
}

function ScenarioDialog({
  open,
  onOpenChange,
  cycles,
  pending,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (value: boolean) => void
  cycles: AssetRow[]
  pending: boolean
  onSubmit: (body: CostScenarioRequest) => void
}) {
  const [cycleId, setCycleId] = useState("")
  const [name, setName] = useState("")
  const [ceaPrice, setCeaPrice] = useState("")
  const [ccerPrice, setCcerPrice] = useState("")
  const [margin, setMargin] = useState("")
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus />
          新建情景
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建碳成本情景</DialogTitle>
          <DialogDescription className="sr-only">配置履约采购价格与安全裕度。</DialogDescription>
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
            <Label>情景名称</Label>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-2">
              <Label>CEA价格</Label>
              <Input type="number" value={ceaPrice} onChange={(event) => setCeaPrice(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>CCER价格</Label>
              <Input type="number" value={ccerPrice} onChange={(event) => setCcerPrice(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>安全裕度</Label>
              <Input type="number" step="0.01" value={margin} onChange={(event) => setMargin(event.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={!cycleId || !name || !ceaPrice || !ccerPrice || pending}
            onClick={() =>
              onSubmit({
                scenarioCode: `COST-${Date.now()}`,
                scenarioName: name,
                cycleId: Number(cycleId),
                parameters: { ceaPrice: Number(ceaPrice), ccerPrice: Number(ccerPrice), safetyMarginRatio: Number(margin) },
              })
            }
          >
            保存情景
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
