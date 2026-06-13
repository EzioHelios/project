import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, RefreshCw, Wand2 } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTableStateRow, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

type BudgetPlan = {
  id: number
  code: string
  name: string
  budget_year: number
  period_type: string
  period_start: string
  period_end: string
  target_scope: string
  target_code?: string | null
  target_name?: string | null
  energy_budget_tce?: number | null
  carbon_budget_co2e?: number | null
  denominator_plan?: number | null
  denominator_unit?: string | null
  energy_intensity_budget?: number | null
  carbon_intensity_budget?: number | null
  status: string
  source_name?: string | null
  standard_code?: string | null
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
  budget_tce: number
  budget_co2e: number
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
  plan: BudgetPlan | null
  items: BudgetProgressRow[]
  summary: {
    elapsed_months: number
    total_months: number
    forecast_tce?: number | null
    forecast_co2e?: number | null
    energy_forecast_rate_pct?: number | null
    carbon_forecast_rate_pct?: number | null
    energy_status: string
    carbon_status: string
  }
}

type BudgetRecommendation = {
  code: string
  priority: string
  title: string
  target?: string | null
  evidence: Record<string, unknown>
  action: string
}

type BudgetAdjustment = {
  id: number
  plan_id: number
  allocation_id?: number | null
  adjustment_no: string
  adjustment_type: string
  effective_month?: string | null
  original_energy_budget_tce?: number | null
  original_carbon_budget_co2e?: number | null
  adjusted_energy_budget_tce?: number | null
  adjusted_carbon_budget_co2e?: number | null
  reason?: string | null
  status: string
  requested_by?: string | null
  approved_by?: string | null
}

const targetScopes = [
  { value: "enterprise", label: "企业" },
  { value: "area", label: "区域" },
  { value: "device", label: "设备" },
]

const currentYear = new Date().getFullYear()

const defaultPlanForm = {
  name: "",
  budget_year: String(currentYear),
  target_scope: "enterprise",
  target_code: "",
  target_name: "",
  energy_budget_tce: "",
  carbon_budget_co2e: "",
  denominator_plan: "",
  denominator_unit: "",
  status: "active",
  source_name: "年度预算目标",
  standard_code: "enterprise_budget_rule",
  confidence_level: "medium",
  remark: "",
}

const defaultAdjustmentForm = {
  allocation_id: "",
  adjusted_energy_budget_tce: "",
  adjusted_carbon_budget_co2e: "",
  reason: "",
  requested_by: "",
  status: "draft",
}

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
  if (value === "warning" || value === "forecast_warning" || value === "submitted") return <Badge className="bg-amber-500 hover:bg-amber-500">{statusLabel(value)}</Badge>
  if (value === "ok" || value === "active" || value === "approved") return <Badge className="bg-emerald-600 hover:bg-emerald-600">{statusLabel(value)}</Badge>
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

function planPayload(form: typeof defaultPlanForm) {
  const year = Number(form.budget_year || currentYear)
  return {
    ...form,
    code: `ECB-${year}-${form.target_scope}-${form.target_code || "all"}`,
    budget_year: year,
    period_start: `${year}-01-01`,
    period_end: `${year}-12-31`,
    target_code: form.target_code || null,
    target_name: form.target_name || null,
    energy_budget_tce: form.energy_budget_tce || null,
    carbon_budget_co2e: form.carbon_budget_co2e || null,
    denominator_plan: form.denominator_plan || null,
    denominator_unit: form.denominator_unit || null,
  }
}

