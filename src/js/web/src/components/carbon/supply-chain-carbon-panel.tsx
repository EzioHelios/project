import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BarChart3, Building2, CheckCircle2, ClipboardList, FileCheck2, Plus, Send } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type SupplyChainSummary = {
  supplier_count: number
  task_count: number
  submitted_task_count: number
  approved_task_count: number
  high_risk_supplier_count: number
}

type Supplier = {
  id: number
  supplier_code: string
  name: string
  industry?: string | null
  supplier_type?: string | null
  contact_name?: string | null
  contact_email?: string | null
  country_region?: string | null
  status: string
  risk_level: string
  task_count?: number
  approved_task_count?: number
}

type SupplierSite = {
  id: number
  supplier_id: number
  site_code: string
  site_name: string
  country_region?: string | null
  facility_scope?: string | null
  status: string
}

type DisclosureTask = {
  id: number
  task_no: string
  task_name: string
  supplier_id: number
  supplier_name?: string | null
  task_type: string
  product_code?: string | null
  product_name?: string | null
  period_start: string
  period_end: string
  due_date?: string | null
  status: string
  data_count?: number
  evidence_count?: number
}

type SupplierCarbonData = {
  id: number
  task_id: number
  data_no: string
  data_type: string
  scope_category?: string | null
  product_code?: string | null
  product_name?: string | null
  material_code?: string | null
  material_name?: string | null
  activity_amount?: number | null
  activity_unit?: string | null
  pcf_value?: number | null
  pcf_unit?: string | null
  co2e_amount?: number | null
  boundary_type?: string | null
  data_quality: string
  verified: boolean
  status: string
}

type SupplierEvidence = {
  id: number
  task_id: number
  evidence_no: string
  evidence_type: string
  file_name: string
  review_status: string
  submitted_by?: string | null
}

type DisclosureRelease = {
  id: number
  release_no: string
  task_id: number
  release_type: string
  recipient_name?: string | null
  status: string
  released_at?: string | null
}

type SupplyChainAnalysis = {
  supplier_ranking: {
    supplier_id: number
    supplier_name: string
    risk_level: string
    data_count: number
    co2e_amount: number
    pcf_value_sum: number
  }[]
  high_carbon_categories: {
    scope_category: string
    data_count: number
    co2e_amount: number
    pcf_value_sum: number
  }[]
  recommendations: {
    target_type: string
    target_name: string
    priority: string
    action: string
  }[]
}

type SupplierForm = {
  supplier_code: string
  name: string
  industry: string
  supplier_type: string
  contact_name: string
  contact_email: string
  country_region: string
  risk_level: string
}

type SiteForm = {
  supplier_id: string
  site_code: string
  site_name: string
  country_region: string
  facility_scope: string
}

type TaskForm = {
  supplier_id: string
  task_no: string
  task_name: string
  task_type: string
  product_code: string
  product_name: string
  period_start: string
  period_end: string
  due_date: string
  requested_by: string
}

type DataForm = {
  data_no: string
  data_type: string
  scope_category: string
  product_code: string
  product_name: string
  material_code: string
  material_name: string
  activity_amount: string
  activity_unit: string
  pcf_value: string
  pcf_unit: string
  co2e_amount: string
  boundary_type: string
  data_quality: string
}

type EvidenceForm = {
  evidence_no: string
  evidence_type: string
  file_name: string
  file_path: string
  submitted_by: string
}

type ReleaseForm = {
  release_no: string
  recipient_name: string
  release_type: string
}

const QUERY_KEY = ["supply-chain-carbon"]

const defaultSupplierForm: SupplierForm = {
  supplier_code: "",
  name: "",
  industry: "",
  supplier_type: "material",
  contact_name: "",
  contact_email: "",
  country_region: "中国",
  risk_level: "medium",
}

const defaultSiteForm: SiteForm = {
  supplier_id: "",
  site_code: "",
  site_name: "",
  country_region: "中国",
  facility_scope: "",
}

const defaultTaskForm: TaskForm = {
  supplier_id: "",
  task_no: "",
  task_name: "",
  task_type: "mixed",
  product_code: "",
  product_name: "",
  period_start: "",
  period_end: "",
  due_date: "",
  requested_by: "",
}

