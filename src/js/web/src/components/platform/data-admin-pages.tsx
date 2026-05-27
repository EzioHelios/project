import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"

type ApiResponse<T> = { code: number; msg?: string; data: T }
export type PageResult<T> = { items: T[]; total: number; limit: number; offset: number }
type Row = Record<string, unknown> & { id?: number | string }

type Option = { label: string; value: string }
type Field = {
  name: string
  label: string
  type?: "text" | "number" | "date" | "datetime" | "select" | "textarea" | "json" | "boolean"
  required?: boolean
  options?: Option[]
}
type Column = { key: string; label: string; align?: "right"; render?: (row: Row) => string }

const emptyPage: PageResult<Row> = { items: [], total: 0, limit: 20, offset: 0 }

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "boolean") return value ? "是" : "否"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

async function request<T>(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  if ("code" in raw && "data" in raw) return raw as ApiResponse<T>
  if ("items" in raw) {
    return { code: 200, msg: "获取成功", data: raw.items } as ApiResponse<T>
  }
  return { code: 200, msg: "操作成功", data: raw } as ApiResponse<T>
}

export function normalizePageResponse<T>(raw: unknown): PageResult<T> {
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>
    if (Array.isArray(obj.items)) {
      return {
        items: obj.items as T[],
        total: Number(obj.total ?? obj.items.length),
        limit: Number(obj.limit ?? obj.items.length ?? 20),
        offset: Number(obj.offset ?? 0),
      }
    }
    if ("code" in obj && "data" in obj) {
      const data = obj.data
      if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).items)) return normalizePageResponse<T>(data)
      if (Array.isArray(data)) return { items: data as T[], total: data.length, limit: data.length || 20, offset: 0 }
    }
  }
  if (Array.isArray(raw)) return { items: raw as T[], total: raw.length, limit: raw.length || 20, offset: 0 }
  return { items: [], total: 0, limit: 20, offset: 0 }
}

export async function requestPage<T>(endpoint: string, params: Record<string, string | number | boolean | null | undefined> = {}) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") qs.set(key, String(value))
  }
  const res = await fetch(`${endpoint}?${qs.toString()}`)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  return normalizePageResponse<T>(raw)
}

function usePagedResource<T extends Row>({
  endpoint,
  queryKey,
  keyword,
  extraParams,
}: {
  endpoint: string
  queryKey: string[]
  keyword: string
  extraParams?: Record<string, string | number | boolean | null | undefined>
}) {
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const query = useQuery<PageResult<T>>({
    queryKey: [...queryKey, { keyword, pageIndex, pageSize, extraParams }],
    queryFn: async () =>
      requestPage<T>(endpoint, {
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
        ...extraParams,
      }),
    placeholderData: (previous) => previous ?? ({ ...emptyPage, limit: pageSize } as PageResult<T>),
  })
  return { query, pageIndex, setPageIndex, pageSize, setPageSize }
}

export function PaginationBar({
  page,
  pageIndex,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  page: PageResult<unknown>
  pageIndex: number
  pageSize: number
  onPageChange: (pageIndex: number) => void
  onPageSizeChange: (pageSize: number) => void
}) {
  const pageCount = Math.max(1, Math.ceil(page.total / pageSize))
  const start = page.total === 0 ? 0 : page.offset + 1
  const end = Math.min(page.offset + page.items.length, page.total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-sm">
      <div className="text-muted-foreground">
        {start}-{end} / 共 {page.total} 条
      </div>
      <div className="flex items-center gap-2">
        <Select value={String(pageSize)} onValueChange={(value) => onPageSizeChange(Number(value))}>
          <SelectTrigger className="w-[104px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[20, 50, 100].map((size) => (
              <SelectItem key={size} value={String(size)}>
                {size} 条/页
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={() => onPageChange(Math.max(0, pageIndex - 1))} disabled={pageIndex === 0}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="w-20 text-center text-muted-foreground">
          {pageIndex + 1} / {pageCount}
        </div>
        <Button variant="outline" size="sm" onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))} disabled={pageIndex + 1 >= pageCount}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function toPayload(fields: Field[], form: Record<string, string>) {
  const payload: Record<string, unknown> = {}
  const numericNames = new Set(["area_id", "sector_id", "category", "status", "trip_state", "sort_index", "event_type"])
  for (const field of fields) {
    const raw = form[field.name]
    if (field.type === "number" || numericNames.has(field.name)) payload[field.name] = raw === "" ? null : Number(raw)
    else if (field.type === "boolean") payload[field.name] = raw === "true"
    else if (field.type === "json") {
      payload[field.name] = raw.trim() ? JSON.parse(raw) : null
    } else payload[field.name] = raw === "" ? null : raw
  }
  return payload
}

