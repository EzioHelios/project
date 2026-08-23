import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useMemo } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import {
  equipmentOptionsForArea,
  formatDateTime,
  formatPercent,
  formatTonnes,
  InventoryStatusBadge,
  OrganizationRunFilterBar,
  organizationCarbonSearchSchema,
  scope2Label,
  toAnalyticsFilters,
  toTonnes,
} from "@/components/carbon/organization-inventory-common"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createDistributionChartOption, createParetoChartOption, createRankingChartOption, createTrendChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useGhgAnalyticsOverview, useGhgAnalyticsTrend, useGhgCalculationRuns, useGhgCatalog } from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon/organization/overview")({
  validateSearch: (search) => organizationCarbonSearchSchema.parse(search),
  component: OrganizationCarbonOverviewPage,
})

function OrganizationCarbonOverviewPage() {
  const chartTheme = useAdminChartTheme("carbon")
  const navigate = useNavigate({ from: Route.fullPath })
  const search = Route.useSearch()
  const runs = useGhgCalculationRuns({ status: "completed" })
  const catalog = useGhgCatalog()
  const runCode = search.run ?? runs.data?.items[0]?.runCode
  const scope2Method = search.scope2
  const selectedRun = runs.data?.items.find((item) => item.runCode === runCode)
  const filters = toAnalyticsFilters(search, runCode)
  const overview = useGhgAnalyticsOverview(filters)
  const trend = useGhgAnalyticsTrend({ ...filters, reportingOrgId: selectedRun?.reportingOrgId ?? undefined, grain: search.grain })
  const data = overview.data

  const scopeValues = useMemo(() => new Map((data?.scopeBreakdown ?? []).map((item) => [item.code, item.valueCo2EKg])), [data?.scopeBreakdown])
  const trendOption = createTrendChartOption(
    chartTheme,
    (trend.data?.items ?? []).map((item) => ({
      period: item.periodName,
      scope1: toTonnes(item.scope1Co2EKg),
      scope2: toTonnes(item.scope2Co2EKg),
      scope3: toTonnes(item.scope3Co2EKg),
    })),
    [
      { key: "scope1", label: "Scope 1", colorKey: "scope1" },
      { key: "scope2", label: `Scope 2 ${scope2Label(scope2Method)}`, colorKey: "scope2" },
      { key: "scope3", label: "Scope 3", colorKey: "scope3" },
    ],
    { periodKey: "period", includeZeroSeries: true },
  )
  const scopeOption = createDistributionChartOption(
    chartTheme,
    (data?.scopeBreakdown ?? []).map((item) => ({ name: item.name, value: toTonnes(item.valueCo2EKg) })),
    { unit: "tCO₂e" },
  )
  const isoOption = createDistributionChartOption(
    chartTheme,
    (data?.isoBreakdown ?? []).map((item) => ({ name: `${item.code} ${item.name}`, value: toTonnes(item.valueCo2EKg) })),
    { unit: "tCO₂e" },
  )
  const sourceOption = createParetoChartOption(
    chartTheme,
    (data?.sourceRanking ?? []).map((item) => ({ name: item.name, value: toTonnes(item.valueCo2EKg) })),
    { unit: "tCO₂e" },
  )
  const areaOption = createRankingChartOption(
    chartTheme,
    (data?.areaRanking ?? []).map((item) => ({ name: item.name, value: toTonnes(item.valueCo2EKg) })),
    { unit: "tCO₂e", limit: 8 },
  )
  const equipmentOption = createRankingChartOption(
    chartTheme,
    (data?.equipmentRanking ?? []).map((item) => ({ name: item.name, value: toTonnes(item.valueCo2EKg) })),
    { unit: "tCO₂e", limit: 8 },
  )

  const refresh = () => void Promise.all([runs.refetch(), overview.refetch(), trend.refetch()])
  const openRecords = (patch: Partial<typeof search>) => void navigate({ to: "/carbon/organization/records", search: { ...search, ...patch, page: 1 } })
  return (
    <AdminPageScaffold
      title="组织碳总览"
      status={<InventoryStatusBadge status={data && !data.scope2Available ? "warning" : (data?.qualityStatus ?? selectedRun?.qualityStatus)} />}
      meta={
        data ? (
          <>
            <span>{data.reportingOrgName}</span>
            <span>{data.reportingPeriodName}</span>
            <span>{data.organizationBoundaryName}</span>
            <span>{data.reportingProfileName}</span>
            <span>完成于 {formatDateTime(data.completedAt)}</span>
          </>
        ) : undefined
      }
      filters={
        <OrganizationRunFilterBar
          runs={runs.data}
          runCode={runCode}
          scope2Method={scope2Method}
          onRunCodeChange={(run) => void navigate({ search: (previous) => ({ ...previous, run }) })}
          onScope2MethodChange={(scope2) => void navigate({ search: (previous) => ({ ...previous, scope2 }) })}
          onRefresh={refresh}
          refreshing={runs.isFetching || overview.isFetching || trend.isFetching}
          extraFields={[
            {
              key: "grain",
              node: (
                <Select value={search.grain} onValueChange={(grain) => void navigate({ search: (previous) => ({ ...previous, grain: grain as "month" | "quarter" | "year" }) })}>
                  <SelectTrigger aria-label="趋势粒度">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="month">按月</SelectItem>
                    <SelectItem value="quarter">按季</SelectItem>
                    <SelectItem value="year">按年</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "area",
              node: (
                <Select
                  value={search.areaId ? String(search.areaId) : "all"}
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, areaId: value === "all" ? undefined : Number(value), equipmentId: undefined }) })}
                >
                  <SelectTrigger aria-label="区域">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部区域</SelectItem>
                    {(catalog.data?.areas ?? []).map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "equipment",
              node: (
                <Select
                  value={search.equipmentId ? String(search.equipmentId) : "all"}
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, equipmentId: value === "all" ? undefined : Number(value) }) })}
                >
                  <SelectTrigger aria-label="设备">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部设备</SelectItem>
                    {equipmentOptionsForArea(catalog.data?.areas ?? [], catalog.data?.equipment ?? [], search.areaId).map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "from",
              node: (
                <Input
                  type="date"
                  aria-label="开始日期"
                  value={search.from ?? ""}
                  onChange={(event) => void navigate({ search: (previous) => ({ ...previous, from: event.target.value || undefined }) })}
                />
              ),
            },
            {
              key: "to",
              node: (
                <Input
                  type="date"
                  aria-label="结束日期"
                  value={search.to ?? ""}
                  onChange={(event) => void navigate({ search: (previous) => ({ ...previous, to: event.target.value || undefined }) })}
                />
              ),
            },
          ]}
        />
      }
      metrics={
        <div className="grid gap-2">
          <MetricStrip>
            <MetricTile
              label="排放总量"
              value={data?.totalCo2EKg == null ? "-" : formatTonnes(data.totalCo2EKg)}
              unit="tCO₂e"
              meta={`${scope2Label(scope2Method)}总量`}
              tone="domain"
            />
            <MetricTile label="Scope 1 直接排放" value={formatTonnes(scopeValues.get("scope1"))} unit="tCO₂e" />
            <MetricTile
              label={`Scope 2 ${scope2Label(scope2Method)}`}
              value={!data?.scope2Available ? "-" : formatTonnes(scopeValues.get("scope2"))}
              unit="tCO₂e"
              tone={!data?.scope2Available ? "warning" : "default"}
            />
            <MetricTile label="Scope 3 其他间接排放" value={formatTonnes(scopeValues.get("scope3"))} unit="tCO₂e" />
          </MetricStrip>
          <MetricStrip>
            <MetricTile
              label="环比变化"
              value={trend.data?.previousChangePct == null ? "-" : `${Number(trend.data.previousChangePct) > 0 ? "+" : ""}${Number(trend.data.previousChangePct).toFixed(1)}`}
              unit="%"
              tone={Number(trend.data?.previousChangePct ?? 0) > 0 ? "warning" : "success"}
            />
            <MetricTile
              label="同比变化"
              value={trend.data?.yearOnYearChangePct == null ? "-" : `${Number(trend.data.yearOnYearChangePct) > 0 ? "+" : ""}${Number(trend.data.yearOnYearChangePct).toFixed(1)}`}
              unit="%"
              tone={Number(trend.data?.yearOnYearChangePct ?? 0) > 0 ? "warning" : "success"}
            />
            <MetricTile label="碳预算" value={data?.budgetTarget ? Number(data.budgetTarget.budgetCo2ETonnes).toFixed(2) : "-"} unit="tCO₂e" />
            <MetricTile
              label="目标执行率"
              value={data?.budgetTarget?.executionRatePct == null ? "-" : Number(data.budgetTarget.executionRatePct).toFixed(1)}
              unit="%"
              tone={Number(data?.budgetTarget?.executionRatePct ?? 0) > 100 ? "warning" : "success"}
            />
          </MetricStrip>
        </div>
      }
    >
      {!data && !overview.isLoading ? (
        <AdminEmptyState title="暂无已完成的组织碳核算" />
      ) : (
        <div className="grid gap-3">
          <ChartPanel title="报告期排放趋势" unit="tCO₂e" source="组织温室气体核算结果" option={trendOption} height={300} />
          <div className="grid gap-3 xl:grid-cols-2">
            <ChartPanel
              title="排放范围构成"
              unit="tCO₂e"
              option={scopeOption}
              height={300}
              onEvents={{
                click: (params: unknown) => {
                  const item = data?.scopeBreakdown.find((candidate) => candidate.name === chartItemName(params))
                  if (item) openRecords({ scope: item.code })
                },
              }}
            />
            <ChartPanel
              title="ISO 14064-1 六类别构成"
              unit="tCO₂e"
              option={isoOption}
              height={300}
              onEvents={{
                click: (params: unknown) => {
                  const name = chartItemName(params)
                  const item = data?.isoBreakdown.find((candidate) => `${candidate.code} ${candidate.name}` === name)
                  if (item) openRecords({ iso: item.code })
                },
              }}
            />
          </div>
          <ChartPanel
            title="重点排放源与累计贡献"
            unit="tCO₂e"
            option={sourceOption}
            height={310}
            onEvents={{
              click: (params: unknown) => {
                const item = data?.sourceRanking.find((candidate) => candidate.name === chartItemName(params))
                if (item) openRecords({ source: item.code })
              },
            }}
          />
          <div className="grid gap-3 xl:grid-cols-2">
            <ChartPanel
              title="区域排放排名"
              unit="tCO₂e"
              option={areaOption}
              height={300}
              onEvents={{
                click: (params: unknown) => {
                  const item = data?.areaRanking.find((candidate) => candidate.name === chartItemName(params))
                  if (item) openRecords({ areaId: Number(item.code), equipmentId: undefined })
                },
              }}
            />
            <ChartPanel
              title="设备排放排名"
              unit="tCO₂e"
              option={equipmentOption}
              height={300}
              onEvents={{
                click: (params: unknown) => {
                  const item = data?.equipmentRanking.find((candidate) => candidate.name === chartItemName(params))
                  if (item) openRecords({ equipmentId: Number(item.code) })
                },
              }}
            />
          </div>
          <MetricStrip>
            <MetricTile label="活动数据" value={data?.activityCount ?? 0} unit="条" />
            <MetricTile label="数据完整率" value={formatPercent(data?.dataCompletenessPct)} />
            <MetricTile label="区域设备归集率" value={formatPercent(data?.allocationCoveragePct)} tone={Number(data?.allocationCoveragePct ?? 0) < 100 ? "warning" : "success"} />
            <MetricTile label="证据覆盖率" value={formatPercent(data?.evidenceCoveragePct)} tone={Number(data?.evidenceCoveragePct ?? 0) < 80 ? "warning" : "success"} />
          </MetricStrip>
          <AdminPanel title="类别质量与证据覆盖" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ISO 类别</TableHead>
                  <TableHead className="text-right">排放量</TableHead>
                  <TableHead className="text-right">占比</TableHead>
                  <TableHead className="text-right">活动数据</TableHead>
                  <TableHead className="text-right">证据覆盖率</TableHead>
                  <TableHead className="text-right">关注项</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.isoBreakdown ?? []).map((item) => (
                  <TableRow key={item.code}>
                    <TableCell className="font-medium">
                      {item.code} {item.name}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatTonnes(item.valueCo2EKg)} tCO₂e</TableCell>
                    <TableCell className="text-right tabular-nums">{formatPercent(item.percentage)}</TableCell>
                    <TableCell className="text-right tabular-nums">{item.recordCount}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatPercent(item.evidenceCoveragePct)}</TableCell>
                    <TableCell className="text-right tabular-nums">{item.warningCount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminPanel>
        </div>
      )}
    </AdminPageScaffold>
  )
}

function chartItemName(params: unknown) {
  if (typeof params !== "object" || params === null || !("name" in params)) return ""
  return String(params.name ?? "")
}
