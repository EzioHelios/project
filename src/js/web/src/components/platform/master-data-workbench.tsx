import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ChevronRight, Plus, RefreshCw } from "lucide-react"
import { type ReactNode, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useAuthStore } from "@/lib/auth"
import { cn } from "@/lib/utils"

type Id = number

type AreaNode = {
  id: Id
  code: string
  name?: string | null
  parent_id?: Id | null
  area_type?: string | null
  sort_index?: number | null
  is_enabled?: boolean
  equipment_count?: number
  child_count?: number
  children: AreaNode[]
}

type AreaSummary = {
  area: AreaNode & {
    manager_name?: string | null
    owner_department?: string | null
    location_desc?: string | null
    remark?: string | null
    parent?: { id: Id; code: string; name?: string | null } | null
  }
  children: AreaNode[]
  devices: DeviceRow[]
  stats: { device_total: number; device_online: number; device_fault: number; child_area_total: number }
}

type DeviceTypeNode = {
  id: Id
  code: string
  name: string
  parent_id?: Id | null
  child_count?: number
  children: DeviceTypeNode[]
}

type DeviceRow = {
  id: Id
  code: string
  name?: string | null
  area_id?: Id | null
  area_name?: string | null
  device_type_id?: Id | null
  device_type?: { id: Id; code: string; name: string } | null
  parent_device_id?: Id | null
  parent_device?: { id: Id; code: string; name?: string | null } | null
  status?: number | null
  asset_code?: string | null
  external_device_id?: string | null
  model?: string | null
  manufacturer?: string | null
  owner_department?: string | null
  maintainer_name?: string | null
  energy_type?: string | null
  protocol?: string | null
  commissioning_status?: string | null
  location_desc?: string | null
  remark?: string | null
  is_enabled?: boolean
  child_device_count?: number
  point_count?: number
}

type DeviceDetail = {
  device: DeviceRow
  children: DeviceRow[]
  points: DevicePointRow[]
}

type DevicePointRow = {
  id: Id
  device_id: Id
  point_code: string
  point_name: string
  unit?: string | null
  value_type?: string | null
  source_field?: string | null
  sampling_interval_seconds?: number | null
  is_enabled?: boolean
  is_alarm_enabled?: boolean
  upper_limit?: number | null
  lower_limit?: number | null
  remark?: string | null
}

type MqttSourceRow = {
  id: Id
  code: string
  name: string
  broker_host?: string | null
  broker_port?: number | null
  client_id?: string | null
  tls_enabled?: boolean | null
  enabled?: boolean | null
}

type MqttSubscriptionRow = {
  id: Id
  source_id: Id
  topic_filter: string
  parser_code?: string | null
  contract_version?: string | null
  qos?: number | null
  expected_interval_seconds?: number | null
  enabled?: boolean | null
}

type MqttBindingRow = {
  id: Id
  subscription_id: Id
  gateway_key: string
  meter_key: string
  selector_name_pattern?: string | null
  equipment_id?: Id | null
  external_device_id?: string | null
  temporary_address?: string | null
  identity_status?: string | null
  scaling_mode?: string | null
  multiplier?: number | null
}

type MqttMappingRow = {
  id: Id
  binding_id: Id
  source_tag: string
  source_name_suffix?: string | null
  point_code: string
  point_name?: string | null
  unit?: string | null
  mapping_version?: string | null
  enabled?: boolean | null
}

type MqttMessageRow = {
  id: Id
  source_id: Id
  subscription_id: Id
  topic?: string | null
  status?: string | null
  received_at?: string | null
  published_at?: string | null
  processed_at?: string | null
  error_code?: string | null
  error_detail?: string | null
}

type MqttTestResult = {
  message: MqttMessageRow
  created: boolean
  readings: Array<{
    id: Id
    equipment_id: Id
    source_point_code: string
    point_code: string
    point_name: string
    normalized_value?: number | null
    unit?: string | null
    quality_status?: string | null
    reading_time?: string | null
  }>
  reading_count: number
}

type AreaForm = {
  code: string
  name: string
  area_type: string
  sort_index: string
  is_enabled: string
  manager_name: string
  owner_department: string
  location_desc: string
  remark: string
}

type DeviceForm = {
  code: string
  name: string
  area_id: string
  device_type_id: string
  parent_device_id: string
  asset_code: string
  external_device_id: string
  model: string
  manufacturer: string
  owner_department: string
  maintainer_name: string
  energy_type: string
  protocol: string
  status: string
  commissioning_status: string
  location_desc: string
  remark: string
  is_enabled: string
}

type DevicePointForm = {
  point_code: string
  point_name: string
  unit: string
  value_type: string
  source_field: string
  sampling_interval_seconds: string
  is_enabled: string
  is_alarm_enabled: string
  upper_limit: string
  lower_limit: string
  remark: string
}

type DeviceDetailTab = "devices" | "types" | "points" | "ingestion" | "quality"

const AREA_TYPE_OPTIONS = [
  { label: "园区/厂区", value: "site" },
  { label: "建筑", value: "building" },
  { label: "车间", value: "workshop" },
  { label: "仓库", value: "warehouse" },
  { label: "区域/库区", value: "zone" },
  { label: "产线", value: "line" },
  { label: "工位", value: "station" },
  { label: "公辅", value: "utility" },
  { label: "其他", value: "other" },
] as const

const STATUS_OPTIONS = [
  { label: "全部状态", value: "all" },
  { label: "在线", value: "0" },
  { label: "故障", value: "1" },
] as const

const ENABLE_OPTIONS = [
  { label: "启用", value: "true" },
  { label: "停用", value: "false" },
] as const

const COMMISSIONING_OPTIONS = [
  { label: "投运", value: "active" },
  { label: "调试中", value: "commissioning" },
  { label: "停用", value: "retired" },
] as const

const PROTOCOL_OPTIONS = [
  { label: "云集 HTTP", value: "http_yunji" },
  { label: "MQTT", value: "mqtt" },
  { label: "Modbus", value: "modbus" },
  { label: "RTSP", value: "rtsp" },
] as const

const VALUE_TYPE_OPTIONS = [
  { label: "浮点数", value: "float" },
  { label: "整数", value: "int" },
  { label: "布尔", value: "bool" },
  { label: "字符串", value: "string" },
  { label: "枚举", value: "enum" },
] as const

function flattenAreaTree(nodes: AreaNode[]): AreaNode[] {
  const items: AreaNode[] = []
  const visit = (node: AreaNode) => {
    items.push(node)
    node.children.forEach(visit)
  }
  nodes.forEach(visit)
  return items
}

function flattenDeviceTypeTree(nodes: DeviceTypeNode[]): DeviceTypeNode[] {
  const items: DeviceTypeNode[] = []
  const visit = (node: DeviceTypeNode) => {
    items.push(node)
    node.children.forEach(visit)
  }
  nodes.forEach(visit)
  return items
}

function areaLabel(area?: { code?: string | null; name?: string | null }) {
  return area?.name || area?.code || "-"
}

function deviceLabel(device?: { code?: string | null; name?: string | null }) {
  return device?.name || device?.code || "-"
}

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

function mqttIdentityStatus(value?: string | null) {
  const labels: Record<string, string> = {
    confirmed: "已确认",
    temporary: "临时识别",
  }
  return labels[String(value || "")] ?? value ?? "-"
}

