import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Download, Plus, RefreshCw, Trash2, Upload } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTableStateRow, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { fetchCarbonApi } from "@/components/carbon/analytics-panels"
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

type BenchmarkProfile = {
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

type BenchmarkItem = {
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
}

type BaselineItem = {
  target_type: string
  target_code?: string | null
  target_name?: string | null
  metric_code: string
  best_value?: number | null
  p25_value?: number | null
  average_value?: number | null
  period_count?: number
  unit?: string
}

type ComparisonItem = {
  target_type: string
  target_code?: string | null
  target_name?: string | null
  metric_code: string
  metric_name?: string | null
  actual_value?: number | null
  benchmark_value?: number | null
  unit?: string | null
  deviation_pct?: number | null
  status: string
  saving_potential?: number | null
  data_quality?: string | null
  profile_name?: string | null
  source_name?: string | null
  confidence_level?: string | null
}

type ConclusionData = {
  summary: {
    total: number
    status_counts: Record<string, number>
    saving_potential: number
    unit: string
  }
  top_deviations: ComparisonItem[]
  missing_benchmarks: ComparisonItem[]
}

type Recommendation = {
  code: string
  priority: string
  title: string
  target: string
  evidence: Record<string, unknown>
  steps: string[]
  expected_effect: string
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

const statusLabels: Record<string, string> = {
  ok: "达标",
  warning: "预警",
  severe: "重点偏差",
  missing_benchmark: "缺少标杆",
  invalid_denominator: "分母缺失",
  unit_mismatch: "单位不一致",
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function statusBadge(status?: string | null) {
  const label = statusLabels[status || ""] ?? status ?? "-"
  if (status === "ok") return <Badge className="bg-emerald-600 hover:bg-emerald-600">{label}</Badge>
  if (status === "severe") return <Badge variant="destructive">{label}</Badge>
  if (status === "warning") return <Badge className="bg-amber-500 hover:bg-amber-500">{label}</Badge>
  return <Badge variant="outline">{label}</Badge>
}

function targetTypeLabel(value?: string | null) {
  return targetTypes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function metricLabel(value?: string | null) {
  return metrics.find((item) => item.value === value)?.label ?? value ?? "-"
}

function buildParams(filters: BenchmarkFilters) {
  const params = new URLSearchParams()
  if (filters.periodStart) params.set("period_start", filters.periodStart)
  if (filters.periodEnd) params.set("period_end", filters.periodEnd)
  if (filters.profileId && filters.profileId !== "auto") params.set("profile_id", filters.profileId)
  params.set("target_type", filters.targetType)
  params.set("metric_code", filters.metricCode)
  params.set("limit", "80")
  return params
}

type BenchmarkFilters = {
  periodStart: string
  periodEnd: string
  profileId: string
  targetType: string
  metricCode: string
}

const defaultFilters: BenchmarkFilters = {
  periodStart: "",
  periodEnd: "",
  profileId: "auto",
  targetType: "device",
  metricCode: "kwh_per_run_hour",
}

export function EnergyBenchmarkPanel() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<BenchmarkFilters>(defaultFilters)
  const [profileOpen, setProfileOpen] = useState(false)
  const [itemOpen, setItemOpen] = useState(false)
  const [csvOpen, setCsvOpen] = useState(false)
  const [profileForm, setProfileForm] = useState({ name: "", industry_name: "", scenario: "", source_name: "", valid_from: "", valid_to: "", remark: "" })
  const [itemForm, setItemForm] = useState({
    target_type: "device",
    target_code: "",
    target_name: "",
    metric_code: "kwh_per_run_hour",
    benchmark_value: "",
    unit: "kWh/h",
    source_name: "",
    confidence_level: "medium",
  })
  const [csvText, setCsvText] = useState("")

  const profilesQuery = useQuery<PageResult<BenchmarkProfile>>({
    queryKey: ["energy-benchmark", "profiles"],
    queryFn: () => requestPage<BenchmarkProfile>("/api/energy/benchmark/profiles", { limit: 200 }),
  })
  const profiles = profilesQuery.data?.items ?? []
  const selectedProfileId = filters.profileId === "auto" ? profiles[0]?.id : Number(filters.profileId)
  const params = useMemo(() => buildParams(filters), [filters])

  const itemsQuery = useQuery<PageResult<BenchmarkItem>>({
    queryKey: ["energy-benchmark", "items", selectedProfileId, filters.targetType, filters.metricCode],
    queryFn: () =>
      requestPage<BenchmarkItem>("/api/energy/benchmark/items", {
        profile_id: selectedProfileId,
        target_type: filters.targetType,
        metric_code: filters.metricCode,
        limit: 200,
      }),
    enabled: !!selectedProfileId,
  })
  const baselineQuery = useQuery({
    queryKey: ["energy-benchmark", "baseline", params.toString()],
    queryFn: () => fetchCarbonApi<{ items: BaselineItem[] }>(`/api/energy/benchmark/baseline?${params.toString()}`),
  })
  const comparisonsQuery = useQuery({
    queryKey: ["energy-benchmark", "comparisons", params.toString()],
    queryFn: () => fetchCarbonApi<{ items: ComparisonItem[]; total: number }>(`/api/energy/benchmark/comparisons?${params.toString()}`),
  })
  const conclusionsQuery = useQuery({
    queryKey: ["energy-benchmark", "conclusions", params.toString()],
    queryFn: () => fetchCarbonApi<ConclusionData>(`/api/energy/benchmark/conclusions?${params.toString()}`),
  })
  const recommendationsQuery = useQuery({
    queryKey: ["energy-benchmark", "recommendations", params.toString()],
    queryFn: () => fetchCarbonApi<{ items: Recommendation[] }>(`/api/energy/benchmark/recommendations?${params.toString()}`),
  })

  useEffect(() => {
    setItemForm((state) => ({
      ...state,
      target_type: filters.targetType,
      metric_code: filters.metricCode,
      unit: metrics.find((item) => item.value === filters.metricCode)?.unit ?? state.unit,
    }))
  }, [filters.targetType, filters.metricCode])

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["energy-benchmark"] })
  }

  const createProfile = useMutation({
    mutationFn: () =>
      request<BenchmarkProfile>("/api/energy/benchmark/profiles", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(profileForm) }),
    onSuccess: () => {
      toast.success("标杆方案已保存")
      setProfileOpen(false)
      setProfileForm({ name: "", industry_name: "", scenario: "", source_name: "", valid_from: "", valid_to: "", remark: "" })
      refreshAll()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const createItem = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<BenchmarkItem>("/api/energy/benchmark/items", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: () => {
      toast.success("标杆项已保存")
      setItemOpen(false)
      setItemForm((state) => ({ ...state, target_code: "", target_name: "", benchmark_value: "", source_name: "" }))
      refreshAll()
    },
    onError: (error) => toast.error("保存失败", { description: error instanceof Error ? error.message : "请检查输入" }),
  })

  const deleteItem = useMutation({
    mutationFn: (itemId: number) => request(`/api/energy/benchmark/items/${itemId}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("标杆项已删除")
      refreshAll()
    },
    onError: (error) => toast.error("删除失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const generate = useMutation({
    mutationFn: (method: string) =>
      request("/api/energy/benchmark/generate-from-history", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          period_start: filters.periodStart || null,
          period_end: filters.periodEnd || null,
          target_type: filters.targetType,
          metric_code: filters.metricCode,
          profile_name: `行业标杆方案-${targetTypeLabel(filters.targetType)}-${metricLabel(filters.metricCode)}`,
          method,
        }),
      }),
    onSuccess: () => {
      toast.success("标杆方案已生成")
      refreshAll()
    },
    onError: (error) => toast.error("生成失败", { description: error instanceof Error ? error.message : "请检查历史数据" }),
  })

  const importCsv = useMutation({
    mutationFn: async () => {
      const rows = parseCsv(csvText)
      for (const row of rows) {
        await request<BenchmarkItem>("/api/energy/benchmark/items", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            profile_id: selectedProfileId,
            target_type: row.target_type || filters.targetType,
            target_code: row.target_code,
            target_name: row.target_name,
            metric_code: row.metric_code || filters.metricCode,
            benchmark_value: row.benchmark_value,
            unit: row.unit || metrics.find((item) => item.value === (row.metric_code || filters.metricCode))?.unit,
            source_name: row.source_name,
            confidence_level: row.confidence_level || "medium",
          }),
        })
      }
      return rows.length
    },
    onSuccess: (count) => {
      toast.success(`已导入 ${count} 条标杆项`)
      setCsvOpen(false)
      setCsvText("")
      refreshAll()
    },
    onError: (error) => toast.error("导入失败", { description: error instanceof Error ? error.message : "请检查 CSV 内容" }),
  })

  const comparisons = comparisonsQuery.data?.data.items ?? []
  const baseline = baselineQuery.data?.data.items ?? []
  const conclusions = conclusionsQuery.data?.data
  const recommendations = recommendationsQuery.data?.data.items ?? []

  return (
    <PageSection className="space-y-4">
      <Tabs defaultValue="baseline" className="space-y-4">
        <AdminPageScaffold
          tabs={
            <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5">
              <TabsTrigger value="baseline">历史基线</TabsTrigger>
              <TabsTrigger value="library">行业标杆库</TabsTrigger>
              <TabsTrigger value="comparison">设备/工序对标</TabsTrigger>
              <TabsTrigger value="conclusion">对标结论</TabsTrigger>
              <TabsTrigger value="recommendation">整改建议</TabsTrigger>
            </TabsList>
          }
          filters={
            <ContextBar
              actions={
                <Button variant="outline" onClick={refreshAll}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
              }
            >
              <Input type="date" value={filters.periodStart} onChange={(event) => setFilters((state) => ({ ...state, periodStart: event.target.value }))} />
              <Input type="date" value={filters.periodEnd} onChange={(event) => setFilters((state) => ({ ...state, periodEnd: event.target.value }))} />
              <Select value={filters.profileId} onValueChange={(value) => setFilters((state) => ({ ...state, profileId: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">最新启用方案</SelectItem>
                  {profiles.map((profile) => (
                    <SelectItem key={profile.id} value={String(profile.id)}>
                      {profile.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filters.targetType} onValueChange={(value) => setFilters((state) => ({ ...state, targetType: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {targetTypes.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filters.metricCode} onValueChange={(value) => setFilters((state) => ({ ...state, metricCode: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {metrics.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </ContextBar>
          }
          metrics={
            <MetricStrip className="md:grid-cols-4 xl:grid-cols-4">
              <StatCard label="对标对象" value={conclusions?.summary.total ?? comparisons.length} />
              <StatCard label="重点偏差" value={conclusions?.summary.status_counts?.severe ?? 0} />
              <StatCard label="预警对象" value={conclusions?.summary.status_counts?.warning ?? 0} />
              <StatCard label="节能潜力" value={formatNumber(conclusions?.summary.saving_potential)} suffix={conclusions?.summary.unit} />
            </MetricStrip>
          }
        >
          <TabsContent value="baseline" className="space-y-4">
            <AdminPanel
              title="历史基线"
              actions={
                <>
                  <Button variant="outline" size="sm" onClick={() => generate.mutate("best_period")} disabled={generate.isPending}>
                    <Download className="mr-2 h-4 w-4" />
                    最优基线生成
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => generate.mutate("p25")} disabled={generate.isPending}>
                    P25 生成
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => generate.mutate("average")} disabled={generate.isPending}>
                    均值生成
                  </Button>
                </>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <BaselineTable rows={baseline} />
              </AdminDataTable>
            </AdminPanel>
          </TabsContent>

          <TabsContent value="library" className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
              <AdminPanel
                title="标杆方案"
                actions={
                  <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        新增
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新增标杆方案</DialogTitle>
                      </DialogHeader>
                      <ProfileForm value={profileForm} onChange={setProfileForm} />
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setProfileOpen(false)}>
                          取消
                        </Button>
                        <Button onClick={() => createProfile.mutate()} disabled={!profileForm.name.trim() || createProfile.isPending}>
                          保存
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                }
                contentClassName="space-y-3"
              >
                {profiles.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    className={`w-full rounded-md border p-3 text-left transition-colors ${selectedProfileId === profile.id ? "border-primary bg-primary/5" : "border-border/60 hover:bg-accent/40"}`}
                    onClick={() => setFilters((state) => ({ ...state, profileId: String(profile.id) }))}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium">{profile.name}</div>
                      <Badge variant={profile.is_enabled ? "secondary" : "outline"}>{profile.is_enabled ? "启用" : "停用"}</Badge>
                    </div>
                    <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                      <span>{profile.industry_name || "行业未标注"}</span>
                      <span>{profile.source_name || "来源未标注"}</span>
                    </div>
                  </button>
                ))}
                {profiles.length === 0 && <EmptyText text="暂无标杆方案" />}
              </AdminPanel>

              <AdminPanel
                title="标杆项"
                actions={
                  <>
                    <Dialog open={csvOpen} onOpenChange={setCsvOpen}>
                      <DialogTrigger asChild>
                        <Button variant="outline" size="sm" disabled={!selectedProfileId}>
                          <Upload className="mr-2 h-4 w-4" />
                          CSV 导入
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>CSV 导入</DialogTitle>
                        </DialogHeader>
                        <Textarea
                          value={csvText}
                          onChange={(event) => setCsvText(event.target.value)}
                          className="min-h-52 font-mono text-xs"
                          placeholder="target_type,target_code,target_name,metric_code,benchmark_value,unit,source_name,confidence_level"
                        />
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setCsvOpen(false)}>
                            取消
                          </Button>
                          <Button onClick={() => importCsv.mutate()} disabled={!csvText.trim() || importCsv.isPending || !selectedProfileId}>
                            导入
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                    <Dialog open={itemOpen} onOpenChange={setItemOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm" disabled={!selectedProfileId}>
                          <Plus className="mr-2 h-4 w-4" />
                          新增
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>新增标杆项</DialogTitle>
                        </DialogHeader>
                        <ItemForm value={itemForm} onChange={setItemForm} />
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setItemOpen(false)}>
                            取消
                          </Button>
                          <Button
                            onClick={() => createItem.mutate({ ...itemForm, profile_id: selectedProfileId })}
                            disabled={!selectedProfileId || !itemForm.benchmark_value || createItem.isPending}
                          >
                            保存
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </>
                }
                contentClassName="p-0"
              >
                <AdminDataTable className="rounded-none border-0">
                  <BenchmarkItemsTable rows={itemsQuery.data?.items ?? []} onDelete={(itemId) => deleteItem.mutate(itemId)} />
                </AdminDataTable>
              </AdminPanel>
            </div>
          </TabsContent>

          <TabsContent value="comparison">
            <AdminPanel
              title="设备/工序对标"
              actions={
                <>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/energy/analysis">能源分析</Link>
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/energy/consumption">能耗查询</Link>
                  </Button>
                </>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <ComparisonTable rows={comparisons} />
              </AdminDataTable>
            </AdminPanel>
          </TabsContent>

          <TabsContent value="conclusion">
            <div className="grid gap-4 xl:grid-cols-2">
              <AdminPanel title="偏差排行" contentClassName="p-0">
                <AdminDataTable className="rounded-none border-0">
                  <ComparisonTable rows={conclusions?.top_deviations ?? []} compact />
                </AdminDataTable>
              </AdminPanel>
              <AdminPanel title="覆盖缺口" contentClassName="p-0">
                <AdminDataTable className="rounded-none border-0">
                  <ComparisonTable rows={conclusions?.missing_benchmarks ?? []} compact />
                </AdminDataTable>
              </AdminPanel>
            </div>
          </TabsContent>

          <TabsContent value="recommendation">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
              <div className="space-y-3">
                {recommendations.map((item) => (
                  <AdminPanel key={item.code}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{item.title}</div>
                        <div className="mt-1 text-sm text-muted-foreground">{item.target}</div>
                      </div>
                      <Badge variant={item.priority === "high" ? "destructive" : "secondary"}>{item.priority === "high" ? "高优先级" : "中优先级"}</Badge>
                    </div>
                    <div className="mt-4 grid gap-2 text-sm">
                      {item.steps.map((step) => (
                        <div key={step} className="rounded-md bg-muted/60 px-3 py-2">
                          {step}
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 text-sm text-muted-foreground">{item.expected_effect}</div>
                  </AdminPanel>
                ))}
                {recommendations.length === 0 && <EmptyText text="当前筛选条件下暂无整改建议" />}
              </div>
              <AdminPanel title="关联入口" contentClassName="grid gap-2">
                <Button variant="outline" asChild>
                  <Link to="/energy/intensity">能源强度</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link to="/data/terminals">设备台账</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link to="/energy/balance">能效平衡</Link>
                </Button>
              </AdminPanel>
            </div>
          </TabsContent>
        </AdminPageScaffold>
      </Tabs>
    </PageSection>
  )
}

function StatCard({ label, value, suffix }: { label: string; value: string | number; suffix?: string }) {
  return <MetricTile label={label} value={value} unit={suffix} />
}

function BaselineTable({ rows }: { rows: BaselineItem[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>对象</TableHead>
          <TableHead>指标</TableHead>
          <TableHead className="text-right">最优基线</TableHead>
          <TableHead className="text-right">P25</TableHead>
          <TableHead className="text-right">均值</TableHead>
          <TableHead className="text-right">期间数</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.target_type}-${row.target_code}-${row.metric_code}`}>
            <TableCell>
              <div className="font-medium">{row.target_name || row.target_code || "-"}</div>
              <div className="text-xs text-muted-foreground">{targetTypeLabel(row.target_type)}</div>
            </TableCell>
            <TableCell>{metricLabel(row.metric_code)}</TableCell>
            <TableCell className="text-right">{formatNumber(row.best_value)}</TableCell>
            <TableCell className="text-right">{formatNumber(row.p25_value)}</TableCell>
            <TableCell className="text-right">{formatNumber(row.average_value)}</TableCell>
            <TableCell className="text-right">{row.period_count ?? 0}</TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <EmptyRow colSpan={6} />}
      </TableBody>
    </Table>
  )
}

function BenchmarkItemsTable({ rows, onDelete }: { rows: BenchmarkItem[]; onDelete: (itemId: number) => void }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>对象</TableHead>
          <TableHead>指标</TableHead>
          <TableHead className="text-right">标杆值</TableHead>
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
            <TableCell className="text-right">
              {formatNumber(row.benchmark_value)} {row.unit}
            </TableCell>
            <TableCell>
              <div>{row.source_name || "-"}</div>
              <div className="text-xs text-muted-foreground">{row.confidence_level || "-"}</div>
            </TableCell>
            <TableCell>
              <Badge variant={row.is_enabled ? "secondary" : "outline"}>{row.is_enabled ? "启用" : "停用"}</Badge>
            </TableCell>
            <TableCell className="text-right">
              <Button variant="ghost" size="icon" onClick={() => onDelete(row.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <EmptyRow colSpan={6} />}
      </TableBody>
    </Table>
  )
}

function ComparisonTable({ rows, compact = false }: { rows: ComparisonItem[]; compact?: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>对象</TableHead>
          {!compact && <TableHead>指标</TableHead>}
          <TableHead className="text-right">实际值</TableHead>
          <TableHead className="text-right">标杆值</TableHead>
          <TableHead className="text-right">偏差率</TableHead>
          {!compact && <TableHead className="text-right">节能潜力</TableHead>}
          <TableHead>状态</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={`${row.target_type}-${row.target_code}-${row.metric_code}-${index}`}>
            <TableCell>
              <div className="font-medium">{row.target_name || row.target_code || "-"}</div>
              <div className="text-xs text-muted-foreground">{targetTypeLabel(row.target_type)}</div>
            </TableCell>
            {!compact && <TableCell>{row.metric_name || metricLabel(row.metric_code)}</TableCell>}
            <TableCell className="text-right">{formatNumber(row.actual_value)}</TableCell>
            <TableCell className="text-right">{formatNumber(row.benchmark_value)}</TableCell>
            <TableCell className="text-right">{row.deviation_pct === null || row.deviation_pct === undefined ? "-" : `${formatNumber(row.deviation_pct)}%`}</TableCell>
            {!compact && <TableCell className="text-right">{formatNumber(row.saving_potential)}</TableCell>}
            <TableCell>{statusBadge(row.status)}</TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && <EmptyRow colSpan={compact ? 5 : 7} />}
      </TableBody>
    </Table>
  )
}

