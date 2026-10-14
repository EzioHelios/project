import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type PageResult<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

type ReportingOrganization = {
  id: number
  code: string
  name: string
  organization_type?: string | null
  control_method?: string | null
  legal_entity_code?: string | null
  enterprise_id?: number | null
  status?: string | null
  source_name?: string | null
}

type ReportingPeriod = {
  id: number
  reporting_org_id: number
  code: string
  name: string
  period_start: string
  period_end: string
  base_year?: number | null
  status?: string | null
}

type BoundaryVersion = {
  id: number
  reporting_org_id: number
  period_id: number
  boundary_no: string
  boundary_name: string
  boundary_method?: string | null
  version?: number | null
  status?: string | null
  facility_count?: number
  included_facility_count?: number
  excluded_facility_count?: number
  published_at?: string | null
}

type BoundaryFacility = {
  id: number
  boundary_id: number
  facility_type?: string | null
  facility_code?: string | null
  facility_name?: string | null
  facility_role?: string | null
  included?: boolean | null
  exclusion_reason?: string | null
  valid_from?: string | null
  valid_to?: string | null
}

type BoundarySummary = {
  organization_count: number
  period_count: number
  boundary_count: number
  published_boundary_count: number
  facility_count: number
  active_boundary?: BoundaryVersion | null
}

type OrganizationForm = {
  code: string
  name: string
  legal_entity_code: string
  control_method: string
  enterprise_id: string
  organization_type: string
}

type PeriodForm = {
  reporting_org_id: string
  code: string
  name: string
  period_start: string
  period_end: string
  base_year: string
}

type BoundaryForm = {
  reporting_org_id: string
  period_id: string
  boundary_no: string
  boundary_name: string
  boundary_method: string
}

type FacilityForm = {
  boundary_id: string
  facility_type: string
  facility_code: string
  facility_name: string
  facility_role: string
  included: string
  exclusion_reason: string
}

const QUERY_KEY = ["organization-boundary"]

const methodLabels: Record<string, string> = {
  operational_control: "运营控制权",
  financial_control: "财务控制权",
  equity_share: "股权比例",
}

const facilityTypeLabels: Record<string, string> = {
  enterprise: "企业",
  area: "区域",
  equipment: "设备",
  other: "其他",
}

const defaultOrganizationForm: OrganizationForm = {
  code: "",
  name: "",
  legal_entity_code: "",
  control_method: "operational_control",
  enterprise_id: "",
  organization_type: "enterprise",
}

const defaultPeriodForm: PeriodForm = {
  reporting_org_id: "",
  code: "",
  name: "",
  period_start: "",
  period_end: "",
  base_year: "",
}

const defaultBoundaryForm: BoundaryForm = {
  reporting_org_id: "",
  period_id: "",
  boundary_no: "",
  boundary_name: "",
  boundary_method: "operational_control",
}

const defaultFacilityForm: FacilityForm = {
  boundary_id: "",
  facility_type: "area",
  facility_code: "",
  facility_name: "",
  facility_role: "",
  included: "true",
  exclusion_reason: "",
}

