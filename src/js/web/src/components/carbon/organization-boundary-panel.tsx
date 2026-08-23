import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
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
}

type PeriodForm = {
  reporting_org_id: string
  code: string
  name: string
  period_start: string
  period_end: string
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
}

const defaultPeriodForm: PeriodForm = {
  reporting_org_id: "",
  code: "",
  name: "",
  period_start: "",
  period_end: "",
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
  const periodById = useMemo(() => new Map(periods.map((item) => [item.id, item])), [periods])
  const boundaryById = useMemo(() => new Map(boundaries.map((item) => [item.id, item])), [boundaries])

  const createOrganization = useMutation({
    mutationFn: () =>
      postCarbonApi<ReportingOrganization>("/api/carbon/organization-boundary/organizations", {
        code: organizationForm.code.trim(),
        name: organizationForm.name.trim(),
        legal_entity_code: optional(organizationForm.legal_entity_code),
        control_method: organizationForm.control_method,
        source_name: "enterprise_inventory",
      }),
    onSuccess: async () => {
      toast.success("报告主体已创建")
      setOrganizationOpen(false)
      setOrganizationForm(defaultOrganizationForm)
      await invalidateBoundary(qc)
    },
    onError: toastError("创建报告主体失败"),
  })

  const createPeriod = useMutation({
    mutationFn: () =>
      postCarbonApi<ReportingPeriod>("/api/carbon/organization-boundary/periods", {
        reporting_org_id: toNumber(periodForm.reporting_org_id),
        code: periodForm.code.trim(),
        name: periodForm.name.trim(),
        period_start: periodForm.period_start,
        period_end: periodForm.period_end,
        period_type: "annual",
        source_name: "enterprise_inventory",
      }),
    onSuccess: async () => {
      toast.success("报告期已创建")
      setPeriodOpen(false)
      setPeriodForm(defaultPeriodForm)
      await invalidateBoundary(qc)
    },
    onError: toastError("创建报告期失败"),
  })

  const createBoundary = useMutation({
    mutationFn: () =>
      postCarbonApi<BoundaryVersion>("/api/carbon/organization-boundary/boundaries", {
        reporting_org_id: toNumber(boundaryForm.reporting_org_id),
        period_id: toNumber(boundaryForm.period_id),
        boundary_no: boundaryForm.boundary_no.trim(),
        boundary_name: boundaryForm.boundary_name.trim(),
        boundary_method: boundaryForm.boundary_method,
        boundary_type: "organization",
        status: "draft",
        source_name: "enterprise_inventory",
        confidence_level: "medium",
      }),
    onSuccess: async () => {
      toast.success("边界版本已创建")
      setBoundaryOpen(false)
      setBoundaryForm(defaultBoundaryForm)
      await invalidateBoundary(qc)
    },
    onError: toastError("创建边界版本失败"),
  })

  const createFacility = useMutation({
    mutationFn: () =>
      postCarbonApi<BoundaryFacility>("/api/carbon/organization-boundary/facilities", {
        boundary_id: toNumber(facilityForm.boundary_id),
        facility_type: facilityForm.facility_type,
        facility_code: optional(facilityForm.facility_code),
        facility_name: optional(facilityForm.facility_name),
        facility_role: optional(facilityForm.facility_role),
        included: facilityForm.included === "true",
        exclusion_reason: optional(facilityForm.exclusion_reason),
        source_name: "enterprise_inventory",
      }),
    onSuccess: async () => {
      toast.success("边界设施已维护")
      setFacilityOpen(false)
      setFacilityForm(defaultFacilityForm)
      await invalidateBoundary(qc)
    },
    onError: toastError("维护边界设施失败"),
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
            <Dialog open={organizationOpen} onOpenChange={setOrganizationOpen}>
              <DialogTrigger asChild>
                <Button size="sm">新增主体</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>新增报告主体</DialogTitle>
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
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setOrganizationOpen(false)}>
                    取消
                  </Button>
                  <Button disabled={!organizationReady || createOrganization.isPending} onClick={() => createOrganization.mutate()}>
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
                  </TableRow>
                ))}
                <EmptyRow visible={!organizations.length} colSpan={4} label="暂无报告主体" />
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>

        <AdminPanel
          title="报告期"
          actions={
            <Dialog open={periodOpen} onOpenChange={setPeriodOpen}>
              <DialogTrigger asChild>
                <Button size="sm">新增报告期</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>新增报告期</DialogTitle>
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
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setPeriodOpen(false)}>
                    取消
                  </Button>
                  <Button disabled={!periodReady || createPeriod.isPending} onClick={() => createPeriod.mutate()}>
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
                  </TableRow>
                ))}
                <EmptyRow visible={!periods.length} colSpan={5} label="暂无报告期" />
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>
      </div>

      <AdminPanel
        title="组织边界版本"
        actions={
          <Dialog open={boundaryOpen} onOpenChange={setBoundaryOpen}>
            <DialogTrigger asChild>
              <Button size="sm">新增边界</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>新增边界版本</DialogTitle>
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
                <Button variant="outline" onClick={() => setBoundaryOpen(false)}>
                  取消
                </Button>
                <Button disabled={!boundaryReady || createBoundary.isPending} onClick={() => createBoundary.mutate()}>
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
          <Dialog open={facilityOpen} onOpenChange={setFacilityOpen}>
            <DialogTrigger asChild>
              <Button size="sm">维护设施</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>维护边界设施</DialogTitle>
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
                <Button variant="outline" onClick={() => setFacilityOpen(false)}>
                  取消
                </Button>
                <Button disabled={!facilityReady || createFacility.isPending} onClick={() => createFacility.mutate()}>
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
                </TableRow>
              ))}
              <EmptyRow visible={!facilities.length} colSpan={7} label="暂无边界设施" />
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

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
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
  const res = await fetch(url, {
    method: "POST",
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
