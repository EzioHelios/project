import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Download, Gauge, Plus, RefreshCw, Trash2, Upload } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminFilterBar, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTabsList, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
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

type BenchmarkProfile = {
  id: number
  name: string
  industry_name?: string | null
  scenario?: string | null
  library_type?: string | null
  source_name?: string | null
  source_url?: string | null
  source_hash?: string | null
  source_file_name?: string | null
  standard_code?: string | null
  version_status?: string | null
  valid_from?: string | null
  valid_to?: string | null
  is_enabled: boolean
  remark?: string | null
}

type BenchmarkItem = {
  id: number
  profile_id: number
  target_type: string
  target_code?: string | null
  target_name?: string | null
  metric_code: string
  metric_name?: string | null
  benchmark_value: number
  unit?: string | null
  standard_code?: string | null
  source_url?: string | null
  source_hash?: string | null
  applicable_industry?: string | null
  applicable_category?: string | null
  applicable_condition?: string | null
  metric_direction?: string | null
  advanced_value?: number | null
  saving_value?: number | null
  access_value?: number | null
  baseline_value?: number | null
  advanced_level?: string | null
  saving_level?: string | null
  access_level?: string | null
  standard_level?: string | null
  version_status?: string | null
  reference_standard?: string | null
  warning_threshold_pct?: number | null
  severe_threshold_pct?: number | null
  source_name?: string | null
  confidence_level?: string | null
  is_enabled: boolean
  remark?: string | null
}

type PolicySource = {
  key: string
  name: string
  page_url: string
  fallback_pdf_url: string
  standard_code: string
}

type ImportPreviewRow = {
  row_number: number
  valid: boolean
  errors: string[]
  row: Record<string, unknown>
}

type ImportPreview = {
  items: ImportPreviewRow[]
  valid_count: number
  invalid_count: number
  total: number
}

type Option = { value: string; label: string; unit?: string }

const libraryTypes = [
  { value: "policy_industry", label: "政策标杆库" },
  { value: "equipment_efficiency", label: "设备能效等级库" },
  { value: "enterprise_standard", label: "企业内部标准库" },
]

const editableLibraryTypes = [{ value: "enterprise_standard", label: "企业内部标准库" }]

const targetTypes = [
  { value: "enterprise", label: "基地总体" },
  { value: "area", label: "区域" },
  { value: "use_system", label: "用能系统" },
  { value: "device_type", label: "设备类型" },
  { value: "device", label: "设备" },
  { value: "line", label: "产线/工序" },
  { value: "product", label: "产品" },
]

const metrics: Option[] = [
  { value: "kwh_per_m2", label: "单位面积用电量", unit: "kWh/m2" },
  { value: "tce_per_m2", label: "单位面积综合能耗", unit: "tce/m2" },
  { value: "kgce_per_10k_value", label: "单位产值综合能耗", unit: "kgce/万元" },
  { value: "kgce_per_unit", label: "单位产品综合能耗", unit: "kgce/unit" },
  { value: "kwh_per_run_hour", label: "单位运行小时用电", unit: "kWh/h" },
  { value: "kwh_per_workload", label: "单位作业量用电", unit: "kWh/unit" },
  { value: "energy_efficiency_level", label: "设备能效等级", unit: "级" },
]

const directions = [
  { value: "lower_is_better", label: "越低越优" },
  { value: "higher_is_better", label: "越高越优" },
  { value: "level_rank", label: "等级数字越小越优" },
]

const emptyProfile = {
  name: "",
  industry_name: "",
  scenario: "",
  library_type: "enterprise_standard",
  source_name: "",
  source_url: "",
  source_hash: "",
  source_file_name: "",
  standard_code: "",
  version_status: "active",
  valid_from: "",
  valid_to: "",
  is_enabled: "true",
  remark: "",
}

const emptyItem = {
  target_type: "device_type",
  target_code: "",
  target_name: "",
  metric_code: "energy_efficiency_level",
  metric_name: "设备能效等级",
  benchmark_value: "2",
  unit: "级",
  standard_code: "",
  source_url: "",
  source_hash: "",
  applicable_industry: "",
  applicable_category: "",
  applicable_condition: "",
  metric_direction: "level_rank",
  advanced_value: "1",
  saving_value: "2",
  access_value: "3",
  baseline_value: "",
  advanced_level: "能效1级",
  saving_level: "能效2级",
  access_level: "能效3级",
  standard_level: "saving",
  version_status: "active",
  reference_standard: "",
  warning_threshold_pct: "10",
  severe_threshold_pct: "25",
  source_name: "",
  confidence_level: "medium",
  is_enabled: "true",
  remark: "",
}