export function EnergyBudgetPanel() {
  const queryClient = useQueryClient()
  const [year, setYear] = useState(String(currentYear))
  const [selectedPlanId, setSelectedPlanId] = useState("auto")
  const [planOpen, setPlanOpen] = useState(false)
  const [adjustmentOpen, setAdjustmentOpen] = useState(false)
  const [planForm, setPlanForm] = useState(defaultPlanForm)
  const [adjustmentForm, setAdjustmentForm] = useState(defaultAdjustmentForm)

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

  const refreshAll = () => queryClient.invalidateQueries({ queryKey: ["energy-budget"] })

  const createPlan = useMutation({
    mutationFn: () =>
      request<BudgetPlan>("/api/energy/budget/plans", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(planPayload(planForm)),
      }),
    onSuccess: (result) => {
      toast.success("预算方案已保存")
      setPlanOpen(false)
      setPlanForm(defaultPlanForm)
      setSelectedPlanId(String(result.data.id))
      refreshAll()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const generateAllocations = useMutation({
    mutationFn: () => request(`/api/energy/budget/plans/${selectedPlan?.id}/generate-allocations`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }),
    onSuccess: () => {
      toast.success("月度预算已生成")
      refreshAll()
    },
    onError: (error) => toast.error("生成失败", { description: error instanceof Error ? error.message : "请先选择预算方案" }),
  })

  const createAdjustment = useMutation({
    mutationFn: () =>
      request<BudgetAdjustment>("/api/energy/budget/adjustments", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          plan_id: selectedPlan?.id,
          allocation_id: adjustmentForm.allocation_id ? Number(adjustmentForm.allocation_id) : null,
          adjusted_energy_budget_tce: adjustmentForm.adjusted_energy_budget_tce || null,
          adjusted_carbon_budget_co2e: adjustmentForm.adjusted_carbon_budget_co2e || null,
          reason: adjustmentForm.reason,
          requested_by: adjustmentForm.requested_by,
          status: adjustmentForm.status,
        }),
      }),
    onSuccess: () => {
      toast.success("调整记录已保存")
      setAdjustmentOpen(false)
      setAdjustmentForm(defaultAdjustmentForm)
      refreshAll()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
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
    <PageSection className="space-y-4">
      <Tabs defaultValue="target" className="space-y-4">
        <AdminPageScaffold
          tabs={
            <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5">
              <TabsTrigger value="target">年度目标</TabsTrigger>
              <TabsTrigger value="allocation">月度预算</TabsTrigger>
              <TabsTrigger value="variance">执行偏差</TabsTrigger>
              <TabsTrigger value="forecast">预测超限</TabsTrigger>
              <TabsTrigger value="adjustment">调整审批</TabsTrigger>
            </TabsList>
          }
          filters={
            <ContextBar
              actions={
                <>
                  <Button variant="outline" onClick={refreshAll}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新
                  </Button>
                  <Dialog open={planOpen} onOpenChange={setPlanOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="mr-2 h-4 w-4" />
                        新增目标
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新增预算目标</DialogTitle>
                      </DialogHeader>
                      <BudgetPlanForm value={planForm} onChange={setPlanForm} />
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setPlanOpen(false)}>
                          取消
                        </Button>
                        <Button onClick={() => createPlan.mutate()} disabled={!planForm.name.trim() || createPlan.isPending}>
                          保存
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
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
          metrics={
            plan ? (
              <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
                <BudgetStat label="能耗预算" value={totals?.budget_tce} unit="tce" status={totals?.energy_status} />
                <BudgetStat label="实际能耗" value={totals?.actual_tce} unit="tce" rate={totals?.energy_execution_rate_pct} />
                <BudgetStat label="碳预算" value={totals?.budget_co2e} unit="tCO2e" status={totals?.carbon_status} />
                <BudgetStat label="实际排放" value={totals?.actual_co2e} unit="tCO2e" rate={totals?.carbon_execution_rate_pct} />
              </MetricStrip>
            ) : (
              <AdminEmptyState title="暂无预算方案" />
            )
          }
        >
          <TabsContent value="target">
            <AdminPanel title={plan?.name ?? "年度目标"} actions={plan ? statusBadge(plan.status) : null}>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <InfoCell label="预算年度" value={plan?.budget_year} />
                <InfoCell label="适用范围" value={targetScopeLabel(plan?.target_scope)} />
                <InfoCell label="对象" value={plan?.target_name || plan?.target_code || "全企业"} />
                <InfoCell label="来源" value={plan?.source_name || "-"} />
                <InfoCell label="能耗目标" value={`${formatNumber(plan?.energy_budget_tce)} tce`} />
                <InfoCell label="碳排目标" value={`${formatNumber(plan?.carbon_budget_co2e)} tCO2e`} />
                <InfoCell label="分母计划" value={`${formatNumber(plan?.denominator_plan)} ${plan?.denominator_unit || ""}`} />
                <InfoCell label="置信度" value={plan?.confidence_level || "-"} />
              </div>
            </AdminPanel>
          </TabsContent>

          <TabsContent value="allocation" className="space-y-4">
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => generateAllocations.mutate()} disabled={!selectedPlan?.id || generateAllocations.isPending}>
                <Wand2 className="mr-2 h-4 w-4" />
                生成月度预算
              </Button>
            </div>
            <MonthlyBudgetTable rows={rows} />
          </TabsContent>

          <TabsContent value="variance">
            <VarianceTable rows={rows} />
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
                {recommendations.length === 0 && <EmptyText text="暂无建议" />}
              </AdminPanel>
            </div>
          </TabsContent>

          <TabsContent value="adjustment" className="space-y-4">
            <div className="flex justify-end">
              <Dialog open={adjustmentOpen} onOpenChange={setAdjustmentOpen}>
                <DialogTrigger asChild>
                  <Button disabled={!selectedPlan?.id}>
                    <Plus className="mr-2 h-4 w-4" />
                    新增调整
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>新增预算调整</DialogTitle>
                  </DialogHeader>
                  <AdjustmentForm rows={rows} value={adjustmentForm} onChange={setAdjustmentForm} />
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setAdjustmentOpen(false)}>
                      取消
                    </Button>
                    <Button onClick={() => createAdjustment.mutate()} disabled={!adjustmentForm.allocation_id || createAdjustment.isPending}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
            <AdjustmentTable rows={adjustments} />
          </TabsContent>
        </AdminPageScaffold>
      </Tabs>

      {alerts.length ? <VarianceTable rows={alerts} compact title="当前预警" /> : null}
    </PageSection>
  )
}

