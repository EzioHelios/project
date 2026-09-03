import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, RefreshCw, Trash2 } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageScaffold, AdminPanel, AdminTableStateRow, AdminTabsList, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type PageResult, type Row, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

type MeasurementBoundary = Row & {
  id: number
  code: string
  name: string
  boundary_type: string
  meter_equipment_id?: number | null
  sector_id?: number | null
  use_system_code?: string | null
  energy_direction: string
  include_in_scope2: boolean
  valid_from?: string | null
  valid_to?: string | null
  status: string
  mapping_version?: string | null
  source_name?: string | null
  confidence_level?: string | null
  remark?: string | null
}

type BoundaryMember = Row & {
  id: number
  boundary_id: number
  member_code: string
  member_type: string
  sector_id?: number | null
  equipment_id?: number | null
  member_role: string
  allocation_weight?: number | null
  confirmation_status: string
  valid_from?: string | null
  valid_to?: string | null
  source_name?: string | null
  remark?: string | null
}

type BalanceSummary = {
  status: string
  input_energy: number
  allocated_energy: number
  unallocated_energy: number
  balance_error_pct?: number | null
  input_record_count: number
  allocated_record_count: number
  member_count: number
  metering_coverage_pct?: number | null
}

type BalanceCalculation = {
  boundary?: MeasurementBoundary | null
  summary: BalanceSummary
  rows: { code: string; label: string; value?: number | null; unit: string; source_name: string; record_count?: number | null }[]
}

type BalanceDiagnostic = {
  code: string
  title: string
  suggestion: string
  severity: string
  value?: number | null
  unit?: string | null
  count?: number | null
}

const emptyBoundary = {
  code: "",
  name: "",
  boundary_type: "site",
  meter_equipment_id: "none",
  sector_id: "none",
  use_system_code: "",
  energy_direction: "import",
  include_in_scope2: "true",
  valid_from: "2026-01-01",
  valid_to: "",
  status: "active",
  mapping_version: "woheng-v1",
  source_name: "",
  confidence_level: "high",
  remark: "",
}

const emptyMember = {
  member_code: "",
  member_type: "equipment",
  sector_id: "none",
  equipment_id: "none",
  member_role: "covered",
  allocation_weight: "",
  confirmation_status: "confirmed",
  valid_from: "2026-01-01",
  valid_to: "",
  source_name: "",
  remark: "",
}

const boundaryTypes = [
  { value: "site", label: "基地边界" },
  { value: "sub_boundary", label: "分项边界" },
  { value: "meter_circuit", label: "计量回路" },
]

const memberTypes = [
  { value: "equipment", label: "设备" },
  { value: "sector", label: "区域" },
]

const memberRoles = [
  { value: "covered", label: "归集成员" },
  { value: "input_meter", label: "输入表" },
]

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "boolean") return value ? "是" : "否"
  return String(value)
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function statusBadge(status?: string | null) {
  if (status === "balanced") return <Badge variant="success">已闭合</Badge>
  if (status === "warning") return <Badge variant="warning">需复核</Badge>
  if (status === "unbalanced") return <Badge variant="destructive">差异偏大</Badge>
  if (status === "active") return <Badge variant="success">启用</Badge>
  if (status === "inactive") return <Badge variant="outline">停用</Badge>
  if (status === "confirmed") return <Badge variant="success">已确认</Badge>
  return <Badge variant="outline">{display(status)}</Badge>
}

function severityBadge(severity: string) {
  if (severity === "ok") return <Badge variant="success">正常</Badge>
  if (severity === "high" || severity === "blocking") return <Badge variant="destructive">需处理</Badge>
  if (severity === "warning") return <Badge variant="warning">需复核</Badge>
  return <Badge variant="outline">{severity}</Badge>
}

function toOptionRows(rows: Row[]) {
  return rows.map((row) => ({
    value: String(row.id ?? ""),
    label: String(row.name ?? row.code ?? row.id ?? ""),
    code: row.code == null ? undefined : String(row.code),
  }))
}

function flattenRows(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenRows((Array.isArray(row.children) ? row.children : []) as Row[])])
}

