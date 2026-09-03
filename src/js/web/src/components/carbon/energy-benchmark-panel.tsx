import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import type { EChartsOption } from "echarts"
import { RefreshCw, Settings } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createComboTrendChartOption, createRankingChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"

type BenchmarkProfile = {
  id: number
  name: string
  library_type?: string | null
  is_enabled: boolean
}

type SummaryData = {
  summary: {
    total: number
    compared: number
    warning_total: number
    severe_total: number
    coverage_rate: number
    average_deviation_pct?: number | null
    saving_potential: number
    unit?: string | null
  }
  metric: { code: string; name: string; unit: string }
}

type ComparisonItem = {
  target_type?: string | null
  target_code?: string | null
  target_name?: string | null
  metric_code?: string | null
  metric_name?: string | null
  actual_value?: number | null
  benchmark_value?: number | null
  unit?: string | null
  deviation_pct?: number | null
  status?: string | null
  saving_potential?: number | null
  denominator?: number | null
  data_quality?: string | null
  profile_name?: string | null
  standard_code?: string | null
  source_url?: string | null
  source_hash?: string | null
  applicable_condition?: string | null
  reference_standard?: string | null
  advanced_value?: number | null
  saving_value?: number | null
  access_value?: number | null
}

type DistributionItem = {
  name: string
  status: string
  value: number
}

type TrendItem = {
  period: string
  actual?: number | null
  benchmark?: number | null
  severe_count?: number | null
  warning_count?: number | null
}

type DetailData = {
  item?: ComparisonItem | null
  data_sources?: Record<string, unknown>
}

const targetTypes = [
  { value: "enterprise", label: "基地总体" },
  { value: "area", label: "区域" },
  { value: "use_system", label: "用能系统" },
  { value: "device_type", label: "设备类型" },
  { value: "device", label: "设备" },
  { value: "line", label: "产线/工序" },
  { value: "product", label: "产品" },
]

const metrics = [
  { value: "kwh_per_m2", label: "单位面积用电量" },
  { value: "tce_per_m2", label: "单位面积综合能耗" },
  { value: "kgce_per_10k_value", label: "单位产值综合能耗" },
  { value: "kgce_per_unit", label: "单位产品综合能耗" },
  { value: "kwh_per_run_hour", label: "单位运行小时用电" },
  { value: "kwh_per_workload", label: "单位作业量用电" },
  { value: "energy_efficiency_level", label: "设备能效等级" },
]

const libraryTypes = [
  { value: "auto", label: "自动匹配" },
  { value: "policy_industry", label: "政策标杆库" },
  { value: "equipment_efficiency", label: "设备能效等级库" },
  { value: "enterprise_standard", label: "企业内部标准库" },
]

const statusLabels: Record<string, string> = {
  ok: "达标",
  warning: "接近预警",
  severe: "明显偏高",
  missing_benchmark: "缺标杆",
  invalid_denominator: "缺分母",
  unit_mismatch: "单位不一致",
}

const defaultFilters = {
  period_start: "2026-01-01",
  period_end: "2026-12-31",
  library_type: "auto",
  profile_id: "auto",
  target_type: "device",
  metric_code: "kwh_per_run_hour",
  target_code: "",
}

type BenchmarkFilters = typeof defaultFilters

function formatNumber(value: number | string | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function optionLabel(options: { value: string; label: string }[], value?: string | null) {
  return options.find((item) => item.value === value)?.label ?? value ?? "-"
}

function statusBadge(status?: string | null) {
  const label = statusLabels[status || ""] ?? status ?? "-"
  if (status === "ok") return <Badge variant="success">{label}</Badge>
  if (status === "severe") return <Badge variant="destructive">{label}</Badge>
  if (status === "warning") return <Badge variant="warning">{label}</Badge>
  return <Badge variant="outline">{label}</Badge>
}

function levelGap(item: ComparisonItem) {
  if (item.actual_value == null || item.benchmark_value == null) return null
  return Math.max(0, Number(item.actual_value) - Number(item.benchmark_value))
}

function resultGapValue(item: ComparisonItem, isLevelMetric: boolean) {
  if (isLevelMetric) {
    const gap = levelGap(item)
    return gap && gap > 0 ? `+${formatNumber(gap, 0)} 级` : "-"
  }
  return `${formatNumber(item.deviation_pct)}%`
}

function buildParams(filters: BenchmarkFilters) {
  const params: Record<string, string | number | undefined> = {
    period_start: filters.period_start,
    period_end: filters.period_end,
    target_type: filters.target_type,
    metric_code: filters.metric_code,
    target_code: filters.target_code.trim() || undefined,
    limit: 120,
  }
  if (filters.profile_id !== "auto") params.profile_id = filters.profile_id
  if (filters.library_type !== "auto") params.library_type = filters.library_type
  return params
}

function queryString(filters: BenchmarkFilters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(buildParams(filters))) {
    if (value !== undefined && value !== "") params.set(key, String(value))
  }
  return params.toString()
}