const templateHeader = "对象类型,对象编码,对象名称,指标编码,指标名称,标杆值,单位,标准编号,适用行业,适用分类,适用条件,指标方向,先进水平,节能水平,准入水平,基准水平,参考标准"

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "boolean") return value ? "启用" : "停用"
  return String(value)
}

function displayDate(value: string | null | undefined) {
  if (!value) return "-"
  return value.includes("T") ? value.split("T")[0] : value
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

function optionLabel(options: Option[], value?: string | null) {
  return options.find((item) => item.value === value)?.label ?? value ?? "-"
}

function libraryTypeLabel(value?: string | null) {
  return libraryTypes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function profileForm(row?: BenchmarkProfile | null) {
  return {
    name: row?.name ?? "",
    industry_name: row?.industry_name ?? "",
    scenario: row?.scenario ?? "",
    library_type: row?.library_type ?? "enterprise_standard",
    source_name: row?.source_name ?? "",
    source_url: row?.source_url ?? "",
    source_hash: row?.source_hash ?? "",
    source_file_name: row?.source_file_name ?? "",
    standard_code: row?.standard_code ?? "",
    version_status: row?.version_status ?? "active",
    valid_from: displayDate(row?.valid_from) === "-" ? "" : displayDate(row?.valid_from),
    valid_to: displayDate(row?.valid_to) === "-" ? "" : displayDate(row?.valid_to),
    is_enabled: row?.is_enabled === false ? "false" : "true",
    remark: row?.remark ?? "",
  }
}

function itemForm(row?: BenchmarkItem | null) {
  const metric = metrics.find((item) => item.value === row?.metric_code)
  return {
    target_type: row?.target_type ?? "device_type",
    target_code: row?.target_code ?? "",
    target_name: row?.target_name ?? "",
    metric_code: row?.metric_code ?? "energy_efficiency_level",
    metric_name: row?.metric_name ?? metric?.label ?? "设备能效等级",
    benchmark_value: row?.benchmark_value == null ? "" : String(row.benchmark_value),
    unit: row?.unit ?? metric?.unit ?? "级",
    standard_code: row?.standard_code ?? "",
    source_url: row?.source_url ?? "",
    source_hash: row?.source_hash ?? "",
    applicable_industry: row?.applicable_industry ?? "",
    applicable_category: row?.applicable_category ?? "",
    applicable_condition: row?.applicable_condition ?? "",
    metric_direction: row?.metric_direction ?? (row?.metric_code === "energy_efficiency_level" ? "level_rank" : "lower_is_better"),
    advanced_value: row?.advanced_value == null ? "" : String(row.advanced_value),
    saving_value: row?.saving_value == null ? "" : String(row.saving_value),
    access_value: row?.access_value == null ? "" : String(row.access_value),
    baseline_value: row?.baseline_value == null ? "" : String(row.baseline_value),
    advanced_level: row?.advanced_level ?? "",
    saving_level: row?.saving_level ?? "",
    access_level: row?.access_level ?? "",
    standard_level: row?.standard_level ?? "",
    version_status: row?.version_status ?? "active",
    reference_standard: row?.reference_standard ?? "",
    warning_threshold_pct: row?.warning_threshold_pct == null ? "10" : String(row.warning_threshold_pct),
    severe_threshold_pct: row?.severe_threshold_pct == null ? "25" : String(row.severe_threshold_pct),
    source_name: row?.source_name ?? "",
    confidence_level: row?.confidence_level ?? "medium",
    is_enabled: row?.is_enabled === false ? "false" : "true",
    remark: row?.remark ?? "",
  }
}

export function EnergyBenchmarkSettingsPanel() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [profileEditing, setProfileEditing] = useState<BenchmarkProfile | null>(null)
  const [profileDetail, setProfileDetail] = useState<BenchmarkProfile | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [profileValues, setProfileValues] = useState(emptyProfile)
  const [itemEditing, setItemEditing] = useState<BenchmarkItem | null>(null)
  const [itemDetail, setItemDetail] = useState<BenchmarkItem | null>(null)
  const [itemOpen, setItemOpen] = useState(false)
  const [itemValues, setItemValues] = useState(emptyItem)
  const [itemTargetType, setItemTargetType] = useState("all")
  const [itemMetricCode, setItemMetricCode] = useState("all")
  const [csvText, setCsvText] = useState("")
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null)

  const profilesQuery = useQuery<PageResult<BenchmarkProfile>>({
    queryKey: ["energy-benchmark-settings", "profiles", keyword],
    queryFn: () =>
      requestPage<BenchmarkProfile>("/api/energy/benchmark/profiles", {
        keyword: keyword.trim(),
        limit: 200,
      }),
  })
  const policySourcesQuery = useQuery({
    queryKey: ["energy-benchmark-settings", "policy-sources"],
    queryFn: () => request<{ items: PolicySource[] }>("/api/energy/benchmark/policy-sources").then((response) => response.data.items),
  })

  const profiles = profilesQuery.data?.items ?? []
  const policyProfiles = profiles.filter((item) => item.library_type === "policy_industry" || item.library_type === "equipment_efficiency")
  const editableProfiles = profiles.filter((item) => item.library_type === "enterprise_standard")
  const selectedProfile = editableProfiles.find((item) => item.id === selectedProfileId) ?? editableProfiles[0]

  const itemsQuery = useQuery<PageResult<BenchmarkItem>>({
    queryKey: ["energy-benchmark-settings", "items", selectedProfile?.id, itemTargetType, itemMetricCode],
    queryFn: () =>
      requestPage<BenchmarkItem>("/api/energy/benchmark/items", {
        profile_id: selectedProfile?.id,
        target_type: itemTargetType,
        metric_code: itemMetricCode,
        limit: 200,
      }),
    enabled: Boolean(selectedProfile?.id),
  })

  const items = itemsQuery.data?.items ?? []
  const enabledProfiles = editableProfiles.filter((item) => item.is_enabled).length

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["energy-benchmark-settings"] })

  const syncPolicy = useMutation({
    mutationFn: () =>
      request("/api/energy/benchmark/policy-library/sync", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ source: "ndrc-2023,ndrc-equipment-2024", apply: true }),
      }),
    onSuccess: () => {
      toast.success("政策资料已同步")
      invalidate()
    },
    onError: (error) => toast.error("同步失败", { description: error instanceof Error ? error.message : "请检查网络和租户数据" }),
  })

  const saveProfile = useMutation({
    mutationFn: () =>
      request<BenchmarkProfile>(profileEditing ? `/api/energy/benchmark/profiles/${profileEditing.id}` : "/api/energy/benchmark/profiles", {
        method: profileEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: profileValues.name,
          industry_name: nullable(profileValues.industry_name),
          scenario: nullable(profileValues.scenario),
          library_type: profileValues.library_type,
          source_name: nullable(profileValues.source_name),
          source_url: nullable(profileValues.source_url),
          source_hash: nullable(profileValues.source_hash),
          source_file_name: nullable(profileValues.source_file_name),
          standard_code: nullable(profileValues.standard_code),
          version_status: profileValues.version_status || "active",
          valid_from: nullable(profileValues.valid_from),
          valid_to: nullable(profileValues.valid_to),
          is_enabled: profileValues.is_enabled === "true",
          remark: nullable(profileValues.remark),
        }),
      }),
    onSuccess: (response) => {
      toast.success(profileEditing ? "标准方案已更新" : "标准方案已保存")
      setProfileOpen(false)
      setProfileEditing(null)
      setProfileValues(emptyProfile)
      setSelectedProfileId(response.data.id)
      invalidate()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteProfile = useMutation({
    mutationFn: (id: number) => request(`/api/energy/benchmark/profiles/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("标准方案已删除")
      setSelectedProfileId(null)
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请先删除关联指标" }),
  })

  const saveItem = useMutation({
    mutationFn: () => {
      const metric = metrics.find((item) => item.value === itemValues.metric_code)
      return request<BenchmarkItem>(itemEditing ? `/api/energy/benchmark/items/${itemEditing.id}` : "/api/energy/benchmark/items", {
        method: itemEditing ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          profile_id: selectedProfile?.id,
          target_type: itemValues.target_type,
          target_code: nullable(itemValues.target_code),
          target_name: nullable(itemValues.target_name),
          metric_code: itemValues.metric_code,
          metric_name: itemValues.metric_name || metric?.label,
          benchmark_value: Number(itemValues.benchmark_value),
          unit: itemValues.unit || metric?.unit,
          standard_code: nullable(itemValues.standard_code),
          source_url: nullable(itemValues.source_url),
          source_hash: nullable(itemValues.source_hash),
          applicable_industry: nullable(itemValues.applicable_industry),
          applicable_category: nullable(itemValues.applicable_category),
          applicable_condition: nullable(itemValues.applicable_condition),
          metric_direction: itemValues.metric_direction,
          advanced_value: numberOrNull(itemValues.advanced_value),
          saving_value: numberOrNull(itemValues.saving_value),
          access_value: numberOrNull(itemValues.access_value),
          baseline_value: numberOrNull(itemValues.baseline_value),
          advanced_level: nullable(itemValues.advanced_level),
          saving_level: nullable(itemValues.saving_level),
          access_level: nullable(itemValues.access_level),
          standard_level: nullable(itemValues.standard_level),
          version_status: itemValues.version_status || "active",
          reference_standard: nullable(itemValues.reference_standard),
          warning_threshold_pct: numberOrNull(itemValues.warning_threshold_pct),
          severe_threshold_pct: numberOrNull(itemValues.severe_threshold_pct),
          source_name: nullable(itemValues.source_name),
          confidence_level: nullable(itemValues.confidence_level),
          is_enabled: itemValues.is_enabled === "true",
          remark: nullable(itemValues.remark),
        }),
      })
    },
    onSuccess: () => {
      toast.success(itemEditing ? "标杆指标已更新" : "标杆指标已保存")
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
      toast.success("标杆指标已删除")
      invalidate()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const previewImport = useMutation({
    mutationFn: () =>
      request<ImportPreview>("/api/energy/benchmark/import/preview", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ csv_text: csvText }),
      }),
    onSuccess: (response) => setImportPreview(response.data),
    onError: (error) => toast.error("预检失败", { description: error instanceof Error ? error.message : "请检查模板内容" }),
  })

  const applyImport = useMutation({
    mutationFn: () =>
      request<{ created: number }>("/api/energy/benchmark/import/apply", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ profile_id: selectedProfile?.id, csv_text: csvText }),
      }),
    onSuccess: (response) => {
      toast.success(`已导入 ${response.data.created} 条标杆指标`)
      invalidate()
    },
    onError: (error) => toast.error("导入失败", { description: error instanceof Error ? error.message : "请先完成预检" }),
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
        title="能效标准与标杆库"
        actions={
          <>
            <Button variant="outline" onClick={() => invalidate()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button variant="outline" asChild>
              <Link to="/energy/benchmark">
                <Gauge className="mr-2 h-4 w-4" />
                对标分析
              </Link>
            </Button>
            <Button onClick={startCreateProfile}>
              <Plus className="mr-2 h-4 w-4" />
              新增方案
            </Button>
          </>
        }
      />

      <MetricStrip className="md:grid-cols-4 xl:grid-cols-4">
        <MetricTile label="企业方案" value={editableProfiles.length} />
        <MetricTile label="启用方案" value={enabledProfiles} />
        <MetricTile label="政策库" value={policyProfiles.length} />
        <MetricTile label="当前指标" value={items.length} />
      </MetricStrip>

      <Tabs defaultValue="enterprise" className="mt-4 space-y-4">
        <AdminTabsList>
          <TabsTrigger value="enterprise">企业标杆</TabsTrigger>
          <TabsTrigger value="policy">政策标准</TabsTrigger>
          <TabsTrigger value="import">模板导入</TabsTrigger>
        </AdminTabsList>

        <TabsContent value="enterprise" className="space-y-4">
          <AdminFilterBar
            fields={[{ key: "keyword", node: <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索方案、行业、来源" /> }]}
            actions={<Button onClick={startCreateProfile}>新增方案</Button>}
          />
          <AdminPanel title="标准方案列表" contentClassName="p-0">
            <ProfileTable
              rows={editableProfiles}
              selectedId={selectedProfile?.id}
              onSelect={setSelectedProfileId}
              onDetail={setProfileDetail}
              onEdit={startEditProfile}
              onDelete={(id) => deleteProfile.mutate(id)}
            />
          </AdminPanel>

          <AdminFilterBar
            fields={[
              {
                key: "profile",
                node: (
                  <Select value={selectedProfile?.id ? String(selectedProfile.id) : ""} onValueChange={(value) => setSelectedProfileId(Number(value))}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择标准方案" />
                    </SelectTrigger>
                    <SelectContent>
                      {profiles.map((profile) => (
                        <SelectItem key={profile.id} value={String(profile.id)}>
                          {profile.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ),
              },
              {
                key: "target_type",
                node: (
                  <Select value={itemTargetType} onValueChange={setItemTargetType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部对象</SelectItem>
                      {targetTypes.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ),
              },
              {
                key: "metric",
                node: (
                  <Select value={itemMetricCode} onValueChange={setItemMetricCode}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部指标</SelectItem>
                      {metrics.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ),
              },
            ]}
            actions={
              <Button onClick={startCreateItem} disabled={!selectedProfile?.id}>
                <Plus className="mr-2 h-4 w-4" />
                新增指标
              </Button>
            }
          />
          <AdminPanel title="标杆指标列表" contentClassName="p-0">
            <BenchmarkItemsTable rows={items} onDetail={setItemDetail} onEdit={startEditItem} onDelete={(id) => deleteItem.mutate(id)} />
          </AdminPanel>
        </TabsContent>

        <TabsContent value="policy" className="space-y-4">
          <AdminPanel
            title="政策资料"
            actions={
              <Button onClick={() => syncPolicy.mutate()} disabled={syncPolicy.isPending}>
                <Download className="mr-2 h-4 w-4" />
                同步政策库
              </Button>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>资料名称</TableHead>
                    <TableHead>标准编号</TableHead>
                    <TableHead>来源网页</TableHead>
                    <TableHead>附件</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(policySourcesQuery.data ?? []).map((source) => (
                    <TableRow key={source.key}>
                      <TableCell className="font-medium">{source.name}</TableCell>
                      <TableCell>{source.standard_code}</TableCell>
                      <TableCell className="max-w-[360px] truncate">{source.page_url}</TableCell>
                      <TableCell className="max-w-[320px] truncate">{source.fallback_pdf_url}</TableCell>
                    </TableRow>
                  ))}
                  {(policySourcesQuery.data ?? []).length === 0 && <AdminTableStateRow colSpan={4}>暂无政策资料</AdminTableStateRow>}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>

          <AdminPanel title="政策标准列表" contentClassName="p-0">
            <ProfileTable rows={policyProfiles} selectedId={selectedProfile?.id} onDetail={setProfileDetail} readonly />
          </AdminPanel>
        </TabsContent>

        <TabsContent value="import" className="space-y-4">
          <AdminFilterBar
            fields={[
              {
                key: "profile",
                node: (
                  <Select value={selectedProfile?.id ? String(selectedProfile.id) : ""} onValueChange={(value) => setSelectedProfileId(Number(value))}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择导入目标方案" />
                    </SelectTrigger>
                    <SelectContent>
                      {editableProfiles.map((profile) => (
                        <SelectItem key={profile.id} value={String(profile.id)}>
                          {profile.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ),
              },
            ]}
            actions={
              <>
                <Button variant="outline" onClick={() => previewImport.mutate()} disabled={previewImport.isPending}>
                  预检
                </Button>
                <Button onClick={() => applyImport.mutate()} disabled={applyImport.isPending || !selectedProfile?.id || Boolean(importPreview?.invalid_count)}>
                  <Upload className="mr-2 h-4 w-4" />
                  导入
                </Button>
              </>
            }
          />
          <Textarea className="min-h-48 font-mono text-xs" value={csvText} onChange={(event) => setCsvText(event.target.value)} placeholder={`${templateHeader}\n`} />
          <AdminPanel title="导入预检" contentClassName="p-0">
            <ImportPreviewTable preview={importPreview} />
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
        onOpenChange={setItemOpen}
        onChange={setItemValues}
        onSave={() => saveItem.mutate()}
      />
      <DetailSheet title="标准方案详情" row={profileDetail} labels={profileLabels} onClose={() => setProfileDetail(null)} />
      <DetailSheet title="标杆指标详情" row={itemDetail} labels={itemLabels} onClose={() => setItemDetail(null)} />
    </PageContainer>
  )
}

function ProfileTable({
  rows,
  selectedId,
  onSelect,
  onDetail,
  onEdit,
  onDelete,
  readonly = false,
}: {
  rows: BenchmarkProfile[]
  selectedId?: number
  onSelect?: (id: number) => void
  onDetail: (row: BenchmarkProfile) => void
  onEdit?: (row: BenchmarkProfile) => void
  onDelete?: (id: number) => void
  readonly?: boolean
}) {
  return (
    <AdminDataTable className="rounded-none border-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>方案名称</TableHead>
            <TableHead>库类型</TableHead>
            <TableHead>标准编号</TableHead>
            <TableHead>来源</TableHead>
            <TableHead>有效期</TableHead>
            <TableHead>状态</TableHead>
            <TableHead className="text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} data-selected={selectedId === row.id}>
              <TableCell className="font-medium">{row.name}</TableCell>
              <TableCell>{libraryTypeLabel(row.library_type)}</TableCell>
              <TableCell>{display(row.standard_code)}</TableCell>
              <TableCell>
                <div>{display(row.source_name)}</div>
                <div className="max-w-52 truncate text-xs text-muted-foreground">{display(row.source_file_name)}</div>
              </TableCell>
              <TableCell className="tabular-nums">
                {displayDate(row.valid_from)} - {displayDate(row.valid_to)}
              </TableCell>
              <TableCell>
                <Badge variant={row.is_enabled ? "success" : "outline"}>{row.is_enabled ? "启用" : "停用"}</Badge>
              </TableCell>
              <TableCell className="space-x-2 text-right">
                <Button variant="secondary" size="sm" onClick={() => onDetail(row)}>
                  详情
                </Button>
                {!readonly && onSelect && (
                  <Button variant="outline" size="sm" onClick={() => onSelect(row.id)}>
                    选择
                  </Button>
                )}
                {!readonly && onEdit && (
                  <Button variant="outline" size="sm" onClick={() => onEdit(row)}>
                    编辑
                  </Button>
                )}
                {!readonly && onDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (window.confirm("确认删除该标准方案？")) onDelete(row.id)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && <AdminTableStateRow colSpan={7}>暂无标准方案</AdminTableStateRow>}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
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
    <AdminDataTable className="rounded-none border-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>对象</TableHead>
            <TableHead>指标</TableHead>
            <TableHead>适用条件</TableHead>
            <TableHead className="text-right">标杆值</TableHead>
            <TableHead className="text-right">先进/节能/准入</TableHead>
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
                <div className="text-xs text-muted-foreground">{optionLabel(targetTypes, row.target_type)}</div>
              </TableCell>
              <TableCell>
                <div>{row.metric_name || optionLabel(metrics, row.metric_code)}</div>
                <div className="text-xs text-muted-foreground">{display(row.reference_standard)}</div>
              </TableCell>
              <TableCell>
                <div>{display(row.applicable_category)}</div>
                <div className="max-w-56 truncate text-xs text-muted-foreground">{display(row.applicable_condition)}</div>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row.benchmark_value)} {row.unit}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row.advanced_value)} / {formatNumber(row.saving_value)} / {formatNumber(row.access_value)}
              </TableCell>
              <TableCell>
                <div>{display(row.standard_code)}</div>
                <div className="max-w-48 truncate text-xs text-muted-foreground">{display(row.source_name)}</div>
              </TableCell>
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
                    if (window.confirm("确认删除该标杆指标？")) onDelete(row.id)
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && <AdminTableStateRow colSpan={8}>暂无标杆指标</AdminTableStateRow>}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

function ImportPreviewTable({ preview }: { preview: ImportPreview | null }) {
  const rows = preview?.items ?? []
  return (
    <AdminDataTable className="rounded-none border-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>行号</TableHead>
            <TableHead>对象</TableHead>
            <TableHead>指标</TableHead>
            <TableHead className="text-right">标杆值</TableHead>
            <TableHead>状态</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((item) => (
            <TableRow key={item.row_number}>
              <TableCell className="tabular-nums">{item.row_number}</TableCell>
              <TableCell>{display(item.row.target_name || item.row.target_code || item.row.target_type)}</TableCell>
              <TableCell>{display(item.row.metric_name || item.row.metric_code)}</TableCell>
              <TableCell className="text-right tabular-nums">{display(item.row.benchmark_value)}</TableCell>
              <TableCell>{item.valid ? <Badge variant="success">可导入</Badge> : <Badge variant="destructive">{item.errors.join("、")}</Badge>}</TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && <AdminTableStateRow colSpan={5}>请先执行预检</AdminTableStateRow>}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: Option[]; onChange: (value: string) => void }) {
  return (
    <Field label={label}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑标准方案" : "新增标准方案"}</DialogTitle>
        </DialogHeader>
        <div className="grid max-h-[70vh] gap-4 overflow-y-auto pr-1 md:grid-cols-2">
          <Field label="方案名称">
            <Input value={values.name} onChange={(event) => onChange({ ...values, name: event.target.value })} />
          </Field>
          <SelectField label="库类型" value={values.library_type} options={editableLibraryTypes} onChange={(value) => onChange({ ...values, library_type: value })} />
          <Field label="行业">
            <Input value={values.industry_name} onChange={(event) => onChange({ ...values, industry_name: event.target.value })} />
          </Field>
          <Field label="适用范围">
            <Input value={values.scenario} onChange={(event) => onChange({ ...values, scenario: event.target.value })} />
          </Field>
          <Field label="来源名称">
            <Input value={values.source_name} onChange={(event) => onChange({ ...values, source_name: event.target.value })} />
          </Field>
          <Field label="标准编号">
            <Input value={values.standard_code} onChange={(event) => onChange({ ...values, standard_code: event.target.value })} />
          </Field>
          <Field label="来源 URL">
            <Input value={values.source_url} onChange={(event) => onChange({ ...values, source_url: event.target.value })} />
          </Field>
          <Field label="资料 Hash">
            <Input value={values.source_hash} onChange={(event) => onChange({ ...values, source_hash: event.target.value })} />
          </Field>
          <Field label="生效日期">
            <Input type="date" value={values.valid_from} onChange={(event) => onChange({ ...values, valid_from: event.target.value })} />
          </Field>
          <Field label="失效日期">
            <Input type="date" value={values.valid_to} onChange={(event) => onChange({ ...values, valid_to: event.target.value })} />
          </Field>
          <SelectField
            label="启用状态"
            value={values.is_enabled}
            options={[
              { value: "true", label: "启用" },
              { value: "false", label: "停用" },
            ]}
            onChange={(value) => onChange({ ...values, is_enabled: value })}
          />
          <Field label="版本状态">
            <Input value={values.version_status} onChange={(event) => onChange({ ...values, version_status: event.target.value })} />
          </Field>
          <div className="md:col-span-2">
            <Field label="备注">
              <Textarea value={values.remark} onChange={(event) => onChange({ ...values, remark: event.target.value })} />
            </Field>
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

function ItemDialog({
  open,
  values,
  editing,
  saving,
  onOpenChange,
  onChange,
  onSave,
}: {
  open: boolean
  values: typeof emptyItem
  editing: BenchmarkItem | null
  saving: boolean
  onOpenChange: (open: boolean) => void
  onChange: (values: typeof emptyItem) => void
  onSave: () => void
}) {
  const updateMetric = (value: string) => {
    const metric = metrics.find((item) => item.value === value)
    onChange({
      ...values,
      metric_code: value,
      metric_name: metric?.label ?? values.metric_name,
      unit: metric?.unit ?? values.unit,
      metric_direction: value === "energy_efficiency_level" ? "level_rank" : "lower_is_better",
    })
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑标杆指标" : "新增标杆指标"}</DialogTitle>
        </DialogHeader>
        <div className="grid max-h-[70vh] gap-4 overflow-y-auto pr-1 md:grid-cols-3">
          <SelectField label="对象层级" value={values.target_type} options={targetTypes} onChange={(value) => onChange({ ...values, target_type: value })} />
          <Field label="对象编码">
            <Input value={values.target_code} onChange={(event) => onChange({ ...values, target_code: event.target.value })} />
          </Field>
          <Field label="对象名称">
            <Input value={values.target_name} onChange={(event) => onChange({ ...values, target_name: event.target.value })} />
          </Field>
          <SelectField label="指标" value={values.metric_code} options={metrics} onChange={updateMetric} />
          <Field label="指标名称">
            <Input value={values.metric_name} onChange={(event) => onChange({ ...values, metric_name: event.target.value })} />
          </Field>
          <Field label="单位">
            <Input value={values.unit} onChange={(event) => onChange({ ...values, unit: event.target.value })} />
          </Field>
          <Field label="标杆值">
            <Input type="number" value={values.benchmark_value} onChange={(event) => onChange({ ...values, benchmark_value: event.target.value })} />
          </Field>
          <Field label="先进水平">
            <Input type="number" value={values.advanced_value} onChange={(event) => onChange({ ...values, advanced_value: event.target.value })} />
          </Field>
          <Field label="节能水平">
            <Input type="number" value={values.saving_value} onChange={(event) => onChange({ ...values, saving_value: event.target.value })} />
          </Field>
          <Field label="准入/基准水平">
            <Input type="number" value={values.access_value} onChange={(event) => onChange({ ...values, access_value: event.target.value })} />
          </Field>
          <SelectField label="指标方向" value={values.metric_direction} options={directions} onChange={(value) => onChange({ ...values, metric_direction: value })} />
          <Field label="标准编号">
            <Input value={values.standard_code} onChange={(event) => onChange({ ...values, standard_code: event.target.value })} />
          </Field>
          <Field label="适用行业">
            <Input value={values.applicable_industry} onChange={(event) => onChange({ ...values, applicable_industry: event.target.value })} />
          </Field>
          <Field label="适用分类">
            <Input value={values.applicable_category} onChange={(event) => onChange({ ...values, applicable_category: event.target.value })} />
          </Field>
          <Field label="适用条件">
            <Input value={values.applicable_condition} onChange={(event) => onChange({ ...values, applicable_condition: event.target.value })} />
          </Field>
          <Field label="参考标准">
            <Input value={values.reference_standard} onChange={(event) => onChange({ ...values, reference_standard: event.target.value })} />
          </Field>
          <Field label="预警阈值 %">
            <Input type="number" value={values.warning_threshold_pct} onChange={(event) => onChange({ ...values, warning_threshold_pct: event.target.value })} />
          </Field>
          <Field label="严重阈值 %">
            <Input type="number" value={values.severe_threshold_pct} onChange={(event) => onChange({ ...values, severe_threshold_pct: event.target.value })} />
          </Field>
          <Field label="来源名称">
            <Input value={values.source_name} onChange={(event) => onChange({ ...values, source_name: event.target.value })} />
          </Field>
          <Field label="来源 URL">
            <Input value={values.source_url} onChange={(event) => onChange({ ...values, source_url: event.target.value })} />
          </Field>
          <SelectField
            label="启用状态"
            value={values.is_enabled}
            options={[
              { value: "true", label: "启用" },
              { value: "false", label: "停用" },
            ]}
            onChange={(value) => onChange({ ...values, is_enabled: value })}
          />
          <div className="md:col-span-3">
            <Field label="备注">
              <Textarea value={values.remark} onChange={(event) => onChange({ ...values, remark: event.target.value })} />
            </Field>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={onSave} disabled={saving || !values.benchmark_value}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DetailSheet({ title, row, labels, onClose }: { title: string; row: Record<string, unknown> | null; labels: Record<string, string>; onClose: () => void }) {
  return (
    <Sheet open={Boolean(row)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <div className="mt-4 grid gap-3">
          {row &&
            Object.entries(labels).map(([key, label]) => (
              <div key={key} className="grid gap-1 border-border/70 border-b pb-2">
                <div className="text-muted-foreground text-xs">{label}</div>
                <div className="break-all text-sm">{display(row[key])}</div>
              </div>
            ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

const profileLabels: Record<string, string> = {
  name: "方案名称",
  library_type: "库类型",
  industry_name: "行业",
  scenario: "适用范围",
  source_name: "来源名称",
  source_url: "来源 URL",
  source_hash: "资料 Hash",
  source_file_name: "资料文件",
  standard_code: "标准编号",
  version_status: "版本状态",
  valid_from: "生效日期",
  valid_to: "失效日期",
  is_enabled: "启用状态",
  remark: "备注",
}

const itemLabels: Record<string, string> = {
  target_type: "对象层级",
  target_code: "对象编码",
  target_name: "对象名称",
  metric_code: "指标编码",
  metric_name: "指标名称",
  benchmark_value: "标杆值",
  unit: "单位",
  standard_code: "标准编号",
  applicable_industry: "适用行业",
  applicable_category: "适用分类",
  applicable_condition: "适用条件",
  metric_direction: "指标方向",
  advanced_value: "先进水平",
  saving_value: "节能水平",
  access_value: "准入/基准水平",
  reference_standard: "参考标准",
  source_name: "来源名称",
  source_url: "来源 URL",
  source_hash: "来源 Hash",
  warning_threshold_pct: "预警阈值",
  severe_threshold_pct: "严重阈值",
  confidence_level: "可信度",
  version_status: "版本状态",
  is_enabled: "启用状态",
  remark: "备注",
}