function buildQuery(boundaryId: string, filters: { periodStart: string; periodEnd: string; granularity: string; energyTypeCode: string }) {
  const params = new URLSearchParams()
  if (boundaryId) params.set("boundary_id", boundaryId)
  if (filters.periodStart) params.set("period_start", filters.periodStart)
  if (filters.periodEnd) params.set("period_end", filters.periodEnd)
  params.set("granularity", filters.granularity)
  if (filters.energyTypeCode && filters.energyTypeCode !== "all") params.set("energy_type_code", filters.energyTypeCode)
  return params.toString()
}

function boundaryForm(row?: MeasurementBoundary | null) {
  return {
    code: row?.code ?? "",
    name: row?.name ?? "",
    boundary_type: row?.boundary_type ?? "site",
    meter_equipment_id: row?.meter_equipment_id == null ? "none" : String(row.meter_equipment_id),
    sector_id: row?.sector_id == null ? "none" : String(row.sector_id),
    use_system_code: row?.use_system_code ?? "",
    energy_direction: row?.energy_direction ?? "import",
    include_in_scope2: row?.include_in_scope2 === false ? "false" : "true",
    valid_from: row?.valid_from ?? "2026-01-01",
    valid_to: row?.valid_to ?? "",
    status: row?.status ?? "active",
    mapping_version: row?.mapping_version ?? "woheng-v1",
    source_name: row?.source_name ?? "",
    confidence_level: row?.confidence_level ?? "high",
    remark: row?.remark ?? "",
  }
}

function memberForm(row?: BoundaryMember | null) {
  return {
    member_code: row?.member_code ?? "",
    member_type: row?.member_type ?? "equipment",
    sector_id: row?.sector_id == null ? "none" : String(row.sector_id),
    equipment_id: row?.equipment_id == null ? "none" : String(row.equipment_id),
    member_role: row?.member_role ?? "covered",
    allocation_weight: row?.allocation_weight == null ? "" : String(row.allocation_weight),
    confirmation_status: row?.confirmation_status ?? "confirmed",
    valid_from: row?.valid_from ?? "2026-01-01",
    valid_to: row?.valid_to ?? "",
    source_name: row?.source_name ?? "",
    remark: row?.remark ?? "",
  }
}

function nullable(value: string) {
  return value.trim() && value !== "none" ? value.trim() : null
}