export function OrganizationBoundaryPanel() {
  const qc = useQueryClient()
  const [organizationOpen, setOrganizationOpen] = useState(false)
  const [periodOpen, setPeriodOpen] = useState(false)
  const [boundaryOpen, setBoundaryOpen] = useState(false)
  const [facilityOpen, setFacilityOpen] = useState(false)
  const [editingOrganizationId, setEditingOrganizationId] = useState<number | null>(null)
  const [editingPeriodId, setEditingPeriodId] = useState<number | null>(null)
  const [editingBoundaryId, setEditingBoundaryId] = useState<number | null>(null)
  const [editingFacilityId, setEditingFacilityId] = useState<number | null>(null)
  const [organizationForm, setOrganizationForm] = useState<OrganizationForm>(defaultOrganizationForm)
  const [periodForm, setPeriodForm] = useState<PeriodForm>(defaultPeriodForm)
  const [boundaryForm, setBoundaryForm] = useState<BoundaryForm>(defaultBoundaryForm)
  const [facilityForm, setFacilityForm] = useState<FacilityForm>(defaultFacilityForm)

  const summaryQuery = useQuery<ApiEnvelope<BoundarySummary>>({
    queryKey: [...QUERY_KEY, "summary"],
    queryFn: () => fetchCarbonApi<BoundarySummary>("/api/carbon/organization-boundary/summary"),
  })
  const organizationsQuery = useQuery<ApiEnvelope<PageResult<ReportingOrganization>>>({
    queryKey: [...QUERY_KEY, "organizations"],
    queryFn: () => fetchCarbonApi<PageResult<ReportingOrganization>>("/api/carbon/organization-boundary/organizations?limit=100"),
  })
  const periodsQuery = useQuery<ApiEnvelope<PageResult<ReportingPeriod>>>({
    queryKey: [...QUERY_KEY, "periods"],
    queryFn: () => fetchCarbonApi<PageResult<ReportingPeriod>>("/api/carbon/organization-boundary/periods?limit=100"),
  })
  const boundariesQuery = useQuery<ApiEnvelope<PageResult<BoundaryVersion>>>({
    queryKey: [...QUERY_KEY, "boundaries"],
    queryFn: () => fetchCarbonApi<PageResult<BoundaryVersion>>("/api/carbon/organization-boundary/boundaries?limit=100"),
  })
  const facilitiesQuery = useQuery<ApiEnvelope<PageResult<BoundaryFacility>>>({
    queryKey: [...QUERY_KEY, "facilities"],
    queryFn: () => fetchCarbonApi<PageResult<BoundaryFacility>>("/api/carbon/organization-boundary/facilities?limit=200"),
  })

  const organizations = organizationsQuery.data?.data.items ?? []
  const periods = periodsQuery.data?.data.items ?? []
  const boundaries = boundariesQuery.data?.data.items ?? []
  const facilities = facilitiesQuery.data?.data.items ?? []
  const summary = summaryQuery.data?.data

  const organizationById = useMemo(() => new Map(organizations.map((item) => [item.id, item])), [organizations])
  const enterpriseQuery = useQuery({
    queryKey: ["data", "company", "enterprise-info"],
    queryFn: () => fetchCarbonApi<{ id?: number; name?: string }>("/api/master-data/enterprise-profile"),
  })
  const periodById = useMemo(() => new Map(periods.map((item) => [item.id, item])), [periods])
  const boundaryById = useMemo(() => new Map(boundaries.map((item) => [item.id, item])), [boundaries])

  const saveOrganization = useMutation({
    mutationFn: () =>
      writeCarbonApi<ReportingOrganization>(
        editingOrganizationId ? "PATCH" : "POST",
        editingOrganizationId ? `/api/carbon/organization-boundary/organizations/${editingOrganizationId}` : "/api/carbon/organization-boundary/organizations",
        {
          code: organizationForm.code.trim(),
          name: organizationForm.name.trim(),
          legal_entity_code: optional(organizationForm.legal_entity_code),
          control_method: organizationForm.control_method,
          enterprise_id: organizationForm.enterprise_id ? toNumber(organizationForm.enterprise_id) : null,
          organization_type: organizationForm.organization_type,
          source_name: "enterprise_inventory",
        },
      ),
    onSuccess: async () => {
      toast.success(editingOrganizationId ? "报告主体已更新" : "报告主体已创建")
      closeOrganizationDialog()
      await invalidateBoundary(qc)
    },
    onError: toastError("保存报告主体失败"),
  })

  const deleteOrganization = useMutation({
    mutationFn: (organizationId: number) => deleteCarbonApi(`/api/carbon/organization-boundary/organizations/${organizationId}`),
    onSuccess: async () => {
      toast.success("报告主体已删除")
      await invalidateBoundary(qc)
    },
    onError: toastError("删除报告主体失败"),
  })

  const savePeriod = useMutation({
    mutationFn: () =>
      writeCarbonApi<ReportingPeriod>(
        editingPeriodId ? "PATCH" : "POST",
        editingPeriodId ? `/api/carbon/organization-boundary/periods/${editingPeriodId}` : "/api/carbon/organization-boundary/periods",
        {
          reporting_org_id: toNumber(periodForm.reporting_org_id),
          code: periodForm.code.trim(),
          name: periodForm.name.trim(),
          period_start: periodForm.period_start,
          period_end: periodForm.period_end,
          period_type: "annual",
          base_year: periodForm.base_year ? toNumber(periodForm.base_year) : null,
          source_name: "enterprise_inventory",
        },
      ),
    onSuccess: async () => {
      toast.success(editingPeriodId ? "报告期已更新" : "报告期已创建")
      closePeriodDialog()
      await invalidateBoundary(qc)
    },
    onError: toastError("保存报告期失败"),
  })

  const deletePeriod = useMutation({
    mutationFn: (periodId: number) => deleteCarbonApi(`/api/carbon/organization-boundary/periods/${periodId}`),
    onSuccess: async () => {
      toast.success("报告期已删除")
      await invalidateBoundary(qc)
    },
    onError: toastError("删除报告期失败"),
  })

  const archivePeriod = useMutation({
    mutationFn: (periodId: number) => patchCarbonApi<ReportingPeriod>(`/api/carbon/organization-boundary/periods/${periodId}`, { status: "archived" }),
    onSuccess: async () => {
      toast.success("报告期已归档")
      await invalidateBoundary(qc)
    },
    onError: toastError("归档报告期失败"),
  })

  const saveBoundary = useMutation({
    mutationFn: () =>
      writeCarbonApi<BoundaryVersion>(
        editingBoundaryId ? "PATCH" : "POST",
        editingBoundaryId ? `/api/carbon/organization-boundary/boundaries/${editingBoundaryId}` : "/api/carbon/organization-boundary/boundaries",
        {
          reporting_org_id: toNumber(boundaryForm.reporting_org_id),
          period_id: toNumber(boundaryForm.period_id),
          boundary_no: boundaryForm.boundary_no.trim(),
          boundary_name: boundaryForm.boundary_name.trim(),
          boundary_method: boundaryForm.boundary_method,
          boundary_type: "organization",
          status: editingBoundaryId ? undefined : "draft",
          source_name: "enterprise_inventory",
          confidence_level: "medium",
        },
      ),
    onSuccess: async () => {
      toast.success(editingBoundaryId ? "边界版本已更新" : "边界版本已创建")
      closeBoundaryDialog()
      await invalidateBoundary(qc)
    },
    onError: toastError("保存边界版本失败"),
  })

  const deleteBoundary = useMutation({
    mutationFn: (boundaryId: number) => deleteCarbonApi(`/api/carbon/organization-boundary/boundaries/${boundaryId}`),
    onSuccess: async () => {
      toast.success("边界版本已删除")
      await invalidateBoundary(qc)
    },
    onError: toastError("删除边界版本失败"),
  })

  const archiveBoundary = useMutation({
    mutationFn: (boundaryId: number) => patchCarbonApi<BoundaryVersion>(`/api/carbon/organization-boundary/boundaries/${boundaryId}`, { status: "archived" }),
    onSuccess: async () => {
      toast.success("边界版本已归档")
      await invalidateBoundary(qc)
    },
    onError: toastError("归档边界版本失败"),
  })

  const saveFacility = useMutation({
    mutationFn: () =>
      writeCarbonApi<BoundaryFacility>(
        editingFacilityId ? "PATCH" : "POST",
        editingFacilityId ? `/api/carbon/organization-boundary/facilities/${editingFacilityId}` : "/api/carbon/organization-boundary/facilities",
        {
          boundary_id: toNumber(facilityForm.boundary_id),
          facility_type: facilityForm.facility_type,
          facility_code: optional(facilityForm.facility_code),
          facility_name: optional(facilityForm.facility_name),
          facility_role: optional(facilityForm.facility_role),
          included: facilityForm.included === "true",
          exclusion_reason: optional(facilityForm.exclusion_reason),
          source_name: "enterprise_inventory",
        },
      ),
    onSuccess: async () => {
      toast.success(editingFacilityId ? "边界设施已更新" : "边界设施已维护")
      closeFacilityDialog()
      await invalidateBoundary(qc)
    },
    onError: toastError("维护边界设施失败"),
  })

  const deleteFacility = useMutation({
    mutationFn: (facilityId: number) => deleteCarbonApi(`/api/carbon/organization-boundary/facilities/${facilityId}`),
    onSuccess: async () => {
      toast.success("边界设施已删除")
      await invalidateBoundary(qc)
    },
    onError: toastError("删除边界设施失败"),
  })

  const publishBoundary = useMutation({
    mutationFn: (boundaryId: number) => postCarbonApi<BoundaryVersion>(`/api/carbon/organization-boundary/boundaries/${boundaryId}/publish`, {}),
    onSuccess: async () => {
      toast.success("组织边界已发布")
      await invalidateBoundary(qc)
    },
    onError: toastError("发布组织边界失败"),
  })

  const createSourceFacility = useMutation({
    mutationFn: (boundaryId: number) => postCarbonApi<BoundaryFacility>(`/api/carbon/organization-boundary/boundaries/${boundaryId}/source-facility`, {}),
    onSuccess: async () => {
      toast.success("来源边界设施已生成")
      await invalidateBoundary(qc)
    },
    onError: toastError("生成来源边界设施失败"),
  })

  const selectedOrgPeriods = periods.filter((period) => !boundaryForm.reporting_org_id || period.reporting_org_id === toNumber(boundaryForm.reporting_org_id))
  const organizationReady = organizationForm.code.trim() && organizationForm.name.trim()
  const periodReady = periodForm.reporting_org_id && periodForm.code.trim() && periodForm.name.trim() && periodForm.period_start && periodForm.period_end
  const boundaryReady = boundaryForm.reporting_org_id && boundaryForm.period_id && boundaryForm.boundary_no.trim() && boundaryForm.boundary_name.trim()
  const facilityReady = facilityForm.boundary_id && (facilityForm.included === "true" || facilityForm.exclusion_reason.trim())

  function closeOrganizationDialog() {
    setOrganizationOpen(false)
    setEditingOrganizationId(null)
    setOrganizationForm(defaultOrganizationForm)
  }

  function openOrganizationDialog(item?: ReportingOrganization) {
    setEditingOrganizationId(item?.id ?? null)
    setOrganizationForm(
      item
        ? {
            code: item.code,
            name: item.name,
            legal_entity_code: item.legal_entity_code ?? "",
            control_method: item.control_method ?? "operational_control",
            enterprise_id: item.enterprise_id ? String(item.enterprise_id) : "",
            organization_type: item.organization_type ?? "enterprise",
          }
        : defaultOrganizationForm,
    )
    setOrganizationOpen(true)
  }

  function closePeriodDialog() {
    setPeriodOpen(false)
    setEditingPeriodId(null)
    setPeriodForm(defaultPeriodForm)
  }

  function openPeriodDialog(item?: ReportingPeriod) {
    setEditingPeriodId(item?.id ?? null)
    setPeriodForm(
      item
        ? {
            reporting_org_id: String(item.reporting_org_id),
            base_year: item.base_year ? String(item.base_year) : "",
            code: item.code,
            name: item.name,
            period_start: item.period_start,
            period_end: item.period_end,
          }
        : defaultPeriodForm,
    )
    setPeriodOpen(true)
  }

  function closeBoundaryDialog() {
    setBoundaryOpen(false)
    setEditingBoundaryId(null)
    setBoundaryForm(defaultBoundaryForm)
  }

  function openBoundaryDialog(item?: BoundaryVersion) {
    setEditingBoundaryId(item?.id ?? null)
    setBoundaryForm(
      item
        ? {
            reporting_org_id: String(item.reporting_org_id),
            period_id: String(item.period_id),
            boundary_no: item.boundary_no,
            boundary_name: item.boundary_name,
            boundary_method: item.boundary_method ?? "operational_control",
          }
        : defaultBoundaryForm,
    )
    setBoundaryOpen(true)
  }

  function closeFacilityDialog() {
    setFacilityOpen(false)
    setEditingFacilityId(null)
    setFacilityForm(defaultFacilityForm)
  }

  function openFacilityDialog(item?: BoundaryFacility) {
    setEditingFacilityId(item?.id ?? null)
    setFacilityForm(
      item
        ? {
            boundary_id: String(item.boundary_id),
            facility_type: item.facility_type ?? "area",
            facility_code: item.facility_code ?? "",
            facility_name: item.facility_name ?? "",
            facility_role: item.facility_role ?? "",
            included: item.included === false ? "false" : "true",
            exclusion_reason: item.exclusion_reason ?? "",
          }
        : defaultFacilityForm,
    )
    setFacilityOpen(true)
  }

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "报告主体", value: summary?.organization_count ?? 0 },
          { label: "边界版本", value: summary?.boundary_count ?? 0 },
          { label: "已发布边界", value: summary?.published_boundary_count ?? 0 },
          { label: "边界设施", value: summary?.facility_count ?? 0 },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <AdminPanel
          title="报告主体"
          actions={
            <Dialog open={organizationOpen} onOpenChange={(open) => (open ? setOrganizationOpen(true) : closeOrganizationDialog())}>
              <Button size="sm" onClick={() => openOrganizationDialog()}>
                新增主体
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingOrganizationId ? "编辑报告主体" : "新增报告主体"}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4">
                  <Field label="主体编号" value={organizationForm.code} onChange={(code) => setOrganizationForm((state) => ({ ...state, code }))} />
                  <Field label="主体名称" value={organizationForm.name} onChange={(name) => setOrganizationForm((state) => ({ ...state, name }))} />
                  <Field
                    label="统一社会信用代码"
                    value={organizationForm.legal_entity_code}
                    onChange={(legal_entity_code) => setOrganizationForm((state) => ({ ...state, legal_entity_code }))}
                  />
                  <MethodSelect value={organizationForm.control_method} onChange={(control_method) => setOrganizationForm((state) => ({ ...state, control_method }))} />
                  <label className="grid gap-2 text-sm">
                    主体类型
                    <select
                      aria-label="主体类型"
                      className="h-9 rounded-md border bg-background px-3"
                      value={organizationForm.organization_type}
                      onChange={(event) => setOrganizationForm((state) => ({ ...state, organization_type: event.target.value }))}
                    >
                      <option value="enterprise">企业</option>
                      <option value="facility">设施</option>
                      <option value="group">集团</option>
                    </select>
                  </label>
                  <label className="grid gap-2 text-sm">
                    关联企业档案
                    <select
                      aria-label="关联企业档案"
                      className="h-9 rounded-md border bg-background px-3"
                      value={organizationForm.enterprise_id}
                      onChange={(event) => setOrganizationForm((state) => ({ ...state, enterprise_id: event.target.value }))}
                    >
                      <option value="">未关联</option>
                      {enterpriseQuery.data?.data.id ? <option value={enterpriseQuery.data.data.id}>{enterpriseQuery.data.data.name}</option> : null}
                    </select>
                  </label>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={closeOrganizationDialog}>
                    取消
                  </Button>
                  <Button disabled={!organizationReady || saveOrganization.isPending} onClick={() => saveOrganization.mutate()}>
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
                  <TableHead>编号</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>控制方法</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {organizations.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.code}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{methodLabel(item.control_method)}</TableCell>
                    <TableCell>
                      <CarbonStatusBadge status={item.status || "active"} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => openOrganizationDialog(item)}>
                          编辑
                        </Button>
                        {item.status !== "inactive" && item.status !== "archived" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              patchCarbonApi<ReportingOrganization>(`/api/carbon/organization-boundary/organizations/${item.id}`, { status: "inactive" })
                                .then(() => invalidateBoundary(qc))
                                .then(() => toast.success("报告主体已停用"))
                                .catch(toastError("停用报告主体失败"))
                            }
                          >
                            停用
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            if (window.confirm("确认删除该报告主体？仅未被报告期和核算记录引用的主体可删除。")) deleteOrganization.mutate(item.id)
                          }}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                <EmptyRow visible={!organizations.length} colSpan={5} label="暂无报告主体" />
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>

        <AdminPanel
          title="报告期"
          actions={
            <Dialog open={periodOpen} onOpenChange={(open) => (open ? setPeriodOpen(true) : closePeriodDialog())}>
              <Button size="sm" onClick={() => openPeriodDialog()}>
                新增报告期
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingPeriodId ? "编辑报告期" : "新增报告期"}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4">
                  <OrgSelect
                    value={periodForm.reporting_org_id}
                    organizations={organizations}
                    onChange={(reporting_org_id) => setPeriodForm((state) => ({ ...state, reporting_org_id }))}
                  />
                  <Field label="报告期编号" value={periodForm.code} onChange={(code) => setPeriodForm((state) => ({ ...state, code }))} />
                  <Field label="报告期名称" value={periodForm.name} onChange={(name) => setPeriodForm((state) => ({ ...state, name }))} />
                  <DateField label="开始日期" value={periodForm.period_start} onChange={(period_start) => setPeriodForm((state) => ({ ...state, period_start }))} />
                  <DateField label="结束日期" value={periodForm.period_end} onChange={(period_end) => setPeriodForm((state) => ({ ...state, period_end }))} />
                  <Field label="基准年" type="number" value={periodForm.base_year} onChange={(base_year) => setPeriodForm((state) => ({ ...state, base_year }))} />
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={closePeriodDialog}>
                    取消
                  </Button>
                  <Button disabled={!periodReady || savePeriod.isPending} onClick={() => savePeriod.mutate()}>
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
                  <TableHead>编号</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>主体</TableHead>
                  <TableHead>期间</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {periods.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.code}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{organizationById.get(item.reporting_org_id)?.name ?? "-"}</TableCell>
                    <TableCell>{dateRange(item.period_start, item.period_end)}</TableCell>
                    <TableCell>
                      <CarbonStatusBadge status={item.status || "draft"} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" disabled={item.status === "locked"} onClick={() => openPeriodDialog(item)}>
                          编辑
                        </Button>
                        {item.status !== "archived" && (
                          <Button size="sm" variant="ghost" disabled={archivePeriod.isPending || item.status === "locked"} onClick={() => archivePeriod.mutate(item.id)}>
                            归档
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={item.status === "locked"}
                          onClick={() => {
                            if (window.confirm("确认删除该报告期？仅未被组织边界和核算记录引用的报告期可删除。")) deletePeriod.mutate(item.id)
                          }}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                <EmptyRow visible={!periods.length} colSpan={6} label="暂无报告期" />
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>
      </div>

      <AdminPanel
        title="组织边界版本"
        actions={
          <Dialog open={boundaryOpen} onOpenChange={(open) => (open ? setBoundaryOpen(true) : closeBoundaryDialog())}>
            <Button size="sm" onClick={() => openBoundaryDialog()}>
              新增边界
            </Button>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingBoundaryId ? "编辑边界版本" : "新增边界版本"}</DialogTitle>
              </DialogHeader>
              <div className="grid gap-4">
                <OrgSelect
                  value={boundaryForm.reporting_org_id}
                  organizations={organizations}
                  onChange={(reporting_org_id) => setBoundaryForm((state) => ({ ...state, reporting_org_id, period_id: "" }))}
                />
                <PeriodSelect periods={selectedOrgPeriods} value={boundaryForm.period_id} onChange={(period_id) => setBoundaryForm((state) => ({ ...state, period_id }))} />
                <Field label="边界编号" value={boundaryForm.boundary_no} onChange={(boundary_no) => setBoundaryForm((state) => ({ ...state, boundary_no }))} />
                <Field label="边界名称" value={boundaryForm.boundary_name} onChange={(boundary_name) => setBoundaryForm((state) => ({ ...state, boundary_name }))} />
                <MethodSelect value={boundaryForm.boundary_method} onChange={(boundary_method) => setBoundaryForm((state) => ({ ...state, boundary_method }))} />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={closeBoundaryDialog}>
                  取消
                </Button>
                <Button disabled={!boundaryReady || saveBoundary.isPending} onClick={() => saveBoundary.mutate()}>
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
                <TableHead>边界编号</TableHead>
                <TableHead>边界名称</TableHead>
                <TableHead>主体</TableHead>
                <TableHead>报告期</TableHead>
                <TableHead>方法</TableHead>
                <TableHead>设施</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {boundaries.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.boundary_no}</TableCell>
                  <TableCell>{item.boundary_name}</TableCell>
                  <TableCell>{organizationById.get(item.reporting_org_id)?.name ?? "-"}</TableCell>
                  <TableCell>{periodById.get(item.period_id)?.name ?? "-"}</TableCell>
                  <TableCell>{methodLabel(item.boundary_method)}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.included_facility_count ?? 0} 纳入</Badge>
                  </TableCell>
                  <TableCell>
                    <CarbonStatusBadge status={item.status || "draft"} />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" disabled={item.status === "published"} onClick={() => openBoundaryDialog(item)}>
                        编辑
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={item.status === "published" || (item.included_facility_count ?? 0) > 0 || createSourceFacility.isPending}
                        onClick={() => createSourceFacility.mutate(item.id)}
                      >
                        生成设施
                      </Button>
                      <Button size="sm" variant="outline" disabled={item.status === "published" || publishBoundary.isPending} onClick={() => publishBoundary.mutate(item.id)}>
                        发布
                      </Button>
                      {item.status !== "archived" && (
                        <Button size="sm" variant="ghost" disabled={archiveBoundary.isPending} onClick={() => archiveBoundary.mutate(item.id)}>
                          归档
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={item.status === "published"}
                        onClick={() => {
                          if (window.confirm("确认删除该边界版本？已发布或已被核算引用的边界不能删除。")) deleteBoundary.mutate(item.id)
                        }}
                      >
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              <EmptyRow visible={!boundaries.length} colSpan={8} label="暂无组织边界" />
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>

      <AdminPanel
        title="边界设施"
        actions={
          <Dialog open={facilityOpen} onOpenChange={(open) => (open ? setFacilityOpen(true) : closeFacilityDialog())}>
            <Button size="sm" onClick={() => openFacilityDialog()}>
              维护设施
            </Button>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingFacilityId ? "编辑边界设施" : "维护边界设施"}</DialogTitle>
              </DialogHeader>
              <div className="grid gap-4">
                <BoundarySelect boundaries={boundaries} value={facilityForm.boundary_id} onChange={(boundary_id) => setFacilityForm((state) => ({ ...state, boundary_id }))} />
                <FacilityTypeSelect value={facilityForm.facility_type} onChange={(facility_type) => setFacilityForm((state) => ({ ...state, facility_type }))} />
                <Field label="设施编号" value={facilityForm.facility_code} onChange={(facility_code) => setFacilityForm((state) => ({ ...state, facility_code }))} />
                <Field label="设施名称" value={facilityForm.facility_name} onChange={(facility_name) => setFacilityForm((state) => ({ ...state, facility_name }))} />
                <Field label="设施角色" value={facilityForm.facility_role} onChange={(facility_role) => setFacilityForm((state) => ({ ...state, facility_role }))} />
                <IncludedSelect value={facilityForm.included} onChange={(included) => setFacilityForm((state) => ({ ...state, included }))} />
                <Field label="排除原因" value={facilityForm.exclusion_reason} onChange={(exclusion_reason) => setFacilityForm((state) => ({ ...state, exclusion_reason }))} />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={closeFacilityDialog}>
                  取消
                </Button>
                <Button disabled={!facilityReady || saveFacility.isPending} onClick={() => saveFacility.mutate()}>
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
                <TableHead>边界</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>编号</TableHead>
                <TableHead>名称</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>纳入</TableHead>
                <TableHead>排除原因</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {facilities.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{boundaryById.get(item.boundary_id)?.boundary_name ?? "-"}</TableCell>
                  <TableCell>{facilityTypeLabel(item.facility_type)}</TableCell>
                  <TableCell>{item.facility_code || "-"}</TableCell>
                  <TableCell>{item.facility_name || "-"}</TableCell>
                  <TableCell>{item.facility_role || "-"}</TableCell>
                  <TableCell>
                    <Badge variant={item.included === false ? "secondary" : "default"}>{item.included === false ? "排除" : "纳入"}</Badge>
                  </TableCell>
                  <TableCell>{item.exclusion_reason || "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" disabled={boundaryById.get(item.boundary_id)?.status === "published"} onClick={() => openFacilityDialog(item)}>
                        编辑
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={boundaryById.get(item.boundary_id)?.status === "published"}
                        onClick={() => {
                          if (window.confirm("确认删除该边界设施？")) deleteFacility.mutate(item.id)
                        }}
                      >
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              <EmptyRow visible={!facilities.length} colSpan={8} label="暂无边界设施" />
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: number }[] }) {
  return (
    <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} />
      ))}
    </MetricStrip>
  )
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: "text" | "number" }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input aria-label={label} type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type="date" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function MethodSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>边界方法</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(methodLabels).map(([key, label]) => (
            <SelectItem key={key} value={key}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function OrgSelect({ value, organizations, onChange }: { value: string; organizations: ReportingOrganization[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>报告主体</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="选择报告主体" />
        </SelectTrigger>
        <SelectContent>
          {organizations.map((item) => (
            <SelectItem key={item.id} value={String(item.id)}>
              {item.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function PeriodSelect({ value, periods, onChange }: { value: string; periods: ReportingPeriod[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>报告期</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="选择报告期" />
        </SelectTrigger>
        <SelectContent>
          {periods.map((item) => (
            <SelectItem key={item.id} value={String(item.id)}>
              {item.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function BoundarySelect({ value, boundaries, onChange }: { value: string; boundaries: BoundaryVersion[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>组织边界</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="选择组织边界" />
        </SelectTrigger>
        <SelectContent>
          {boundaries
            .filter((item) => item.status !== "published")
            .map((item) => (
              <SelectItem key={item.id} value={String(item.id)}>
                {item.boundary_name}
              </SelectItem>
            ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function FacilityTypeSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>设施类型</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(facilityTypeLabels).map(([key, label]) => (
            <SelectItem key={key} value={key}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function IncludedSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>纳入边界</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="true">纳入</SelectItem>
          <SelectItem value="false">排除</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

function EmptyRow({ visible, colSpan, label }: { visible: boolean; colSpan: number; label: string }) {
  if (!visible) return null
  return <AdminTableStateRow colSpan={colSpan}>{label}</AdminTableStateRow>
}

async function postCarbonApi<T>(url: string, payload: Record<string, unknown>) {
  return writeCarbonApi<T>("POST", url, payload)
}

async function patchCarbonApi<T>(url: string, payload: Record<string, unknown>) {
  return writeCarbonApi<T>("PATCH", url, payload)
}

async function deleteCarbonApi(url: string) {
  const res = await fetch(url, { method: "DELETE" })
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<{ deleted: boolean }>
}

async function writeCarbonApi<T>(method: "POST" | "PATCH", url: string, payload: Record<string, unknown>) {
  const res = await fetch(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  })
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}

async function invalidateBoundary(qc: ReturnType<typeof useQueryClient>) {
  await qc.invalidateQueries({ queryKey: QUERY_KEY })
}

function toastError(title: string) {
  return (error: unknown) => toast.error(title, { description: error instanceof Error ? error.message : "请稍后重试" })
}

function optional(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function toNumber(value: string) {
  return Number.parseInt(value, 10)
}

function methodLabel(value?: string | null) {
  return value ? (methodLabels[value] ?? value) : "-"
}

function facilityTypeLabel(value?: string | null) {
  return value ? (facilityTypeLabels[value] ?? value) : "-"
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "-"
  return `${start || "-"} 至 ${end || "-"}`
}