function mqttMessageStatus(value?: string | null) {
  const labels: Record<string, string> = {
    received: "已接收",
    processed: "已处理",
    rejected: "已拒收",
  }
  return labels[String(value || "")] ?? value ?? "-"
}

function boolValue(value?: boolean | null) {
  return value === false ? "false" : "true"
}

function emptyAreaForm(): AreaForm {
  return {
    code: "",
    name: "",
    area_type: "zone",
    sort_index: "0",
    is_enabled: "true",
    manager_name: "",
    owner_department: "",
    location_desc: "",
    remark: "",
  }
}

function emptyDeviceForm(): DeviceForm {
  return {
    code: "",
    name: "",
    area_id: "",
    device_type_id: "",
    parent_device_id: "",
    asset_code: "",
    external_device_id: "",
    model: "",
    manufacturer: "",
    owner_department: "",
    maintainer_name: "",
    energy_type: "",
    protocol: "http_yunji",
    status: "0",
    commissioning_status: "active",
    location_desc: "",
    remark: "",
    is_enabled: "true",
  }
}

function emptyPointForm(): DevicePointForm {
  return {
    point_code: "",
    point_name: "",
    unit: "",
    value_type: "float",
    source_field: "",
    sampling_interval_seconds: "",
    is_enabled: "true",
    is_alarm_enabled: "false",
    upper_limit: "",
    lower_limit: "",
    remark: "",
  }
}