const defaultDataForm: DataForm = {
  data_no: "",
  data_type: "activity",
  scope_category: "purchased_goods",
  product_code: "",
  product_name: "",
  material_code: "",
  material_name: "",
  activity_amount: "",
  activity_unit: "",
  pcf_value: "",
  pcf_unit: "kgCO2e/unit",
  co2e_amount: "",
  boundary_type: "cradle_to_gate",
  data_quality: "supplier_reported",
}

const defaultEvidenceForm: EvidenceForm = {
  evidence_no: "",
  evidence_type: "pcf_report",
  file_name: "",
  file_path: "",
  submitted_by: "",
}

const defaultReleaseForm: ReleaseForm = {
  release_no: "",
  recipient_name: "",
  release_type: "customer_disclosure",
}

const taskStatusLabels: Record<string, string> = {
  draft: "草稿",
  issued: "已下发",
  submitted: "待审核",
  needs_revision: "待补正",
  approved: "已审核",
  rejected: "已驳回",
  expired: "已过期",
}

const riskLabels: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
}

export function SupplyChainCarbonPanel() {
  const qc = useQueryClient()
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [supplierOpen, setSupplierOpen] = useState(false)
  const [siteOpen, setSiteOpen] = useState(false)
  const [taskOpen, setTaskOpen] = useState(false)
  const [dataOpen, setDataOpen] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [releaseOpen, setReleaseOpen] = useState(false)
  const [supplierForm, setSupplierForm] = useState<SupplierForm>(defaultSupplierForm)
  const [siteForm, setSiteForm] = useState<SiteForm>(defaultSiteForm)
  const [taskForm, setTaskForm] = useState<TaskForm>(defaultTaskForm)
  const [dataForm, setDataForm] = useState<DataForm>(defaultDataForm)
  const [evidenceForm, setEvidenceForm] = useState<EvidenceForm>(defaultEvidenceForm)
  const [releaseForm, setReleaseForm] = useState<ReleaseForm>(defaultReleaseForm)

  const summaryQuery = useQuery<ApiEnvelope<SupplyChainSummary>>({
    queryKey: [...QUERY_KEY, "summary"],
    queryFn: () => fetchCarbonApi<SupplyChainSummary>("/api/carbon/supply-chain/summary"),
  })
  const suppliersQuery = useQuery<PageResult<Supplier>>({
    queryKey: [...QUERY_KEY, "suppliers"],
    queryFn: () => requestPage<Supplier>("/api/carbon/supply-chain/suppliers", { limit: 100 }),
  })
  const tasksQuery = useQuery<PageResult<DisclosureTask>>({
    queryKey: [...QUERY_KEY, "tasks"],
    queryFn: () => requestPage<DisclosureTask>("/api/carbon/supply-chain/tasks", { limit: 100 }),
  })

  const suppliers = suppliersQuery.data?.items ?? []
  const tasks = tasksQuery.data?.items ?? []
  const activeTaskId = selectedTaskId ?? tasks[0]?.id ?? null
  const activeTask = useMemo(() => tasks.find((item) => item.id === activeTaskId) ?? null, [activeTaskId, tasks])

  const sitesQuery = useQuery<PageResult<SupplierSite>>({
    queryKey: [...QUERY_KEY, "sites"],
    queryFn: () => requestPage<SupplierSite>("/api/carbon/supply-chain/sites", { limit: 100 }),
  })
  const dataQuery = useQuery<PageResult<SupplierCarbonData>>({
    queryKey: [...QUERY_KEY, "data", activeTaskId],
    queryFn: () => requestPage<SupplierCarbonData>(`/api/carbon/supply-chain/tasks/${activeTaskId}/data`, { limit: 200 }),
    enabled: Boolean(activeTaskId),
  })
  const evidenceQuery = useQuery<PageResult<SupplierEvidence>>({
    queryKey: [...QUERY_KEY, "evidence", activeTaskId],
    queryFn: () => requestPage<SupplierEvidence>(`/api/carbon/supply-chain/tasks/${activeTaskId}/evidence`, { limit: 200 }),
    enabled: Boolean(activeTaskId),
  })
  const releasesQuery = useQuery<PageResult<DisclosureRelease>>({
    queryKey: [...QUERY_KEY, "releases"],
    queryFn: () => requestPage<DisclosureRelease>("/api/carbon/supply-chain/releases", { limit: 100 }),
  })
  const analysisQuery = useQuery<ApiEnvelope<SupplyChainAnalysis>>({
    queryKey: [...QUERY_KEY, "analysis"],
    queryFn: () => fetchCarbonApi<SupplyChainAnalysis>("/api/carbon/supply-chain/analysis"),
  })

  const summary = summaryQuery.data?.data
  const sites = sitesQuery.data?.items ?? []
  const dataItems = dataQuery.data?.items ?? []
  const evidenceItems = evidenceQuery.data?.items ?? []
  const releases = releasesQuery.data?.items ?? []
  const analysis = analysisQuery.data?.data

  const createSupplier = useMutation({
    mutationFn: () =>
      request<Supplier>("/api/carbon/supply-chain/suppliers", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(supplierPayload(supplierForm)),
      }),
    onSuccess: async () => {
      toast.success("供应商已创建")
      setSupplierOpen(false)
      setSupplierForm(defaultSupplierForm)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("创建供应商失败"),
  })

  const createSite = useMutation({
    mutationFn: () =>
      request<SupplierSite>("/api/carbon/supply-chain/sites", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(sitePayload(siteForm)),
      }),
    onSuccess: async () => {
      toast.success("供应商场站已创建")
      setSiteOpen(false)
      setSiteForm(defaultSiteForm)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("创建场站失败"),
  })

  const createTask = useMutation({
    mutationFn: () =>
      request<DisclosureTask>("/api/carbon/supply-chain/tasks", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(taskPayload(taskForm)),
      }),
    onSuccess: async (response) => {
      toast.success("填报任务已创建")
      setTaskOpen(false)
      setTaskForm(defaultTaskForm)
      setSelectedTaskId(response.data.id)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("创建任务失败"),
  })

  const createData = useMutation({
    mutationFn: () =>
      request<SupplierCarbonData>(`/api/carbon/supply-chain/tasks/${activeTaskId}/data`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(dataPayload(dataForm)),
      }),
    onSuccess: async () => {
      toast.success("填报数据已创建")
      setDataOpen(false)
      setDataForm(defaultDataForm)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("创建数据失败"),
  })

  const createEvidence = useMutation({
    mutationFn: () =>
      request<SupplierEvidence>(`/api/carbon/supply-chain/tasks/${activeTaskId}/evidence`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(evidencePayload(evidenceForm)),
      }),
    onSuccess: async () => {
      toast.success("证据已创建")
      setEvidenceOpen(false)
      setEvidenceForm(defaultEvidenceForm)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("创建证据失败"),
  })

  const decideTask = useMutation({
    mutationFn: ({ taskId, action, reason }: { taskId: number; action: "submit" | "approve" | "reject"; reason?: string }) =>
      request<DisclosureTask>(`/api/carbon/supply-chain/tasks/${taskId}/${action}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ reason, reviewed_by: "current_user" }),
      }),
    onSuccess: async () => {
      toast.success("任务状态已更新")
      await invalidateSupplyChain(qc)
    },
    onError: toastError("更新任务状态失败"),
  })

  const createRelease = useMutation({
    mutationFn: () =>
      request<DisclosureRelease>(`/api/carbon/supply-chain/tasks/${activeTaskId}/releases`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(releasePayload(releaseForm)),
      }),
    onSuccess: async () => {
      toast.success("披露记录已生成")
      setReleaseOpen(false)
      setReleaseForm(defaultReleaseForm)
      await invalidateSupplyChain(qc)
    },
    onError: toastError("生成披露失败"),
  })

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "供应商", value: String(summary?.supplier_count ?? 0), icon: Building2 },
          { label: "填报任务", value: String(summary?.task_count ?? 0), icon: ClipboardList },
          { label: "待审核", value: String(summary?.submitted_task_count ?? 0), icon: FileCheck2 },
          { label: "高风险", value: String(summary?.high_risk_supplier_count ?? 0), icon: BarChart3 },
        ]}
      />

      <Tabs defaultValue="suppliers" className="space-y-4">
        <TabsList className="flex h-auto w-full flex-wrap justify-start">
          <TabsTrigger value="suppliers">供应商档案</TabsTrigger>
          <TabsTrigger value="tasks">填报任务</TabsTrigger>
          <TabsTrigger value="review">数据审核</TabsTrigger>
          <TabsTrigger value="disclosure">下游披露</TabsTrigger>
          <TabsTrigger value="analysis">供应链分析</TabsTrigger>
        </TabsList>

        <TabsContent value="suppliers">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            <AdminPanel
              title="供应商档案"
              actions={
                <Dialog open={supplierOpen} onOpenChange={setSupplierOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">
                      <Plus className="size-4" />
                      新建供应商
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>新建供应商</DialogTitle>
                    </DialogHeader>
                    <SupplierFormView value={supplierForm} onChange={setSupplierForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setSupplierOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createSupplier.isPending} onClick={() => createSupplier.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>供应商</TableHead>
                      <TableHead>行业</TableHead>
                      <TableHead>联系人</TableHead>
                      <TableHead>风险</TableHead>
                      <TableHead>任务</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {suppliers.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div className="font-medium">{item.name}</div>
                          <div className="text-muted-foreground text-xs">{item.supplier_code}</div>
                        </TableCell>
                        <TableCell>{item.industry || "-"}</TableCell>
                        <TableCell>
                          <div>{item.contact_name || "-"}</div>
                          <div className="text-muted-foreground text-xs">{item.contact_email || "-"}</div>
                        </TableCell>
                        <TableCell>
                          <RiskBadge level={item.risk_level} />
                        </TableCell>
                        <TableCell>
                          {item.approved_task_count ?? 0}/{item.task_count ?? 0}
                        </TableCell>
                        <TableCell>
                          <CarbonStatusBadge status={item.status} />
                        </TableCell>
                      </TableRow>
                    ))}
                    {!suppliers.length ? <EmptyRow colSpan={6} label="暂无供应商" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>

            <AdminPanel
              title="供应商场站"
              actions={
                <Dialog open={siteOpen} onOpenChange={setSiteOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!suppliers.length}>
                      <Plus className="size-4" />
                      新增场站
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增场站</DialogTitle>
                    </DialogHeader>
                    <SiteFormView suppliers={suppliers} value={siteForm} onChange={setSiteForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setSiteOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createSite.isPending} onClick={() => createSite.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>场站</TableHead>
                      <TableHead>范围</TableHead>
                      <TableHead>区域</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sites.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div>{item.site_name}</div>
                          <div className="text-muted-foreground text-xs">{item.site_code}</div>
                        </TableCell>
                        <TableCell>{item.facility_scope || "-"}</TableCell>
                        <TableCell>{item.country_region || "-"}</TableCell>
                      </TableRow>
                    ))}
                    {!sites.length ? <EmptyRow colSpan={3} label="暂无场站" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="tasks">
          <AdminPanel
            title="填报任务"
            actions={
              <Dialog open={taskOpen} onOpenChange={setTaskOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" disabled={!suppliers.length}>
                    <Plus className="size-4" />
                    新建任务
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-4xl">
                  <DialogHeader>
                    <DialogTitle>新建填报任务</DialogTitle>
                  </DialogHeader>
                  <TaskFormView suppliers={suppliers} value={taskForm} onChange={setTaskForm} />
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setTaskOpen(false)}>
                      取消
                    </Button>
                    <Button disabled={createTask.isPending} onClick={() => createTask.mutate()}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>任务</TableHead>
                    <TableHead>供应商</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>产品</TableHead>
                    <TableHead>期间</TableHead>
                    <TableHead>数据/证据</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tasks.map((item) => (
                    <TableRow key={item.id} data-state={item.id === activeTaskId ? "selected" : undefined}>
                      <TableCell>
                        <div className="font-medium">{item.task_no}</div>
                        <div className="text-muted-foreground text-xs">{item.task_name}</div>
                      </TableCell>
                      <TableCell>{item.supplier_name || supplierName(suppliers, item.supplier_id)}</TableCell>
                      <TableCell>{taskTypeLabel(item.task_type)}</TableCell>
                      <TableCell>{item.product_name || item.product_code || "-"}</TableCell>
                      <TableCell>{dateRange(item.period_start, item.period_end)}</TableCell>
                      <TableCell>
                        {item.data_count ?? 0}/{item.evidence_count ?? 0}
                      </TableCell>
                      <TableCell>
                        <TaskStatusBadge status={item.status} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="outline" onClick={() => setSelectedTaskId(item.id)}>
                            查看
                          </Button>
                          <Button size="sm" variant="outline" disabled={item.status === "approved"} onClick={() => decideTask.mutate({ taskId: item.id, action: "submit" })}>
                            提交
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!tasks.length ? <EmptyRow colSpan={8} label="暂无填报任务" /> : null}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="review">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            <AdminPanel
              title="填报数据"
              actions={
                <Dialog open={dataOpen} onOpenChange={setDataOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!activeTaskId || activeTask?.status === "approved"}>
                      <Plus className="size-4" />
                      新增数据
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-4xl">
                    <DialogHeader>
                      <DialogTitle>新增填报数据</DialogTitle>
                    </DialogHeader>
                    <DataFormView value={dataForm} onChange={setDataForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setDataOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createData.isPending} onClick={() => createData.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>数据</TableHead>
                      <TableHead>品类/产品</TableHead>
                      <TableHead>活动量</TableHead>
                      <TableHead>PCF</TableHead>
                      <TableHead>CO2e</TableHead>
                      <TableHead>质量</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dataItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div>{item.data_no}</div>
                          <div className="text-muted-foreground text-xs">{dataTypeLabel(item.data_type)}</div>
                        </TableCell>
                        <TableCell>
                          <div>{item.material_name || item.product_name || item.scope_category || "-"}</div>
                          <div className="text-muted-foreground text-xs">{item.material_code || item.product_code || "-"}</div>
                        </TableCell>
                        <TableCell>{amountWithUnit(item.activity_amount, item.activity_unit)}</TableCell>
                        <TableCell>{amountWithUnit(item.pcf_value, item.pcf_unit)}</TableCell>
                        <TableCell>{formatNumber(item.co2e_amount)}</TableCell>
                        <TableCell>{item.data_quality}</TableCell>
                        <TableCell>
                          <TaskStatusBadge status={item.status} />
                        </TableCell>
                      </TableRow>
                    ))}
                    {!dataItems.length ? <EmptyRow colSpan={7} label="暂无填报数据" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>

            <AdminPanel
              title="证据与审核"
              actions={
                <Dialog open={evidenceOpen} onOpenChange={setEvidenceOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!activeTaskId || activeTask?.status === "approved"}>
                      <Plus className="size-4" />
                      新增证据
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增证据</DialogTitle>
                    </DialogHeader>
                    <EvidenceFormView value={evidenceForm} onChange={setEvidenceForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setEvidenceOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createEvidence.isPending} onClick={() => createEvidence.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="space-y-4"
            >
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!activeTaskId || activeTask?.status !== "submitted"}
                  onClick={() => decideTask.mutate({ taskId: activeTaskId ?? 0, action: "approve" })}
                >
                  <CheckCircle2 className="size-4" />
                  通过
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!activeTaskId || activeTask?.status !== "submitted"}
                  onClick={() => {
                    const reason = window.prompt("驳回原因", "资料不完整")
                    if (reason) decideTask.mutate({ taskId: activeTaskId ?? 0, action: "reject", reason })
                  }}
                >
                  驳回
                </Button>
              </div>
              <AdminDataTable>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>证据</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {evidenceItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div>{item.file_name}</div>
                          <div className="text-muted-foreground text-xs">{item.evidence_no}</div>
                        </TableCell>
                        <TableCell>{item.evidence_type}</TableCell>
                        <TableCell>{evidenceStatusLabel(item.review_status)}</TableCell>
                      </TableRow>
                    ))}
                    {!evidenceItems.length ? <EmptyRow colSpan={3} label="暂无证据" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="disclosure">
          <AdminPanel
            title="下游披露"
            actions={
              <Dialog open={releaseOpen} onOpenChange={setReleaseOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" disabled={!activeTaskId || activeTask?.status !== "approved"}>
                    <Send className="size-4" />
                    生成披露
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>生成披露记录</DialogTitle>
                  </DialogHeader>
                  <ReleaseFormView value={releaseForm} onChange={setReleaseForm} />
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setReleaseOpen(false)}>
                      取消
                    </Button>
                    <Button disabled={createRelease.isPending} onClick={() => createRelease.mutate()}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>披露编号</TableHead>
                    <TableHead>任务</TableHead>
                    <TableHead>接收方</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {releases.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.release_no}</TableCell>
                      <TableCell>{taskName(tasks, item.task_id)}</TableCell>
                      <TableCell>{item.recipient_name || "-"}</TableCell>
                      <TableCell>{item.release_type}</TableCell>
                      <TableCell>{item.released_at || "-"}</TableCell>
                      <TableCell>
                        <CarbonStatusBadge status={item.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {!releases.length ? <EmptyRow colSpan={6} label="暂无披露记录" /> : null}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="analysis">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <AnalysisTable
              title="供应商排行"
              rows={(analysis?.supplier_ranking ?? []).map((item) => ({
                name: item.supplier_name,
                value: item.co2e_amount || item.pcf_value_sum,
                meta: `${item.data_count} 条 / 风险${riskLabels[item.risk_level] ?? item.risk_level}`,
              }))}
            />
            <AnalysisTable
              title="高碳品类"
              rows={(analysis?.high_carbon_categories ?? []).map((item) => ({
                name: item.scope_category,
                value: item.co2e_amount || item.pcf_value_sum,
                meta: `${item.data_count} 条`,
              }))}
            />
          </div>
          <AdminPanel title="建议" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>对象</TableHead>
                    <TableHead>优先级</TableHead>
                    <TableHead>动作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(analysis?.recommendations ?? []).map((item) => (
                    <TableRow key={`${item.target_type}-${item.target_name}`}>
                      <TableCell>{item.target_name}</TableCell>
                      <TableCell>
                        <RiskBadge level={item.priority} />
                      </TableCell>
                      <TableCell>{item.action}</TableCell>
                    </TableRow>
                  ))}
                  {!analysis?.recommendations?.length ? <EmptyRow colSpan={3} label="暂无建议" /> : null}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function SupplierFormView({ value, onChange }: { value: SupplierForm; onChange: (value: SupplierForm) => void }) {
  const set = (key: keyof SupplierForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="供应商编码" value={value.supplier_code} onChange={(next) => set("supplier_code", next)} />
      <Field label="供应商名称" value={value.name} onChange={(next) => set("name", next)} />
      <Field label="行业" value={value.industry} onChange={(next) => set("industry", next)} />
      <SelectField
        label="类型"
        value={value.supplier_type}
        options={[
          { label: "材料", value: "material" },
          { label: "运输", value: "transport" },
          { label: "服务", value: "service" },
        ]}
        onChange={(next) => set("supplier_type", next)}
      />
      <Field label="联系人" value={value.contact_name} onChange={(next) => set("contact_name", next)} />
      <Field label="邮箱" value={value.contact_email} onChange={(next) => set("contact_email", next)} />
      <Field label="国家/地区" value={value.country_region} onChange={(next) => set("country_region", next)} />
      <SelectField
        label="风险"
        value={value.risk_level}
        options={[
          { label: "低", value: "low" },
          { label: "中", value: "medium" },
          { label: "高", value: "high" },
        ]}
        onChange={(next) => set("risk_level", next)}
      />
    </div>
  )
}

function SiteFormView({ suppliers, value, onChange }: { suppliers: Supplier[]; value: SiteForm; onChange: (value: SiteForm) => void }) {
  const set = (key: keyof SiteForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <SelectField
        label="供应商"
        value={value.supplier_id}
        options={suppliers.map((item) => ({ label: item.name, value: String(item.id) }))}
        onChange={(next) => set("supplier_id", next)}
      />
      <Field label="场站编码" value={value.site_code} onChange={(next) => set("site_code", next)} />
      <Field label="场站名称" value={value.site_name} onChange={(next) => set("site_name", next)} />
      <Field label="国家/地区" value={value.country_region} onChange={(next) => set("country_region", next)} />
      <Field label="设施范围" value={value.facility_scope} onChange={(next) => set("facility_scope", next)} />
    </div>
  )
}

function TaskFormView({ suppliers, value, onChange }: { suppliers: Supplier[]; value: TaskForm; onChange: (value: TaskForm) => void }) {
  const set = (key: keyof TaskForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SelectField
        label="供应商"
        value={value.supplier_id}
        options={suppliers.map((item) => ({ label: item.name, value: String(item.id) }))}
        onChange={(next) => set("supplier_id", next)}
      />
      <SelectField
        label="任务类型"
        value={value.task_type}
        options={[
          { label: "Scope3 活动", value: "scope3_activity" },
          { label: "产品 PCF", value: "product_pcf" },
          { label: "综合", value: "mixed" },
        ]}
        onChange={(next) => set("task_type", next)}
      />
      <Field label="任务编号" value={value.task_no} onChange={(next) => set("task_no", next)} />
      <Field label="任务名称" value={value.task_name} onChange={(next) => set("task_name", next)} />
      <Field label="产品编码" value={value.product_code} onChange={(next) => set("product_code", next)} />
      <Field label="产品名称" value={value.product_name} onChange={(next) => set("product_name", next)} />
      <Field label="开始日期" type="date" value={value.period_start} onChange={(next) => set("period_start", next)} />
      <Field label="结束日期" type="date" value={value.period_end} onChange={(next) => set("period_end", next)} />
      <Field label="截止日期" type="date" value={value.due_date} onChange={(next) => set("due_date", next)} />
      <Field label="发起人" value={value.requested_by} onChange={(next) => set("requested_by", next)} />
    </div>
  )
}

function DataFormView({ value, onChange }: { value: DataForm; onChange: (value: DataForm) => void }) {
  const set = (key: keyof DataForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Field label="数据编号" value={value.data_no} onChange={(next) => set("data_no", next)} />
      <SelectField
        label="数据类型"
        value={value.data_type}
        options={[
          { label: "活动数据", value: "activity" },
          { label: "产品 PCF", value: "pcf" },
        ]}
        onChange={(next) => set("data_type", next)}
      />
      <Field label="Scope3 类别" value={value.scope_category} onChange={(next) => set("scope_category", next)} />
      <Field label="产品编码" value={value.product_code} onChange={(next) => set("product_code", next)} />
      <Field label="产品名称" value={value.product_name} onChange={(next) => set("product_name", next)} />
      <Field label="材料编码" value={value.material_code} onChange={(next) => set("material_code", next)} />
      <Field label="材料名称" value={value.material_name} onChange={(next) => set("material_name", next)} />
      <Field label="活动量" type="number" value={value.activity_amount} onChange={(next) => set("activity_amount", next)} />
      <Field label="活动单位" value={value.activity_unit} onChange={(next) => set("activity_unit", next)} />
      <Field label="PCF 值" type="number" value={value.pcf_value} onChange={(next) => set("pcf_value", next)} />
      <Field label="PCF 单位" value={value.pcf_unit} onChange={(next) => set("pcf_unit", next)} />
      <Field label="CO2e" type="number" value={value.co2e_amount} onChange={(next) => set("co2e_amount", next)} />
      <Field label="边界" value={value.boundary_type} onChange={(next) => set("boundary_type", next)} />
      <Field label="数据质量" value={value.data_quality} onChange={(next) => set("data_quality", next)} />
    </div>
  )
}

function EvidenceFormView({ value, onChange }: { value: EvidenceForm; onChange: (value: EvidenceForm) => void }) {
  const set = (key: keyof EvidenceForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <Field label="证据编号" value={value.evidence_no} onChange={(next) => set("evidence_no", next)} />
      <Field label="证据类型" value={value.evidence_type} onChange={(next) => set("evidence_type", next)} />
      <Field label="文件名" value={value.file_name} onChange={(next) => set("file_name", next)} />
      <Field label="文件路径" value={value.file_path} onChange={(next) => set("file_path", next)} />
      <Field label="提交人" value={value.submitted_by} onChange={(next) => set("submitted_by", next)} />
    </div>
  )
}

function ReleaseFormView({ value, onChange }: { value: ReleaseForm; onChange: (value: ReleaseForm) => void }) {
  const set = (key: keyof ReleaseForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <Field label="披露编号" value={value.release_no} onChange={(next) => set("release_no", next)} />
      <Field label="接收方" value={value.recipient_name} onChange={(next) => set("recipient_name", next)} />
      <Field label="披露类型" value={value.release_type} onChange={(next) => set("release_type", next)} />
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string; icon: typeof Building2 }[] }) {
  return (
    <MetricStrip className="sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} />
      ))}
    </MetricStrip>
  )
}

function AnalysisTable({ title, rows }: { title: string; rows: { name: string; value: number; meta: string }[] }) {
  return (
    <AdminPanel title={title} contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>对象</TableHead>
              <TableHead>数值</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.name}>
                <TableCell>{row.name}</TableCell>
                <TableCell>{formatNumber(row.value)}</TableCell>
                <TableCell>{row.meta}</TableCell>
              </TableRow>
            ))}
            {!rows.length ? <EmptyRow colSpan={3} label="暂无数据" /> : null}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: { label: string; value: string }[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
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

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return <AdminTableStateRow colSpan={colSpan}>{label}</AdminTableStateRow>
}

function TaskStatusBadge({ status }: { status: string }) {
  if (status === "approved") return <CarbonStatusBadge status="approved" />
  if (status === "submitted") return <Badge variant="outline">{taskStatusLabels[status]}</Badge>
  if (status === "rejected" || status === "needs_revision") return <Badge variant="secondary">{taskStatusLabels[status]}</Badge>
  return <Badge>{taskStatusLabels[status] ?? status}</Badge>
}

function RiskBadge({ level }: { level?: string | null }) {
  if (level === "high") return <Badge variant="destructive">高</Badge>
  if (level === "low") return <Badge variant="secondary">低</Badge>
  return <Badge variant="outline">{riskLabels[level || "medium"] ?? level}</Badge>
}

function supplierPayload(form: SupplierForm) {
  return {
    supplier_code: form.supplier_code.trim(),
    name: form.name.trim(),
    industry: optional(form.industry),
    supplier_type: optional(form.supplier_type),
    contact_name: optional(form.contact_name),
    contact_email: optional(form.contact_email),
    country_region: optional(form.country_region),
    risk_level: form.risk_level,
    source_name: "supply_chain_carbon",
    standard_code: "GHG Protocol Scope 3",
  }
}

function sitePayload(form: SiteForm) {
  return {
    supplier_id: toNumber(form.supplier_id),
    site_code: form.site_code.trim(),
    site_name: form.site_name.trim(),
    country_region: optional(form.country_region),
    facility_scope: optional(form.facility_scope),
  }
}

function taskPayload(form: TaskForm) {
  return {
    supplier_id: toNumber(form.supplier_id),
    task_no: form.task_no.trim(),
    task_name: form.task_name.trim(),
    task_type: form.task_type,
    product_code: optional(form.product_code),
    product_name: optional(form.product_name),
    period_start: form.period_start,
    period_end: form.period_end,
    due_date: optional(form.due_date),
    requested_by: optional(form.requested_by),
    standard_code: "GHG Protocol Scope 3",
    source_name: "supply_chain_carbon",
    confidence_level: "medium",
  }
}

function dataPayload(form: DataForm) {
  return {
    data_no: form.data_no.trim(),
    data_type: form.data_type,
    scope_category: optional(form.scope_category),
    product_code: optional(form.product_code),
    product_name: optional(form.product_name),
    material_code: optional(form.material_code),
    material_name: optional(form.material_name),
    activity_amount: toNumber(form.activity_amount),
    activity_unit: optional(form.activity_unit),
    pcf_value: toNumber(form.pcf_value),
    pcf_unit: optional(form.pcf_unit),
    co2e_amount: toNumber(form.co2e_amount),
    boundary_type: optional(form.boundary_type),
    data_quality: optional(form.data_quality),
    source_type: "manual",
  }
}

function evidencePayload(form: EvidenceForm) {
  return {
    evidence_no: form.evidence_no.trim(),
    evidence_type: form.evidence_type.trim(),
    file_name: form.file_name.trim(),
    file_path: optional(form.file_path),
    submitted_by: optional(form.submitted_by),
  }
}

function releasePayload(form: ReleaseForm) {
  return {
    release_no: form.release_no.trim(),
    recipient_name: optional(form.recipient_name),
    release_type: optional(form.release_type),
  }
}

function optional(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function toNumber(value: string) {
  if (!value) return undefined
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function supplierName(suppliers: Supplier[], supplierId: number) {
  return suppliers.find((item) => item.id === supplierId)?.name ?? "-"
}

function taskName(tasks: DisclosureTask[], taskId: number) {
  return tasks.find((item) => item.id === taskId)?.task_name ?? String(taskId)
}

function taskTypeLabel(value: string) {
  return { scope3_activity: "Scope3 活动", product_pcf: "产品 PCF", mixed: "综合" }[value] ?? value
}

function dataTypeLabel(value: string) {
  return { activity: "活动数据", pcf: "产品 PCF" }[value] ?? value
}

function evidenceStatusLabel(value: string) {
  return { pending: "待审核", accepted: "已接受", rejected: "已拒绝" }[value] ?? value
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "-"
  return `${start || "-"} 至 ${end || "-"}`
}

function amountWithUnit(value?: number | null, unit?: string | null) {
  if (value === null || value === undefined) return "-"
  return `${formatNumber(value)} ${unit || ""}`.trim()
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value)
}

function toastError(prefix: string) {
  return (error: Error) => toast.error(prefix, { description: error.message })
}

async function invalidateSupplyChain(qc: ReturnType<typeof useQueryClient>) {
  await qc.invalidateQueries({ queryKey: QUERY_KEY })
}
