import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download, GitCompare, Search } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminPageScaffold, AdminPanel, AdminTableStateRow, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import {
  equipmentOptionsForArea,
  formatDateTime,
  formatPercent,
  formatQuantity,
  formatTonnes,
  InventoryStatusBadge,
  OrganizationRunFilterBar,
  organizationCarbonSearchSchema,
  scope2Label,
  toAnalyticsFilters,
  toTonnes,
} from "@/components/carbon/organization-inventory-common"
import { PaginationBar } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createParetoChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import {
  exportGhgResults,
  useGhgAnalyticsOverview,
  useGhgCalculationRuns,
  useGhgCatalog,
  useGhgComparison,
  useGhgResultDetail,
  useGhgResultSummary,
  useGhgResults,
} from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon/organization/records")({
  validateSearch: (search) => organizationCarbonSearchSchema.parse(search),
  component: OrganizationCarbonRecordsPage,
})

const fieldLabels: Record<string, string> = {
  periodStart: "开始日期",
  periodEnd: "结束日期",
  dataSourceType: "数据来源",
  measurementMethod: "计量方法",
  remarks: "备注",
  methodCode: "核算方法编码",
  methodVersion: "方法版本",
  methodName: "核算方法",
  humanFormula: "计算公式",
  parameterCode: "参数",
  parameterRole: "参数角色",
  value: "数值",
  unit: "单位",
  sourceMode: "来源方式",
  sourceName: "来源名称",
  sourceVersion: "来源版本",
  standardCode: "标准",
  clauseReference: "条款",
  tableReference: "表格位置",
  selectionRule: "选择规则",
  areaCode: "区域编码",
  areaName: "区域",
  areaPath: "区域路径",
  equipmentCode: "设备编码",
  equipmentName: "设备",
  allocationRole: "归集角色",
  allocationRatio: "归集比例",
  sourceKind: "归集来源",
  evidenceCode: "证据编号",
  fileName: "文件名",
  documentType: "文档类型",
  issuer: "出具方",
  verificationStatus: "核验状态",
  evidenceRole: "证据角色",
  reviewStatus: "复核状态",
  pageOrCellReference: "页码/单元格",
}

const fieldValueLabels: Record<string, Record<string, string>> = {
  dataSourceType: { manual: "人工填报", measured: "实测数据", calculated: "计算数据", estimated: "估算数据" },
  measurementMethod: { monthly_statement: "月度结算单", direct_metering: "直接计量", invoice: "票据记录" },
  sourceMode: { authority_published: "权威机构发布", enterprise_measured: "企业实测", supplier_provided: "供应商提供" },
  sourceKind: { migration: "历史数据归集", manual: "人工配置", import: "文件导入" },
  parameterCode: { EMISSION_FACTOR: "排放因子" },
  parameterRole: { emission_factor: "排放因子" },
  allocationRole: {
    asset_location: "设备归属",
    energy_consumption: "用能归属",
    physical_origin: "物理来源",
    responsibility: "责任归属",
    operation: "运营归属",
    measurement: "计量归属",
    waste_generation: "废弃物产生",
  },
}

