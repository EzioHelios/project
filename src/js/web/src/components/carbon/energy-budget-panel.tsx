import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { RefreshCw, Settings } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTableStateRow, AdminTabsList, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { type PageResult, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"

type BudgetPlan = {
  id: number
  name: string
  budget_year: number
  target_scope: string
  target_code?: string | null
  target_name?: string | null
  energy_budget_tce?: number | null
  carbon_budget_co2e?: number | null
  denominator_plan?: number | null
  denominator_unit?: string | null
  status: string
  source_name?: string | null
  confidence_level?: string | null
}

type BudgetProgressRow = {
  id: number
  period: string
  period_month: string
  energy_budget_tce?: number | null
  carbon_budget_co2e?: number | null
  actual_tce?: number | null
  actual_co2e?: number | null
  energy_execution_rate_pct?: number | null
  carbon_execution_rate_pct?: number | null
  energy_variance_tce?: number | null
  carbon_variance_co2e?: number | null
  energy_status: string
  carbon_status: string
  record_count: number
}

type BudgetTotals = {
  actual_tce: number
  actual_co2e: number
  energy_execution_rate_pct?: number | null
  carbon_execution_rate_pct?: number | null
  energy_variance_tce?: number | null
  carbon_variance_co2e?: number | null
  energy_status: string
  carbon_status: string
}

type BudgetProgress = {
  plan: BudgetPlan | null
  rows: BudgetProgressRow[]
  totals: BudgetTotals
}

type BudgetForecast = {
  summary: {
    elapsed_months: number
    total_months: number
    forecast_tce?: number | null
    forecast_co2e?: number | null
    energy_status: string
    carbon_status: string
  }
}

type BudgetRecommendation = {
  code: string
  priority: string
  title: string
  target?: string | null
  action: string
}

type BudgetAdjustment = {
  id: number
  adjustment_no: string
  effective_month?: string | null
  adjusted_energy_budget_tce?: number | null
  adjusted_carbon_budget_co2e?: number | null
  requested_by?: string | null
  status: string
}

const targetScopes = [
  { value: "enterprise", label: "企业" },
  { value: "area", label: "区域" },
  { value: "device", label: "设备" },
]

const currentYear = new Date().getFullYear()

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function statusLabel(value?: string | null) {
  return (
    {
      ok: "正常",
      warning: "预警",
      exceeded: "超限",
      forecast_warning: "预测预警",
      forecast_exceeded: "预测超限",
      missing_budget: "无预算",
      invalid_budget: "预算无效",
      no_actual: "无实际值",
      draft: "草稿",
      active: "启用",
      approved: "已批准",
      rejected: "已驳回",
      submitted: "已提交",
    }[value || ""] ??
    value ??
    "-"
  )
}

function statusBadge(value?: string | null) {
  if (value === "exceeded" || value === "forecast_exceeded" || value === "rejected") return <Badge variant="destructive">{statusLabel(value)}</Badge>
  if (value === "warning" || value === "forecast_warning" || value === "submitted") return <Badge variant="warning">{statusLabel(value)}</Badge>
  if (value === "ok" || value === "active" || value === "approved") return <Badge variant="success">{statusLabel(value)}</Badge>
  return <Badge variant="outline">{statusLabel(value)}</Badge>
}

function targetScopeLabel(value?: string | null) {
  return targetScopes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function buildQuery(planId: string, year: string) {
  const params = new URLSearchParams()
  if (planId && planId !== "auto") params.set("plan_id", planId)
  if (year) params.set("budget_year", year)
  params.set("status", "all")
  const text = params.toString()
  return text ? `?${text}` : ""
}

export function EnergyBudgetPanel({ header }: { header?: ReactNode }) {
  const queryClient = useQueryClient()
  const [year, setYear] = useState(String(currentYear))
  const [selectedPlanId, setSelectedPlanId] = useState("auto")

  const plansQuery = useQuery<PageResult<BudgetPlan>>({
    queryKey: ["energy-budget", "plans", year],
    queryFn: () => requestPage<BudgetPlan>("/api/energy/budget/plans", { budget_year: year, limit: 100 }),
  })
  const plans = plansQuery.data?.items ?? []
  const selectedPlan = selectedPlanId === "auto" ? (plans.find((plan) => plan.status === "active") ?? plans[0]) : plans.find((plan) => String(plan.id) === selectedPlanId)
  const query = useMemo(() => buildQuery(selectedPlan ? String(selectedPlan.id) : selectedPlanId, year), [selectedPlan, selectedPlanId, year])

  const progressQuery = useQuery<ApiEnvelope<BudgetProgress>>({
    queryKey: ["energy-budget", "progress", query],
    queryFn: () => fetchCarbonApi<BudgetProgress>(`/api/energy/budget/progress${query}`),
  })
  const alertsQuery = useQuery<ApiEnvelope<{ items: BudgetProgressRow[] }>>({
    queryKey: ["energy-budget", "alerts", query],
    queryFn: () => fetchCarbonApi<{ items: BudgetProgressRow[] }>(`/api/energy/budget/alerts${query}`),
  })
  const forecastQuery = useQuery<ApiEnvelope<BudgetForecast>>({
    queryKey: ["energy-budget", "forecast", query],
    queryFn: () => fetchCarbonApi<BudgetForecast>(`/api/energy/budget/forecast${query}`),
  })
  const recommendationsQuery = useQuery<ApiEnvelope<{ items: BudgetRecommendation[] }>>({
    queryKey: ["energy-budget", "recommendations", query],
    queryFn: () => fetchCarbonApi<{ items: BudgetRecommendation[] }>(`/api/energy/budget/recommendations${query}`),
  })
  const adjustmentsQuery = useQuery<PageResult<BudgetAdjustment>>({
    queryKey: ["energy-budget", "adjustments", selectedPlan?.id],
    queryFn: () => requestPage<BudgetAdjustment>("/api/energy/budget/adjustments", { plan_id: selectedPlan?.id, limit: 100 }),
    enabled: !!selectedPlan?.id,
  })

  const progress = progressQuery.data?.data
  const plan = progress?.plan ?? selectedPlan ?? null
  const rows = progress?.rows ?? []
  const totals = progress?.totals
  const forecast = forecastQuery.data?.data.summary
  const alerts = alertsQuery.data?.data.items ?? []
  const recommendations = recommendationsQuery.data?.data.items ?? []
  const adjustments = adjustmentsQuery.data?.items ?? []

  return (
    <Tabs defaultValue="target" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="target">年度目标</TabsTrigger>
            <TabsTrigger value="allocation">月度预算</TabsTrigger>
            <TabsTrigger value="variance">执行偏差</TabsTrigger>
            <TabsTrigger value="forecast">预测超限</TabsTrigger>
            <TabsTrigger value="adjustment">调整记录</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <ContextBar
            actions={
              <>
                <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ["energy-budget"] })}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
                <Button asChild>
                  <Link to="/data/energy-budget">
                    <Settings className="mr-2 h-4 w-4" />
                    维护预算
                  </Link>
                </Button>
              </>
            }
          >
            <Input value={year} onChange={(event) => setYear(event.target.value)} placeholder="年度" />
            <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
              <SelectTrigger>
                <SelectValue placeholder="预算方案" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">最新预算方案</SelectItem>
                {plans.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ContextBar>
        }
      >
        <TabsContent value="target">
          {plan ? (
            <AdminPanel title={plan.name} actions={statusBadge(plan.status)}>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <InfoCell label="预算年度" value={plan.budget_year} />
                <InfoCell label="适用范围" value={targetScopeLabel(plan.target_scope)} />
                <InfoCell label="对象" value={plan.target_name || plan.target_code || "全企业"} />
                <InfoCell label="来源" value={plan.source_name || "-"} />
                <InfoCell label="能耗目标" value={`${formatNumber(plan.energy_budget_tce)} tce`} />
                <InfoCell label="碳排目标" value={`${formatNumber(plan.carbon_budget_co2e)} tCO2e`} />
                <InfoCell label="分母计划" value={`${formatNumber(plan.denominator_plan)} ${plan.denominator_unit || ""}`} />
                <InfoCell label="置信度" value={plan.confidence_level || "-"} />
              </div>
            </AdminPanel>
          ) : (
            <AdminEmptyState title="暂无预算方案" />
          )}
        </TabsContent>

        <TabsContent value="allocation">
          <MonthlyBudgetTable rows={rows} />
        </TabsContent>

        <TabsContent value="variance" className="space-y-4">
          {plan ? (
            <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
              <MetricTile label="实际能耗" value={formatNumber(totals?.actual_tce)} unit="tce" meta={`执行率 ${formatNumber(totals?.energy_execution_rate_pct, 2)}%`} />
              <MetricTile label="能耗偏差" value={formatNumber(totals?.energy_variance_tce)} unit="tce" meta={statusBadge(totals?.energy_status)} />
              <MetricTile label="实际排放" value={formatNumber(totals?.actual_co2e)} unit="tCO2e" meta={`执行率 ${formatNumber(totals?.carbon_execution_rate_pct, 2)}%`} />
              <MetricTile label="碳排偏差" value={formatNumber(totals?.carbon_variance_co2e)} unit="tCO2e" meta={statusBadge(totals?.carbon_status)} />
            </MetricStrip>
          ) : null}
          <VarianceTable rows={rows} />
          {alerts.length ? <VarianceTable rows={alerts} compact title="当前预警" /> : null}
        </TabsContent>

        <TabsContent value="forecast">
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
            <AdminPanel title="预测结果" contentClassName="space-y-4">
              <InfoCell label="已发生月份" value={`${forecast?.elapsed_months ?? 0} / ${forecast?.total_months ?? 0}`} />
              <InfoCell label="预测能耗" value={`${formatNumber(forecast?.forecast_tce)} tce`} />
              <InfoCell label="预测排放" value={`${formatNumber(forecast?.forecast_co2e)} tCO2e`} />
              <div className="flex flex-wrap gap-2">
                {statusBadge(forecast?.energy_status)}
                {statusBadge(forecast?.carbon_status)}
              </div>
            </AdminPanel>
            <AdminPanel title="规则建议" contentClassName="space-y-3">
              {recommendations.map((item) => (
                <div key={`${item.code}-${item.target}`} className="rounded-md border border-border/60 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{item.target}</div>
                    </div>
                    <Badge variant={item.priority === "high" ? "destructive" : "secondary"}>{item.priority === "high" ? "高" : "中"}</Badge>
                  </div>
                  <div className="mt-3 text-sm">{item.action}</div>
                </div>
              ))}
              {recommendations.length === 0 && <AdminEmptyState title="暂无建议" />}
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="adjustment">
          <AdjustmentTable rows={adjustments} />
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

function InfoCell({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-border/60 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 font-medium">{value === null || value === undefined || value === "" ? "-" : String(value)}</div>
    </div>
  )
}

function MonthlyBudgetTable({ rows }: { rows: BudgetProgressRow[] }) {
  return (
    <AdminPanel title="月度预算" contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>月份</TableHead>
              <TableHead className="text-right">能耗预算(tce)</TableHead>
              <TableHead className="text-right">碳预算(tCO2e)</TableHead>
              <TableHead className="text-right">实际能耗</TableHead>
              <TableHead className="text-right">实际排放</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.period}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.energy_budget_tce)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.carbon_budget_co2e)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.actual_tce)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.actual_co2e)}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {statusBadge(row.energy_status)}
                    {statusBadge(row.carbon_status)}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <AdminTableStateRow colSpan={6}>暂无数据</AdminTableStateRow>}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