export function EnergyBalancePanel({ header }: { header?: ReactNode }) {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [selectedBoundaryId, setSelectedBoundaryId] = useState("")
  const [filters, setFilters] = useState({ periodStart: "", periodEnd: "", granularity: "day", energyTypeCode: "purchased_electricity" })
  const [boundaryOpen, setBoundaryOpen] = useState(false)
  const [boundaryEditing, setBoundaryEditing] = useState<MeasurementBoundary | null>(null)
  const [boundaryValues, setBoundaryValues] = useState(emptyBoundary)
  const [memberOpen, setMemberOpen] = useState(false)
  const [memberEditing, setMemberEditing] = useState<BoundaryMember | null>(null)
  const [memberValues, setMemberValues] = useState(emptyMember)

  const boundariesQuery = useQuery<PageResult<MeasurementBoundary>>({
    queryKey: ["energy-balance", "boundaries", appliedKeyword],
    queryFn: () => requestPage<MeasurementBoundary>("/api/energy/balance/boundaries", { keyword: appliedKeyword, limit: 200 }),
  })
  const boundaries = boundariesQuery.data?.items ?? []
  const currentBoundaryId = selectedBoundaryId || (boundaries[0]?.id == null ? "" : String(boundaries[0].id))
  const currentBoundary = boundaries.find((item) => String(item.id) === currentBoundaryId) ?? boundaries[0]

  const queryString = useMemo(() => buildQuery(currentBoundaryId, filters), [currentBoundaryId, filters])
  const calculationQuery = useQuery({
    queryKey: ["energy-balance", "calculation", queryString],
    queryFn: async () => (await request<BalanceCalculation>(`/api/energy/balance/calculation?${queryString}`)).data,
    enabled: Boolean(currentBoundaryId),
  })
  const diagnosticsQuery = useQuery({
    queryKey: ["energy-balance", "diagnostics", queryString],
    queryFn: async () => (await request<{ items: BalanceDiagnostic[] }>(`/api/energy/balance/diagnostics?${queryString}`)).data,
    enabled: Boolean(currentBoundaryId),
  })
  const membersQuery = useQuery<PageResult<BoundaryMember>>({
    queryKey: ["energy-balance", "members", currentBoundaryId],
    queryFn: () => requestPage<BoundaryMember>("/api/energy/balance/boundary-members", { boundary_id: currentBoundaryId, limit: 200 }),
    enabled: Boolean(currentBoundaryId),
  })
  const devicesQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-balance", "devices"],
    queryFn: () => requestPage<Row>("/api/master-data/devices", { limit: 500 }),
  })
  const areasQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-balance", "areas"],
    queryFn: async () => (await request<PageResult<Row>>("/api/master-data/areas/tree")).data,
  })
  const energyTypesQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-balance", "energy-types"],
    queryFn: () => requestPage<Row>("/api/energy/types", { limit: 200 }),
  })

  const deviceOptions = useMemo(() => toOptionRows(devicesQuery.data?.items ?? []), [devicesQuery.data?.items])
  const areaOptions = useMemo(() => toOptionRows(flattenRows(areasQuery.data?.items ?? [])), [areasQuery.data?.items])
  const energyTypeOptions = useMemo(() => toOptionRows(energyTypesQuery.data?.items ?? []), [energyTypesQuery.data?.items])
  const deviceNameById = useMemo(() => new Map(deviceOptions.map((option) => [option.value, option.label])), [deviceOptions])
  const areaNameById = useMemo(() => new Map(areaOptions.map((option) => [option.value, option.label])), [areaOptions])
  const members = membersQuery.data?.items ?? []
  const calculation = calculationQuery.data
  const diagnostics = diagnosticsQuery.data?.items ?? []
  const summary = calculation?.summary

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["energy-balance"] })
  }

  const saveBoundary = useMutation({
    mutationFn: () =>
      request<MeasurementBoundary>(boundaryEditing ? `/api/energy/balance/boundaries/${boundaryEditing.id}` : "/api/energy/balance/boundaries", {
        method: boundaryEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          code: boundaryValues.code,
          name: boundaryValues.name,
          boundary_type: boundaryValues.boundary_type,
          meter_equipment_id: nullable(boundaryValues.meter_equipment_id),
          sector_id: nullable(boundaryValues.sector_id),
          use_system_code: nullable(boundaryValues.use_system_code),
          energy_direction: boundaryValues.energy_direction,
          include_in_scope2: boundaryValues.include_in_scope2 === "true",
          valid_from: nullable(boundaryValues.valid_from),
          valid_to: nullable(boundaryValues.valid_to),
          status: boundaryValues.status,
          mapping_version: nullable(boundaryValues.mapping_version),
          source_name: nullable(boundaryValues.source_name),
          confidence_level: nullable(boundaryValues.confidence_level),
          remark: nullable(boundaryValues.remark),
        }),
      }),
    onSuccess: (result) => {
      toast.success(boundaryEditing ? "计量边界已更新" : "计量边界已保存")
      setSelectedBoundaryId(String(result.data.id))
      setBoundaryOpen(false)
      setBoundaryEditing(null)
      setBoundaryValues(emptyBoundary)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteBoundary = useMutation({
    mutationFn: (id: number) => request(`/api/energy/balance/boundaries/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("计量边界已删除")
      setSelectedBoundaryId("")
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请先停用或清理引用" }),
  })

  const saveMember = useMutation({
    mutationFn: () =>
      request<BoundaryMember>(memberEditing ? `/api/energy/balance/boundary-members/${memberEditing.id}` : "/api/energy/balance/boundary-members", {
        method: memberEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          boundary_id: currentBoundaryId,
          member_code: memberValues.member_code,
          member_type: memberValues.member_type,
          sector_id: nullable(memberValues.sector_id),
          equipment_id: nullable(memberValues.equipment_id),
          member_role: memberValues.member_role,
          allocation_weight: nullable(memberValues.allocation_weight),
          confirmation_status: memberValues.confirmation_status,
          valid_from: nullable(memberValues.valid_from),
          valid_to: nullable(memberValues.valid_to),
          source_name: nullable(memberValues.source_name),
          remark: nullable(memberValues.remark),
        }),
      }),
    onSuccess: () => {
      toast.success(memberEditing ? "边界成员已更新" : "边界成员已保存")
      setMemberOpen(false)
      setMemberEditing(null)
      setMemberValues(emptyMember)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteMember = useMutation({
    mutationFn: (id: number) => request(`/api/energy/balance/boundary-members/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("边界成员已删除")
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  return (
    <Tabs defaultValue="calculation" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="calculation">平衡计算</TabsTrigger>
            <TabsTrigger value="diagnostics">差异诊断</TabsTrigger>
            <TabsTrigger value="boundaries">计量边界</TabsTrigger>
            <TabsTrigger value="members">边界成员</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <ContextBar
            actions={
              <>
                <Button variant="outline" onClick={invalidate}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
                <Button
                  onClick={() => {
                    setBoundaryEditing(null)
                    setBoundaryValues(emptyBoundary)
                    setBoundaryOpen(true)
                  }}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新增边界
                </Button>
              </>
            }
          >
            <Select value={currentBoundaryId || undefined} onValueChange={setSelectedBoundaryId}>
              <SelectTrigger>
                <SelectValue placeholder="选择计量边界" />
              </SelectTrigger>
              <SelectContent>
                {boundaries.map((boundary) => (
                  <SelectItem key={boundary.id} value={String(boundary.id)}>
                    {boundary.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="date" value={filters.periodStart} onChange={(event) => setFilters((state) => ({ ...state, periodStart: event.target.value }))} />
            <Input type="date" value={filters.periodEnd} onChange={(event) => setFilters((state) => ({ ...state, periodEnd: event.target.value }))} />
            <Select value={filters.granularity} onValueChange={(value) => setFilters((state) => ({ ...state, granularity: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hour">小时</SelectItem>
                <SelectItem value="day">日</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filters.energyTypeCode} onValueChange={(value) => setFilters((state) => ({ ...state, energyTypeCode: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部能源</SelectItem>
                {energyTypeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.code ?? option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ContextBar>
        }
      >
        <TabsContent value="calculation" className="space-y-4">
          <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="边界输入" value={formatNumber(summary?.input_energy)} unit="kWh" meta={`${summary?.input_record_count ?? 0} 条输入记录`} />
            <MetricTile label="已归集用能" value={formatNumber(summary?.allocated_energy)} unit="kWh" meta={`${summary?.allocated_record_count ?? 0} 条成员记录`} />
            <MetricTile
              label="未归集差异"
              value={formatNumber(summary?.unallocated_energy)}
              unit="kWh"
              tone={summary?.status === "balanced" ? "success" : summary?.status === "warning" ? "warning" : "danger"}
            />
            <MetricTile label="平衡误差率" value={formatNumber(summary?.balance_error_pct)} unit="%" meta={summary ? statusBadge(summary.status) : "-"} />
          </MetricStrip>
          <AdminPanel title={currentBoundary?.name ?? "能量平衡表"} actions={summary ? statusBadge(summary.status) : null} contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>项目</TableHead>
                    <TableHead className="text-right">数值</TableHead>
                    <TableHead>单位</TableHead>
                    <TableHead className="text-right">记录数</TableHead>
                    <TableHead>口径</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(calculation?.rows ?? []).map((row) => (
                    <TableRow key={row.code}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(row.value)}</TableCell>
                      <TableCell>{row.unit}</TableCell>
                      <TableCell className="text-right tabular-nums">{display(row.record_count)}</TableCell>
                      <TableCell>{row.source_name}</TableCell>
                    </TableRow>
                  ))}
                  {(!calculation?.rows || calculation.rows.length === 0) && <AdminTableStateRow colSpan={5}>暂无平衡计算结果</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="diagnostics">
          <AdminPanel title="差异诊断" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>诊断项</TableHead>
                    <TableHead>建议</TableHead>
                    <TableHead className="text-right">数值</TableHead>
                    <TableHead className="text-right">记录数</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {diagnostics.map((item) => (
                    <TableRow key={`${item.code}-${item.title}`}>
                      <TableCell>{item.title}</TableCell>
                      <TableCell>{item.suggestion}</TableCell>
                      <TableCell className="text-right tabular-nums">{item.value == null ? "-" : `${formatNumber(item.value)} ${item.unit ?? ""}`}</TableCell>
                      <TableCell className="text-right tabular-nums">{display(item.count)}</TableCell>
                      <TableCell>{severityBadge(item.severity)}</TableCell>
                    </TableRow>
                  ))}
                  {diagnostics.length === 0 && <AdminTableStateRow colSpan={5}>暂无诊断结果</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="boundaries">
          <AdminPanel
            title="计量边界"
            actions={
              <div className="flex items-center gap-2">
                <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索边界" />
                <Button variant="outline" onClick={() => setAppliedKeyword(keyword)}>
                  查询
                </Button>
              </div>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>边界</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>输入表</TableHead>
                    <TableHead>区域</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {boundaries.map((boundary) => (
                    <TableRow key={boundary.id}>
                      <TableCell>
                        <div className="font-medium">{boundary.name}</div>
                        <div className="text-muted-foreground text-xs">{boundary.code}</div>
                      </TableCell>
                      <TableCell>{boundaryTypes.find((item) => item.value === boundary.boundary_type)?.label ?? boundary.boundary_type}</TableCell>
                      <TableCell>
                        {boundary.meter_equipment_id == null ? "-" : (deviceNameById.get(String(boundary.meter_equipment_id)) ?? display(boundary.meter_equipment_id))}
                      </TableCell>
                      <TableCell>{boundary.sector_id == null ? "-" : (areaNameById.get(String(boundary.sector_id)) ?? display(boundary.sector_id))}</TableCell>
                      <TableCell>{statusBadge(boundary.status)}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setSelectedBoundaryId(String(boundary.id))
                          }}
                        >
                          选择
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setBoundaryEditing(boundary)
                            setBoundaryValues(boundaryForm(boundary))
                            setBoundaryOpen(true)
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (window.confirm("确认删除该计量边界？")) deleteBoundary.mutate(boundary.id)
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {boundaries.length === 0 && <AdminTableStateRow colSpan={6}>暂无计量边界</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="members">
          <AdminPanel
            title="边界成员"
            actions={
              <Button
                onClick={() => {
                  setMemberEditing(null)
                  setMemberValues(emptyMember)
                  setMemberOpen(true)
                }}
                disabled={!currentBoundaryId}
              >
                <Plus className="mr-2 h-4 w-4" />
                新增成员
              </Button>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>成员</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>角色</TableHead>
                    <TableHead>设备</TableHead>
                    <TableHead>区域</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell>{member.member_code}</TableCell>
                      <TableCell>{memberTypes.find((item) => item.value === member.member_type)?.label ?? member.member_type}</TableCell>
                      <TableCell>{memberRoles.find((item) => item.value === member.member_role)?.label ?? member.member_role}</TableCell>
                      <TableCell>{member.equipment_id == null ? "-" : (deviceNameById.get(String(member.equipment_id)) ?? display(member.equipment_id))}</TableCell>
                      <TableCell>{member.sector_id == null ? "-" : (areaNameById.get(String(member.sector_id)) ?? display(member.sector_id))}</TableCell>
                      <TableCell>{statusBadge(member.confirmation_status)}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setMemberEditing(member)
                            setMemberValues(memberForm(member))
                            setMemberOpen(true)
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (window.confirm("确认删除该边界成员？")) deleteMember.mutate(member.id)
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {members.length === 0 && <AdminTableStateRow colSpan={7}>暂无边界成员</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>
      </AdminPageScaffold>
      <BoundaryDialog
        open={boundaryOpen}
        values={boundaryValues}
        editing={boundaryEditing}
        saving={saveBoundary.isPending}
        deviceOptions={deviceOptions}
        areaOptions={areaOptions}
        onOpenChange={setBoundaryOpen}
        onChange={setBoundaryValues}
        onSave={() => saveBoundary.mutate()}
      />
      <MemberDialog
        open={memberOpen}
        values={memberValues}
        editing={memberEditing}
        saving={saveMember.isPending}
        deviceOptions={deviceOptions}
        areaOptions={areaOptions}
        onOpenChange={setMemberOpen}
        onChange={setMemberValues}
        onSave={() => saveMember.mutate()}
      />
    </Tabs>
  )
}

function BoundaryDialog({
  open,
  values,
  editing,
  saving,
  deviceOptions,
  areaOptions,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyBoundary
  editing: MeasurementBoundary | null
  saving: boolean
  deviceOptions: { value: string; label: string; code?: string }[]
  areaOptions: { value: string; label: string; code?: string }[]
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyBoundary) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyBoundary, value: string) => onChange({ ...values, [key]: value })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑计量边界" : "新增计量边界"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="边界编码" value={values.code} onChange={(next) => set("code", next)} />
          <TextField label="边界名称" value={values.name} onChange={(next) => set("name", next)} />
          <SelectField label="边界类型" value={values.boundary_type} options={boundaryTypes} onChange={(next) => set("boundary_type", next)} />
          <SelectField
            label="输入表"
            value={values.meter_equipment_id}
            options={[{ value: "none", label: "未选择" }, ...deviceOptions]}
            onChange={(next) => set("meter_equipment_id", next)}
          />
          <SelectField label="覆盖区域" value={values.sector_id} options={[{ value: "none", label: "未选择" }, ...areaOptions]} onChange={(next) => set("sector_id", next)} />
          <TextField label="用能系统编码" value={values.use_system_code} onChange={(next) => set("use_system_code", next)} />
          <SelectField
            label="能源方向"
            value={values.energy_direction}
            options={[
              { value: "import", label: "输入" },
              { value: "export", label: "输出" },
            ]}
            onChange={(next) => set("energy_direction", next)}
          />
          <SelectField
            label="纳入范围二"
            value={values.include_in_scope2}
            options={[
              { value: "true", label: "是" },
              { value: "false", label: "否" },
            ]}
            onChange={(next) => set("include_in_scope2", next)}
          />
          <TextField label="生效日期" type="date" value={values.valid_from} onChange={(next) => set("valid_from", next)} />
          <TextField label="截止日期" type="date" value={values.valid_to} onChange={(next) => set("valid_to", next)} />
          <SelectField
            label="状态"
            value={values.status}
            options={[
              { value: "active", label: "启用" },
              { value: "inactive", label: "停用" },
            ]}
            onChange={(next) => set("status", next)}
          />
          <TextField label="映射版本" value={values.mapping_version} onChange={(next) => set("mapping_version", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <TextField label="置信度" value={values.confidence_level} onChange={(next) => set("confidence_level", next)} />
          <div className="grid gap-2 md:col-span-2">
            <Label htmlFor="energy-balance-boundary-remark">备注</Label>
            <Textarea id="energy-balance-boundary-remark" value={values.remark} onChange={(event) => set("remark", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={!values.code.trim() || !values.name.trim() || saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MemberDialog({
  open,
  values,
  editing,
  saving,
  deviceOptions,
  areaOptions,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyMember
  editing: BoundaryMember | null
  saving: boolean
  deviceOptions: { value: string; label: string; code?: string }[]
  areaOptions: { value: string; label: string; code?: string }[]
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyMember) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyMember, value: string) => onChange({ ...values, [key]: value })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑边界成员" : "新增边界成员"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="成员编码" value={values.member_code} onChange={(next) => set("member_code", next)} />
          <SelectField label="成员类型" value={values.member_type} options={memberTypes} onChange={(next) => set("member_type", next)} />
          <SelectField label="成员角色" value={values.member_role} options={memberRoles} onChange={(next) => set("member_role", next)} />
          <SelectField label="设备" value={values.equipment_id} options={[{ value: "none", label: "未选择" }, ...deviceOptions]} onChange={(next) => set("equipment_id", next)} />
          <SelectField label="区域" value={values.sector_id} options={[{ value: "none", label: "未选择" }, ...areaOptions]} onChange={(next) => set("sector_id", next)} />
          <TextField label="归集权重" type="number" value={values.allocation_weight} onChange={(next) => set("allocation_weight", next)} />
          <SelectField
            label="确认状态"
            value={values.confirmation_status}
            options={[
              { value: "confirmed", label: "已确认" },
              { value: "candidate", label: "候选" },
            ]}
            onChange={(next) => set("confirmation_status", next)}
          />
          <TextField label="生效日期" type="date" value={values.valid_from} onChange={(next) => set("valid_from", next)} />
          <TextField label="截止日期" type="date" value={values.valid_to} onChange={(next) => set("valid_to", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <div className="grid gap-2 md:col-span-2">
            <Label htmlFor="energy-balance-member-remark">备注</Label>
            <Textarea id="energy-balance-member-remark" value={values.remark} onChange={(event) => set("remark", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={!values.member_code.trim() || saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TextField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  const id = `energy-balance-field-${label}`
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void }) {
  const id = `energy-balance-select-${label}`
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger id={id}>
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