export function EnergyBenchmarkPanel({ header }: { header?: ReactNode }) {
  const theme = useAdminChartTheme("energy")
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<BenchmarkFilters>(defaultFilters)
  const [selectedItem, setSelectedItem] = useState<ComparisonItem | null>(null)
  const params = useMemo(() => queryString(filters), [filters])

  const profilesQuery = useQuery<PageResult<BenchmarkProfile>>({
    queryKey: ["energy-benchmark", "profiles", filters.library_type],
    queryFn: () =>
      requestPage<BenchmarkProfile>("/api/energy/benchmark/profiles", {
        is_enabled: true,
        library_type: filters.library_type === "auto" ? undefined : filters.library_type,
        limit: 200,
      }),
  })
  const profiles = profilesQuery.data?.items ?? []

  const summaryQuery = useQuery({
    queryKey: ["energy-benchmark", "summary", params],
    queryFn: () => request<SummaryData>(`/api/energy/benchmark/summary?${params}`).then((response) => response.data),
  })
  const comparisonsQuery = useQuery({
    queryKey: ["energy-benchmark", "comparisons", params],
    queryFn: () => request<{ items: ComparisonItem[]; total: number }>(`/api/energy/benchmark/comparisons?${params}`).then((response) => response.data),
  })
  const distributionQuery = useQuery({
    queryKey: ["energy-benchmark", "distribution", params],
    queryFn: () => request<{ items: DistributionItem[] }>(`/api/energy/benchmark/distribution?${params}`).then((response) => response.data),
  })
  const trendQuery = useQuery({
    queryKey: ["energy-benchmark", "trend", params],
    queryFn: () => request<{ items: TrendItem[] }>(`/api/energy/benchmark/trend?${params}`).then((response) => response.data),
  })
  const detailQuery = useQuery({
    queryKey: ["energy-benchmark", "detail", params, selectedItem?.target_code],
    queryFn: () =>
      request<DetailData>(`/api/energy/benchmark/detail?${queryString({ ...filters, target_code: selectedItem?.target_code ?? "" })}`).then((response) => response.data),
    enabled: Boolean(selectedItem),
  })

  const summary = summaryQuery.data?.summary
  const metric = summaryQuery.data?.metric
  const comparisons = comparisonsQuery.data?.items ?? []
  const distribution = distributionQuery.data?.items ?? []
  const trend = trendQuery.data?.items ?? []
  const isLevelMetric = filters.metric_code === "energy_efficiency_level"
  const levelGapItems = comparisons
    .map((item) => ({ name: item.target_name || item.target_code || "-", value: levelGap(item) ?? 0 }))
    .filter((item) => item.value > 0)
    .sort((left, right) => Number(right.value) - Number(left.value))
  const maxLevelGap = levelGapItems[0]?.value ?? 0
  const okTotal = comparisons.filter((item) => item.status === "ok").length

  const deviationOption = createRankingChartOption(
    theme,
    isLevelMetric
      ? levelGapItems
      : comparisons
          .filter((item) => item.deviation_pct != null)
          .sort((left, right) => Number(right.deviation_pct ?? 0) - Number(left.deviation_pct ?? 0))
          .map((item) => ({ name: item.target_name || item.target_code || "-", value: Number(item.deviation_pct ?? 0) })),
    { unit: isLevelMetric ? "级" : "%", colorKey: "warning", limit: 10 },
  )
  const savingOption = createRankingChartOption(
    theme,
    isLevelMetric
      ? levelGapItems
      : comparisons
          .filter((item) => Number(item.saving_potential ?? 0) > 0)
          .sort((left, right) => Number(right.saving_potential ?? 0) - Number(left.saving_potential ?? 0))
          .map((item) => ({ name: item.target_name || item.target_code || "-", value: Number(item.saving_potential ?? 0) })),
    { unit: isLevelMetric ? "级" : (summary?.unit ?? metric?.unit), colorKey: "energy", limit: 10 },
  )
  const distributionOption = createRankingChartOption(
    theme,
    distribution.map((item) => ({ name: item.name, value: item.value })).sort((left, right) => Number(right.value) - Number(left.value)),
    { unit: "项", colorKey: "success", limit: 10 },
  )
  const trendOption = createComboTrendChartOption(theme, trend as unknown as Record<string, string | number | null | undefined>[], {
    bars: [
      { key: "severe_count", label: "明显偏高" },
      { key: "warning_count", label: "接近预警" },
    ],
    lines: [
      { key: "actual", label: "实际值" },
      { key: "benchmark", label: "标杆值" },
    ],
    leftAxisName: "项",
    rightAxisName: metric?.unit ?? "",
  }) as EChartsOption | undefined

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["energy-benchmark"] })

  return (
    <AdminPageScaffold
      header={header}
      filters={
        <AdminFilterBar
          fields={[
            {
              key: "period_start",
              node: <Input type="date" value={filters.period_start} onChange={(event) => setFilters((state) => ({ ...state, period_start: event.target.value }))} />,
            },
            {
              key: "period_end",
              node: <Input type="date" value={filters.period_end} onChange={(event) => setFilters((state) => ({ ...state, period_end: event.target.value }))} />,
            },
            {
              key: "library_type",
              node: (
                <Select value={filters.library_type} onValueChange={(value) => setFilters((state) => ({ ...state, library_type: value, profile_id: "auto" }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {libraryTypes.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "profile_id",
              node: (
                <Select value={filters.profile_id} onValueChange={(value) => setFilters((state) => ({ ...state, profile_id: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">自动方案</SelectItem>
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
                <Select value={filters.target_type} onValueChange={(value) => setFilters((state) => ({ ...state, target_type: value }))}>
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
              ),
            },
            {
              key: "metric_code",
              node: (
                <Select value={filters.metric_code} onValueChange={(value) => setFilters((state) => ({ ...state, metric_code: value }))}>
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
              ),
            },
            {
              key: "target_code",
              node: <Input value={filters.target_code} onChange={(event) => setFilters((state) => ({ ...state, target_code: event.target.value }))} placeholder="对象编码" />,
            },
          ]}
          actions={
            <>
              <Button variant="outline" onClick={refresh}>
                <RefreshCw className="mr-2 h-4 w-4" />
                刷新
              </Button>
              <Button asChild>
                <Link to="/data/energy-benchmark">
                  <Settings className="mr-2 h-4 w-4" />
                  标准库
                </Link>
              </Button>
            </>
          }
        />
      }
      metrics={
        <MetricStrip className="md:grid-cols-5 xl:grid-cols-5">
          <MetricTile label="对标覆盖率" value={formatNumber(summary?.coverage_rate)} unit="%" tone={Number(summary?.coverage_rate ?? 0) >= 80 ? "success" : "warning"} />
          <MetricTile label={isLevelMetric ? "重点设备" : "对标对象"} value={summary?.total ?? comparisons.length} />
          <MetricTile
            label={isLevelMetric ? "待提升设备" : "超标对象"}
            value={summary?.warning_total ?? 0}
            tone={Number(summary?.warning_total ?? 0) > 0 ? "warning" : "success"}
          />
          <MetricTile
            label={isLevelMetric ? "最高等级差距" : "平均偏差"}
            value={isLevelMetric ? formatNumber(maxLevelGap, 0) : formatNumber(summary?.average_deviation_pct)}
            unit={isLevelMetric ? "级" : "%"}
          />
          <MetricTile
            label={isLevelMetric ? "达标设备" : "节能潜力"}
            value={isLevelMetric ? okTotal : formatNumber(summary?.saving_potential)}
            unit={isLevelMetric ? "台" : (summary?.unit ?? metric?.unit)}
          />
        </MetricStrip>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartPanel title={isLevelMetric ? "等级差距排行" : "偏差排行"} option={deviationOption} unit={isLevelMetric ? "级" : "%"} height={300} />
        <ChartPanel title="达标等级分布" option={distributionOption} unit="项" height={300} />
        <ChartPanel title="实际值 vs 标杆趋势" option={trendOption} unit={metric?.unit} height={300} />
        <ChartPanel title={isLevelMetric ? "待提升设备 Top" : "节能潜力 Top"} option={savingOption} unit={isLevelMetric ? "级" : (summary?.unit ?? metric?.unit)} height={300} />
      </div>

      <AdminPanel title="对标结果" className="mt-4" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>对象</TableHead>
                <TableHead>指标</TableHead>
                <TableHead className="text-right">实际值</TableHead>
                <TableHead className="text-right">标杆值</TableHead>
                <TableHead className="text-right">{isLevelMetric ? "等级差距" : "偏差率"}</TableHead>
                <TableHead>数据状态</TableHead>
                <TableHead>标准来源</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparisons.map((item, index) => (
                <TableRow key={`${item.target_type}-${item.target_code}-${index}`}>
                  <TableCell>
                    <div className="font-medium">{item.target_name || item.target_code || "-"}</div>
                    <div className="text-xs text-muted-foreground">{optionLabel(targetTypes, item.target_type)}</div>
                  </TableCell>
                  <TableCell>
                    <div>{item.metric_name || optionLabel(metrics, item.metric_code)}</div>
                    <div className="text-xs text-muted-foreground">{item.unit || metric?.unit || "-"}</div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(item.actual_value)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(item.benchmark_value)}</TableCell>
                  <TableCell className="text-right tabular-nums">{resultGapValue(item, isLevelMetric)}</TableCell>
                  <TableCell>{statusBadge(item.status)}</TableCell>
                  <TableCell>
                    <div>{item.standard_code || "-"}</div>
                    <div className="max-w-52 truncate text-xs text-muted-foreground">{item.profile_name || item.reference_standard || "-"}</div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm" onClick={() => setSelectedItem(item)}>
                      详情
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {comparisons.length === 0 && <AdminTableStateRow colSpan={8}>暂无对标结果</AdminTableStateRow>}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>

      <AdminPanel title="维护入口" className="mt-4">
        <div className="grid gap-2 md:grid-cols-5">
          <Button variant="outline" asChild>
            <Link to="/data/energy-benchmark">标准库</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/data/energy-consumption">能源数据</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/data/terminals">设备台账</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/data/production-output">产量数据</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/data/product-prices">价格台账</Link>
          </Button>
        </div>
      </AdminPanel>

      <BenchmarkDetailSheet
        item={detailQuery.data?.item ?? selectedItem}
        dataSources={detailQuery.data?.data_sources}
        isLevelMetric={isLevelMetric}
        open={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
      />
    </AdminPageScaffold>
  )
}

function BenchmarkDetailSheet({
  open,
  item,
  dataSources,
  isLevelMetric,
  onClose,
}: {
  open: boolean
  item?: ComparisonItem | null
  dataSources?: Record<string, unknown>
  isLevelMetric: boolean
  onClose: () => void
}) {
  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>对标详情</SheetTitle>
        </SheetHeader>
        <div className="mt-4 grid gap-4">
          <AdminPanel title="计算结果">
            <div className="grid gap-3 md:grid-cols-2">
              <DetailItem label="对象" value={item?.target_name || item?.target_code} />
              <DetailItem label="对象层级" value={optionLabel(targetTypes, item?.target_type)} />
              <DetailItem label="指标" value={item?.metric_name || optionLabel(metrics, item?.metric_code)} />
              <DetailItem label="状态" value={statusLabels[item?.status || ""] ?? item?.status} />
              <DetailItem label="实际值" value={`${formatNumber(item?.actual_value)} ${item?.unit ?? ""}`} />
              <DetailItem label="标杆值" value={`${formatNumber(item?.benchmark_value)} ${item?.unit ?? ""}`} />
              <DetailItem label={isLevelMetric ? "等级差距" : "偏差率"} value={item ? resultGapValue(item, isLevelMetric) : "-"} />
              {!isLevelMetric && <DetailItem label="节能潜力" value={formatNumber(item?.saving_potential)} />}
            </div>
          </AdminPanel>
          <AdminPanel title="标准来源">
            <div className="grid gap-3 md:grid-cols-2">
              <DetailItem label="标准编号" value={item?.standard_code} />
              <DetailItem label="方案" value={item?.profile_name} />
              <DetailItem label="参考标准" value={item?.reference_standard} />
              <DetailItem label="适用条件" value={item?.applicable_condition} />
              <DetailItem label="先进水平" value={formatNumber(item?.advanced_value)} />
              <DetailItem label="节能水平" value={formatNumber(item?.saving_value)} />
              <DetailItem label="准入/基准" value={formatNumber(item?.access_value)} />
              <DetailItem label="来源 Hash" value={item?.source_hash} />
            </div>
          </AdminPanel>
          <AdminPanel title="数据来源">
            <div className="grid gap-3">
              {Object.entries(dataSources ?? {}).map(([key, value]) => (
                <DetailItem key={key} label={sourceLabel(key)} value={value == null ? "-" : String(value)} />
              ))}
            </div>
          </AdminPanel>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function DetailItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid gap-1 border-border/70 border-b pb-2">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="break-all text-sm">{value || "-"}</div>
    </div>
  )
}

function sourceLabel(value: string) {
  const labels: Record<string, string> = {
    numerator: "分子来源",
    denominator: "分母来源",
    benchmark_source: "标杆来源",
    standard_code: "标准编号",
    reference_standard: "参考标准",
    data_quality: "数据质量",
  }
  return labels[value] ?? value
}
