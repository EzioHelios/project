import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Gauge, Plus, RefreshCw, Trash2, Wand2 } from "lucide-react"
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

type BenchmarkProfile = Row & {
  id: number
  name: string
  industry_name?: string | null
  scenario?: string | null
  source_name?: string | null
  valid_from?: string | null
  valid_to?: string | null
  is_enabled: boolean
  remark?: string | null
}

type BenchmarkItem = Row & {
  id: number
  profile_id: number
  target_type: string
  target_code?: string | null
  target_name?: string | null
  metric_code: string
  metric_name: string
  benchmark_value: number
  unit: string
  excellent_value?: number | null
  warning_threshold_pct?: number | null
  severe_threshold_pct?: number | null
  source_name?: string | null
  confidence_level?: string | null
  is_enabled: boolean
  remark?: string | null
}

type Option = {
  value: string
  label: string
  code?: string
}

const targetTypes = [
  { value: "device", label: "设备" },
  { value: "use_system", label: "用能系统" },
  { value: "area", label: "区域" },
  { value: "enterprise", label: "企业" },
  { value: "line", label: "产线" },
  { value: "product", label: "产品" },
  { value: "device_type", label: "设备类型" },
]

const metrics = [
  { value: "kwh_per_run_hour", label: "单位运行小时用电", unit: "kWh/h" },
  { value: "kwh_per_workload", label: "单位作业量用电", unit: "kWh/unit" },
  { value: "kgce_per_unit", label: "单位产品综合能耗", unit: "kgce/unit" },
  { value: "kgce_per_10k_value", label: "单位产值综合能耗", unit: "kgce/万元" },
  { value: "tce_per_m2", label: "单位面积综合能耗", unit: "tce/m2" },
  { value: "kwh_per_m2", label: "单位面积用电量", unit: "kWh/m2" },
]

const confidenceOptions = [
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
]

const emptyProfile = {
  name: "",
  industry_name: "",
  scenario: "",
  source_name: "",
  valid_from: "",
  valid_to: "",
  is_enabled: "true",
  remark: "",
}

const emptyItem = {
  target_type: "device",
  target_code: "",
  target_name: "",
  metric_code: "kwh_per_run_hour",
  metric_name: "单位运行小时用电",
  benchmark_value: "",
  unit: "kWh/h",
  excellent_value: "",
  warning_threshold_pct: "10",
  severe_threshold_pct: "20",
  source_name: "",
  confidence_level: "medium",
  is_enabled: "true",
  remark: "",
}

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "boolean") return value ? "启用" : "停用"
  return String(value)
}