function BudgetStat({ label, value, unit, rate, status }: { label: string; value?: number | null; unit: string; rate?: number | null; status?: string | null }) {
  return <MetricTile label={label} value={formatNumber(value)} unit={unit} meta={rate !== undefined ? `执行率 ${formatNumber(rate, 2)}%` : status ? statusBadge(status) : null} />
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
            {rows.length === 0 && <EmptyRow colSpan={6} />}
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
            {rows.length === 0 && <EmptyRow colSpan={compact ? 6 : 7} />}
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
            {rows.length === 0 && <EmptyRow colSpan={6} />}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

function BudgetPlanForm({ value, onChange }: { value: typeof defaultPlanForm; onChange: (value: typeof defaultPlanForm) => void }) {
  const set = (key: keyof typeof defaultPlanForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Field label="名称">
        <Input value={value.name} onChange={(event) => set("name", event.target.value)} />
      </Field>
      <Field label="年度">
        <Input value={value.budget_year} onChange={(event) => set("budget_year", event.target.value)} />
      </Field>
      <Field label="范围">
        <Select value={value.target_scope} onValueChange={(next) => set("target_scope", next)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {targetScopes.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="对象编码">
        <Input value={value.target_code} onChange={(event) => set("target_code", event.target.value)} />
      </Field>
      <Field label="对象名称">
        <Input value={value.target_name} onChange={(event) => set("target_name", event.target.value)} />
      </Field>
      <Field label="能耗预算(tce)">
        <Input type="number" value={value.energy_budget_tce} onChange={(event) => set("energy_budget_tce", event.target.value)} />
      </Field>
      <Field label="碳预算(tCO2e)">
        <Input type="number" value={value.carbon_budget_co2e} onChange={(event) => set("carbon_budget_co2e", event.target.value)} />
      </Field>
      <Field label="分母计划">
        <Input type="number" value={value.denominator_plan} onChange={(event) => set("denominator_plan", event.target.value)} />
      </Field>
      <Field label="分母单位">
        <Input value={value.denominator_unit} onChange={(event) => set("denominator_unit", event.target.value)} />
      </Field>
      <Field label="来源">
        <Input value={value.source_name} onChange={(event) => set("source_name", event.target.value)} />
      </Field>
      <div className="md:col-span-2">
        <Field label="备注">
          <Textarea value={value.remark} onChange={(event) => set("remark", event.target.value)} />
        </Field>
      </div>
    </div>
  )
}

function AdjustmentForm({ rows, value, onChange }: { rows: BudgetProgressRow[]; value: typeof defaultAdjustmentForm; onChange: (value: typeof defaultAdjustmentForm) => void }) {
  const set = (key: keyof typeof defaultAdjustmentForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Field label="月份">
        <Select value={value.allocation_id} onValueChange={(next) => set("allocation_id", next)}>
          <SelectTrigger>
            <SelectValue placeholder="选择月份" />
          </SelectTrigger>
          <SelectContent>
            {rows.map((row) => (
              <SelectItem key={row.id} value={String(row.id)}>
                {row.period}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="状态">
        <Select value={value.status} onValueChange={(next) => set("status", next)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="submitted">提交</SelectItem>
            <SelectItem value="approved">批准</SelectItem>
          </SelectContent>
        </Select>
      </Field>
      <Field label="调整后能耗(tce)">
        <Input type="number" value={value.adjusted_energy_budget_tce} onChange={(event) => set("adjusted_energy_budget_tce", event.target.value)} />
      </Field>
      <Field label="调整后碳排(tCO2e)">
        <Input type="number" value={value.adjusted_carbon_budget_co2e} onChange={(event) => set("adjusted_carbon_budget_co2e", event.target.value)} />
      </Field>
      <Field label="申请人">
        <Input value={value.requested_by} onChange={(event) => set("requested_by", event.target.value)} />
      </Field>
      <div className="md:col-span-2">
        <Field label="原因">
          <Textarea value={value.reason} onChange={(event) => set("reason", event.target.value)} />
        </Field>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function EmptyRow({ colSpan }: { colSpan: number }) {
  return <AdminTableStateRow colSpan={colSpan}>暂无数据</AdminTableStateRow>
}

function EmptyText({ text }: { text: string }) {
  return <AdminEmptyState title={text} />
}