function ProfileForm({
  value,
  onChange,
}: {
  value: Record<string, string>
  onChange: (value: { name: string; industry_name: string; scenario: string; source_name: string; valid_from: string; valid_to: string; remark: string }) => void
}) {
  const update = (key: string, next: string) =>
    onChange({ ...value, [key]: next } as { name: string; industry_name: string; scenario: string; source_name: string; valid_from: string; valid_to: string; remark: string })
  return (
    <div className="grid gap-4">
      <Field label="方案名称" value={value.name} onChange={(next) => update("name", next)} />
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="行业" value={value.industry_name} onChange={(next) => update("industry_name", next)} />
        <Field label="适用范围" value={value.scenario} onChange={(next) => update("scenario", next)} />
      </div>
      <Field label="来源" value={value.source_name} onChange={(next) => update("source_name", next)} />
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="生效日期" type="date" value={value.valid_from} onChange={(next) => update("valid_from", next)} />
        <Field label="截止日期" type="date" value={value.valid_to} onChange={(next) => update("valid_to", next)} />
      </div>
      <div className="grid gap-2">
        <Label>备注</Label>
        <Textarea value={value.remark} onChange={(event) => update("remark", event.target.value)} />
      </div>
    </div>
  )
}

function ItemForm({
  value,
  onChange,
}: {
  value: Record<string, string>
  onChange: (value: {
    target_type: string
    target_code: string
    target_name: string
    metric_code: string
    benchmark_value: string
    unit: string
    source_name: string
    confidence_level: string
  }) => void
}) {
  const update = (key: string, next: string) =>
    onChange({ ...value, [key]: next } as {
      target_type: string
      target_code: string
      target_name: string
      metric_code: string
      benchmark_value: string
      unit: string
      source_name: string
      confidence_level: string
    })
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-2">
          <Label>对象类型</Label>
          <Select value={value.target_type} onValueChange={(next) => update("target_type", next)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {targetTypes.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label>指标</Label>
          <Select
            value={value.metric_code}
            onValueChange={(next) => {
              onChange({ ...value, metric_code: next, unit: metrics.find((item) => item.value === next)?.unit ?? value.unit } as {
                target_type: string
                target_code: string
                target_name: string
                metric_code: string
                benchmark_value: string
                unit: string
                source_name: string
                confidence_level: string
              })
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {metrics.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="对象编码" value={value.target_code} onChange={(next) => update("target_code", next)} />
        <Field label="对象名称" value={value.target_name} onChange={(next) => update("target_name", next)} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="标杆值" type="number" value={value.benchmark_value} onChange={(next) => update("benchmark_value", next)} />
        <Field label="单位" value={value.unit} onChange={(next) => update("unit", next)} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="来源" value={value.source_name} onChange={(next) => update("source_name", next)} />
        <Field label="置信度" value={value.confidence_level} onChange={(next) => update("confidence_level", next)} />
      </div>
    </div>
  )
}

function Field({ label, value, onChange, type = "text" }: { label: string; value?: string; onChange: (value: string) => void; type?: string }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type={type} value={value ?? ""} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function EmptyRow({ colSpan }: { colSpan: number }) {
  return <AdminTableStateRow colSpan={colSpan}>暂无数据</AdminTableStateRow>
}

function EmptyText({ text }: { text: string }) {
  return <AdminEmptyState title={text} />
}

function parseCsv(value: string) {
  const [headerLine, ...lines] = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!headerLine) return []
  const headers = headerLine.split(",").map((item) => item.trim())
  return lines.map((line) => {
    const cells = line.split(",").map((item) => item.trim())
    return Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ""]))
  })
}
