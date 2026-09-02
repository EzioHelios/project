import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { RefreshCw, Settings } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminEmptyState, AdminPageScaffold, AdminPanel, AdminTableStateRow, AdminTabsList, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { type PageResult, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"

type BenchmarkProfile = {
  id: number
  name: string
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
  { value: "kwh_per_run_hour", label: "单位运行小时用电" },
  { value: "kwh_per_workload", label: "单位作业量用电" },
  { value: "kgce_per_unit", label: "单位产品综合能耗" },
  { value: "kgce_per_10k_value", label: "单位产值综合能耗" },
  { value: "tce_per_m2", label: "单位面积综合能耗" },
  { value: "kwh_per_m2", label: "单位面积用电量" },
]

const statusLabels: Record<string, string> = {
  ok: "达标",
  warning: "预警",
  severe: "重点偏差",
  missing_benchmark: "缺少标杆",
  invalid_denominator: "分母缺失",
  unit_mismatch: "单位不一致",
}

const defaultFilters = {
  periodStart: "",
  periodEnd: "",
  profileId: "auto",
  targetType: "device",
  metricCode: "kwh_per_run_hour",
}

type BenchmarkFilters = typeof defaultFilters

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function targetTypeLabel(value?: string | null) {
  return targetTypes.find((item) => item.value === value)?.label ?? value ?? "-"
}

function metricLabel(value?: string | null) {
  return metrics.find((item) => item.value === value)?.label ?? value ?? "-"
}

function statusBadge(status?: string | null) {
  const label = statusLabels[status || ""] ?? status ?? "-"
  if (status === "ok") return <Badge variant="success">{label}</Badge>
  if (status === "severe") return <Badge variant="destructive">{label}</Badge>
  if (status === "warning") return <Badge variant="warning">{label}</Badge>
  return <Badge variant="outline">{label}</Badge>
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

export function EnergyBenchmarkPanel({ header }: { header?: ReactNode }) {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<BenchmarkFilters>(defaultFilters)
  const params = useMemo(() => buildParams(filters), [filters])

  const profilesQuery = useQuery<PageResult<BenchmarkProfile>>({
    queryKey: ["energy-benchmark", "profiles"],
    queryFn: () => requestPage<BenchmarkProfile>("/api/energy/benchmark/profiles", { is_enabled: true, limit: 200 }),
  })
  const profiles = profilesQuery.data?.items ?? []

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

  const baseline = baselineQuery.data?.data.items ?? []
  const comparisons = comparisonsQuery.data?.data.items ?? []
  const conclusions = conclusionsQuery.data?.data
  const recommendations = recommendationsQuery.data?.data.items ?? []

  return (
    <Tabs defaultValue="baseline" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="baseline">历史基线</TabsTrigger>
            <TabsTrigger value="comparison">设备/工序对标</TabsTrigger>
            <TabsTrigger value="conclusion">对标结论</TabsTrigger>
            <TabsTrigger value="recommendation">整改建议</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <ContextBar
            actions={
              <>
                <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ["energy-benchmark"] })}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
                <Button asChild>
                  <Link to="/data/energy-benchmark">
                    <Settings className="mr-2 h-4 w-4" />
                    维护标杆
                  </Link>
                </Button>
              </>
            }
          >
            <Input type="date" value={filters.periodStart} onChange={(event) => setFilters((state) => ({ ...state, periodStart: event.target.value }))} />
            <Input type="date" value={filters.periodEnd} onChange={(event) => setFilters((state) => ({ ...state, periodEnd: event.target.value }))} />
            <Select value={filters.profileId} onValueChange={(value) => setFilters((state) => ({ ...state, profileId: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">自动匹配方案</SelectItem>
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
      >
        <TabsContent value="baseline">
          <AdminPanel title="历史基线" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <BaselineTable rows={baseline} />
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="comparison" className="space-y-4">
          <MetricStrip className="md:grid-cols-4 xl:grid-cols-4">
            <MetricTile label="对标对象" value={conclusions?.summary.total ?? comparisons.length} />
            <MetricTile label="重点偏差" value={conclusions?.summary.status_counts?.severe ?? 0} />
            <MetricTile label="预警对象" value={conclusions?.summary.status_counts?.warning ?? 0} />
            <MetricTile label="节能潜力" value={formatNumber(conclusions?.summary.saving_potential)} unit={conclusions?.summary.unit} />
          </MetricStrip>
          <AdminPanel title="设备/工序对标" contentClassName="p-0">
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
              {recommendations.length === 0 && <AdminEmptyState title="暂无整改建议" />}
            </div>
            <AdminPanel title="关联入口" contentClassName="grid gap-2">
              <Button variant="outline" asChild>
                <Link to="/energy/intensity">能源强度</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to="/data/terminals">设备台账</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to="/data/energy-benchmark">标杆配置</Link>
              </Button>
            </AdminPanel>
          </div>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
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
        {rows.length === 0 && <AdminTableStateRow colSpan={6}>暂无数据</AdminTableStateRow>}
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
        {rows.length === 0 && <AdminTableStateRow colSpan={compact ? 5 : 7}>暂无数据</AdminTableStateRow>}
      </TableBody>
    </Table>
  )
}
