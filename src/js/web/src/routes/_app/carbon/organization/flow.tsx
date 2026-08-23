import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useCallback, useMemo, useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import {
  equipmentOptionsForArea,
  formatPercent,
  formatTonnes,
  InventoryStatusBadge,
  OrganizationRunFilterBar,
  organizationCarbonSearchSchema,
  scope2Label,
  toAnalyticsFilters,
  toTonnes,
} from "@/components/carbon/organization-inventory-common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createSankeyChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { useGhgAnalyticsFlow, useGhgAnalyticsOverview, useGhgCalculationRuns, useGhgCatalog, useGhgResultSummary } from "@/lib/api/hooks/ghg-inventory"
import type { GhgFlowNodeResponse } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/organization/flow")({
  validateSearch: (search) => organizationCarbonSearchSchema.parse(search),
  component: OrganizationCarbonFlowPage,
})

function OrganizationCarbonFlowPage() {
  const navigate = useNavigate({ from: Route.fullPath })
  const search = Route.useSearch()
  const chartTheme = useAdminChartTheme("carbon")
  const runs = useGhgCalculationRuns({ status: "completed" })
  const catalog = useGhgCatalog()
  const [classification, setClassification] = useState<"scope" | "iso_category">("scope")
  const [selectedNode, setSelectedNode] = useState<GhgFlowNodeResponse>()
  const runCode = search.run ?? runs.data?.items[0]?.runCode
  const scope2Method = search.scope2
  const analyticsFilters = toAnalyticsFilters(search, runCode)
  const flow = useGhgAnalyticsFlow({ ...analyticsFilters, classification })
  const overview = useGhgAnalyticsOverview(analyticsFilters)
  const summary = useGhgResultSummary(analyticsFilters)
  const selectedFilters = { ...analyticsFilters, ...toDrilldownFilters(selectedNode?.drilldown) }
  const nodeSummary = useGhgResultSummary(selectedFilters)
  const data = flow.data
  const option = useMemo(
    () =>
      createSankeyChartOption(
        chartTheme,
        (data?.nodes ?? []).map((node) => ({ id: node.id, name: node.name, value: toTonnes(node.value), category: node.category })),
        (data?.links ?? []).map((link) => ({ source: link.source, target: link.target, value: toTonnes(link.value) })),
        {
          categoryColorMap: { boundary: "text", classification: "scope2", category: "carbon", source: "scope1", resource: "scope3" },
          labelWidth: 128,
          nodeGap: 24,
          right: "13%",
        },
      ),
    [chartTheme, data],
  )
  const handleChartClick = useCallback(
    (params: unknown) => {
      const nodeId = resolveFlowNodeId(params)
      setSelectedNode(data?.nodes.find((node) => node.id === nodeId))
    },
    [data],
  )
  const chartEvents = useMemo(() => ({ click: handleChartClick }), [handleChartClick])
  const sourceCount = data?.nodes.filter((node) => node.category === "source").length ?? 0
  const resourceCount = data?.nodes.filter((node) => node.category === "resource").length ?? 0
  const evidenceCoverage = overview.data?.evidenceCoveragePct
  const anomalyCount = (summary.data?.missingEvidenceCount ?? 0) + (summary.data?.unallocatedCount ?? 0) + (overview.data && !overview.data.scope2Available ? 1 : 0)

  return (
    <AdminPageScaffold
      title="碳流分析"
      status={<InventoryStatusBadge status={overview.data && !overview.data.scope2Available ? "warning" : overview.data?.qualityStatus} />}
      meta={
        overview.data ? (
          <>
            <span>{overview.data.reportingPeriodName}</span>
            <span>{overview.data.organizationBoundaryName}</span>
            <span>总量口径：{scope2Label(scope2Method)}</span>
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
          onRefresh={() => void flow.refetch()}
          refreshing={flow.isFetching}
          extraFields={[
            {
              key: "classification",
              node: (
                <Select value={classification} onValueChange={(value) => setClassification(value as "scope" | "iso_category")}>
                  <SelectTrigger aria-label="分析维度">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="scope">GHG Protocol 排放范围</SelectItem>
                    <SelectItem value="iso_category">ISO 14064-1 六类别</SelectItem>
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
          ]}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="排放总量" value={data?.totalCo2EKg == null ? "-" : formatTonnes(data.totalCo2EKg)} unit="tCO₂e" tone="domain" />
          <MetricTile label="排放源" value={sourceCount} unit="个" />
          <MetricTile label="归集区域/设备" value={resourceCount} unit="个" />
          <MetricTile label="证据覆盖率" value={formatPercent(evidenceCoverage)} tone={Number(evidenceCoverage ?? 0) < 80 ? "warning" : "success"} />
          <MetricTile label="核算异常" value={anomalyCount} unit="项" tone={anomalyCount ? "warning" : "success"} />
        </MetricStrip>
      }
    >
      {!data && !flow.isLoading ? (
        <AdminEmptyState title="暂无可用碳流数据" />
      ) : (
        <div className="grid gap-3">
          <ChartPanel title="组织边界至区域设备碳流" unit="tCO₂e" source="核算结果与区域设备归集" option={option} height={540} onEvents={chartEvents} />
          <AdminPanel title="主要排放路径" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>组织边界</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead>排放类别</TableHead>
                  <TableHead>排放源</TableHead>
                  <TableHead>区域/设备</TableHead>
                  <TableHead className="text-right">活动数据</TableHead>
                  <TableHead className="text-right">排放量</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.topPaths ?? []).map((item, index) => (
                  <TableRow
                    key={`${item.path.join(":")}-${index}`}
                    className="cursor-pointer"
                    onClick={() => void navigate({ to: "/carbon/organization/records", search: { ...search, ...toRecordSearch(item.drilldown), page: 1 } })}
                  >
                    {[0, 1, 2, 3, 4].map((position) => (
                      <TableCell key={position}>{item.path[position] ?? "-"}</TableCell>
                    ))}
                    <TableCell className="text-right tabular-nums">{item.recordCount}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{formatTonnes(item.value)} tCO₂e</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminPanel>
          <AdminPanel title="核算异常" contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>异常类型</TableHead>
                  <TableHead>检查范围</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">影响记录</TableHead>
                  <TableHead className="text-right">处理</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnomalyRow
                  name="证据链缺失"
                  scope="当前核算运行"
                  count={summary.data?.missingEvidenceCount ?? 0}
                  onOpen={() => void navigate({ to: "/carbon/organization/records", search: { ...search, page: 1 } })}
                />
                <AnomalyRow
                  name="区域设备未归集"
                  scope="活动数据归集"
                  count={summary.data?.unallocatedCount ?? 0}
                  onOpen={() => void navigate({ to: "/carbon/organization/records", search: { ...search, page: 1 } })}
                />
                <AnomalyRow
                  name="Scope 2 口径不可用"
                  scope={scope2Label(scope2Method)}
                  count={overview.data && !overview.data.scope2Available ? 1 : 0}
                  onOpen={() => void navigate({ to: "/carbon/organization/records", search: { ...search, scope: "scope2", page: 1 } })}
                />
              </TableBody>
            </Table>
          </AdminPanel>
        </div>
      )}
      <Sheet open={Boolean(selectedNode)} onOpenChange={(open) => !open && setSelectedNode(undefined)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{selectedNode?.name ?? "碳流节点"}</SheetTitle>
          </SheetHeader>
          <div className="space-y-4 px-4 pb-6">
            <MetricStrip>
              <MetricTile label="排放量" value={formatTonnes(selectedNode?.value)} unit="tCO₂e" />
              <MetricTile label="活动数据" value={nodeSummary.data?.activityCount ?? selectedNode?.recordCount ?? 0} unit="条" />
              <MetricTile label="证据缺失" value={nodeSummary.data?.missingEvidenceCount ?? 0} unit="条" tone={nodeSummary.data?.missingEvidenceCount ? "warning" : "success"} />
            </MetricStrip>
            <AdminPanel title="排放范围构成" contentClassName="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>范围</TableHead>
                    <TableHead className="text-right">排放量</TableHead>
                    <TableHead className="text-right">占比</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(nodeSummary.data?.scopeBreakdown ?? []).map((item) => (
                    <TableRow key={item.code}>
                      <TableCell>{item.name}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatTonnes(item.valueCo2EKg)} tCO₂e</TableCell>
                      <TableCell className="text-right tabular-nums">{formatPercent(item.percentage)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminPanel>
            <Button
              onClick={() => selectedNode && void navigate({ to: "/carbon/organization/records", search: { ...search, ...toRecordSearch(selectedNode.drilldown), page: 1 } })}
            >
              查看排放记录
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function AnomalyRow({ name, scope, count, onOpen }: { name: string; scope: string; count: number; onOpen: () => void }) {
  return (
    <TableRow>
      <TableCell className="font-medium">{name}</TableCell>
      <TableCell>{scope}</TableCell>
      <TableCell>
        <InventoryStatusBadge status={count ? "warning" : "pass"} />
      </TableCell>
      <TableCell className="text-right tabular-nums">{count}</TableCell>
      <TableCell className="text-right">
        <Button size="sm" variant="ghost" disabled={!count} onClick={onOpen}>
          查看记录
        </Button>
      </TableCell>
    </TableRow>
  )
}

function toDrilldownFilters(drilldown?: Record<string, unknown>) {
  if (!drilldown) return {}
  return {
    ghgScope: typeof drilldown.ghgScope === "string" ? drilldown.ghgScope : undefined,
    isoCategoryCode: typeof drilldown.isoCategoryCode === "string" ? drilldown.isoCategoryCode : undefined,
    sourceCode: typeof drilldown.sourceCode === "string" ? drilldown.sourceCode : undefined,
    keyword: typeof drilldown.keyword === "string" ? drilldown.keyword : undefined,
    areaId: typeof drilldown.areaId === "number" ? drilldown.areaId : undefined,
    equipmentId: typeof drilldown.equipmentId === "number" ? drilldown.equipmentId : undefined,
  }
}

function toRecordSearch(drilldown: Record<string, unknown>) {
  const filters = toDrilldownFilters(drilldown)
  return {
    scope: filters.ghgScope,
    iso: filters.isoCategoryCode,
    source: filters.sourceCode,
    keyword: filters.keyword,
    areaId: filters.areaId,
    equipmentId: filters.equipmentId,
  }
}

function resolveFlowNodeId(params: unknown) {
  if (typeof params !== "object" || params === null) return undefined
  if ("data" in params && typeof params.data === "object" && params.data !== null) {
    if ("id" in params.data) return String(params.data.id)
    if ("name" in params.data) return String(params.data.name)
  }
  return "name" in params ? String(params.name) : undefined
}
