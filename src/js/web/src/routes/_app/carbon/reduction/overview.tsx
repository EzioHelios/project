import { createFileRoute } from "@tanstack/react-router"
import { Plus, RefreshCw } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminPanel, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { asNumber, asText, formatReductionNumber, ReductionStatusBadge, reductionCategoryLabels } from "@/components/carbon/reduction-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  createBubbleChartOption,
  createMaccChartOption,
  createRankingChartOption,
  createTrendChartOption,
  createWaterfallChartOption,
  useAdminChartTheme,
} from "@/lib/admin-chart-theme"
import { useCreateReductionTarget, usePublishReductionTarget, useReductionOverview } from "@/lib/api/hooks/decarbonization"
import type { ReductionTargetRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/reduction/overview")({ component: ReductionOverviewPage })

function ReductionOverviewPage() {
  const chartTheme = useAdminChartTheme("carbon")
  const [year, setYear] = useState(new Date().getFullYear())
  const [category, setCategory] = useState("all")
  const [status, setStatus] = useState("all")
  const [targetOpen, setTargetOpen] = useState(false)
  const [targetForm, setTargetForm] = useState<ReductionTargetRequest>({
    code: `REDUCTION-${new Date().getFullYear()}`,
    name: `${new Date().getFullYear()}年度减排目标`,
    targetYear: new Date().getFullYear() + 1,
    baselineYear: new Date().getFullYear() - 1,
    baselineTco2E: 0,
    targetReductionTco2E: 0,
    sourceName: "企业减排目标",
  })
  const createTarget = useCreateReductionTarget()
  const publishTarget = usePublishReductionTarget()
  const overview = useReductionOverview({ target_year: year, category: category === "all" ? undefined : category, status: status === "all" ? undefined : status })
  const data = overview.data
  const metrics = data?.metrics

  const trend = useMemo(
    () =>
      (data?.trend ?? []).map((item) => ({
        period: asText(item.period),
        actual: asNumber(item.actualTco2e),
        target: asNumber(item.targetTco2e),
        forecast: asNumber(item.forecastTco2e),
      })),
    [data?.trend],
  )
  const trendOption = createTrendChartOption(
    chartTheme,
    trend,
    [
      { key: "actual", label: "组织盘查实际排放", colorKey: "scope1" },
      { key: "target", label: "目标排放", colorKey: "carbon" },
      { key: "forecast", label: "预测排放", colorKey: "scope2" },
    ],
    { includeZeroSeries: true },
  )
  const waterfallOption = createWaterfallChartOption(
    chartTheme,
    (data?.waterfall ?? []).map((item) => ({
      name: asText(item.name),
      value: asNumber(item.value),
      kind: item.kind === "total" ? "total" : asNumber(item.value) < 0 ? "decrease" : "increase",
    })),
    { unit: "tCO₂e" },
  )
  const contributionOption = createRankingChartOption(
    chartTheme,
    (data?.contribution ?? []).map((item) => ({ name: asText(item.name), value: asNumber(item.reductionTco2e) })),
    { unit: "tCO₂e", colorKey: "carbon", limit: 8 },
  )
  const portfolio = data?.portfolio ?? []
  const bubbleOption = createBubbleChartOption(
    chartTheme,
    portfolio.map((item) => ({
      name: asText(item.name),
      x: asNumber(item.investmentCny) / 10000,
      y: asNumber(item.reductionTco2e),
      size: Math.max(asNumber(item.progressPct), 4),
      category: asText(item.category),
    })),
    { xUnit: "万元", yUnit: "tCO₂e" },
  )
  const maccOption = createMaccChartOption(
    chartTheme,
    portfolio.map((item) => {
      const reduction = asNumber(item.reductionTco2e)
      return { name: asText(item.name), reduction, cost: reduction > 0 ? asNumber(item.investmentCny) / reduction : 0 }
    }),
  )

  const saveAndPublishTarget = async () => {
    const created = await createTarget.mutateAsync(targetForm)
    await publishTarget.mutateAsync(created.id)
    setYear(created.targetYear)
    setTargetOpen(false)
  }

  return (
    <AdminPageScaffold
      title="减排概览"
      topActions={
        <Dialog open={targetOpen} onOpenChange={setTargetOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4" />
              建立目标
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>建立并发布减排目标</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-2 sm:grid-cols-2">
              <TargetField label="目标编号" value={targetForm.code} onChange={(value) => setTargetForm({ ...targetForm, code: value })} />
              <TargetField label="目标名称" value={targetForm.name} onChange={(value) => setTargetForm({ ...targetForm, name: value })} />
              <TargetNumberField label="基准年度" value={targetForm.baselineYear} onChange={(value) => setTargetForm({ ...targetForm, baselineYear: value })} />
              <TargetNumberField label="目标年度" value={targetForm.targetYear} onChange={(value) => setTargetForm({ ...targetForm, targetYear: value })} />
              <TargetNumberField label="基准排放（tCO₂e）" value={targetForm.baselineTco2E} onChange={(value) => setTargetForm({ ...targetForm, baselineTco2E: value })} />
              <TargetNumberField
                label="目标减排量（tCO₂e）"
                value={targetForm.targetReductionTco2E}
                onChange={(value) => setTargetForm({ ...targetForm, targetReductionTco2E: value })}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setTargetOpen(false)}>
                取消
              </Button>
              <Button
                onClick={() => void saveAndPublishTarget()}
                disabled={
                  !targetForm.code || !targetForm.name || targetForm.baselineTco2E <= 0 || targetForm.targetReductionTco2E <= 0 || createTarget.isPending || publishTarget.isPending
                }
              >
                保存并发布
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      }
      meta={
        data?.target ? (
          <span>
            目标：{data.target.name} · {data.target.targetYear}年
          </span>
        ) : undefined
      }
      filters={
        <AdminFilterBar
          fields={[
            { key: "year", node: <Input aria-label="目标年度" type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} /> },
            {
              key: "category",
              node: (
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger aria-label="项目分类">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部分类</SelectItem>
                    {Object.entries(reductionCategoryLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "status",
              node: (
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger aria-label="项目状态">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="implementing">实施中</SelectItem>
                    <SelectItem value="monitoring">监测中</SelectItem>
                    <SelectItem value="verified">已核查</SelectItem>
                    <SelectItem value="issued">已签发</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={
            <Button variant="outline" size="sm" onClick={() => void overview.refetch()} disabled={overview.isFetching}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
          }
        />
      }
      metrics={
        <MetricStrip className="xl:grid-cols-6">
          <MetricTile label="组织盘查实际排放" value={formatReductionNumber(metrics?.actualInventoryTco2E)} unit="tCO₂e" tone="domain" />
          <MetricTile label="目标差距" value={formatReductionNumber(metrics?.targetGapTco2E)} unit="tCO₂e" tone={(metrics?.targetGapTco2E ?? 0) > 0 ? "warning" : "success"} />
          <MetricTile label="预计减排量" value={formatReductionNumber(metrics?.expectedReductionTco2E)} unit="tCO₂e" />
          <MetricTile label="已监测减排量" value={formatReductionNumber(metrics?.monitoredReductionTco2E)} unit="tCO₂e" />
          <MetricTile label="已核查减排量" value={formatReductionNumber(metrics?.verifiedReductionTco2E)} unit="tCO₂e" tone="success" />
          <MetricTile label="已签发CCER" value={formatReductionNumber(metrics?.issuedCcerTco2E)} unit="tCO₂e" />
        </MetricStrip>
      }
    >
      {!data && !overview.isLoading ? (
        <AdminEmptyState title="暂无减排管理数据" description="建立年度目标和减排项目后即可形成组合分析。" />
      ) : (
        <div className="grid gap-3">
          <div className="grid gap-3 xl:grid-cols-2">
            <ChartPanel title="排放目标与预测趋势" unit="tCO₂e" source="组织碳盘查与减排目标" option={trendOption} height={310} />
            <ChartPanel title="基准排放至当前排放" unit="tCO₂e" source="组织碳盘查结果" option={waterfallOption} height={310} />
          </div>
          <div className="grid gap-3 xl:grid-cols-3">
            <ChartPanel title="区域与业务减排贡献" unit="tCO₂e" source="已登记减排项目" option={contributionOption} height={300} />
            <ChartPanel title="项目投资与减排组合" unit="tCO₂e" source="项目财务与减排评价" option={bubbleOption} height={300} />
            <ChartPanel title="边际减排成本曲线" unit="元/tCO₂e" source="项目组合评价" option={maccOption} height={300} />
          </div>
          <AdminPanel title="重点措施与执行成效" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>项目</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead>责任人</TableHead>
                  <TableHead>进度</TableHead>
                  <TableHead>预计减排量</TableHead>
                  <TableHead>监测减排量</TableHead>
                  <TableHead>阶段</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.keyMeasures ?? []).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <div className="font-medium">{item.name}</div>
                      <div className="text-muted-foreground text-xs">{item.code}</div>
                    </TableCell>
                    <TableCell>{reductionCategoryLabels[item.category] ?? item.category}</TableCell>
                    <TableCell>{item.ownerName}</TableCell>
                    <TableCell className="tabular-nums">{formatReductionNumber(item.progressPct, 0)}%</TableCell>
                    <TableCell className="tabular-nums">{formatReductionNumber(item.expectedReductionTco2E)} tCO₂e</TableCell>
                    <TableCell className="tabular-nums">{formatReductionNumber(item.monitoredReductionTco2E)} tCO₂e</TableCell>
                    <TableCell>
                      <ReductionStatusBadge status={item.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminPanel>
        </div>
      )}
    </AdminPageScaffold>
  )
}

function TargetField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function TargetNumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  )
}
