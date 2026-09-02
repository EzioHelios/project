import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { BarChart3, Plus, RefreshCw, Trash2, Wand2 } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTabsList, ContextBar } from "@/components/admin-ui"
import { type PageResult, type Row, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

type BudgetPlan = Row & {
  id: number
  code: string
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
  standard_code?: string | null
  confidence_level?: string | null
  remark?: string | null
}

type BudgetAllocation = Row & {
  id: number
  plan_id: number
  period_month: string
  target_scope: string
  target_code?: string | null
  target_name?: string | null
  energy_budget_tce?: number | null
  carbon_budget_co2e?: number | null
  denominator_budget?: number | null
  energy_intensity_budget?: number | null
  carbon_intensity_budget?: number | null
  status: string
  source_name?: string | null
  remark?: string | null
}

type BudgetAdjustment = Row & {
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

type Option = {
  value: string
  label: string
}

const targetScopes = [
  { value: "enterprise", label: "企业" },
  { value: "area", label: "区域" },
  { value: "device", label: "设备" },
]

const statusOptions = [
  { value: "draft", label: "草稿" },
  { value: "active", label: "启用" },
  { value: "closed", label: "关闭" },
]

const adjustmentStatusOptions = [
  { value: "draft", label: "草稿" },
  { value: "submitted", label: "提交" },
  { value: "approved", label: "批准" },
  { value: "rejected", label: "驳回" },
]

const currentYear = new Date().getFullYear()

const emptyPlan = {
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

const emptyAllocation = {
  period_month: "",
  energy_budget_tce: "",
  carbon_budget_co2e: "",
  denominator_budget: "",
  status: "active",
  source_name: "月度预算分解",
  remark: "",
}

const emptyAdjustment = {
  allocation_id: "",
  adjustment_type: "manual",
  adjusted_energy_budget_tce: "",
  adjusted_carbon_budget_co2e: "",
  reason: "",
  requested_by: "",
  approved_by: "",
  status: "draft",
}

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  return String(value)
}

function formatNumber(value: number | string | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function nullable(value: string) {
  return value.trim() ? value.trim() : null
}

function numberOrNull(value: string) {
  return value.trim() ? Number(value) : null
}

function targetScopeLabel(value?: string | null) {
  return targetScopes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function statusLabel(value?: string | null) {
  return [...statusOptions, ...adjustmentStatusOptions].find((item) => item.value === value)?.label ?? value ?? "-"
}

function statusBadge(value?: string | null) {
  if (value === "active" || value === "approved") return <Badge variant="success">{statusLabel(value)}</Badge>
  if (value === "submitted") return <Badge variant="warning">{statusLabel(value)}</Badge>
  if (value === "rejected") return <Badge variant="destructive">{statusLabel(value)}</Badge>
  return <Badge variant="outline">{statusLabel(value)}</Badge>
}

function planForm(row?: BudgetPlan | null) {
  return {
    name: row?.name ?? "",
    budget_year: row?.budget_year == null ? String(currentYear) : String(row.budget_year),
    target_scope: row?.target_scope ?? "enterprise",
    target_code: row?.target_code ?? "",
    target_name: row?.target_name ?? "",
    energy_budget_tce: row?.energy_budget_tce == null ? "" : String(row.energy_budget_tce),
    carbon_budget_co2e: row?.carbon_budget_co2e == null ? "" : String(row.carbon_budget_co2e),
    denominator_plan: row?.denominator_plan == null ? "" : String(row.denominator_plan),
    denominator_unit: row?.denominator_unit ?? "",
    status: row?.status ?? "active",
    source_name: row?.source_name ?? "年度预算目标",
    standard_code: row?.standard_code ?? "enterprise_budget_rule",
    confidence_level: row?.confidence_level ?? "medium",
    remark: row?.remark ?? "",
  }
}

function allocationForm(row?: BudgetAllocation | null) {
  return {
    period_month: row?.period_month ?? "",
    energy_budget_tce: row?.energy_budget_tce == null ? "" : String(row.energy_budget_tce),
    carbon_budget_co2e: row?.carbon_budget_co2e == null ? "" : String(row.carbon_budget_co2e),
    denominator_budget: row?.denominator_budget == null ? "" : String(row.denominator_budget),
    status: row?.status ?? "active",
    source_name: row?.source_name ?? "月度预算分解",
    remark: row?.remark ?? "",
  }
}

function adjustmentForm(row?: BudgetAdjustment | null) {
  return {
    allocation_id: row?.allocation_id == null ? "" : String(row.allocation_id),
    adjustment_type: row?.adjustment_type ?? "manual",
    adjusted_energy_budget_tce: row?.adjusted_energy_budget_tce == null ? "" : String(row.adjusted_energy_budget_tce),
    adjusted_carbon_budget_co2e: row?.adjusted_carbon_budget_co2e == null ? "" : String(row.adjusted_carbon_budget_co2e),
    reason: row?.reason ?? "",
    requested_by: row?.requested_by ?? "",
    approved_by: row?.approved_by ?? "",
    status: row?.status ?? "draft",
  }
}

export function EnergyBudgetSettingsPanel() {
  const queryClient = useQueryClient()
  const [year, setYear] = useState(String(currentYear))
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)
  const [planOpen, setPlanOpen] = useState(false)
  const [planEditing, setPlanEditing] = useState<BudgetPlan | null>(null)
  const [planDetail, setPlanDetail] = useState<BudgetPlan | null>(null)
  const [planValues, setPlanValues] = useState(emptyPlan)
  const [allocationOpen, setAllocationOpen] = useState(false)
  const [allocationEditing, setAllocationEditing] = useState<BudgetAllocation | null>(null)
  const [allocationValues, setAllocationValues] = useState(emptyAllocation)
  const [adjustmentOpen, setAdjustmentOpen] = useState(false)
  const [adjustmentEditing, setAdjustmentEditing] = useState<BudgetAdjustment | null>(null)
  const [adjustmentDetail, setAdjustmentDetail] = useState<BudgetAdjustment | null>(null)
  const [adjustmentValues, setAdjustmentValues] = useState(emptyAdjustment)

  const plansQuery = useQuery<PageResult<BudgetPlan>>({
    queryKey: ["energy-budget-settings", "plans", year],
    queryFn: () => requestPage<BudgetPlan>("/api/energy/budget/plans", { budget_year: year, limit: 200 }),
  })
  const plans = plansQuery.data?.items ?? []
  const selectedPlan = plans.find((item) => item.id === selectedPlanId) ?? plans[0]

  const allocationsQuery = useQuery<PageResult<BudgetAllocation>>({
    queryKey: ["energy-budget-settings", "allocations", selectedPlan?.id],
    queryFn: () => requestPage<BudgetAllocation>("/api/energy/budget/allocations", { plan_id: selectedPlan?.id, limit: 200 }),
    enabled: Boolean(selectedPlan?.id),
  })

  const adjustmentsQuery = useQuery<PageResult<BudgetAdjustment>>({
    queryKey: ["energy-budget-settings", "adjustments", selectedPlan?.id],
    queryFn: () => requestPage<BudgetAdjustment>("/api/energy/budget/adjustments", { plan_id: selectedPlan?.id, limit: 200 }),
    enabled: Boolean(selectedPlan?.id),
  })

  const areasQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-budget-settings", "areas"],
    queryFn: async () => (await request<PageResult<Row>>("/api/master-data/areas/tree")).data,
  })
  const devicesQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-budget-settings", "devices"],
    queryFn: () => requestPage<Row>("/api/master-data/devices", { limit: 500, offset: 0 }),
  })

  const areaOptions = useMemo(() => toOptions(flattenRows(areasQuery.data?.items ?? [])), [areasQuery.data?.items])
  const deviceOptions = useMemo(() => toOptions(devicesQuery.data?.items ?? []), [devicesQuery.data?.items])
  const allocations = allocationsQuery.data?.items ?? []
  const adjustments = adjustmentsQuery.data?.items ?? []

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["energy-budget-settings"] })

  const savePlan = useMutation({
    mutationFn: () => {
      const budgetYear = Number(planValues.budget_year || currentYear)
      const payload = {
        name: planValues.name,
        code: planEditing?.code ?? `ECB-${budgetYear}-${planValues.target_scope}-${planValues.target_code || "all"}-${Date.now()}`,
        budget_year: budgetYear,
        period_start: `${budgetYear}-01-01`,
        period_end: `${budgetYear}-12-31`,
        target_scope: planValues.target_scope,
        target_code: nullable(planValues.target_code),
        target_name: nullable(planValues.target_name),
        energy_budget_tce: numberOrNull(planValues.energy_budget_tce),
        carbon_budget_co2e: numberOrNull(planValues.carbon_budget_co2e),
        denominator_plan: numberOrNull(planValues.denominator_plan),
        denominator_unit: nullable(planValues.denominator_unit),
        status: planValues.status,
        source_name: nullable(planValues.source_name),
        standard_code: nullable(planValues.standard_code),
        confidence_level: nullable(planValues.confidence_level),
        remark: nullable(planValues.remark),
      }
      return request<BudgetPlan>(planEditing ? `/api/energy/budget/plans/${planEditing.id}` : "/api/energy/budget/plans", {
        method: planEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (result) => {
      toast.success(planEditing ? "预算目标已更新" : "预算目标已保存")
      setPlanOpen(false)
      setPlanEditing(null)
      setPlanValues(emptyPlan)
      setSelectedPlanId(result.data.id)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deletePlan = useMutation({
    mutationFn: (id: number) => request(`/api/energy/budget/plans/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("预算目标已删除")
      setSelectedPlanId(null)
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const generateAllocations = useMutation({
    mutationFn: () => request(`/api/energy/budget/plans/${selectedPlan?.id}/generate-allocations`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }),
    onSuccess: () => {
      toast.success("月度预算已生成")
      invalidate()
    },
    onError: (error) => toast.error("生成失败", { description: error instanceof Error ? error.message : "请先选择预算目标" }),
  })

  const saveAllocation = useMutation({
    mutationFn: () =>
      request<BudgetAllocation>(`/api/energy/budget/allocations/${allocationEditing?.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          energy_budget_tce: numberOrNull(allocationValues.energy_budget_tce),
          carbon_budget_co2e: numberOrNull(allocationValues.carbon_budget_co2e),
          denominator_budget: numberOrNull(allocationValues.denominator_budget),
          status: allocationValues.status,
          source_name: nullable(allocationValues.source_name),
          remark: nullable(allocationValues.remark),
        }),
      }),
    onSuccess: () => {
      toast.success("月度预算已更新")
      setAllocationOpen(false)
      setAllocationEditing(null)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const saveAdjustment = useMutation({
    mutationFn: () =>
      request<BudgetAdjustment>(adjustmentEditing ? `/api/energy/budget/adjustments/${adjustmentEditing.id}` : "/api/energy/budget/adjustments", {
        method: adjustmentEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          plan_id: selectedPlan?.id,
          allocation_id: adjustmentValues.allocation_id ? Number(adjustmentValues.allocation_id) : null,
          adjustment_type: adjustmentValues.adjustment_type,
          adjusted_energy_budget_tce: numberOrNull(adjustmentValues.adjusted_energy_budget_tce),
          adjusted_carbon_budget_co2e: numberOrNull(adjustmentValues.adjusted_carbon_budget_co2e),
          reason: nullable(adjustmentValues.reason),
          requested_by: nullable(adjustmentValues.requested_by),
          approved_by: nullable(adjustmentValues.approved_by),
          status: adjustmentValues.status,
        }),
      }),
    onSuccess: () => {
      toast.success(adjustmentEditing ? "调整记录已更新" : "调整记录已保存")
      setAdjustmentOpen(false)
      setAdjustmentEditing(null)
      setAdjustmentValues(emptyAdjustment)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteAdjustment = useMutation({
    mutationFn: (id: number) => request(`/api/energy/budget/adjustments/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("调整记录已删除")
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const startCreatePlan = () => {
    setPlanEditing(null)
    setPlanValues({ ...emptyPlan, budget_year: year || String(currentYear) })
    setPlanOpen(true)
  }

  const startEditPlan = (row: BudgetPlan) => {
    setPlanEditing(row)
    setPlanValues(planForm(row))
    setPlanOpen(true)
  }

  const startEditAllocation = (row: BudgetAllocation) => {
    setAllocationEditing(row)
    setAllocationValues(allocationForm(row))
    setAllocationOpen(true)
  }

  const startCreateAdjustment = () => {
    setAdjustmentEditing(null)
    setAdjustmentValues(emptyAdjustment)
    setAdjustmentOpen(true)
  }

  const startEditAdjustment = (row: BudgetAdjustment) => {
    setAdjustmentEditing(row)
    setAdjustmentValues(adjustmentForm(row))
    setAdjustmentOpen(true)
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageHeader
        title="能碳预算维护"
        actions={
          <>
            <Button variant="outline" onClick={() => invalidate()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button variant="outline" asChild>
              <Link to="/energy/budget">
                <BarChart3 className="mr-2 h-4 w-4" />
                查看执行
              </Link>
            </Button>
            <Button onClick={startCreatePlan}>
              <Plus className="mr-2 h-4 w-4" />
              新增目标
            </Button>
          </>
        }
      />

      <Tabs defaultValue="plans" className="space-y-4">
        <AdminTabsList>
          <TabsTrigger value="plans">年度目标</TabsTrigger>
          <TabsTrigger value="allocations">月度分解</TabsTrigger>
          <TabsTrigger value="adjustments">调整记录</TabsTrigger>
        </AdminTabsList>

        <TabsContent value="plans" className="space-y-4">
          <ContextBar>
            <Input value={year} onChange={(event) => setYear(event.target.value)} placeholder="年度" />
            <Select value={selectedPlan?.id ? String(selectedPlan.id) : undefined} onValueChange={(value) => setSelectedPlanId(Number(value))}>
              <SelectTrigger>
                <SelectValue placeholder="选择预算目标" />
              </SelectTrigger>
              <SelectContent>
                {plans.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ContextBar>
          <AdminPanel title="年度预算目标" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <PlanTable
                rows={plans}
                selectedId={selectedPlan?.id}
                onSelect={setSelectedPlanId}
                onDetail={setPlanDetail}
                onEdit={startEditPlan}
                onDelete={(id) => deletePlan.mutate(id)}
              />
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="allocations" className="space-y-4">
          <ContextBar
            actions={
              <Button variant="outline" onClick={() => generateAllocations.mutate()} disabled={!selectedPlan?.id || generateAllocations.isPending}>
                <Wand2 className="mr-2 h-4 w-4" />
                生成月度预算
              </Button>
            }
          >
            <Input value={selectedPlan?.name ?? ""} readOnly placeholder="当前预算目标" />
          </ContextBar>
          <AdminPanel title="月度预算分解" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <AllocationTable rows={allocations} onEdit={startEditAllocation} />
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="adjustments" className="space-y-4">
          <ContextBar
            actions={
              <Button onClick={startCreateAdjustment} disabled={!selectedPlan?.id}>
                <Plus className="mr-2 h-4 w-4" />
                新增调整
              </Button>
            }
          >
            <Input value={selectedPlan?.name ?? ""} readOnly placeholder="当前预算目标" />
          </ContextBar>
          <AdminPanel title="调整记录" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <AdjustmentTable rows={adjustments} onDetail={setAdjustmentDetail} onEdit={startEditAdjustment} onDelete={(id) => deleteAdjustment.mutate(id)} />
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>
      </Tabs>

      <PlanDialog
        open={planOpen}
        values={planValues}
        editing={planEditing}
        saving={savePlan.isPending}
        areaOptions={areaOptions}
        deviceOptions={deviceOptions}
        onOpenChange={setPlanOpen}
        onChange={setPlanValues}
        onSave={() => savePlan.mutate()}
      />
      <AllocationDialog
        open={allocationOpen}
        values={allocationValues}
        saving={saveAllocation.isPending}
        onOpenChange={setAllocationOpen}
        onChange={setAllocationValues}
        onSave={() => saveAllocation.mutate()}
      />
      <AdjustmentDialog
        open={adjustmentOpen}
        values={adjustmentValues}
        editing={adjustmentEditing}
        saving={saveAdjustment.isPending}
        allocations={allocations}
        onOpenChange={setAdjustmentOpen}
        onChange={setAdjustmentValues}
        onSave={() => saveAdjustment.mutate()}
      />
      <DetailSheet title="预算目标详情" row={planDetail} labels={planLabels} onClose={() => setPlanDetail(null)} />
      <DetailSheet title="调整记录详情" row={adjustmentDetail} labels={adjustmentLabels} onClose={() => setAdjustmentDetail(null)} />
    </PageContainer>
  )
}

function toOptions(rows: Row[]): Option[] {
  return rows.map((row) => ({
    value: String(row.id ?? row.code ?? ""),
    label: String(row.name ?? row.code ?? row.id ?? ""),
  }))
}

function flattenRows(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenRows((Array.isArray(row.children) ? row.children : []) as Row[])])
}

function PlanTable({
  rows,
  selectedId,
  onSelect,
  onDetail,
  onEdit,
  onDelete,
}: {
  rows: BudgetPlan[]
  selectedId?: number
  onSelect: (id: number) => void
  onDetail: (row: BudgetPlan) => void
  onEdit: (row: BudgetPlan) => void
  onDelete: (id: number) => void
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>目标名称</TableHead>
          <TableHead>年度</TableHead>
          <TableHead>对象</TableHead>
          <TableHead className="text-right">能耗预算(tce)</TableHead>
          <TableHead className="text-right">碳预算(tCO2e)</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id} data-selected={selectedId === row.id}>
            <TableCell className="font-medium">{row.name}</TableCell>
            <TableCell>{row.budget_year}</TableCell>
            <TableCell>
              <div>{row.target_name || row.target_code || "全企业"}</div>
              <div className="text-xs text-muted-foreground">{targetScopeLabel(row.target_scope)}</div>
            </TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.energy_budget_tce)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.carbon_budget_co2e)}</TableCell>
            <TableCell>{statusBadge(row.status)}</TableCell>
            <TableCell className="space-x-2 text-right">
              <Button variant="secondary" size="sm" onClick={() => onDetail(row)}>
                详情
              </Button>
              <Button variant="outline" size="sm" onClick={() => onSelect(row.id)}>
                选择
              </Button>
              <Button variant="outline" size="sm" onClick={() => onEdit(row)}>
                编辑
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  if (window.confirm("确认删除该预算目标？")) onDelete(row.id)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <AdminTableStateRow colSpan={7}>暂无预算目标</AdminTableStateRow>}
      </TableBody>
    </Table>
  )
}

function AllocationTable({ rows, onEdit }: { rows: BudgetAllocation[]; onEdit: (row: BudgetAllocation) => void }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>月份</TableHead>
          <TableHead className="text-right">能耗预算(tce)</TableHead>
          <TableHead className="text-right">碳预算(tCO2e)</TableHead>
          <TableHead className="text-right">分母预算</TableHead>
          <TableHead className="text-right">能耗强度</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell>{row.period_month}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.energy_budget_tce)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.carbon_budget_co2e)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.denominator_budget)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.energy_intensity_budget)}</TableCell>
            <TableCell>{statusBadge(row.status)}</TableCell>
            <TableCell className="text-right">
              <Button variant="outline" size="sm" onClick={() => onEdit(row)}>
                编辑
              </Button>
            </TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <AdminTableStateRow colSpan={7}>暂无月度预算</AdminTableStateRow>}
      </TableBody>
    </Table>
  )
}

function AdjustmentTable({
  rows,
  onDetail,
  onEdit,
  onDelete,
}: {
  rows: BudgetAdjustment[]
  onDetail: (row: BudgetAdjustment) => void
  onEdit: (row: BudgetAdjustment) => void
  onDelete: (id: number) => void
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>编号</TableHead>
          <TableHead>类型</TableHead>
          <TableHead>生效月份</TableHead>
          <TableHead className="text-right">调整后能耗</TableHead>
          <TableHead className="text-right">调整后碳排</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell className="font-medium">{row.adjustment_no}</TableCell>
            <TableCell>{display(row.adjustment_type)}</TableCell>
            <TableCell>{display(row.effective_month)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.adjusted_energy_budget_tce)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.adjusted_carbon_budget_co2e)}</TableCell>
            <TableCell>{statusBadge(row.status)}</TableCell>
            <TableCell className="space-x-2 text-right">
              <Button variant="secondary" size="sm" onClick={() => onDetail(row)}>
                详情
              </Button>
              <Button variant="outline" size="sm" onClick={() => onEdit(row)}>
                编辑
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="删除调整记录"
                onClick={() => {
                  if (window.confirm("确认删除该调整记录？")) onDelete(row.id)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <AdminTableStateRow colSpan={7}>暂无调整记录</AdminTableStateRow>}
      </TableBody>
    </Table>
  )
}

function PlanDialog({
  open,
  values,
  editing,
  saving,
  areaOptions,
  deviceOptions,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyPlan
  editing: BudgetPlan | null
  saving: boolean
  areaOptions: Option[]
  deviceOptions: Option[]
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyPlan) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyPlan, value: string) => onChange({ ...values, [key]: value })
  const targetOptions = values.target_scope === "area" ? areaOptions : values.target_scope === "device" ? deviceOptions : []
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑预算目标" : "新增预算目标"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="目标名称" value={values.name} onChange={(next) => set("name", next)} />
          <TextField label="年度" value={values.budget_year} onChange={(next) => set("budget_year", next)} />
          <SelectField
            label="适用范围"
            value={values.target_scope}
            options={targetScopes}
            onChange={(next) => {
              onChange({ ...values, target_scope: next, target_code: "", target_name: "" })
            }}
          />
          {values.target_scope === "area" || values.target_scope === "device" ? (
            <SelectField
              label="对象"
              value={values.target_code}
              options={targetOptions}
              onChange={(next) => {
                const option = targetOptions.find((item) => item.value === next)
                onChange({ ...values, target_code: next, target_name: option?.label ?? "" })
              }}
            />
          ) : values.target_scope === "enterprise" ? null : (
            <>
              <TextField label="对象编码" value={values.target_code} onChange={(next) => set("target_code", next)} />
              <TextField label="对象名称" value={values.target_name} onChange={(next) => set("target_name", next)} />
            </>
          )}
          <TextField label="能耗预算(tce)" type="number" value={values.energy_budget_tce} onChange={(next) => set("energy_budget_tce", next)} />
          <TextField label="碳排预算(tCO2e)" type="number" value={values.carbon_budget_co2e} onChange={(next) => set("carbon_budget_co2e", next)} />
          <TextField label="分母计划" type="number" value={values.denominator_plan} onChange={(next) => set("denominator_plan", next)} />
          <TextField label="分母单位" value={values.denominator_unit} onChange={(next) => set("denominator_unit", next)} />
          <SelectField label="状态" value={values.status} options={statusOptions} onChange={(next) => set("status", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <TextField label="标准/口径编码" value={values.standard_code} onChange={(next) => set("standard_code", next)} />
          <TextField label="置信度" value={values.confidence_level} onChange={(next) => set("confidence_level", next)} />
          <div className="grid gap-2 md:col-span-2">
            <Label>备注</Label>
            <Textarea value={values.remark} onChange={(event) => set("remark", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={!values.name.trim() || saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AllocationDialog({
  open,
  values,
  saving,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyAllocation
  saving: boolean
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyAllocation) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyAllocation, value: string) => onChange({ ...values, [key]: value })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>编辑月度预算</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="月份" value={values.period_month} readOnly />
          <SelectField label="状态" value={values.status} options={statusOptions} onChange={(next) => set("status", next)} />
          <TextField label="能耗预算(tce)" type="number" value={values.energy_budget_tce} onChange={(next) => set("energy_budget_tce", next)} />
          <TextField label="碳排预算(tCO2e)" type="number" value={values.carbon_budget_co2e} onChange={(next) => set("carbon_budget_co2e", next)} />
          <TextField label="分母预算" type="number" value={values.denominator_budget} onChange={(next) => set("denominator_budget", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <div className="grid gap-2 md:col-span-2">
            <Label>备注</Label>
            <Textarea value={values.remark} onChange={(event) => set("remark", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AdjustmentDialog({
  open,
  values,
  editing,
  saving,
  allocations,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyAdjustment
  editing: BudgetAdjustment | null
  saving: boolean
  allocations: BudgetAllocation[]
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyAdjustment) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyAdjustment, value: string) => onChange({ ...values, [key]: value })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑预算调整" : "新增预算调整"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            label="月份"
            value={values.allocation_id}
            options={allocations.map((row) => ({ value: String(row.id), label: row.period_month }))}
            onChange={(next) => set("allocation_id", next)}
          />
          <SelectField label="状态" value={values.status} options={adjustmentStatusOptions} onChange={(next) => set("status", next)} />
          <TextField label="调整类型" value={values.adjustment_type} onChange={(next) => set("adjustment_type", next)} />
          <TextField label="申请人" value={values.requested_by} onChange={(next) => set("requested_by", next)} />
          <TextField label="批准人" value={values.approved_by} onChange={(next) => set("approved_by", next)} />
          <TextField label="调整后能耗(tce)" type="number" value={values.adjusted_energy_budget_tce} onChange={(next) => set("adjusted_energy_budget_tce", next)} />
          <TextField label="调整后碳排(tCO2e)" type="number" value={values.adjusted_carbon_budget_co2e} onChange={(next) => set("adjusted_carbon_budget_co2e", next)} />
          <div className="grid gap-2 md:col-span-2">
            <Label>原因</Label>
            <Textarea value={values.reason} onChange={(event) => set("reason", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={!values.allocation_id || saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
  readOnly = false,
}: {
  label: string
  value: string
  onChange?: (value: string) => void
  type?: string
  readOnly?: boolean
}) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type={type} value={value} readOnly={readOnly} onChange={(event) => onChange?.(event.target.value)} />
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: Option[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="请选择" />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

const planLabels: Record<string, string> = {
  code: "目标编码",
  name: "目标名称",
  budget_year: "年度",
  target_scope: "适用范围",
  target_code: "对象编码",
  target_name: "对象名称",
  energy_budget_tce: "能耗预算",
  carbon_budget_co2e: "碳排预算",
  denominator_plan: "分母计划",
  denominator_unit: "分母单位",
  status: "状态",
  source_name: "来源",
  standard_code: "标准/口径编码",
  confidence_level: "置信度",
  remark: "备注",
}

const adjustmentLabels: Record<string, string> = {
  adjustment_no: "调整编号",
  adjustment_type: "调整类型",
  effective_month: "生效月份",
  original_energy_budget_tce: "原能耗预算",
  original_carbon_budget_co2e: "原碳排预算",
  adjusted_energy_budget_tce: "调整后能耗",
  adjusted_carbon_budget_co2e: "调整后碳排",
  reason: "原因",
  status: "状态",
  requested_by: "申请人",
  approved_by: "批准人",
}

function DetailSheet({ title, row, labels, onClose }: { title: string; row: Row | null; labels: Record<string, string>; onClose: () => void }) {
  const entries = row ? Object.entries(row).filter(([key]) => key !== "id" && key !== "created_at" && key !== "updated_at") : []
  return (
    <Sheet open={Boolean(row)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <div className="space-y-2 px-4 pb-6">
          {entries.map(([key, value]) => (
            <div key={key} className="grid grid-cols-[128px_1fr] gap-3 rounded-md border px-3 py-2 text-sm">
              <div className="text-muted-foreground">{labels[key] ?? key}</div>
              <div className="min-w-0 break-all">{display(value)}</div>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}