function AreaTreeNode({
  node,
  selectedId,
  expandedIds,
  onToggle,
  onSelect,
}: {
  node: AreaNode
  selectedId: number | null
  expandedIds: Set<number>
  onToggle: (nodeId: number) => void
  onSelect: (nodeId: number) => void
}) {
  const hasChildren = node.children.length > 0
  const expanded = expandedIds.has(node.id)

  return (
    <div>
      <div
        className={cn(
          "flex items-center rounded-md text-sm transition-colors hover:bg-accent/70",
          selectedId === node.id && "bg-primary/10 text-primary",
          node.is_enabled === false && "opacity-60",
        )}
      >
        <button type="button" className="flex size-7 items-center justify-center" onClick={() => hasChildren && onToggle(node.id)}>
          {hasChildren && <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />}
        </button>
        <button type="button" className="min-w-0 flex-1 py-2 text-left" onClick={() => onSelect(node.id)}>
          <div className="truncate font-medium">{areaLabel(node)}</div>
          <div className="truncate text-xs text-muted-foreground">
            {node.area_type || "zone"} · {node.equipment_count ?? 0} 台设备
          </div>
        </button>
      </div>
      {hasChildren && expanded && (
        <div className="ml-4 border-l border-border/60 pl-2">
          {node.children.map((child) => (
            <AreaTreeNode key={child.id} node={child} selectedId={selectedId} expandedIds={expandedIds} onToggle={onToggle} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}

function DeviceTypeTreeNode({
  node,
  selectedId,
  expandedIds,
  onToggle,
  onSelect,
}: {
  node: DeviceTypeNode
  selectedId: number | null
  expandedIds: Set<number>
  onToggle: (nodeId: number) => void
  onSelect: (nodeId: number | null) => void
}) {
  const hasChildren = node.children.length > 0
  const expanded = expandedIds.has(node.id)
  return (
    <div>
      <div className={cn("flex items-center rounded-md text-sm hover:bg-accent/70", selectedId === node.id && "bg-primary/10 text-primary")}>
        <button type="button" className="flex size-7 items-center justify-center" onClick={() => hasChildren && onToggle(node.id)}>
          {hasChildren && <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />}
        </button>
        <button type="button" className="min-w-0 flex-1 truncate py-2 text-left" onClick={() => onSelect(node.id)}>
          {node.name}
        </button>
      </div>
      {hasChildren && expanded && (
        <div className="ml-4 border-l border-border/60 pl-2">
          {node.children.map((child) => (
            <DeviceTypeTreeNode key={child.id} node={child} selectedId={selectedId} expandedIds={expandedIds} onToggle={onToggle} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}

export function MonitorAreaWorkbenchPage() {
  const qc = useQueryClient()
  const [selectedAreaId, setSelectedAreaId] = useState<number | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingArea, setEditingArea] = useState<AreaNode | null>(null)
  const [parentId, setParentId] = useState<number | null>(null)
  const [form, setForm] = useState<AreaForm>(emptyAreaForm())

  const treeQuery = useQuery({
    queryKey: ["master-data", "areas", "tree"],
    queryFn: async () => (await request<{ items: AreaNode[]; root?: AreaNode | null }>("/api/master-data/areas/tree")).data,
  })

  const treeItems = treeQuery.data?.items ?? []
  const flatAreas = useMemo(() => flattenAreaTree(treeItems), [treeItems])

  useEffect(() => {
    if (!selectedAreaId && flatAreas.length > 0) {
      const firstRealArea = flatAreas.find((item) => item.code !== "ROOT") ?? flatAreas[0]
      setSelectedAreaId(firstRealArea.id)
      setExpandedIds(new Set([firstRealArea.id, ...(firstRealArea.parent_id ? [firstRealArea.parent_id] : [])]))
    }
  }, [flatAreas, selectedAreaId])

  const summaryQuery = useQuery({
    queryKey: ["master-data", "areas", "summary", selectedAreaId],
    queryFn: async () => (await request<AreaSummary>(`/api/master-data/areas/${selectedAreaId}/summary`)).data,
    enabled: selectedAreaId !== null,
  })

  function openCreate(mode: "child" | "sibling") {
    const selected = flatAreas.find((item) => item.id === selectedAreaId)
    const nextParentId = mode === "child" ? (selected?.id ?? null) : (selected?.parent_id ?? null)
    setEditingArea(null)
    setParentId(nextParentId)
    setForm(emptyAreaForm())
    setDialogOpen(true)
  }

  function openEdit() {
    const selected = summaryQuery.data?.area
    if (!selected) return
    setEditingArea(selected)
    setParentId(selected.parent_id ?? null)
    setForm({
      code: selected.code,
      name: selected.name ?? "",
      area_type: selected.area_type ?? "zone",
      sort_index: String(selected.sort_index ?? 0),
      is_enabled: boolValue(selected.is_enabled),
      manager_name: selected.manager_name ?? "",
      owner_department: selected.owner_department ?? "",
      location_desc: selected.location_desc ?? "",
      remark: selected.remark ?? "",
    })
    setDialogOpen(true)
  }

  const saveArea = useMutation({
    mutationFn: async () => {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        parent_id: parentId,
        area_type: form.area_type,
        sort_index: Number(form.sort_index || 0),
        is_enabled: form.is_enabled === "true",
        manager_name: form.manager_name.trim() || null,
        owner_department: form.owner_department.trim() || null,
        location_desc: form.location_desc.trim() || null,
        remark: form.remark.trim() || null,
      }
      return request(editingArea ? `/api/master-data/areas/${editingArea.id}` : "/api/master-data/areas", {
        method: editingArea ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: async () => {
      toast.success(editingArea ? "区域已更新" : "区域已创建")
      setDialogOpen(false)
      await qc.invalidateQueries({ queryKey: ["master-data", "areas"] })
      if (!editingArea) {
        await qc.invalidateQueries({ queryKey: ["master-data", "devices"] })
      }
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const disableArea = useMutation({
    mutationFn: async () =>
      request(`/api/master-data/areas/${selectedAreaId}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ is_enabled: false }) }),
    onSuccess: async () => {
      toast.success("区域已停用")
      await qc.invalidateQueries({ queryKey: ["master-data", "areas"] })
    },
    onError: (error) => toast.error("停用失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="区域主数据工作台" />
      <PageSection>
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <AdminPanel
            title="区域树"
            className="min-h-[720px]"
            actions={
              <>
                <Button variant="outline" size="sm" onClick={() => treeQuery.refetch()} disabled={treeQuery.isFetching}>
                  <RefreshCw className="mr-2 size-4" />
                  刷新
                </Button>
                <Button size="sm" onClick={() => openCreate("child")} disabled={!selectedAreaId}>
                  <Plus className="mr-2 size-4" />
                  新增子区域
                </Button>
                <Button variant="outline" size="sm" onClick={() => openCreate("sibling")} disabled={!selectedAreaId}>
                  新增同级
                </Button>
              </>
            }
            contentClassName="space-y-2"
          >
            {treeItems.map((node) => (
              <AreaTreeNode
                key={node.id}
                node={node}
                selectedId={selectedAreaId}
                expandedIds={expandedIds}
                onToggle={(nodeId) =>
                  setExpandedIds((current) => {
                    const next = new Set(current)
                    if (next.has(nodeId)) next.delete(nodeId)
                    else next.add(nodeId)
                    return next
                  })
                }
                onSelect={(nodeId) => setSelectedAreaId(nodeId)}
              />
            ))}
          </AdminPanel>

          <AdminPanel
            title={summaryQuery.data?.area ? areaLabel(summaryQuery.data.area) : "区域详情"}
            className="min-h-[720px]"
            actions={
              <>
                <Button variant="outline" size="sm" onClick={openEdit} disabled={!summaryQuery.data?.area}>
                  编辑
                </Button>
                <Button variant="outline" size="sm" onClick={() => disableArea.mutate()} disabled={!summaryQuery.data?.area || disableArea.isPending}>
                  停用
                </Button>
              </>
            }
            contentClassName="space-y-5"
          >
            {summaryQuery.data?.area ? (
              <>
                <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
                  <SummaryMetric label="子区域" value={String(summaryQuery.data.stats.child_area_total)} />
                  <SummaryMetric label="本区设备" value={String(summaryQuery.data.stats.device_total)} />
                  <SummaryMetric label="在线设备" value={String(summaryQuery.data.stats.device_online)} />
                  <SummaryMetric label="故障设备" value={String(summaryQuery.data.stats.device_fault)} />
                </MetricStrip>

                <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
                  <DetailCard title="基础信息">
                    <DetailRow label="编码" value={summaryQuery.data.area.code} />
                    <DetailRow label="类型" value={summaryQuery.data.area.area_type ?? "-"} />
                    <DetailRow label="上级区域" value={areaLabel(summaryQuery.data.area.parent ?? undefined)} />
                    <DetailRow label="负责人" value={summaryQuery.data.area.manager_name ?? "-"} />
                    <DetailRow label="归属部门" value={summaryQuery.data.area.owner_department ?? "-"} />
                    <DetailRow label="位置说明" value={summaryQuery.data.area.location_desc ?? "-"} />
                    <DetailRow label="备注" value={summaryQuery.data.area.remark ?? "-"} />
                  </DetailCard>

                  <DetailCard title="影响范围">
                    <div className="space-y-2 text-sm">
                      <div>子区域数：{summaryQuery.data.children.length}</div>
                      <div>本区域设备数：{summaryQuery.data.devices.length}</div>
                      <div>删除前必须先清空子区域与设备。</div>
                    </div>
                  </DetailCard>
                </div>

                <DetailCard title="下级区域">
                  {summaryQuery.data.children.length === 0 ? (
                    <div className="text-sm text-muted-foreground">暂无子区域</div>
                  ) : (
                    <div className="grid gap-2 md:grid-cols-2">
                      {summaryQuery.data.children.map((child) => (
                        <button
                          key={child.id}
                          type="button"
                          className="rounded-md border border-border/70 p-3 text-left transition-colors hover:bg-accent/60"
                          onClick={() => setSelectedAreaId(child.id)}
                        >
                          <div className="font-medium">{areaLabel(child)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {child.area_type ?? "zone"} · {child.equipment_count ?? 0} 台设备
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </DetailCard>

                <DetailCard title="本区域设备">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>名称</TableHead>
                        <TableHead>类型</TableHead>
                        <TableHead>资产编码</TableHead>
                        <TableHead>状态</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {summaryQuery.data.devices.length === 0 && <AdminTableStateRow colSpan={4}>暂无设备</AdminTableStateRow>}
                      {summaryQuery.data.devices.map((device) => (
                        <TableRow key={device.id}>
                          <TableCell>{deviceLabel(device)}</TableCell>
                          <TableCell>{device.device_type?.name ?? "-"}</TableCell>
                          <TableCell>{device.asset_code || "-"}</TableCell>
                          <TableCell>{device.status === 1 ? "故障" : "在线"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </DetailCard>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">选择左侧区域后查看详情。</div>
            )}
          </AdminPanel>
        </div>
      </PageSection>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingArea ? "编辑区域" : "新增区域"}</DialogTitle>
            <DialogDescription className="sr-only">维护区域树节点的名称、层级语义和管理归属。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="区域编码">
              <Input value={form.code} onChange={(event) => setForm((state) => ({ ...state, code: event.target.value }))} />
            </Field>
            <Field label="区域名称">
              <Input value={form.name} onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))} />
            </Field>
            <Field label="区域类型">
              <Select value={form.area_type} onValueChange={(value) => setForm((state) => ({ ...state, area_type: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AREA_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="启用状态">
              <Select value={form.is_enabled} onValueChange={(value) => setForm((state) => ({ ...state, is_enabled: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENABLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="负责人">
              <Input value={form.manager_name} onChange={(event) => setForm((state) => ({ ...state, manager_name: event.target.value }))} />
            </Field>
            <Field label="归属部门">
              <Input value={form.owner_department} onChange={(event) => setForm((state) => ({ ...state, owner_department: event.target.value }))} />
            </Field>
            <Field label="排序">
              <Input type="number" value={form.sort_index} onChange={(event) => setForm((state) => ({ ...state, sort_index: event.target.value }))} />
            </Field>
            <Field label="位置说明" className="sm:col-span-2">
              <Input value={form.location_desc} onChange={(event) => setForm((state) => ({ ...state, location_desc: event.target.value }))} />
            </Field>
            <Field label="备注" className="sm:col-span-2">
              <Textarea value={form.remark} onChange={(event) => setForm((state) => ({ ...state, remark: event.target.value }))} className="min-h-24" />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={() => saveArea.mutate()} disabled={saveArea.isPending || !form.code.trim() || !form.name.trim()}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}

function DeviceWorkbench({ title, initialTab }: { title: string; initialTab: DeviceDetailTab }) {
  const qc = useQueryClient()
  const currentUser = useAuthStore((state) => state.user)
  const [expandedAreaIds, setExpandedAreaIds] = useState<Set<number>>(new Set())
  const [expandedTypeIds, setExpandedTypeIds] = useState<Set<number>>(new Set())
  const [selectedAreaFilter, setSelectedAreaFilter] = useState<number | null>(null)
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState("all")
  const [keyword, setKeyword] = useState("")
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingDevice, setEditingDevice] = useState<DeviceRow | null>(null)
  const [pointDialogOpen, setPointDialogOpen] = useState(false)
  const [editingPoint, setEditingPoint] = useState<DevicePointRow | null>(null)
  const [deviceForm, setDeviceForm] = useState<DeviceForm>(emptyDeviceForm())
  const [pointForm, setPointForm] = useState<DevicePointForm>(emptyPointForm())
  const [detailTab, setDetailTab] = useState(initialTab)
  const [ingestionCheckResult, setIngestionCheckResult] = useState<string | null>(null)

  const areaTreeQuery = useQuery({
    queryKey: ["master-data", "areas", "tree"],
    queryFn: async () => (await request<{ items: AreaNode[] }>("/api/master-data/areas/tree")).data,
  })
  const deviceTypeTreeQuery = useQuery({
    queryKey: ["master-data", "device-types", "tree"],
    queryFn: async () => (await request<{ items: DeviceTypeNode[] }>("/api/master-data/device-types/tree")).data,
  })

  const flatAreas = useMemo(() => flattenAreaTree(areaTreeQuery.data?.items ?? []), [areaTreeQuery.data?.items])
  const flatTypes = useMemo(() => flattenDeviceTypeTree(deviceTypeTreeQuery.data?.items ?? []), [deviceTypeTreeQuery.data?.items])

  const devicesQuery = useQuery<PageResult<DeviceRow>>({
    queryKey: ["master-data", "devices", { selectedAreaFilter, selectedTypeFilter, statusFilter, keyword }],
    queryFn: async () =>
      requestPage<DeviceRow>("/api/master-data/devices", {
        area_id: selectedAreaFilter ?? undefined,
        device_type_id: selectedTypeFilter ?? undefined,
        status: statusFilter === "all" ? undefined : Number(statusFilter),
        search: keyword.trim() || undefined,
        limit: 100,
        offset: 0,
      }),
  })

  useEffect(() => {
    const first = devicesQuery.data?.items?.[0]
    if (!selectedDeviceId && first?.id) {
      setSelectedDeviceId(first.id)
    } else if (selectedDeviceId && !(devicesQuery.data?.items ?? []).some((item) => item.id === selectedDeviceId)) {
      setSelectedDeviceId(first?.id ?? null)
    }
  }, [devicesQuery.data?.items, selectedDeviceId])

  const detailQuery = useQuery({
    queryKey: ["master-data", "devices", "detail", selectedDeviceId],
    queryFn: async () => (await request<DeviceDetail>(`/api/master-data/devices/${selectedDeviceId}`)).data,
    enabled: selectedDeviceId !== null,
  })
  const mqttSourcesQuery = useQuery<PageResult<MqttSourceRow>>({
    queryKey: ["iot-ingestion", "mqtt-sources"],
    queryFn: async () => requestPage<MqttSourceRow>("/api/iot-ingestion/mqtt-sources", { limit: 100, offset: 0 }),
  })
  const mqttSubscriptionsQuery = useQuery<PageResult<MqttSubscriptionRow>>({
    queryKey: ["iot-ingestion", "mqtt-subscriptions"],
    queryFn: async () => requestPage<MqttSubscriptionRow>("/api/iot-ingestion/mqtt-subscriptions", { limit: 100, offset: 0 }),
  })
  const mqttBindingsQuery = useQuery<PageResult<MqttBindingRow>>({
    queryKey: ["iot-ingestion", "mqtt-bindings"],
    queryFn: async () => requestPage<MqttBindingRow>("/api/iot-ingestion/mqtt-device-bindings", { limit: 200, offset: 0 }),
  })
  const mqttMappingsQuery = useQuery<PageResult<MqttMappingRow>>({
    queryKey: ["iot-ingestion", "mqtt-mappings"],
    queryFn: async () => requestPage<MqttMappingRow>("/api/iot-ingestion/mqtt-point-mappings", { limit: 200, offset: 0 }),
  })
  const mqttMessagesQuery = useQuery<PageResult<MqttMessageRow>>({
    queryKey: ["iot-ingestion", "mqtt-messages"],
    queryFn: async () => requestPage<MqttMessageRow>("/api/iot-ingestion/mqtt-messages", { limit: 100, offset: 0 }),
  })

  const currentArea = useMemo(() => flatAreas.find((item) => item.id === selectedAreaFilter) ?? null, [flatAreas, selectedAreaFilter])
  const selectedDevice = detailQuery.data?.device
  const selectedPoints = detailQuery.data?.points ?? []
  const enabledPoints = selectedPoints.filter((point) => point.is_enabled !== false)
  const alarmEnabledPoints = selectedPoints.filter((point) => point.is_alarm_enabled === true)
  const mappedPoints = selectedPoints.filter((point) => Boolean(point.source_field?.trim()))
  const isMqttDevice = selectedDevice?.protocol?.toLowerCase() === "mqtt"
  const mqttBindings = useMemo(
    () => (mqttBindingsQuery.data?.items ?? []).filter((binding) => binding.equipment_id === selectedDevice?.id),
    [mqttBindingsQuery.data?.items, selectedDevice?.id],
  )
  const selectedMqttBinding = mqttBindings[0] ?? null
  const mqttMappings = useMemo(
    () => (mqttMappingsQuery.data?.items ?? []).filter((mapping) => mapping.binding_id === selectedMqttBinding?.id),
    [mqttMappingsQuery.data?.items, selectedMqttBinding?.id],
  )
  const selectedMqttSubscription = useMemo(
    () => (mqttSubscriptionsQuery.data?.items ?? []).find((subscription) => subscription.id === selectedMqttBinding?.subscription_id) ?? null,
    [mqttSubscriptionsQuery.data?.items, selectedMqttBinding?.subscription_id],
  )
  const selectedMqttSource = useMemo(
    () => (mqttSourcesQuery.data?.items ?? []).find((source) => source.id === selectedMqttSubscription?.source_id) ?? null,
    [mqttSourcesQuery.data?.items, selectedMqttSubscription?.source_id],
  )
  const selectedMqttMessages = useMemo(
    () =>
      (mqttMessagesQuery.data?.items ?? []).filter((message) => {
        if (!selectedMqttSubscription) return false
        return message.subscription_id === selectedMqttSubscription.id && message.source_id === selectedMqttSubscription.source_id
      }),
    [mqttMessagesQuery.data?.items, selectedMqttSubscription],
  )
  const latestMqttMessage = selectedMqttMessages[0] ?? null
  const canRunMqttTest = Boolean(currentUser?.isSuperuser)
  const ingestionIssues = useMemo(() => {
    if (!selectedDevice) return ["请先选择设备"]
    const issues: string[] = []
    if (!selectedDevice.protocol) issues.push("未选择采集协议")
    if (!selectedDevice.external_device_id) issues.push("未维护采集标识")
    if (selectedPoints.length === 0) issues.push("未配置测点")
    if (enabledPoints.length === 0) issues.push("没有启用测点")
    if (mappedPoints.length === 0) issues.push("启用前至少应配置一个来源字段")
    if (selectedDevice.protocol?.toLowerCase() === "mqtt") {
      if (mqttBindingsQuery.isError || mqttMappingsQuery.isError) issues.push("MQTT配置读取失败")
      if (!mqttBindingsQuery.isLoading && mqttBindings.length === 0) issues.push("未绑定MQTT表计")
      if (!mqttMappingsQuery.isLoading && mqttBindings.length > 0 && mqttMappings.length === 0) issues.push("未配置MQTT点位映射")
    }
    return issues
  }, [
    enabledPoints.length,
    mappedPoints.length,
    mqttBindings.length,
    mqttBindingsQuery.isError,
    mqttBindingsQuery.isLoading,
    mqttMappings.length,
    mqttMappingsQuery.isError,
    mqttMappingsQuery.isLoading,
    selectedDevice,
    selectedPoints.length,
  ])

  function openCreateDevice() {
    setEditingDevice(null)
    setDeviceForm({
      ...emptyDeviceForm(),
      area_id: currentArea && currentArea.code !== "ROOT" ? String(currentArea.id) : "",
      device_type_id: selectedTypeFilter ? String(selectedTypeFilter) : "",
    })
    setDialogOpen(true)
  }

  function validateIngestion() {
    setDetailTab("ingestion")
    if (ingestionIssues.length > 0) {
      const message = `接入配置待补充：${ingestionIssues.join("、")}`
      setIngestionCheckResult(message)
      toast.warning("接入配置待补充", { description: ingestionIssues.join("、") })
      return
    }
    const message = "接入配置具备进入监测的必要条件，可继续核对实时读数和告警规则。"
    setIngestionCheckResult(message)
    toast.success("接入配置校验通过")
  }

  function openEditDevice(device: DeviceRow) {
    setEditingDevice(device)
    setDeviceForm({
      code: device.code,
      name: device.name ?? "",
      area_id: device.area_id ? String(device.area_id) : "",
      device_type_id: device.device_type_id ? String(device.device_type_id) : "",
      parent_device_id: device.parent_device_id ? String(device.parent_device_id) : "",
      asset_code: device.asset_code ?? "",
      external_device_id: device.external_device_id ?? "",
      model: device.model ?? "",
      manufacturer: device.manufacturer ?? "",
      owner_department: device.owner_department ?? "",
      maintainer_name: device.maintainer_name ?? "",
      energy_type: device.energy_type ?? "",
      protocol: device.protocol ?? "http_yunji",
      status: String(device.status ?? 0),
      commissioning_status: device.commissioning_status ?? "active",
      location_desc: device.location_desc ?? "",
      remark: device.remark ?? "",
      is_enabled: boolValue(device.is_enabled),
    })
    setDialogOpen(true)
  }

  function openPointDialog(point?: DevicePointRow) {
    setEditingPoint(point ?? null)
    setDetailTab("points")
    setPointForm(
      point
        ? {
            point_code: point.point_code,
            point_name: point.point_name,
            unit: point.unit ?? "",
            value_type: point.value_type ?? "float",
            source_field: point.source_field ?? "",
            sampling_interval_seconds: point.sampling_interval_seconds ? String(point.sampling_interval_seconds) : "",
            is_enabled: boolValue(point.is_enabled),
            is_alarm_enabled: boolValue(point.is_alarm_enabled),
            upper_limit: point.upper_limit == null ? "" : String(point.upper_limit),
            lower_limit: point.lower_limit == null ? "" : String(point.lower_limit),
            remark: point.remark ?? "",
          }
        : emptyPointForm(),
    )
    setPointDialogOpen(true)
  }

  const saveDevice = useMutation({
    mutationFn: async () => {
      const payload = {
        code: deviceForm.code.trim(),
        name: deviceForm.name.trim(),
        area_id: Number(deviceForm.area_id),
        device_type_id: Number(deviceForm.device_type_id),
        parent_device_id: deviceForm.parent_device_id ? Number(deviceForm.parent_device_id) : null,
        asset_code: deviceForm.asset_code.trim() || null,
        external_device_id: deviceForm.external_device_id.trim() || null,
        model: deviceForm.model.trim() || null,
        manufacturer: deviceForm.manufacturer.trim() || null,
        owner_department: deviceForm.owner_department.trim() || null,
        maintainer_name: deviceForm.maintainer_name.trim() || null,
        energy_type: deviceForm.energy_type.trim() || null,
        protocol: deviceForm.protocol,
        status: Number(deviceForm.status),
        commissioning_status: deviceForm.commissioning_status,
        location_desc: deviceForm.location_desc.trim() || null,
        remark: deviceForm.remark.trim() || null,
        is_enabled: deviceForm.is_enabled === "true",
      }
      return request(editingDevice ? `/api/master-data/devices/${editingDevice.id}` : "/api/master-data/devices", {
        method: editingDevice ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: async () => {
      toast.success(editingDevice ? "设备已更新" : "设备已创建")
      setDialogOpen(false)
      await qc.invalidateQueries({ queryKey: ["master-data", "devices"] })
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const savePoint = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId) throw new Error("请先选择设备")
      const payload = {
        device_id: selectedDeviceId,
        point_code: pointForm.point_code.trim(),
        point_name: pointForm.point_name.trim(),
        unit: pointForm.unit.trim() || null,
        value_type: pointForm.value_type,
        source_field: pointForm.source_field.trim() || null,
        sampling_interval_seconds: pointForm.sampling_interval_seconds ? Number(pointForm.sampling_interval_seconds) : null,
        is_enabled: pointForm.is_enabled === "true",
        is_alarm_enabled: pointForm.is_alarm_enabled === "true",
        upper_limit: pointForm.upper_limit ? Number(pointForm.upper_limit) : null,
        lower_limit: pointForm.lower_limit ? Number(pointForm.lower_limit) : null,
        remark: pointForm.remark.trim() || null,
      }
      return request(editingPoint ? `/api/master-data/device-points/${editingPoint.id}` : "/api/master-data/device-points", {
        method: editingPoint ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: async () => {
      toast.success(editingPoint ? "测点已更新" : "测点已创建")
      setPointDialogOpen(false)
      await qc.invalidateQueries({ queryKey: ["master-data", "devices", "detail", selectedDeviceId] })
      await qc.invalidateQueries({ queryKey: ["master-data", "devices"] })
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const deletePoint = useMutation({
    mutationFn: async (pointId: number) => request(`/api/master-data/device-points/${pointId}`, { method: "DELETE" }),
    onSuccess: async () => {
      toast.success("测点已删除")
      await qc.invalidateQueries({ queryKey: ["master-data", "devices", "detail", selectedDeviceId] })
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })
  const testMqttIngestion = useMutation({
    mutationFn: async () => {
      if (!selectedMqttBinding) throw new Error("当前设备未绑定 MQTT 表计")
      const sourceTag = mqttMappings.find((mapping) => mapping.source_tag === "EPI")?.source_tag ?? mqttMappings[0]?.source_tag
      const result = await request<MqttTestResult>("/api/iot-ingestion/mqtt-test-messages", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          binding_id: selectedMqttBinding.id,
          source_tag: sourceTag,
          value: (860 + Math.random() * 40).toFixed(3),
        }),
      })
      return result.data
    },
    onSuccess: async (result) => {
      const reading = result.readings[0]
      setIngestionCheckResult(
        reading
          ? `MQTT测试报文已处理：${reading.point_name} ${reading.normalized_value ?? "-"} ${reading.unit ?? ""}`
          : `MQTT测试报文已处理，生成读数 ${result.reading_count} 条。`,
      )
      toast.success("MQTT接入测试完成")
      await qc.invalidateQueries({ queryKey: ["iot-ingestion", "mqtt-messages"] })
      await qc.invalidateQueries({ queryKey: ["master-data", "devices", "detail", selectedDeviceId] })
      await qc.invalidateQueries({ queryKey: ["iot-monitoring", "points"] })
    },
    onError: (error) => toast.error("MQTT接入测试失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title={title} />
      <PageSection>
        <AdminPanel title="设备接入主线" contentClassName="grid gap-3 md:grid-cols-4">
          <FlowStep title="1. 设备建档" detail="维护区域、类型、资产编码和采集标识" active={Boolean(selectedDevice)} />
          <FlowStep title="2. 协议配置" detail="选择 MQTT、Modbus、RTSP 或接口采集方式" active={Boolean(selectedDevice?.protocol)} />
          <FlowStep title="3. 测点映射" detail="维护来源字段、单位、采样周期和阈值" active={mappedPoints.length > 0} />
          <FlowStep title="4. 监测验证" detail="查看实时读数、质量状态和告警结果" active={enabledPoints.length > 0} />
        </AdminPanel>
      </PageSection>
      <PageSection>
        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_380px]">
          <AdminPanel
            title="筛选树"
            className="min-h-[760px]"
            actions={
              <Button size="sm" onClick={openCreateDevice}>
                <Plus className="mr-2 size-4" />
                新增设备
              </Button>
            }
            contentClassName="space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">区域</div>
                <Button variant="ghost" size="sm" onClick={() => setSelectedAreaFilter(null)}>
                  清除
                </Button>
              </div>
              {(areaTreeQuery.data?.items ?? []).map((node) => (
                <AreaTreeNode
                  key={node.id}
                  node={node}
                  selectedId={selectedAreaFilter}
                  expandedIds={expandedAreaIds}
                  onToggle={(nodeId) =>
                    setExpandedAreaIds((current) => {
                      const next = new Set(current)
                      if (next.has(nodeId)) next.delete(nodeId)
                      else next.add(nodeId)
                      return next
                    })
                  }
                  onSelect={(nodeId) => setSelectedAreaFilter(nodeId)}
                />
              ))}
            </div>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">设备类型</div>
                <Button variant="ghost" size="sm" onClick={() => setSelectedTypeFilter(null)}>
                  清除
                </Button>
              </div>
              {(deviceTypeTreeQuery.data?.items ?? []).map((node) => (
                <DeviceTypeTreeNode
                  key={node.id}
                  node={node}
                  selectedId={selectedTypeFilter}
                  expandedIds={expandedTypeIds}
                  onToggle={(nodeId) =>
                    setExpandedTypeIds((current) => {
                      const next = new Set(current)
                      if (next.has(nodeId)) next.delete(nodeId)
                      else next.add(nodeId)
                      return next
                    })
                  }
                  onSelect={setSelectedTypeFilter}
                />
              ))}
            </div>
          </AdminPanel>

          <AdminPanel title="设备列表" className="min-h-[760px]" actions={<Badge variant="secondary">{devicesQuery.data?.total ?? 0} 台</Badge>} contentClassName="space-y-3">
            <div className="grid gap-3 md:grid-cols-[1fr_160px]">
              <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索设备名称、编码、资产编码" />
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <AdminDataTable>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>区域</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">测点</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(devicesQuery.data?.items ?? []).length === 0 && <AdminTableStateRow colSpan={5}>暂无设备</AdminTableStateRow>}
                  {(devicesQuery.data?.items ?? []).map((device) => (
                    <TableRow key={device.id} className={cn("cursor-pointer", selectedDeviceId === device.id && "bg-primary/5")} onClick={() => setSelectedDeviceId(device.id)}>
                      <TableCell>
                        <div className="font-medium">{deviceLabel(device)}</div>
                        <div className="text-xs text-muted-foreground">{device.code}</div>
                      </TableCell>
                      <TableCell>{device.area_name || "-"}</TableCell>
                      <TableCell>{device.device_type?.name ?? "-"}</TableCell>
                      <TableCell>{device.status === 1 ? "故障" : "在线"}</TableCell>
                      <TableCell className="text-right">{device.point_count ?? 0}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>

          <AdminPanel
            title={detailQuery.data?.device ? deviceLabel(detailQuery.data.device) : "设备详情"}
            className="min-h-[760px]"
            actions={
              detailQuery.data?.device ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (detailQuery.data?.device) openEditDevice(detailQuery.data.device)
                  }}
                >
                  编辑
                </Button>
              ) : null
            }
          >
            {detailQuery.data?.device ? (
              <Tabs value={detailTab} onValueChange={(value) => setDetailTab(value as typeof detailTab)} className="space-y-4">
                <TabsList className="grid w-full grid-cols-5">
                  <TabsTrigger value="devices">基础</TabsTrigger>
                  <TabsTrigger value="types">结构</TabsTrigger>
                  <TabsTrigger value="points">测点</TabsTrigger>
                  <TabsTrigger value="ingestion">接入</TabsTrigger>
                  <TabsTrigger value="quality">质量</TabsTrigger>
                </TabsList>

                <TabsContent value="devices" className="space-y-3">
                  <DetailRow label="区域" value={detailQuery.data.device.area_name ?? "-"} />
                  <DetailRow label="设备类型" value={detailQuery.data.device.device_type?.name ?? "-"} />
                  <DetailRow label="父设备" value={deviceLabel(detailQuery.data.device.parent_device ?? undefined)} />
                  <DetailRow label="资产编码" value={detailQuery.data.device.asset_code ?? "-"} />
                  <DetailRow label="采集标识" value={detailQuery.data.device.external_device_id ?? "-"} />
                  <DetailRow label="位置说明" value={detailQuery.data.device.location_desc ?? "-"} />
                  <DetailRow label="厂家/型号" value={`${detailQuery.data.device.manufacturer ?? "-"} / ${detailQuery.data.device.model ?? "-"}`} />
                  <DetailRow label="负责人" value={detailQuery.data.device.maintainer_name ?? "-"} />
                  <DetailRow label="投运状态" value={detailQuery.data.device.commissioning_status ?? "-"} />
                  <DetailRow label="备注" value={detailQuery.data.device.remark ?? "-"} />
                </TabsContent>

                <TabsContent value="types" className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">子设备</div>
                    <Badge variant="secondary">{detailQuery.data.children.length}</Badge>
                  </div>
                  {detailQuery.data.children.length === 0 ? (
                    <div className="text-sm text-muted-foreground">暂无子设备</div>
                  ) : (
                    <div className="space-y-2">
                      {detailQuery.data.children.map((child) => (
                        <button
                          key={child.id}
                          type="button"
                          className="w-full rounded-md border border-border/70 p-3 text-left transition-colors hover:bg-accent/60"
                          onClick={() => setSelectedDeviceId(child.id)}
                        >
                          <div className="font-medium">{deviceLabel(child)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {child.device_type?.name ?? "-"} · {child.area_name ?? "-"}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="points" className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">测点</div>
                    <Button size="sm" onClick={() => openPointDialog()}>
                      <Plus className="mr-2 size-4" />
                      新增测点
                    </Button>
                  </div>
                  <AdminDataTable>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>编码</TableHead>
                          <TableHead>名称</TableHead>
                          <TableHead>类型</TableHead>
                          <TableHead className="text-right">操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailQuery.data.points.length === 0 && <AdminTableStateRow colSpan={4}>暂无测点</AdminTableStateRow>}
                        {detailQuery.data.points.map((point) => (
                          <TableRow key={point.id}>
                            <TableCell>{point.point_code}</TableCell>
                            <TableCell>{point.point_name}</TableCell>
                            <TableCell>
                              <div>{point.value_type ?? "-"}</div>
                              <div className="text-muted-foreground text-xs">{point.source_field || "未配置来源字段"}</div>
                            </TableCell>
                            <TableCell className="space-x-2 text-right">
                              <Button variant="outline" size="sm" onClick={() => openPointDialog(point)}>
                                编辑
                              </Button>
                              <Button variant="destructive" size="sm" onClick={() => deletePoint.mutate(point.id)} disabled={deletePoint.isPending}>
                                删除
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </AdminDataTable>
                </TabsContent>

                <TabsContent value="ingestion" className="space-y-4">
                  <MetricStrip className="md:grid-cols-2">
                    <SummaryMetric label="启用测点" value={String(enabledPoints.length)} />
                    <SummaryMetric label="告警测点" value={String(alarmEnabledPoints.length)} />
                    <SummaryMetric label="已映射来源字段" value={String(mappedPoints.length)} />
                    <SummaryMetric label="配置问题" value={String(ingestionIssues.length)} />
                  </MetricStrip>
                  <DetailCard title="采集配置">
                    <DetailRow label="采集协议" value={selectedDevice?.protocol ?? "-"} />
                    <DetailRow label="采集标识" value={selectedDevice?.external_device_id ?? "-"} />
                    <DetailRow label="能源类型" value={selectedDevice?.energy_type ?? "-"} />
                    <DetailRow label="启用状态" value={selectedDevice?.is_enabled === false ? "停用" : "启用"} />
                    <DetailRow label="投运状态" value={selectedDevice?.commissioning_status ?? "-"} />
                  </DetailCard>
                  <DetailCard title="MQTT接入">
                    {!isMqttDevice ? (
                      <div className="text-sm text-muted-foreground">当前设备未选择 MQTT 采集协议。</div>
                    ) : mqttBindingsQuery.isLoading || mqttMappingsQuery.isLoading || mqttSubscriptionsQuery.isLoading || mqttSourcesQuery.isLoading ? (
                      <div className="text-sm text-muted-foreground">正在读取接入配置...</div>
                    ) : selectedMqttBinding ? (
                      <div className="space-y-3">
                        <DetailRow
                          label="数据源"
                          value={selectedMqttSource ? `${selectedMqttSource.name}（${selectedMqttSource.broker_host}:${selectedMqttSource.broker_port ?? 1883}）` : "-"}
                        />
                        <DetailRow label="订阅主题" value={selectedMqttSubscription?.topic_filter ?? "-"} />
                        <DetailRow label="网关/表计" value={`${selectedMqttBinding.gateway_key} / ${selectedMqttBinding.meter_key}`} />
                        <DetailRow label="绑定状态" value={mqttIdentityStatus(selectedMqttBinding.identity_status)} />
                        <DetailRow
                          label="最近报文"
                          value={
                            latestMqttMessage
                              ? `${mqttMessageStatus(latestMqttMessage.status)} · ${formatDateTime(latestMqttMessage.processed_at || latestMqttMessage.received_at)}`
                              : "-"
                          }
                        />
                        <div className="space-y-2">
                          <div className="text-xs font-medium text-muted-foreground">点位映射</div>
                          {mqttMappings.length === 0 ? (
                            <div className="text-sm text-muted-foreground">暂无 MQTT 点位映射</div>
                          ) : (
                            mqttMappings.map((mapping) => (
                              <div key={mapping.id} className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2 text-sm">
                                <div>
                                  <div className="font-medium">{mapping.point_name || mapping.point_code}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {mapping.source_tag} {"->"} {mapping.point_code}
                                  </div>
                                </div>
                                <Badge variant={mapping.enabled === false ? "outline" : "secondary"}>{mapping.unit || "-"}</Badge>
                              </div>
                            ))
                          )}
                        </div>
                        {canRunMqttTest ? (
                          <Button size="sm" onClick={() => testMqttIngestion.mutate()} disabled={testMqttIngestion.isPending || mqttMappings.length === 0}>
                            {testMqttIngestion.isPending ? "测试中..." : "发送测试报文"}
                          </Button>
                        ) : (
                          <div className="text-xs text-muted-foreground">接入测试由系统管理员执行。</div>
                        )}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">当前设备尚未绑定 MQTT 表计。</div>
                    )}
                  </DetailCard>
                  <DetailCard title="接入校验">
                    {ingestionIssues.length === 0 ? (
                      <div className="text-sm">协议、采集标识、启用测点和来源字段已具备进入监测的必要条件。</div>
                    ) : (
                      <div className="space-y-2 text-sm">
                        {ingestionIssues.map((issue) => (
                          <div key={issue}>- {issue}</div>
                        ))}
                      </div>
                    )}
                    {ingestionCheckResult && <div className="rounded-md border border-border/70 bg-muted/35 px-3 py-2 text-sm">{ingestionCheckResult}</div>}
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={validateIngestion}>
                        校验配置
                      </Button>
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/data/point-monitoring">查看实时读数</Link>
                      </Button>
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/energy-carbon/monitor">进入监测中心</Link>
                      </Button>
                    </div>
                  </DetailCard>
                </TabsContent>

                <TabsContent value="quality" className="space-y-4">
                  <MetricStrip className="md:grid-cols-2">
                    <SummaryMetric label="测点总数" value={String(selectedPoints.length)} />
                    <SummaryMetric label="未启用测点" value={String(selectedPoints.length - enabledPoints.length)} />
                    <SummaryMetric label="未映射来源字段" value={String(selectedPoints.length - mappedPoints.length)} />
                    <SummaryMetric label="阈值测点" value={String(selectedPoints.filter((point) => point.upper_limit != null || point.lower_limit != null).length)} />
                  </MetricStrip>
                  <DetailCard title="质量检查项">
                    <div className="space-y-2 text-sm">
                      <QualityLine label="协议与采集标识" ok={Boolean(selectedDevice?.protocol && selectedDevice?.external_device_id)} />
                      <QualityLine label="测点启用" ok={enabledPoints.length > 0} />
                      <QualityLine label="来源字段映射" ok={mappedPoints.length > 0} />
                      <QualityLine label="告警阈值配置" ok={alarmEnabledPoints.length > 0} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/data/meter">查看电表汇总</Link>
                      </Button>
                      <Button size="sm" variant="outline" asChild>
                        <Link to="/energy-carbon/alerts">查看告警中心</Link>
                      </Button>
                    </div>
                  </DetailCard>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="text-sm text-muted-foreground">从中间列表选择设备后查看详情。</div>
            )}
          </AdminPanel>
        </div>
      </PageSection>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editingDevice ? "编辑设备" : "新增设备"}</DialogTitle>
            <DialogDescription className="sr-only">先选归属区域和设备类型，再补充结构与台账信息。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="设备编码">
              <Input value={deviceForm.code} onChange={(event) => setDeviceForm((state) => ({ ...state, code: event.target.value }))} />
            </Field>
            <Field label="设备名称">
              <Input value={deviceForm.name} onChange={(event) => setDeviceForm((state) => ({ ...state, name: event.target.value }))} />
            </Field>
            <Field label="所属区域">
              <Select value={deviceForm.area_id} onValueChange={(value) => setDeviceForm((state) => ({ ...state, area_id: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="选择区域" />
                </SelectTrigger>
                <SelectContent>
                  {flatAreas
                    .filter((item) => item.code !== "ROOT")
                    .map((area) => (
                      <SelectItem key={area.id} value={String(area.id)}>
                        {areaLabel(area)}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="设备类型">
              <Select value={deviceForm.device_type_id} onValueChange={(value) => setDeviceForm((state) => ({ ...state, device_type_id: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="选择设备类型" />
                </SelectTrigger>
                <SelectContent>
                  {flatTypes.map((deviceType) => (
                    <SelectItem key={deviceType.id} value={String(deviceType.id)}>
                      {deviceType.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="父设备">
              <Select
                value={deviceForm.parent_device_id || "none"}
                onValueChange={(value) => setDeviceForm((state) => ({ ...state, parent_device_id: value === "none" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">无</SelectItem>
                  {(devicesQuery.data?.items ?? [])
                    .filter((item) => item.id !== editingDevice?.id)
                    .map((device) => (
                      <SelectItem key={device.id} value={String(device.id)}>
                        {deviceLabel(device)}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="资产编码">
              <Input value={deviceForm.asset_code} onChange={(event) => setDeviceForm((state) => ({ ...state, asset_code: event.target.value }))} />
            </Field>
            <Field label="采集标识">
              <Input value={deviceForm.external_device_id} onChange={(event) => setDeviceForm((state) => ({ ...state, external_device_id: event.target.value }))} />
            </Field>
            <Field label="厂家">
              <Input value={deviceForm.manufacturer} onChange={(event) => setDeviceForm((state) => ({ ...state, manufacturer: event.target.value }))} />
            </Field>
            <Field label="型号">
              <Input value={deviceForm.model} onChange={(event) => setDeviceForm((state) => ({ ...state, model: event.target.value }))} />
            </Field>
            <Field label="归属部门">
              <Input value={deviceForm.owner_department} onChange={(event) => setDeviceForm((state) => ({ ...state, owner_department: event.target.value }))} />
            </Field>
            <Field label="维护负责人">
              <Input value={deviceForm.maintainer_name} onChange={(event) => setDeviceForm((state) => ({ ...state, maintainer_name: event.target.value }))} />
            </Field>
            <Field label="能源类型">
              <Input value={deviceForm.energy_type} onChange={(event) => setDeviceForm((state) => ({ ...state, energy_type: event.target.value }))} />
            </Field>
            <Field label="采集协议">
              <Select value={deviceForm.protocol} onValueChange={(value) => setDeviceForm((state) => ({ ...state, protocol: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROTOCOL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="在线状态">
              <Select value={deviceForm.status} onValueChange={(value) => setDeviceForm((state) => ({ ...state, status: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.filter((option) => option.value !== "all").map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="投运状态">
              <Select value={deviceForm.commissioning_status} onValueChange={(value) => setDeviceForm((state) => ({ ...state, commissioning_status: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COMMISSIONING_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="启用状态">
              <Select value={deviceForm.is_enabled} onValueChange={(value) => setDeviceForm((state) => ({ ...state, is_enabled: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENABLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="位置说明" className="sm:col-span-2">
              <Input value={deviceForm.location_desc} onChange={(event) => setDeviceForm((state) => ({ ...state, location_desc: event.target.value }))} />
            </Field>
            <Field label="备注" className="sm:col-span-2">
              <Textarea value={deviceForm.remark} onChange={(event) => setDeviceForm((state) => ({ ...state, remark: event.target.value }))} className="min-h-24" />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              取消
            </Button>
            <Button
              onClick={() => saveDevice.mutate()}
              disabled={saveDevice.isPending || !deviceForm.code.trim() || !deviceForm.name.trim() || !deviceForm.area_id || !deviceForm.device_type_id}
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pointDialogOpen} onOpenChange={setPointDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingPoint ? "编辑测点" : "新增测点"}</DialogTitle>
            <DialogDescription className="sr-only">测点直接挂在当前选中设备下维护，不再手填设备 ID。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="测点编码">
              <Input value={pointForm.point_code} onChange={(event) => setPointForm((state) => ({ ...state, point_code: event.target.value }))} />
            </Field>
            <Field label="测点名称">
              <Input value={pointForm.point_name} onChange={(event) => setPointForm((state) => ({ ...state, point_name: event.target.value }))} />
            </Field>
            <Field label="数值类型">
              <Select value={pointForm.value_type} onValueChange={(value) => setPointForm((state) => ({ ...state, value_type: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VALUE_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="单位">
              <Input value={pointForm.unit} onChange={(event) => setPointForm((state) => ({ ...state, unit: event.target.value }))} />
            </Field>
            <Field label="来源字段">
              <Input value={pointForm.source_field} onChange={(event) => setPointForm((state) => ({ ...state, source_field: event.target.value }))} />
            </Field>
            <Field label="采样周期">
              <Input
                type="number"
                value={pointForm.sampling_interval_seconds}
                onChange={(event) => setPointForm((state) => ({ ...state, sampling_interval_seconds: event.target.value }))}
              />
            </Field>
            <Field label="启用">
              <Select value={pointForm.is_enabled} onValueChange={(value) => setPointForm((state) => ({ ...state, is_enabled: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENABLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="告警启用">
              <Select value={pointForm.is_alarm_enabled} onValueChange={(value) => setPointForm((state) => ({ ...state, is_alarm_enabled: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENABLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="上限">
              <Input type="number" value={pointForm.upper_limit} onChange={(event) => setPointForm((state) => ({ ...state, upper_limit: event.target.value }))} />
            </Field>
            <Field label="下限">
              <Input type="number" value={pointForm.lower_limit} onChange={(event) => setPointForm((state) => ({ ...state, lower_limit: event.target.value }))} />
            </Field>
            <Field label="备注" className="sm:col-span-2">
              <Textarea value={pointForm.remark} onChange={(event) => setPointForm((state) => ({ ...state, remark: event.target.value }))} className="min-h-24" />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPointDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={() => savePoint.mutate()} disabled={savePoint.isPending || !pointForm.point_code.trim() || !pointForm.point_name.trim()}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}

export function TerminalsWorkbenchPage() {
  return <DeviceWorkbench title="设备台账" initialTab="devices" />
}

export function DeviceTypesWorkbenchPage() {
  return <DeviceWorkbench title="设备台账" initialTab="types" />
}

export function DevicePointsWorkbenchPage() {
  return <DeviceWorkbench title="设备台账" initialTab="points" />
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return <MetricTile label={label} value={value} />
}

function DetailCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border/70 p-4">
      <div className="mb-3 text-sm font-medium">{title}</div>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 text-sm sm:grid-cols-[96px_1fr]">
      <div className="text-muted-foreground">{label}</div>
      <div>{value}</div>
    </div>
  )
}

function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-2", className)}>
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function FlowStep({ title, detail, active }: { title: string; detail: string; active: boolean }) {
  return (
    <div className={cn("rounded-md border px-3 py-3", active ? "border-primary/30 bg-primary/5" : "border-border/70 bg-background")}>
      <div className="font-medium text-sm">{title}</div>
      <div className="mt-1 text-muted-foreground text-xs leading-5">{detail}</div>
    </div>
  )
}

function QualityLine({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <Badge variant={ok ? "secondary" : "destructive"}>{ok ? "通过" : "待处理"}</Badge>
    </div>
  )
}