function OrganizationCarbonRecordsPage() {
  const chartTheme = useAdminChartTheme("carbon")
  const navigate = useNavigate({ from: Route.fullPath })
  const search = Route.useSearch()
  const runs = useGhgCalculationRuns({ status: "completed" })
  const catalog = useGhgCatalog()
  const [selectedRecordCode, setSelectedRecordCode] = useState<string>()
  const [comparisonOpen, setComparisonOpen] = useState(false)
  const [comparisonRunCodes, setComparisonRunCodes] = useState<string[]>([])
  const runCode = search.run ?? runs.data?.items[0]?.runCode
  const scope2Method = search.scope2
  const analyticsFilters = toAnalyticsFilters(search, runCode)
  const overview = useGhgAnalyticsOverview(analyticsFilters)
  const results = useGhgResults({
    ...analyticsFilters,
    page: search.page,
    pageSize: search.pageSize,
    sortBy: search.sortBy,
    sortOrder: search.sortOrder,
  })
  const summary = useGhgResultSummary(analyticsFilters)
  const comparison = useGhgComparison({ ...analyticsFilters, runCodes: comparisonRunCodes })
  const detail = useGhgResultDetail({ runCode, recordCode: selectedRecordCode, scope2Method })
  const items = results.data?.items ?? []
  const sourcePareto = useMemo(() => {
    return createParetoChartOption(
      chartTheme,
      (summary.data?.sourceBreakdown ?? []).map((item) => ({ name: item.name, value: toTonnes(item.valueCo2EKg) })),
      { unit: "tCO₂e", limit: 12 },
    )
  }, [chartTheme, summary.data?.sourceBreakdown])
  const isoOptions = catalog.data?.categories ?? []

  return (
    <AdminPageScaffold
      title="碳排放查询"
      status={<InventoryStatusBadge status={overview.data && !overview.data.scope2Available ? "warning" : overview.data?.qualityStatus} />}
      meta={
        overview.data ? (
          <>
            <span>{overview.data.reportingPeriodName}</span>
            <span>{overview.data.organizationBoundaryName}</span>
            <span>
              总量口径：{scope2Label(scope2Method)}
              {overview.data.scope2Available ? "" : " · 当前运行不可用"}
            </span>
          </>
        ) : undefined
      }
      filters={
        <OrganizationRunFilterBar
          runs={runs.data}
          runCode={runCode}
          scope2Method={scope2Method}
          onRunCodeChange={(run) => void navigate({ search: (previous) => ({ ...previous, run, page: 1 }) })}
          onScope2MethodChange={(scope2) => void navigate({ search: (previous) => ({ ...previous, scope2, page: 1 }) })}
          onRefresh={() => void Promise.all([results.refetch(), summary.refetch()])}
          refreshing={results.isFetching || summary.isFetching}
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setComparisonRunCodes((current) => (current.length === 0 && runCode ? [runCode] : current))
                  setComparisonOpen(true)
                }}
              >
                <GitCompare />
                运行比较
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void exportGhgResults(analyticsFilters).catch((error: Error) => toast.error("导出失败", { description: error.message }))}
              >
                <Download />
                导出 XLSX
              </Button>
            </>
          }
          extraFields={[
            {
              key: "keyword",
              node: (
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-8"
                    value={search.keyword ?? ""}
                    onChange={(event) => void navigate({ search: (previous) => ({ ...previous, keyword: event.target.value || undefined, page: 1 }) })}
                    placeholder="活动、来源或记录号"
                  />
                </div>
              ),
            },
            {
              key: "scope",
              node: (
                <Select
                  value={search.scope ?? "all"}
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, scope: value === "all" ? undefined : value, page: 1 }) })}
                >
                  <SelectTrigger aria-label="排放范围">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部范围</SelectItem>
                    <SelectItem value="scope1">Scope 1</SelectItem>
                    <SelectItem value="scope2">Scope 2</SelectItem>
                    <SelectItem value="scope3">Scope 3</SelectItem>
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
                  onChange={(event) => void navigate({ search: (previous) => ({ ...previous, from: event.target.value || undefined, page: 1 }) })}
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
                  onChange={(event) => void navigate({ search: (previous) => ({ ...previous, to: event.target.value || undefined, page: 1 }) })}
                />
              ),
            },
            {
              key: "iso",
              node: (
                <Select
                  value={search.iso ?? "all"}
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, iso: value === "all" ? undefined : value, page: 1 }) })}
                >
                  <SelectTrigger aria-label="ISO 类别">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部 ISO 类别</SelectItem>
                    {isoOptions.map((item) => (
                      <SelectItem key={item.code} value={item.code}>
                        {item.code} {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "quality",
              node: (
                <Select
                  value={search.quality ?? "all"}
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, quality: value === "all" ? undefined : value, page: 1 }) })}
                >
                  <SelectTrigger aria-label="质量状态">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部质量状态</SelectItem>
                    <SelectItem value="pass">通过</SelectItem>
                    <SelectItem value="warning">需关注</SelectItem>
                    <SelectItem value="failed">失败</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "area",
              node: (
                <Select
                  value={search.areaId ? String(search.areaId) : "all"}
                  onValueChange={(value) =>
                    void navigate({ search: (previous) => ({ ...previous, areaId: value === "all" ? undefined : Number(value), equipmentId: undefined, page: 1 }) })
                  }
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
                  onValueChange={(value) => void navigate({ search: (previous) => ({ ...previous, equipmentId: value === "all" ? undefined : Number(value), page: 1 }) })}
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
          <MetricTile label="查询结果" value={summary.data?.resultCount ?? 0} unit="条" />
          <MetricTile label="排放合计" value={formatTonnes(summary.data?.totalCo2EKg)} unit="tCO₂e" />
          <MetricTile label="缺少证据" value={summary.data?.missingEvidenceCount ?? 0} unit="条" tone={summary.data?.missingEvidenceCount ? "warning" : "success"} />
          <MetricTile label="未归集区域/设备" value={summary.data?.unallocatedCount ?? 0} unit="条" tone={summary.data?.unallocatedCount ? "warning" : "success"} />
        </MetricStrip>
      }
    >
      <div className="grid gap-3">
        <ChartPanel title="排放源帕累托分析" unit="tCO₂e" option={sourcePareto} height={300} />
        <AdminPanel title="排放结果明细" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>活动/排放源</TableHead>
                <TableHead>范围与类别</TableHead>
                <TableHead>活动数据</TableHead>
                <TableHead>核算方法</TableHead>
                <TableHead>区域/设备</TableHead>
                <TableHead className="text-right">排放量</TableHead>
                <TableHead>质量/证据</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.isLoading && <AdminTableStateRow colSpan={7}>正在加载核算结果…</AdminTableStateRow>}
              {!results.isLoading && items.length === 0 && <AdminTableStateRow colSpan={7}>当前筛选条件下无核算结果</AdminTableStateRow>}
              {items.map((item) => (
                <TableRow key={`${item.recordCode}:${item.gasCode}`} className="cursor-pointer" onClick={() => setSelectedRecordCode(item.recordCode)}>
                  <TableCell>
                    <div className="font-medium">{item.sourceName}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.activityName !== item.sourceName ? `${item.activityName} · ` : ""}
                      {item.recordCode}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>{item.ghgScope.replace("scope", "Scope ")}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.isoCategoryCode} {item.isoCategoryName}
                    </div>
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatQuantity(item.activityAmount)} {item.activityUnit}
                  </TableCell>
                  <TableCell>
                    <div>{item.methodName}</div>
                    <div className="text-xs text-muted-foreground">{item.gasCode}</div>
                  </TableCell>
                  <TableCell>
                    <div>{item.areaNames.join("、") || "-"}</div>
                    <div className="text-xs text-muted-foreground">{item.equipmentNames.join("、") || "-"}</div>
                  </TableCell>
                  <TableCell className="text-right font-medium tabular-nums">{formatTonnes(item.attributedCo2EKg)} tCO₂e</TableCell>
                  <TableCell>
                    <InventoryStatusBadge status={item.qualityStatus} />
                    <div className="mt-1 text-xs text-muted-foreground">证据 {item.evidenceCount} 份</div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4 pb-4">
            <PaginationBar
              page={results.data ?? { items: [], total: 0, limit: search.pageSize, offset: (search.page - 1) * search.pageSize }}
              pageIndex={search.page - 1}
              pageSize={search.pageSize}
              pageSizeOptions={[25, 50, 100]}
              onPageChange={(pageIndex) => void navigate({ search: (previous) => ({ ...previous, page: pageIndex + 1 }) })}
              onPageSizeChange={(pageSize) => void navigate({ search: (previous) => ({ ...previous, page: 1, pageSize: pageSize as 25 | 50 | 100 }) })}
            />
          </div>
        </AdminPanel>
      </div>
      <Sheet open={Boolean(selectedRecordCode)} onOpenChange={(open) => !open && setSelectedRecordCode(undefined)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
          <SheetHeader>
            <SheetTitle>{detail.data?.result.sourceName ?? detail.data?.result.activityName ?? "排放结果详情"}</SheetTitle>
          </SheetHeader>
          <div className="space-y-3 px-4 pb-6">
            {detail.data && (
              <>
                <MetricStrip>
                  <MetricTile label="归属排放量" value={formatTonnes(detail.data.result.attributedCo2EKg)} unit="tCO₂e" />
                  <MetricTile label="完整核算值" value={formatTonnes(detail.data.result.calculatedCo2EKg)} unit="tCO₂e" />
                  <MetricTile label="归属比例" value={formatPercent(Number(detail.data.result.attributionRatio) * 100)} />
                  <MetricTile label="活动数据" value={formatQuantity(detail.data.result.activityAmount)} unit={detail.data.result.activityUnit} />
                </MetricStrip>
                <DetailBlock title="活动与核算公式" records={[detail.data.activityDetails, detail.data.formulaSnapshot]} />
                <DetailBlock title="参数与因子" records={detail.data.assignments} />
                <DetailBlock title="区域与设备归集" records={detail.data.allocations} />
                <DetailBlock title="证据文件" records={detail.data.evidence} />
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>
      <Sheet open={comparisonOpen} onOpenChange={setComparisonOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-4xl">
          <SheetHeader>
            <SheetTitle>核算运行比较</SheetTitle>
          </SheetHeader>
          <div className="space-y-4 px-4 pb-6">
            <div className="grid gap-2 sm:grid-cols-2">
              {(runs.data?.items ?? []).map((run) => {
                const checked = comparisonRunCodes.includes(run.runCode)
                return (
                  <label key={run.runCode} className="flex items-start gap-3 rounded-md border p-3 text-sm">
                    <input
                      type="checkbox"
                      className="mt-0.5 size-4 accent-primary"
                      checked={checked}
                      disabled={!checked && comparisonRunCodes.length >= 3}
                      onChange={(event) => setComparisonRunCodes((current) => (event.target.checked ? [...current, run.runCode] : current.filter((code) => code !== run.runCode)))}
                    />
                    <span>
                      <span className="block font-medium">{run.reportingPeriodName ?? run.inventoryCode}</span>
                      <span className="block text-muted-foreground">{run.organizationBoundaryName ?? "组织边界"}</span>
                      <span className="block text-xs text-muted-foreground">完成于 {formatDateTime(run.completedAt)}</span>
                    </span>
                  </label>
                )
              })}
            </div>
            {comparisonRunCodes.length < 2 ? (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">请选择 2–3 个核算运行</div>
            ) : (
              <AdminPanel title="比较结果" contentClassName="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>报告期</TableHead>
                      <TableHead>边界版本</TableHead>
                      <TableHead className="text-right">排放总量</TableHead>
                      <TableHead className="text-right">相邻变化</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(comparison.data?.items ?? []).map((item, index) => {
                      const delta = index === 0 ? undefined : comparison.data?.deltas[index - 1]
                      return (
                        <TableRow key={item.runCode}>
                          <TableCell>{item.reportingPeriodName ?? item.runCode}</TableCell>
                          <TableCell>V{item.boundaryVersion ?? "-"}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatTonnes(item.totalCo2EKg)} tCO₂e</TableCell>
                          <TableCell className="text-right tabular-nums">
                            {delta ? `${Number(delta.changeCo2EKg) > 0 ? "+" : ""}${formatTonnes(delta.changeCo2EKg)} tCO₂e` : "-"}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </AdminPanel>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function DetailBlock({ title, records }: { title: string; records: Array<Record<string, unknown>> }) {
  return (
    <AdminPanel title={title} contentClassName="space-y-3">
      {records.length === 0 ? (
        <div className="text-sm text-muted-foreground">暂无记录</div>
      ) : (
        records.map((record) => (
          <dl
            className="grid gap-x-4 gap-y-2 border-b border-border/60 pb-3 last:border-0 last:pb-0 sm:grid-cols-2"
            key={`${title}-${String(record.recordCode ?? record.parameterCode ?? record.allocationCode ?? record.evidenceCode ?? Object.values(record)[0])}`}
          >
            {Object.entries(record)
              .filter(
                ([key, value]) =>
                  key in fieldLabels &&
                  value !== null &&
                  value !== undefined &&
                  value !== "" &&
                  typeof value !== "object" &&
                  !(key === "remarks" && String(value).includes("[carbon_mvp_seed]")),
              )
              .map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs text-muted-foreground">{fieldLabels[key]}</dt>
                  <dd className="mt-0.5 break-words text-sm">
                    {key === "allocationRatio" ? formatPercent(Number(value) * 100) : (fieldValueLabels[key]?.[String(value)] ?? String(value))}
                  </dd>
                </div>
              ))}
          </dl>
        ))
      )}
    </AdminPanel>
  )
}