function formatNumber(value: number | string | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function booleanString(value: unknown) {
  return value === false ? "false" : "true"
}

function profileForm(row?: BenchmarkProfile | null) {
  return {
    name: row?.name ?? "",
    industry_name: row?.industry_name ?? "",
    scenario: row?.scenario ?? "",
    source_name: row?.source_name ?? "",
    valid_from: row?.valid_from ?? "",
    valid_to: row?.valid_to ?? "",
    is_enabled: booleanString(row?.is_enabled),
    remark: row?.remark ?? "",
  }
}

function itemForm(row?: BenchmarkItem | null) {
  const metric = metrics.find((item) => item.value === row?.metric_code)
  return {
    target_type: row?.target_type ?? "device",
    target_code: row?.target_code ?? "",
    target_name: row?.target_name ?? "",
    metric_code: row?.metric_code ?? "kwh_per_run_hour",
    metric_name: row?.metric_name ?? metric?.label ?? "单位运行小时用电",
    benchmark_value: row?.benchmark_value == null ? "" : String(row.benchmark_value),
    unit: row?.unit ?? metric?.unit ?? "kWh/h",
    excellent_value: row?.excellent_value == null ? "" : String(row.excellent_value),
    warning_threshold_pct: row?.warning_threshold_pct == null ? "10" : String(row.warning_threshold_pct),
    severe_threshold_pct: row?.severe_threshold_pct == null ? "20" : String(row.severe_threshold_pct),
    source_name: row?.source_name ?? "",
    confidence_level: row?.confidence_level ?? "medium",
    is_enabled: booleanString(row?.is_enabled),
    remark: row?.remark ?? "",
  }
}

function nullable(value: string) {
  return value.trim() ? value.trim() : null
}

function numberOrNull(value: string) {
  return value.trim() ? Number(value) : null
}

function targetTypeLabel(value?: string | null) {
  return targetTypes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function metricLabel(value?: string | null) {
  return metrics.find((item) => item.value === value)?.label ?? value ?? "-"
}

export function EnergyBenchmarkSettingsPanel() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [profileEditing, setProfileEditing] = useState<BenchmarkProfile | null>(null)
  const [profileDetail, setProfileDetail] = useState<BenchmarkProfile | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [profileValues, setProfileValues] = useState(emptyProfile)
  const [itemEditing, setItemEditing] = useState<BenchmarkItem | null>(null)
  const [itemDetail, setItemDetail] = useState<BenchmarkItem | null>(null)
  const [itemOpen, setItemOpen] = useState(false)
  const [itemValues, setItemValues] = useState(emptyItem)

  const profilesQuery = useQuery<PageResult<BenchmarkProfile>>({
    queryKey: ["energy-benchmark-settings", "profiles", appliedKeyword],
    queryFn: () => requestPage<BenchmarkProfile>("/api/energy/benchmark/profiles", { keyword: appliedKeyword, limit: 200 }),
  })
  const profiles = profilesQuery.data?.items ?? []
  const selectedProfile = profiles.find((item) => item.id === selectedProfileId) ?? profiles[0]

  const itemsQuery = useQuery<PageResult<BenchmarkItem>>({
    queryKey: ["energy-benchmark-settings", "items", selectedProfile?.id],
    queryFn: () => requestPage<BenchmarkItem>("/api/energy/benchmark/items", { profile_id: selectedProfile?.id, limit: 200 }),
    enabled: Boolean(selectedProfile?.id),
  })

  const areasQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-benchmark-settings", "areas"],
    queryFn: async () => (await request<PageResult<Row>>("/api/master-data/areas/tree")).data,
  })
  const devicesQuery = useQuery<PageResult<Row>>({
    queryKey: ["energy-benchmark-settings", "devices"],
    queryFn: () => requestPage<Row>("/api/master-data/devices", { limit: 500, offset: 0 }),
  })

  const areaOptions = useMemo(() => toOptions(flattenRows(areasQuery.data?.items ?? [])), [areasQuery.data?.items])
  const deviceOptions = useMemo(() => toOptions(devicesQuery.data?.items ?? []), [devicesQuery.data?.items])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["energy-benchmark-settings"] })

  const saveProfile = useMutation({
    mutationFn: () => {
      const payload = {
        name: profileValues.name,
        industry_name: nullable(profileValues.industry_name),
        scenario: nullable(profileValues.scenario),
        source_name: nullable(profileValues.source_name),
        valid_from: nullable(profileValues.valid_from),
        valid_to: nullable(profileValues.valid_to),
        is_enabled: profileValues.is_enabled === "true",
        remark: nullable(profileValues.remark),
      }
      return request<BenchmarkProfile>(profileEditing ? `/api/energy/benchmark/profiles/${profileEditing.id}` : "/api/energy/benchmark/profiles", {
        method: profileEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (result) => {
      toast.success(profileEditing ? "标杆方案已更新" : "标杆方案已保存")
      setProfileOpen(false)
      setProfileEditing(null)
      setProfileValues(emptyProfile)
      setSelectedProfileId(result.data.id)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteProfile = useMutation({
    mutationFn: (id: number) => request(`/api/energy/benchmark/profiles/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("标杆方案已删除")
      setSelectedProfileId(null)
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请先清理标杆项或稍后重试" }),
  })

  const saveItem = useMutation({
    mutationFn: () => {
      const metric = metrics.find((item) => item.value === itemValues.metric_code)
      const payload = {
        profile_id: selectedProfile?.id,
        target_type: itemValues.target_type,
        target_code: nullable(itemValues.target_code),
        target_name: nullable(itemValues.target_name),
        metric_code: itemValues.metric_code,
        metric_name: itemValues.metric_name || metric?.label,
        benchmark_value: Number(itemValues.benchmark_value),
        unit: itemValues.unit || metric?.unit,
        excellent_value: numberOrNull(itemValues.excellent_value),
        warning_threshold_pct: numberOrNull(itemValues.warning_threshold_pct),
        severe_threshold_pct: numberOrNull(itemValues.severe_threshold_pct),
        source_name: nullable(itemValues.source_name),
        confidence_level: nullable(itemValues.confidence_level),
        is_enabled: itemValues.is_enabled === "true",
        remark: nullable(itemValues.remark),
      }
      return request<BenchmarkItem>(itemEditing ? `/api/energy/benchmark/items/${itemEditing.id}` : "/api/energy/benchmark/items", {
        method: itemEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
    },
    onSuccess: () => {
      toast.success(itemEditing ? "标杆项已更新" : "标杆项已保存")
      setItemOpen(false)
      setItemEditing(null)
      setItemValues(emptyItem)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteItem = useMutation({
    mutationFn: (id: number) => request(`/api/energy/benchmark/items/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("标杆项已删除")
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const generate = useMutation({
    mutationFn: (method: string) =>
      request("/api/energy/benchmark/generate-from-history", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target_type: itemValues.target_type,
          metric_code: itemValues.metric_code,
          profile_name: `历史基线标杆-${Date.now()}`,
          method,
        }),
      }),
    onSuccess: () => {
      toast.success("历史基线标杆已生成")
      invalidate()
    },
    onError: (error) => toast.error("生成失败", { description: error instanceof Error ? error.message : "请检查历史数据" }),
  })

  const startCreateProfile = () => {
    setProfileEditing(null)
    setProfileValues(emptyProfile)
    setProfileOpen(true)
  }

  const startEditProfile = (row: BenchmarkProfile) => {
    setProfileEditing(row)
    setProfileValues(profileForm(row))
    setProfileOpen(true)
  }

  const startCreateItem = () => {
    setItemEditing(null)
    setItemValues(emptyItem)
    setItemOpen(true)
  }

  const startEditItem = (row: BenchmarkItem) => {
    setItemEditing(row)
    setItemValues(itemForm(row))
    setItemOpen(true)
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageHeader
        title="能效对标配置"
        actions={
          <>
            <Button variant="outline" onClick={() => invalidate()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button variant="outline" asChild>
              <Link to="/energy/benchmark">
                <Gauge className="mr-2 h-4 w-4" />
                查看对标
              </Link>
            </Button>
            <Button onClick={startCreateProfile}>
              <Plus className="mr-2 h-4 w-4" />
              新增方案
            </Button>
          </>
        }
      />

      <Tabs defaultValue="profiles" className="space-y-4">
        <AdminTabsList>
          <TabsTrigger value="profiles">标杆方案</TabsTrigger>
          <TabsTrigger value="items">标杆项</TabsTrigger>
          <TabsTrigger value="generate">历史基线生成</TabsTrigger>
        </AdminTabsList>

        <TabsContent value="profiles" className="space-y-4">
          <ContextBar
            actions={
              <Button
                variant="secondary"
                onClick={() => {
                  setAppliedKeyword(keyword)
                }}
              >
                查询
              </Button>
            }
          >
            <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索方案名称、行业或适用范围" />
          </ContextBar>
          <AdminPanel title="标杆方案列表" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>方案名称</TableHead>
                    <TableHead>行业</TableHead>
                    <TableHead>适用范围</TableHead>
                    <TableHead>来源</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {profiles.map((row) => (
                    <TableRow key={row.id} data-selected={selectedProfile?.id === row.id}>
                      <TableCell className="font-medium">{row.name}</TableCell>
                      <TableCell>{display(row.industry_name)}</TableCell>
                      <TableCell>{display(row.scenario)}</TableCell>
                      <TableCell>{display(row.source_name)}</TableCell>
                      <TableCell>
                        <Badge variant={row.is_enabled ? "success" : "outline"}>{row.is_enabled ? "启用" : "停用"}</Badge>
                      </TableCell>
                      <TableCell className="space-x-2 text-right">
                        <Button variant="secondary" size="sm" onClick={() => setProfileDetail(row)}>
                          详情
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setSelectedProfileId(row.id)}>
                          选择
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => startEditProfile(row)}>
                          编辑
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => {
                            if (window.confirm("确认删除该标杆方案？")) deleteProfile.mutate(row.id)
                          }}
                        >
                          删除
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {profiles.length === 0 && <AdminTableStateRow colSpan={6}>暂无标杆方案</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="items" className="space-y-4">
          <ContextBar
            actions={
              <Button onClick={startCreateItem} disabled={!selectedProfile?.id}>
                <Plus className="mr-2 h-4 w-4" />
                新增标杆项
              </Button>
            }
          >
            <Select value={selectedProfile?.id ? String(selectedProfile.id) : undefined} onValueChange={(value) => setSelectedProfileId(Number(value))}>
              <SelectTrigger>
                <SelectValue placeholder="选择标杆方案" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((profile) => (
                  <SelectItem key={profile.id} value={String(profile.id)}>
                    {profile.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ContextBar>
          <AdminPanel title="标杆项列表" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <BenchmarkItemsTable rows={itemsQuery.data?.items ?? []} onDetail={setItemDetail} onEdit={startEditItem} onDelete={(id) => deleteItem.mutate(id)} />
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="generate">
          <AdminPanel
            title="历史基线生成"
            actions={
              <>
                <Button variant="outline" onClick={() => generate.mutate("best_period")} disabled={generate.isPending}>
                  <Wand2 className="mr-2 h-4 w-4" />
                  最优基线生成
                </Button>
                <Button variant="outline" onClick={() => generate.mutate("p25")} disabled={generate.isPending}>
                  P25 生成
                </Button>
                <Button variant="outline" onClick={() => generate.mutate("average")} disabled={generate.isPending}>
                  均值生成
                </Button>
              </>
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField label="对象类型" value={itemValues.target_type} options={targetTypes} onChange={(next) => setItemValues((state) => ({ ...state, target_type: next }))} />
              <SelectField
                label="指标"
                value={itemValues.metric_code}
                options={metrics}
                onChange={(next) => {
                  const metric = metrics.find((item) => item.value === next)
                  setItemValues((state) => ({ ...state, metric_code: next, metric_name: metric?.label ?? state.metric_name, unit: metric?.unit ?? state.unit }))
                }}
              />
            </div>
          </AdminPanel>
        </TabsContent>
      </Tabs>

      <ProfileDialog
        open={profileOpen}
        values={profileValues}
        editing={profileEditing}
        saving={saveProfile.isPending}
        onOpenChange={setProfileOpen}
        onChange={setProfileValues}
        onSave={() => saveProfile.mutate()}
      />
      <ItemDialog
        open={itemOpen}
        values={itemValues}
        editing={itemEditing}
        saving={saveItem.isPending}
        areaOptions={areaOptions}
        deviceOptions={deviceOptions}
        onOpenChange={setItemOpen}
        onChange={setItemValues}
        onSave={() => saveItem.mutate()}
      />
      <DetailSheet title="标杆方案详情" row={profileDetail} labels={profileLabels} onClose={() => setProfileDetail(null)} />
      <DetailSheet title="标杆项详情" row={itemDetail} labels={itemLabels} onClose={() => setItemDetail(null)} />
    </PageContainer>
  )
}

function toOptions(rows: Row[]): Option[] {
  return rows.map((row) => ({
    value: String(row.id ?? row.code ?? ""),
    label: String(row.name ?? row.code ?? row.id ?? ""),
    code: row.code == null ? undefined : String(row.code),
  }))
}

function flattenRows(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenRows((Array.isArray(row.children) ? row.children : []) as Row[])])
}

function BenchmarkItemsTable({
  rows,
  onDetail,
  onEdit,
  onDelete,
}: {
  rows: BenchmarkItem[]
  onDetail: (row: BenchmarkItem) => void
  onEdit: (row: BenchmarkItem) => void
  onDelete: (id: number) => void
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>对象</TableHead>
          <TableHead>指标</TableHead>
          <TableHead className="text-right">标杆值</TableHead>
          <TableHead className="text-right">预警阈值</TableHead>
          <TableHead>来源</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell>
              <div className="font-medium">{row.target_name || row.target_code || "通用标杆"}</div>
              <div className="text-xs text-muted-foreground">{targetTypeLabel(row.target_type)}</div>
            </TableCell>
            <TableCell>{row.metric_name || metricLabel(row.metric_code)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatNumber(row.benchmark_value)} {row.unit}
            </TableCell>
            <TableCell className="text-right tabular-nums">{formatNumber(row.warning_threshold_pct)}%</TableCell>
            <TableCell>{display(row.source_name)}</TableCell>
            <TableCell>
              <Badge variant={row.is_enabled ? "success" : "outline"}>{row.is_enabled ? "启用" : "停用"}</Badge>
            </TableCell>
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
                onClick={() => {
                  if (window.confirm("确认删除该标杆项？")) onDelete(row.id)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <AdminTableStateRow colSpan={7}>暂无标杆项</AdminTableStateRow>}
      </TableBody>
    </Table>
  )
}

function ProfileDialog({
  open,
  values,
  editing,
  saving,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyProfile
  editing: BenchmarkProfile | null
  saving: boolean
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyProfile) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyProfile, value: string) => onChange({ ...values, [key]: value })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑标杆方案" : "新增标杆方案"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="方案名称" value={values.name} onChange={(next) => set("name", next)} />
          <TextField label="行业" value={values.industry_name} onChange={(next) => set("industry_name", next)} />
          <TextField label="适用范围" value={values.scenario} onChange={(next) => set("scenario", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <TextField label="生效日期" type="date" value={values.valid_from} onChange={(next) => set("valid_from", next)} />
          <TextField label="截止日期" type="date" value={values.valid_to} onChange={(next) => set("valid_to", next)} />
          <SelectField
            label="状态"
            value={values.is_enabled}
            options={[
              { value: "true", label: "启用" },
              { value: "false", label: "停用" },
            ]}
            onChange={(next) => set("is_enabled", next)}
          />
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

function ItemDialog({
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
  values: typeof emptyItem
  editing: BenchmarkItem | null
  saving: boolean
  areaOptions: Option[]
  deviceOptions: Option[]
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyItem) => void
  onSave: () => void
}) {
  const set = (key: keyof typeof emptyItem, value: string) => onChange({ ...values, [key]: value })
  const targetOptions = values.target_type === "area" ? areaOptions : values.target_type === "device" ? deviceOptions : []
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑标杆项" : "新增标杆项"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            label="对象类型"
            value={values.target_type}
            options={targetTypes}
            onChange={(next) => {
              onChange({ ...values, target_type: next, target_code: "", target_name: "" })
            }}
          />
          <SelectField
            label="指标"
            value={values.metric_code}
            options={metrics}
            onChange={(next) => {
              const metric = metrics.find((item) => item.value === next)
              onChange({ ...values, metric_code: next, metric_name: metric?.label ?? "", unit: metric?.unit ?? "" })
            }}
          />
          {values.target_type === "area" || values.target_type === "device" ? (
            <SelectField
              label="对象"
              value={values.target_code}
              options={targetOptions}
              onChange={(next) => {
                const option = targetOptions.find((item) => item.value === next)
                onChange({ ...values, target_code: next, target_name: option?.label ?? "" })
              }}
            />
          ) : values.target_type === "enterprise" ? null : (
            <>
              <TextField label="对象编码" value={values.target_code} onChange={(next) => set("target_code", next)} />
              <TextField label="对象名称" value={values.target_name} onChange={(next) => set("target_name", next)} />
            </>
          )}
          <TextField label="标杆值" type="number" value={values.benchmark_value} onChange={(next) => set("benchmark_value", next)} />
          <TextField label="优秀值" type="number" value={values.excellent_value} onChange={(next) => set("excellent_value", next)} />
          <TextField label="单位" value={values.unit} onChange={(next) => set("unit", next)} />
          <TextField label="预警阈值(%)" type="number" value={values.warning_threshold_pct} onChange={(next) => set("warning_threshold_pct", next)} />
          <TextField label="重点偏差阈值(%)" type="number" value={values.severe_threshold_pct} onChange={(next) => set("severe_threshold_pct", next)} />
          <TextField label="来源" value={values.source_name} onChange={(next) => set("source_name", next)} />
          <SelectField label="置信度" value={values.confidence_level} options={confidenceOptions} onChange={(next) => set("confidence_level", next)} />
          <SelectField
            label="状态"
            value={values.is_enabled}
            options={[
              { value: "true", label: "启用" },
              { value: "false", label: "停用" },
            ]}
            onChange={(next) => set("is_enabled", next)}
          />
          <div className="grid gap-2 md:col-span-2">
            <Label>备注</Label>
            <Textarea value={values.remark} onChange={(event) => set("remark", event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={!values.benchmark_value || saving}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TextField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
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

const profileLabels: Record<string, string> = {
  name: "方案名称",
  industry_name: "行业",
  scenario: "适用范围",
  source_name: "来源",
  valid_from: "生效日期",
  valid_to: "截止日期",
  is_enabled: "状态",
  remark: "备注",
}

const itemLabels: Record<string, string> = {
  target_type: "对象类型",
  target_code: "对象编码",
  target_name: "对象名称",
  metric_code: "指标编码",
  metric_name: "指标名称",
  benchmark_value: "标杆值",
  unit: "单位",
  excellent_value: "优秀值",
  warning_threshold_pct: "预警阈值",
  severe_threshold_pct: "重点偏差阈值",
  source_name: "来源",
  confidence_level: "置信度",
  is_enabled: "状态",
  remark: "备注",
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