function makeInitial(fields: Field[], row?: Row) {
  return Object.fromEntries(
    fields.map((field) => {
      const value = row?.[field.name]
      if (field.type === "json") return [field.name, value ? JSON.stringify(value, null, 2) : ""]
      if (field.type === "boolean") return [field.name, value === false ? "false" : "true"]
      return [field.name, value === null || value === undefined ? "" : String(value)]
    }),
  )
}

function FieldControl({ field, value, onChange }: { field: Field; value: string; onChange: (value: string) => void }) {
  if (field.type === "select" || field.type === "boolean") {
    const options =
      field.type === "boolean"
        ? [
            { label: "启用", value: "true" },
            { label: "停用", value: "false" },
          ]
        : (field.options ?? [])
    return (
      <Select value={value || options[0]?.value} onValueChange={onChange}>
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
    )
  }
  if (field.type === "textarea" || field.type === "json") {
    return <Textarea value={value} onChange={(event) => onChange(event.target.value)} className="min-h-24 font-mono text-xs" />
  }
  return (
    <Input
      type={field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "datetime" ? "datetime-local" : "text"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function RowDetail({ row, title, onClose }: { row: Row | null; title: string; onClose: () => void }) {
  return (
    <Sheet open={Boolean(row)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>查看完整字段与关联信息。</SheetDescription>
        </SheetHeader>
        <div className="space-y-2 px-4 pb-6">
          {row &&
            Object.entries(row).map(([key, value]) => (
              <div key={key} className="grid grid-cols-[120px_1fr] gap-3 rounded-md border px-3 py-2 text-sm">
                <div className="text-muted-foreground">{key}</div>
                <div className="min-w-0 break-all">{display(value)}</div>
              </div>
            ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function CrudDataPage({
  eyebrow = "数据管理",
  title,
  description,
  endpoint,
  queryKey,
  columns,
  fields,
  searchPlaceholder = "搜索关键字",
}: {
  eyebrow?: string
  title: string
  description: string
  endpoint: string
  queryKey: string[]
  columns: Column[]
  fields: Field[]
  searchPlaceholder?: string
}) {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Row | null>(null)
  const [detail, setDetail] = useState<Row | null>(null)
  const [form, setForm] = useState<Record<string, string>>(makeInitial(fields))
  const { query: listQuery, pageIndex, setPageIndex, pageSize, setPageSize } = usePagedResource<Row>({ endpoint, queryKey, keyword: appliedKeyword })

  function startCreate() {
    setEditing(null)
    setForm(makeInitial(fields))
  }

  function startEdit(row: Row) {
    setEditing(row)
    setForm(makeInitial(fields, row))
    setOpen(true)
  }

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload = toPayload(fields, form)
      return request<Row>(editing?.id ? `${endpoint}/${editing.id}` : endpoint, {
        method: editing?.id ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: async () => {
      toast.success(editing ? "更新成功" : "新增成功")
      setOpen(false)
      setEditing(null)
      setForm(makeInitial(fields))
      if (!editing) setPageIndex(0)
      await qc.invalidateQueries({ queryKey })
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteMut = useMutation({
    mutationFn: async (id: number | string) => request(`${endpoint}/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      toast.success("删除成功")
      await qc.invalidateQueries({ queryKey })
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <PageSection>
        <Card>
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>{title}列表</CardTitle>
              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button onClick={startCreate}>新增</Button>
                </DialogTrigger>
                <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>
                      {editing ? "编辑" : "新增"}
                      {title}
                    </DialogTitle>
                  </DialogHeader>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {fields.map((field) => (
                      <div key={field.name} className={field.type === "textarea" || field.type === "json" ? "grid gap-2 sm:col-span-2" : "grid gap-2"}>
                        <Label>{field.label}</Label>
                        <FieldControl field={field} value={form[field.name] ?? ""} onChange={(value) => setForm((state) => ({ ...state, [field.name]: value }))} />
                      </div>
                    ))}
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setOpen(false)}>
                      取消
                    </Button>
                    <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || fields.some((field) => field.required && !form[field.name]?.trim())}>
                      保存
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
            <div className="flex flex-wrap gap-3">
              <Input
                className="min-w-[260px] flex-1"
                value={keyword}
                onChange={(event) => {
                  setKeyword(event.target.value)
                }}
                placeholder={searchPlaceholder}
              />
              <Button
                variant="secondary"
                onClick={() => {
                  setAppliedKeyword(keyword)
                  setPageIndex(0)
                  if (keyword === appliedKeyword) void listQuery.refetch()
                }}
                disabled={listQuery.isFetching}
              >
                查询
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((column) => (
                    <TableHead key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                      {column.label}
                    </TableHead>
                  ))}
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(listQuery.data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={columns.length + 1} className="h-24 text-center text-muted-foreground">
                      暂无数据
                    </TableCell>
                  </TableRow>
                )}
                {(listQuery.data?.items ?? []).map((row) => (
                  <TableRow key={String(row.id)}>
                    {columns.map((column) => (
                      <TableCell key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                        {column.render ? column.render(row) : display(row[column.key])}
                      </TableCell>
                    ))}
                    <TableCell className="space-x-2 text-right">
                      <Button variant="secondary" size="sm" onClick={() => setDetail(row)}>
                        详情
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => startEdit(row)}>
                        编辑
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => row.id && deleteMut.mutate(row.id)} disabled={deleteMut.isPending}>
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <PaginationBar page={listQuery.data ?? emptyPage} pageIndex={pageIndex} pageSize={pageSize} onPageChange={setPageIndex} onPageSizeChange={setPageSize} />
          </CardContent>
        </Card>
      </PageSection>
      <RowDetail row={detail} title={`${title}详情`} onClose={() => setDetail(null)} />
    </PageContainer>
  )
}

export function RolesPage() {
  const fields: Field[] = [{ name: "name", label: "角色名称", required: true }]
  return (
    <CrudDataPage
      eyebrow="权限管理"
      title="角色管理"
      description="维护系统角色，并通过后端默认角色保护规则避免误删关键角色。"
      endpoint="/api/roles"
      queryKey={["roles", "manage"]}
      columns={[
        { key: "name", label: "角色名称" },
        { key: "slug", label: "标识" },
        { key: "createdAt", label: "创建时间" },
      ]}
      fields={fields}
    />
  )
}

export function EnergyStoragePage() {
  const qc = useQueryClient()
  const fields = useMemo<Field[]>(
    () => [
      { name: "cn_total", label: "总容量", type: "number", required: true },
      { name: "ratio_total", label: "总比例", type: "number", required: true },
      { name: "cn1", label: "储能单元1容量", type: "number", required: true },
      { name: "ratio1", label: "储能单元1比例", type: "number", required: true },
      { name: "cn2", label: "储能单元2容量", type: "number", required: true },
      { name: "ratio2", label: "储能单元2比例", type: "number", required: true },
    ],
    [],
  )
  const query = useQuery<ApiResponse<Row | null>>({
    queryKey: ["data", "energy-storage"],
    queryFn: async () => request<Row | null>("/api/data/energy-storage"),
  })
  const [form, setForm] = useState<Record<string, string>>({})
  const setting = query.data?.data
  useEffect(() => {
    setForm(makeInitial(fields, setting ?? undefined))
  }, [fields, setting])
  const save = useMutation({
    mutationFn: async () =>
      request<Row>("/api/data/energy-storage", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(toPayload(fields, form)) }),
    onSuccess: async () => {
      toast.success("保存成功")
      await qc.invalidateQueries({ queryKey: ["data", "energy-storage"] })
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="数据管理" title="储能数值设置" description="维护储能容量与比例参数，供电能监测大屏读取。" />
      <PageSection>
        <Card>
          <CardHeader>
            <CardTitle>储能参数</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {fields.map((field) => (
              <div key={field.name} className="grid gap-2">
                <Label>{field.label}</Label>
                <FieldControl field={field} value={form[field.name] ?? ""} onChange={(value) => setForm((state) => ({ ...state, [field.name]: value }))} />
              </div>
            ))}
            <div className="sm:col-span-2">
              <Button onClick={() => save.mutate()} disabled={save.isPending}>
                保存设置
              </Button>
            </div>
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}

export function MonitorAreaPage() {
  const fields: Field[] = [
    { name: "code", label: "区域编码", required: true },
    { name: "name", label: "区域名称", required: true },
    { name: "area", label: "面积/区域" },
    { name: "area_id", label: "区域ID", type: "number" },
    { name: "is_enable", label: "启用状态", type: "boolean" },
    { name: "description", label: "描述", type: "textarea" },
  ]
  return (
    <CrudDataPage
      title="监测区域"
      description="维护监测区域主数据，并在详情中查看照片路径和关联设备数量。"
      endpoint="/api/data/monitor-sectors"
      queryKey={["data", "monitor-sectors"]}
      columns={[
        { key: "code", label: "编码" },
        { key: "name", label: "名称" },
        { key: "area", label: "区域" },
        { key: "equipment_count", label: "关联设备", align: "right" },
        { key: "is_enable", label: "状态", render: (row) => (row.is_enable === false ? "停用" : "启用") },
      ]}
      fields={fields}
    />
  )
}

export function TerminalsPage() {
  const deviceTypeOptions = [
    { label: "电表", value: "1" },
    { label: "光伏逆变器", value: "2" },
    { label: "储能 BMS", value: "3" },
    { label: "充电桩", value: "4" },
    { label: "叉车", value: "5" },
    { label: "起重机", value: "6" },
    { label: "衡器设备", value: "7" },
    { label: "自动化及辅助设备", value: "8" },
    { label: "摄像头", value: "9" },
  ]
  const fields: Field[] = [
    { name: "code", label: "设备编码", required: true },
    { name: "name", label: "设备名称", required: true },
    { name: "external_device_id", label: "采集设备标识" },
    { name: "asset_code", label: "资产编码/牌照" },
    {
      name: "device_type_id",
      label: "设备类型",
      type: "select",
      options: deviceTypeOptions,
    },
    { name: "sector_id", label: "区域ID", type: "number" },
    { name: "warehouse_name", label: "所属仓库" },
    { name: "warehouse_code", label: "仓库编码" },
    { name: "model", label: "规格型号" },
    { name: "manufacturer", label: "生产厂家" },
    { name: "owner_unit", label: "产权单位" },
    { name: "energy_type", label: "能源类型" },
    { name: "rated_power_kw", label: "额定功率(kW)", type: "number" },
    { name: "network_env", label: "网络环境" },
    { name: "data_acquisition_method", label: "采集方式" },
    { name: "running_status", label: "运行状态" },
    { name: "supplier", label: "供应商" },
    {
      name: "protocol",
      label: "采集协议",
      type: "select",
      options: [
        { label: "云集 HTTP", value: "http_yunji" },
        { label: "MQTT", value: "mqtt" },
        { label: "Modbus", value: "modbus" },
      ],
    },
    {
      name: "status",
      label: "在线状态",
      type: "select",
      options: [
        { label: "在线", value: "0" },
        { label: "故障", value: "1" },
      ],
    },
    {
      name: "trip_state",
      label: "开关状态",
      type: "select",
      options: [
        { label: "合闸", value: "0" },
        { label: "跳闸", value: "1" },
      ],
    },
    { name: "location", label: "安装位置" },
    { name: "install_time", label: "安装时间", type: "date" },
    { name: "last_inspection_at", label: "最近年检时间", type: "date" },
    { name: "inspection_due_at", label: "下次年检时间", type: "date" },
    { name: "registration_code", label: "登记证编号" },
    { name: "remark", label: "备注", type: "textarea" },
    { name: "sort_index", label: "排序", type: "number" },
    { name: "is_enable", label: "启用状态", type: "boolean" },
  ]
  return (
    <CrudDataPage
      title="监控终端"
      description="维护设备主档、采集配置和基础台账信息。"
      endpoint="/api/data/monitor-equipments"
      queryKey={["data", "monitor-equipments"]}
      columns={[
        { key: "code", label: "编码" },
        { key: "name", label: "名称" },
        { key: "external_device_id", label: "采集标识" },
        { key: "warehouse_name", label: "仓库" },
        { key: "sector_name", label: "区域" },
        { key: "device_type_name", label: "类型" },
        { key: "asset_code", label: "资产编码" },
        { key: "status", label: "状态", render: (row) => (Number(row.status) === 1 ? "故障" : "在线") },
      ]}
      fields={fields}
    />
  )
}

export function DeviceTypesPage() {
  return (
    <CrudDataPage
      title="设备类型"
      description="维护设备分类和默认能力模板。"
      endpoint="/api/data/device-types"
      queryKey={["data", "device-types"]}
      columns={[
        { key: "code", label: "类型编码" },
        { key: "name", label: "类型名称" },
        { key: "energy_type", label: "默认能源类型" },
        { key: "is_energy_device", label: "能碳设备", render: (row) => (row.is_energy_device ? "是" : "否") },
        { key: "is_special_equipment", label: "特种设备", render: (row) => (row.is_special_equipment ? "是" : "否") },
      ]}
      fields={[
        { name: "code", label: "类型编码", required: true },
        { name: "name", label: "类型名称", required: true },
        { name: "parent_code", label: "父级编码" },
        { name: "energy_type", label: "默认能源类型" },
        { name: "default_protocol", label: "默认协议" },
        { name: "is_energy_device", label: "能碳设备", type: "boolean" },
        { name: "is_special_equipment", label: "特种设备", type: "boolean" },
        { name: "is_enabled", label: "启用状态", type: "boolean" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

export function DevicePointsPage() {
  return (
    <CrudDataPage
      title="设备测点"
      description="维护设备测点定义和基础告警阈值。"
      endpoint="/api/data/device-points"
      queryKey={["data", "device-points"]}
      columns={[
        { key: "device_name", label: "设备" },
        { key: "point_code", label: "测点编码" },
        { key: "point_name", label: "测点名称" },
        { key: "unit", label: "单位" },
        { key: "value_type", label: "值类型" },
        { key: "is_alarm_enabled", label: "告警", render: (row) => (row.is_alarm_enabled ? "启用" : "关闭") },
      ]}
      fields={[
        { name: "device_id", label: "设备ID", type: "number", required: true },
        { name: "point_code", label: "测点编码", required: true },
        { name: "point_name", label: "测点名称", required: true },
        { name: "unit", label: "单位" },
        {
          name: "value_type",
          label: "值类型",
          type: "select",
          options: [
            { label: "浮点数", value: "float" },
            { label: "整数", value: "int" },
            { label: "布尔", value: "bool" },
            { label: "字符串", value: "string" },
            { label: "枚举", value: "enum" },
          ],
        },
        { name: "source_field", label: "来源字段" },
        { name: "sampling_interval_seconds", label: "采样周期(秒)", type: "number" },
        { name: "is_enabled", label: "启用", type: "boolean" },
        { name: "is_alarm_enabled", label: "告警启用", type: "boolean" },
        { name: "upper_limit", label: "上限", type: "number" },
        { name: "lower_limit", label: "下限", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

export function VideoPage() {
  return (
    <CrudDataPage
      title="视频监控"
      description="维护视频点位台账，并保留视频预警事件入口。"
      endpoint="/api/data/video-monitors"
      queryKey={["data", "video-monitors"]}
      columns={[
        { key: "location", label: "位置" },
        { key: "f_area", label: "区域" },
        { key: "ip_address", label: "IP" },
        { key: "brand", label: "品牌" },
        { key: "status", label: "状态", render: (row) => (Number(row.status) === 1 ? "故障" : "在线") },
      ]}
      fields={[
        { name: "location", label: "位置", required: true },
        { name: "f_area", label: "所属区域" },
        { name: "f_area_type", label: "区域类型" },
        { name: "video_url", label: "视频地址" },
        {
          name: "status",
          label: "状态",
          type: "select",
          options: [
            { label: "在线", value: "0" },
            { label: "故障", value: "1" },
          ],
        },
        { name: "ip_address", label: "IP地址" },
        { name: "brand", label: "品牌" },
        { name: "b_model", label: "型号" },
        { name: "install_time", label: "安装时间" },
      ]}
    />
  )
}

export function WarningRulesPage() {
  return (
    <CrudDataPage
      title="预警规则"
      description="维护设备、用电、发电和碳排放异常规则，阈值使用结构化 JSON。"
      endpoint="/api/data/warning-rules"
      queryKey={["data", "warning-rules"]}
      columns={[
        { key: "name", label: "规则名称" },
        { key: "alarm_name", label: "告警名称" },
        { key: "event_type", label: "事件类型" },
        { key: "equipment_id", label: "设备ID" },
        { key: "point_code", label: "测点编码" },
        { key: "table_name", label: "来源表/视图" },
        { key: "sector_id", label: "区域ID" },
      ]}
      fields={[
        { name: "name", label: "规则名称", required: true },
        { name: "alarm_code", label: "告警编码" },
        { name: "alarm_name", label: "告警名称" },
        {
          name: "alarm_level",
          label: "告警等级",
          type: "select",
          options: [
            { label: "提示", value: "info" },
            { label: "预警", value: "warning" },
            { label: "严重", value: "critical" },
          ],
        },
        {
          name: "event_type",
          label: "事件类型",
          type: "select",
          options: [
            { label: "设备故障", value: "1" },
            { label: "用电异常", value: "2" },
            { label: "发电异常", value: "3" },
            { label: "碳排放异常", value: "4" },
          ],
        },
        { name: "sector_id", label: "区域ID", type: "number" },
        { name: "equipment_id", label: "设备ID", type: "number" },
        { name: "point_code", label: "测点编码" },
        { name: "table_name", label: "来源表/视图" },
        { name: "is_enabled", label: "启用", type: "boolean" },
        { name: "range_val", label: "阈值 JSON", type: "json" },
        { name: "description", label: "说明", type: "textarea" },
      ]}
    />
  )
}

export function ApiKeyMappingPage() {
  return (
    <CrudDataPage
      title="接口结果key映射"
      description="维护大屏接口字段的中文展示名称。"
      endpoint="/api/data/api-result-key-mappings"
      queryKey={["data", "api-result-key-mappings"]}
      columns={[
        { key: "key_name", label: "字段 Key" },
        { key: "cn_name", label: "中文名" },
      ]}
      fields={[
        { name: "key_name", label: "字段 Key", required: true },
        { name: "cn_name", label: "中文名", required: true },
      ]}
    />
  )
}

export function EventWorkbenchPage({ title, endpoint, queryKey, video = false }: { title: string; endpoint: string; queryKey: string[]; video?: boolean }) {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [handled, setHandled] = useState("all")
  const eventParams = useMemo(() => ({ is_handle: handled === "all" ? undefined : handled }), [handled])
  const { query, pageIndex, setPageIndex, pageSize, setPageSize } = usePagedResource<Row>({ endpoint, queryKey, keyword: appliedKeyword, extraParams: eventParams })
  const unhandledIds = (query.data?.items ?? [])
    .filter((row) => row.is_handle !== true)
    .map((row) => row.id)
    .filter(Boolean)
  const handleOne = useMutation({
    mutationFn: async (id: number | string) => request(`${endpoint}/${id}/handle`, { method: "POST" }),
    onSuccess: async () => {
      toast.success("已处理")
      await qc.invalidateQueries({ queryKey })
    },
  })
  const handleBatch = useMutation({
    mutationFn: async () => request(`${endpoint}/handle-batch`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ ids: unhandledIds }) }),
    onSuccess: async () => {
      toast.success("批量处理完成")
      await qc.invalidateQueries({ queryKey })
    },
  })
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="数据管理" title={title} description={video ? "查看视频识别预警事件并完成处理闭环。" : "查看规则触发的预警事件并完成处理闭环。"} />
      <PageSection>
        <Card>
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>事件列表</CardTitle>
              <Button onClick={() => handleBatch.mutate()} disabled={unhandledIds.length === 0 || handleBatch.isPending}>
                处理当前未处理
              </Button>
            </div>
            <div className="flex flex-wrap gap-3">
              <Input
                className="min-w-[260px] flex-1"
                value={keyword}
                onChange={(event) => {
                  setKeyword(event.target.value)
                }}
                placeholder="搜索事件说明"
              />
              <Select
                value={handled}
                onValueChange={(value) => {
                  setHandled(value)
                  setPageIndex(0)
                }}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="false">未处理</SelectItem>
                  <SelectItem value="true">已处理</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="secondary"
                onClick={() => {
                  setAppliedKeyword(keyword)
                  setPageIndex(0)
                  if (keyword === appliedKeyword) void query.refetch()
                }}
                disabled={query.isFetching}
              >
                查询
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>类型</TableHead>
                  <TableHead>说明</TableHead>
                  <TableHead>时间</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(query.data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                      暂无事件
                    </TableCell>
                  </TableRow>
                )}
                {(query.data?.items ?? []).map((row) => (
                  <TableRow key={String(row.id)}>
                    <TableCell>{display(row.alarm_name) || display(row.event_type)}</TableCell>
                    <TableCell className="max-w-[520px] whitespace-normal">{display(row.event_desc)}</TableCell>
                    <TableCell>{display(row.event_time)}</TableCell>
                    <TableCell>
                      <Badge variant={row.status === "resolved" || row.is_handle ? "secondary" : row.alarm_level === "critical" ? "destructive" : "outline"}>
                        {display(row.status) || (row.is_handle ? "resolved" : "open")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="secondary" onClick={() => row.id && handleOne.mutate(row.id)} disabled={row.is_handle === true || row.status === "resolved" || handleOne.isPending}>
                        处理
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <PaginationBar page={query.data ?? emptyPage} pageIndex={pageIndex} pageSize={pageSize} onPageChange={setPageIndex} onPageSizeChange={setPageSize} />
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}

export function ReadonlyLedgerPage({
  title,
  description,
  endpoint,
  queryKey,
  columns,
}: {
  title: string
  description: string
  endpoint: string
  queryKey: string[]
  columns: Column[]
}) {
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [detail, setDetail] = useState<Row | null>(null)
  const { query, pageIndex, setPageIndex, pageSize, setPageSize } = usePagedResource<Row>({ endpoint, queryKey, keyword: appliedKeyword })
  const items = query.data?.items ?? []
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="数据管理" title={title} description={description} />
      <PageSection>
        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>{title}台账</CardTitle>
            <div className="flex flex-wrap gap-3">
              <Input
                className="min-w-[260px] flex-1"
                value={keyword}
                onChange={(event) => {
                  setKeyword(event.target.value)
                }}
                placeholder="搜索关键字"
              />
              <Button
                variant="secondary"
                onClick={() => {
                  setAppliedKeyword(keyword)
                  setPageIndex(0)
                  if (keyword === appliedKeyword) void query.refetch()
                }}
                disabled={query.isFetching}
              >
                查询
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((column) => (
                    <TableHead key={column.key}>{column.label}</TableHead>
                  ))}
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={columns.length + 1} className="h-24 text-center text-muted-foreground">
                      暂无数据
                    </TableCell>
                  </TableRow>
                )}
                {items.map((row) => (
                  <TableRow key={String(row.id)}>
                    {columns.map((column) => (
                      <TableCell key={column.key}>{column.render ? column.render(row) : display(row[column.key])}</TableCell>
                    ))}
                    <TableCell className="text-right">
                      <Button size="sm" variant="secondary" onClick={() => setDetail(row)}>
                        详情
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <PaginationBar page={query.data ?? emptyPage} pageIndex={pageIndex} pageSize={pageSize} onPageChange={setPageIndex} onPageSizeChange={setPageSize} />
          </CardContent>
        </Card>
      </PageSection>
      <RowDetail row={detail} title={`${title}详情`} onClose={() => setDetail(null)} />
    </PageContainer>
  )
}

export function TasksPage({ mode }: { mode: "interval" | "crontab" | "schedules" }) {
  const query = useQuery<ApiResponse<{ name: string; tasks: Row[]; scheduled_tasks: Row[] }[]>>({
    queryKey: ["system", "tasks"],
    queryFn: async () => request("/api/system/tasks"),
  })
  const rows = useMemo(() => {
    const queues = query.data?.data ?? []
    const flat = queues.flatMap((queue) => [...queue.tasks, ...queue.scheduled_tasks])
    if (mode === "interval") return flat.filter((row) => !row.cron)
    if (mode === "crontab") return flat.filter((row) => row.cron)
    return flat
  }, [mode, query.data?.data])
  const title = mode === "interval" ? "时间间隔设置" : mode === "crontab" ? "crontab设置" : "定时任务设置"
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="定时任务" title={title} description="当前任务来自后端 SAQ 静态配置，本页只读展示，不提供在线修改。" />
      <PageSection>
        <Card>
          <CardHeader>
            <CardTitle>任务配置</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务</TableHead>
                  <TableHead>模块</TableHead>
                  <TableHead>队列</TableHead>
                  <TableHead>Cron</TableHead>
                  <TableHead>超时</TableHead>
                  <TableHead>TTL</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                      暂无任务
                    </TableCell>
                  </TableRow>
                )}
                {rows.map((row) => (
                  <TableRow key={`${row.name}-${row.cron ?? "task"}`}>
                    <TableCell>{display(row.name)}</TableCell>
                    <TableCell>{display(row.module)}</TableCell>
                    <TableCell>{display(row.queue)}</TableCell>
                    <TableCell>{display(row.cron)}</TableCell>
                    <TableCell>{display(row.timeout)}</TableCell>
                    <TableCell>{display(row.ttl)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}

export function VideoMonitorsLink() {
  return <Link to="/data/video-alarm-events">视频预警事件</Link>
}