function VarianceTable({ rows, compact = false, title = "执行偏差" }: { rows: BudgetProgressRow[]; compact?: boolean; title?: string }) {
  return (
    <AdminPanel title={title} contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>月份</TableHead>
              <TableHead className="text-right">能耗执行率</TableHead>
              <TableHead className="text-right">能耗偏差</TableHead>
              <TableHead className="text-right">碳执行率</TableHead>
              <TableHead className="text-right">碳偏差</TableHead>
              {!compact && <TableHead className="text-right">记录数</TableHead>}
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.period}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.energy_execution_rate_pct, 2)}%</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.energy_variance_tce)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.carbon_execution_rate_pct, 2)}%</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.carbon_variance_co2e)}</TableCell>
                {!compact && <TableCell className="text-right tabular-nums">{row.record_count}</TableCell>}
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {statusBadge(row.energy_status)}
                    {statusBadge(row.carbon_status)}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <AdminTableStateRow colSpan={compact ? 6 : 7}>暂无数据</AdminTableStateRow>}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

function AdjustmentTable({ rows }: { rows: BudgetAdjustment[] }) {
  return (
    <AdminPanel title="调整记录" contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>编号</TableHead>
              <TableHead>生效月份</TableHead>
              <TableHead className="text-right">调整后能耗</TableHead>
              <TableHead className="text-right">调整后碳排</TableHead>
              <TableHead>申请人</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.adjustment_no}</TableCell>
                <TableCell>{row.effective_month || "-"}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.adjusted_energy_budget_tce)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.adjusted_carbon_budget_co2e)}</TableCell>
                <TableCell>{row.requested_by || "-"}</TableCell>
                <TableCell>{statusBadge(row.status)}</TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <AdminTableStateRow colSpan={6}>暂无数据</AdminTableStateRow>}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}
