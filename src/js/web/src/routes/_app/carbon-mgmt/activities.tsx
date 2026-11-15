import { createFileRoute, Link } from "@tanstack/react-router"
import { Download, Edit, Eye, FileUp, Plus, RefreshCw, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { z } from "zod"

import { AdminDataTable, AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { ghgObjectLabel } from "@/components/carbon/ghg-entry-selectors"
import { GhgGenerateActivities } from "@/components/carbon/ghg-generate-activities"
import { ActivityForm, AllocationEditor, activityDefaults, CarbonFormField, categoryLabel, choiceLabel, sourceLabel, statusLabel } from "@/components/carbon/ghg-maintenance"
import { formatGhgAmount } from "@/components/carbon/ghg-record-results"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useActivityFactorCandidates, useCalculationFactorActions } from "@/lib/api/hooks/factor-library"
import {
  type GhgActivity,
  type GhgActivityWrite,
  useGhgActivities,
  useGhgActivity,
  useGhgActivityAllocations,
  useGhgCatalog,
  useGhgEmissionSources,
  useGhgEntryOptions,
  useGhgImportBatches,
  useGhgInventoryActions,
} from "@/lib/api/hooks/ghg-inventory"
import { getCategoryLabel, getScopeLabel, getSubCategoryLabel } from "@/lib/carbon-factor-labels"
import { normalizeGhgCategoryCode } from "@/lib/ghg-categories"

export const ghgLedgerSearchSchema = z.object({
  category: z.preprocess(normalizeGhgCategoryCode, z.string().optional()),
  inventory: z.string().optional(),
  batch: z.string().optional(),
  record: z.string().optional(),
})

export const Route = createFileRoute("/_app/carbon-mgmt/activities")({
  validateSearch: (search) => ghgLedgerSearchSchema.parse(search),
  component: GhgActivityLedgerPage,
})

function GhgActivityLedgerPage() {
  const { category, inventory, batch, record } = Route.useSearch()
  return <GhgActivityLedger initialCategoryCode={category} initialInventoryCode={inventory} initialBatchCode={batch} initialRecordCode={record} readOnly />
}

export function GhgActivityLedger({
  fixedCategoryCode,
  initialCategoryCode,
  initialInventoryCode,
  initialBatchCode,
  initialRecordCode,
  readOnly = false,
}: {
  fixedCategoryCode?: string
  initialCategoryCode?: string
  initialInventoryCode?: string
  initialBatchCode?: string
  initialRecordCode?: string
  readOnly?: boolean
}) {
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [inventoryCode, setInventoryCode] = useState(initialInventoryCode ?? "")
  const [batchCode, setBatchCode] = useState(initialBatchCode ?? "")
  const [offset, setOffset] = useState(0)
  const [saved, setSaved] = useState<GhgActivity | null>(null)
  const batches = useGhgImportBatches()
  const entryOptions = useGhgEntryOptions()
  const [linkedRecordCode, setLinkedRecordCode] = useState(initialRecordCode)
  const linkedActivity = useGhgActivity({ inventoryCode: initialInventoryCode, recordCode: linkedRecordCode })
  useEffect(() => setLinkedRecordCode(initialRecordCode), [initialRecordCode])
  const [categoryCode, setCategoryCode] = useState(initialCategoryCode ?? fixedCategoryCode ?? "all")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [recordStatus, setRecordStatus] = useState(readOnly ? "all" : "available")
  const [keyword, setKeyword] = useState("")
  const [editing, setEditing] = useState<GhgActivity | "new" | null>(null)
  const [detail, setDetail] = useState<GhgActivity | null>(null)

  useEffect(() => {
    setCategoryCode(initialCategoryCode ?? fixedCategoryCode ?? "all")
  }, [fixedCategoryCode, initialCategoryCode])

  useEffect(() => {
    setInventoryCode(initialInventoryCode ?? "")
    setBatchCode(initialBatchCode ?? "")
    setOffset(0)
  }, [initialInventoryCode, initialBatchCode])
  useEffect(() => {
    if (linkedActivity.data) setDetail(linkedActivity.data)
  }, [linkedActivity.data])
  // biome-ignore lint/correctness/useExhaustiveDependencies: Each filter change starts a new result page.
  useEffect(() => {
    setOffset(0)
  }, [inventoryCode, batchCode, categoryCode, qualityStatus, recordStatus])

  const activeCategoryCode = fixedCategoryCode ?? categoryCode
  const selectedCategory = catalog.data?.categories.find((item) => item.code === activeCategoryCode)
  const mainFields: Record<string, string[]> = {
    "1.1": ["fuel_or_material"],
    "1.2": ["fuel_or_material", "vehicle_type"],
    "1.4": ["gas_code"],
    "2.1": ["energy_type", "supplier_name"],
    "3.1": ["transport_mode", "distance_km", "cargo_ton"],
    "3.2": ["transport_mode", "distance_km", "cargo_ton"],
    "3.3": ["transport_mode", "distance_km", "passenger_count"],
    "3.4": ["transport_mode", "distance_km", "passenger_count"],
    "3.5": ["transport_mode", "distance_km", "passenger_count"],
  }
  const dynamicFields = (selectedCategory?.activityFields ?? []).filter((field) => mainFields[activeCategoryCode]?.includes(field.code) ?? field.required).slice(0, 3)
  const availableMethods = useMemo(
    () => (catalog.data?.methods ?? []).filter((method) => selectedCategory?.defaultMethods.includes(method.code) && method.executable),
    [catalog.data?.methods, selectedCategory],
  )
  const activities = useGhgActivities({
    inventoryCode: inventoryCode || undefined,
    categoryCode: activeCategoryCode === "all" ? undefined : activeCategoryCode,
    qualityStatus: qualityStatus === "all" ? undefined : qualityStatus,
    status: recordStatus === "all" ? undefined : recordStatus,
    batchCode: batchCode || undefined,
    offset,
  })
  const sources = useGhgEmissionSources({
    inventoryCode: inventoryCode || undefined,
    categoryCode: activeCategoryCode === "all" ? undefined : activeCategoryCode,
    status: "active",
  })
  const allocations = useGhgActivityAllocations({ inventoryCode: detail?.inventoryCode, recordCode: detail?.recordCode })
  const loadedRows = activities.data?.items ?? []
  const visibleRows =
    saved &&
    offset === 0 &&
    (!inventoryCode || saved.inventoryCode === inventoryCode) &&
    (activeCategoryCode === "all" || saved.isoCategoryCode === activeCategoryCode) &&
    (!batchCode || saved.batchCode === batchCode) &&
    (qualityStatus === "all" || saved.qualityStatus === qualityStatus) &&
    (recordStatus === "all" || (recordStatus === "available" ? saved.status !== "archived" : saved.status === recordStatus)) &&
    !loadedRows.some((row) => row.recordCode === saved.recordCode && row.inventoryCode === saved.inventoryCode)
      ? [saved, ...loadedRows]
      : loadedRows
  const rows = visibleRows.filter(
    (row) =>
      !keyword.trim() ||
      `${row.recordCode}${row.activityName}${row.sourceName ?? ""}${row.sourceCode}${row.allocatedAreaNames.join(" ")}${row.allocatedEquipmentNames.join(" ")}`
        .toLowerCase()
        .includes(keyword.trim().toLowerCase()),
  )
  const inventoryOptions = useMemo(() => {
    const byCode = new Map<string, { code: string; label: string; reportingPeriodId?: number | null }>()
    for (const period of catalog.data?.periods ?? []) byCode.set(period.code, { code: period.code, label: period.name, reportingPeriodId: period.id })
    for (const item of [...(sources.data?.items ?? []), ...(activities.data?.items ?? [])]) {
      if (!item.inventoryCode || byCode.has(item.inventoryCode)) continue
      const periodName = catalog.data?.periods.find((period) => period.id === item.reportingPeriodId)?.name
      byCode.set(item.inventoryCode, {
        code: item.inventoryCode,
        label: periodName ?? "未关联报告期的盘查任务",
        reportingPeriodId: item.reportingPeriodId,
      })
    }
    return [...byCode.values()].sort((a, b) => a.label.localeCompare(b.label, "zh-CN"))
  }, [activities.data?.items, catalog.data?.periods, sources.data?.items])

  const approved = rows.filter((row) => row.status === "approved").length
  const allocated = rows.filter((row) => row.allocationStatus === "complete").length
  const failures = rows.filter((row) => row.qualityStatus === "failed").length
  const selectedPeriod = catalog.data?.periods.find(
    (item) => item.code === inventoryCode || item.id === inventoryOptions.find((option) => option.code === inventoryCode)?.reportingPeriodId,
  )
  const selectedOrganization = catalog.data?.organizations.find((item) => item.code === selectedPeriod?.organizationCode) ?? catalog.data?.organizations[0]
  const selectedArea = catalog.data?.areas.find((item) => item.level === 0) ?? catalog.data?.areas[0]
  const selectedProfile = catalog.data?.reportingProfiles[0]
  const defaultMethod = availableMethods[0]
  const importContextReady = Boolean(selectedPeriod && selectedOrganization && selectedArea && selectedProfile && defaultMethod && selectedCategory)
  const formInitial = useMemo<GhgActivityWrite>(() => {
    if (editing && editing !== "new") {
      return {
        recordCode: editing.recordCode,
        inventoryCode: editing.inventoryCode,
        reportingPeriodId: editing.reportingPeriodId,
        organizationBoundaryId: editing.organizationBoundaryId,
        organizationCode: editing.organizationCode,
        facilityCode: editing.facilityCode,
        sourceCode: editing.sourceCode,
        activityCode: editing.activityCode,
        activityName: editing.activityName,
        periodStart: editing.periodStart,
        periodEnd: editing.periodEnd,
        isoCategoryCode: editing.isoCategoryCode,
        activityAmount: editing.activityAmount,
        activityUnit: editing.activityUnit,
        dataSourceType: editing.dataSourceType,
        measurementMethod: editing.measurementMethod,
        qualityStatus: editing.qualityStatus,
        parameterSetCode: editing.parameterSetCode,
        sourcePayload: editing.activityDetails,
        remarks: editing.remarks,
        status: editing.status,
        sourceSystem: editing.sourceSystem,
        sourceRecordType: editing.sourceRecordType,
        sourceRecordId: editing.sourceRecordId,
      }
    }
    return activityDefaults(catalog.data, sources.data?.items[0], activeCategoryCode === "all" ? undefined : activeCategoryCode)
  }, [activeCategoryCode, catalog.data, editing, sources.data?.items])

  const locate = (row: GhgActivity) => {
    setEditing(null)
    setDetail(row)
    setSaved(row)
    setInventoryCode(row.inventoryCode)
    setBatchCode("")
    setQualityStatus("all")
    setRecordStatus(row.status === "archived" ? "archived" : "available")
    setKeyword("")
    setOffset(0)
  }

  const save = (body: GhgActivityWrite) => {
    if (readOnly) return
    if (editing && editing !== "new") {
      actions.updateActivity.mutate({ recordCode: editing.recordCode, body }, { onSuccess: locate })
      return
    }
    actions.createActivity.mutate(body, { onSuccess: locate })
  }

  if (fixedCategoryCode && !catalog.isLoading && !selectedCategory) {
    return (
      <PageContainer className="flex-1" maxWidth="4xl">
        <AdminPageScaffold title="活动数据分类">
          <AdminEmptyState title="未找到该活动分类" />
        </AdminPageScaffold>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title={selectedCategory ? `${selectedCategory.name}活动数据` : "温室气体活动总账"}
        status={
          readOnly ? (
            <StatusBadge status="pending" label="只读查询" />
          ) : (
            <StatusBadge status={availableMethods.length ? "approved" : "pending"} label={availableMethods.length ? "可维护" : "方法待配置"} />
          )
        }
        topActions={
          readOnly ? undefined : (
            <div className="flex flex-wrap gap-2">
              <GhgGenerateActivities catalog={catalog.data} categoryCode={activeCategoryCode} inventoryCode={inventoryCode} onSelect={locate} />
              <Button
                size="sm"
                variant="outline"
                disabled={!importContextReady || actions.downloadTemplate.isPending}
                onClick={() => {
                  if (!selectedPeriod || !selectedOrganization || !selectedArea || !selectedProfile || !defaultMethod || !selectedCategory) return
                  actions.downloadTemplate.mutate({
                    inventoryCode: selectedPeriod.code,
                    reportingPeriodId: selectedPeriod.id,
                    organizationCode: selectedOrganization.code,
                    facilityCode: selectedArea.code,
                    isoCategoryCode: selectedCategory.code,
                    reportingProfileCode: selectedProfile.code,
                    methodCode: defaultMethod.code,
                  })
                }}
              >
                <Download />
                下载本类模板
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/carbon-mgmt/import" search={selectedCategory ? { category: selectedCategory.code } : {}}>
                  <FileUp />
                  导入本类数据
                </Link>
              </Button>
              <Button size="sm" onClick={() => setEditing("new")} disabled={!inventoryCode || (sources.data?.items ?? []).length === 0 || !selectedCategory}>
                <Plus />
                新增本类活动
              </Button>
            </div>
          )
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "search",
                node: (
                  <CarbonFormField label="搜索">
                    <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索本页活动、设备或排放源" />
                  </CarbonFormField>
                ),
              },
              {
                key: "inventory",
                node: (
                  <CarbonFormField label="盘查任务">
                    <Select value={inventoryCode || "all"} onValueChange={(value) => setInventoryCode(value === "all" ? "" : value)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部盘查任务</SelectItem>
                        {inventoryOptions.map((option) => (
                          <SelectItem key={option.code} value={option.code}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              ...(fixedCategoryCode
                ? []
                : [
                    {
                      key: "category",
                      node: (
                        <CarbonFormField label="ISO 二级分类">
                          <Select value={categoryCode} onValueChange={setCategoryCode}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">全部分类</SelectItem>
                              {(catalog.data?.categories ?? []).map((item, index) => (
                                <SelectItem key={`${item.code}-${index}`} value={item.code}>
                                  {item.code} {item.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </CarbonFormField>
                      ),
                    },
                  ]),
              {
                key: "status",
                node: (
                  <CarbonFormField label="记录状态">
                    <Select value={recordStatus} onValueChange={setRecordStatus}>
                      <SelectTrigger aria-label="记录状态">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="available">可用记录</SelectItem>
                        <SelectItem value="approved">已确认</SelectItem>
                        <SelectItem value="draft">草稿</SelectItem>
                        <SelectItem value="archived">已归档</SelectItem>
                        <SelectItem value="all">全部记录</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              {
                key: "batch",
                node: (
                  <CarbonFormField label="导入批次">
                    <Select
                      value={batchCode || "all"}
                      onValueChange={(value) => {
                        setBatchCode(value === "all" ? "" : value)
                        setSaved(null)
                      }}
                    >
                      <SelectTrigger aria-label="导入批次">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部批次</SelectItem>
                        {batchCode && !batches.data?.items.some((batch) => batch.batchCode === batchCode) && <SelectItem value={batchCode}>当前导入批次</SelectItem>}
                        {(batches.data?.items ?? [])
                          .filter((batch) => batch.status === "committed")
                          .map((batch) => (
                            <SelectItem key={batch.batchCode} value={batch.batchCode}>
                              {batch.fileName} · {batch.committedAt?.slice(0, 16).replace("T", " ")}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              {
                key: "quality",
                node: (
                  <CarbonFormField label="数据质量">
                    <Select value={qualityStatus} onValueChange={setQualityStatus}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部状态</SelectItem>
                        <SelectItem value="pass">通过</SelectItem>
                        <SelectItem value="warning">警告</SelectItem>
                        <SelectItem value="failed">失败</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
            ]}
            actions={
              <Button size="sm" variant="outline" disabled={activities.isFetching} onClick={() => void activities.refetch()}>
                <RefreshCw className={activities.isFetching ? "animate-spin" : ""} />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip>
            <MetricTile label="活动记录" value={rows.length} unit="条" />
            <MetricTile label="已确认" value={approved} unit="条" tone="success" />
            <MetricTile label="完成归集" value={allocated} unit="条" tone={allocated === rows.length && rows.length ? "success" : "warning"} />
            <MetricTile label="阻断记录" value={failures} unit="条" tone={failures ? "danger" : "default"} />
          </MetricStrip>
        }
      >
        {!readOnly && selectedCategory && availableMethods.length === 0 && !catalog.isLoading && <AdminEmptyState title="该分类尚未配置可执行核算方法" />}
        {!readOnly && selectedCategory && !inventoryCode && <AdminEmptyState title="请选择盘查任务" />}
        {!readOnly && selectedCategory && inventoryCode && (sources.data?.items ?? []).length === 0 && !sources.isLoading && <AdminEmptyState title="当前分类暂无启用排放源" />}
        {saved && (
          <AdminPanel
            title="最近保存的记录"
            actions={
              <Button size="sm" variant="link" onClick={() => setDetail(saved)}>
                查看保存值
              </Button>
            }
          >
            <div className="text-sm">
              {saved.activityName} · {saved.periodStart} 至 {saved.periodEnd} ·{" "}
              <span className="font-medium tabular-nums">
                {formatGhgAmount(saved.activityAmount)} {saved.activityUnit}
              </span>
            </div>
          </AdminPanel>
        )}
        {linkedActivity.isError && (
          <div role="alert" className="text-destructive text-sm">
            指定活动记录加载失败
          </div>
        )}
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>活动 / 排放源</TableHead>
                <TableHead>区域 / 设备</TableHead>
                {!fixedCategoryCode && <TableHead>分类</TableHead>}
                <TableHead>周期</TableHead>
                {dynamicFields.map((field) => (
                  <TableHead key={field.code}>{field.label}</TableHead>
                ))}
                <TableHead className="text-right">活动量</TableHead>
                <TableHead>来源</TableHead>
                {!fixedCategoryCode && (
                  <>
                    <TableHead>质量</TableHead>
                    <TableHead>归集</TableHead>
                  </>
                )}
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.isLoading && <AdminTableStateRow colSpan={(fixedCategoryCode ? 7 : 10) + dynamicFields.length}>正在加载活动台账</AdminTableStateRow>}
              {activities.isError && (
                <AdminTableStateRow colSpan={(fixedCategoryCode ? 7 : 10) + dynamicFields.length} tone="danger">
                  活动台账加载失败
                </AdminTableStateRow>
              )}
              {!activities.isLoading && !activities.isError && rows.length === 0 && (
                <AdminTableStateRow colSpan={(fixedCategoryCode ? 7 : 10) + dynamicFields.length}>当前筛选条件下没有活动记录</AdminTableStateRow>
              )}
              {rows.map((row) => (
                <TableRow
                  key={`${row.inventoryCode}-${row.recordCode}`}
                  className={saved?.recordCode === row.recordCode && saved.inventoryCode === row.inventoryCode ? "cursor-pointer bg-accent/40" : "cursor-pointer"}
                  onClick={() => setDetail(row)}
                >
                  <TableCell>
                    <div className="font-medium">{row.activityName}</div>
                    <div className="text-muted-foreground text-xs">
                      {row.sourceName ||
                        sources.data?.items.find((source) => source.inventoryCode === row.inventoryCode && source.sourceCode === row.sourceCode)?.sourceName ||
                        "未命名排放源"}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>{row.allocatedAreaNames.join("、") || "未归集"}</div>
                    <div className="text-muted-foreground text-xs">
                      {row.allocatedEquipmentNames.join("、") ||
                        ghgObjectLabel(
                          "facility_or_device",
                          row.activityDetails.facility_or_device ?? row.activityDetails.vehicle_or_machine ?? row.activityDetails.meter_point,
                          catalog.data,
                        ) ||
                        "区域级归集"}
                    </div>
                  </TableCell>
                  {!fixedCategoryCode && (
                    <TableCell>
                      <div>{categoryLabel(catalog.data, row.isoCategoryCode)}</div>
                      <div className="text-muted-foreground text-xs">{getScopeLabel(row.ghgScope)}</div>
                    </TableCell>
                  )}
                  <TableCell>
                    {row.periodStart} 至 {row.periodEnd}
                  </TableCell>
                  {dynamicFields.map((field) => (
                    <TableCell key={field.code}>
                      {choiceLabel(field.code, ghgObjectLabel(field.code, row.activityDetails[field.code], catalog.data, entryOptions.data?.energy))}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-mono tabular-nums">
                    {formatGhgAmount(row.activityAmount)} {row.activityUnit}
                  </TableCell>
                  <TableCell>{sourceLabel(row.dataSourceType)}</TableCell>
                  {!fixedCategoryCode && (
                    <>
                      <TableCell>
                        <StatusBadge
                          status={row.qualityStatus === "pass" ? "approved" : row.qualityStatus === "failed" ? "rejected" : "pending"}
                          label={statusLabel(row.qualityStatus)}
                        />
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          status={row.allocationStatus === "complete" ? "approved" : "rejected"}
                          label={row.allocationStatus === "complete" ? `${row.allocationCount} 项` : "待归集"}
                        />
                      </TableCell>
                    </>
                  )}
                  <TableCell>
                    <StatusBadge status={row.status === "approved" ? "approved" : "draft"} label={statusLabel(row.status)} />
                    {fixedCategoryCode && row.qualityStatus !== "pass" && <div className="text-muted-foreground text-xs">{statusLabel(row.qualityStatus)}</div>}
                  </TableCell>
                  <TableCell className="text-right" onClick={(event) => event.stopPropagation()}>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" aria-label={`查看${row.activityName}`} onClick={() => setDetail(row)}>
                        <Eye />
                      </Button>
                      {!readOnly && (
                        <>
                          <Button size="sm" variant="ghost" aria-label={`编辑${row.activityName}`} onClick={() => setEditing(row)}>
                            <Edit />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`删除${row.activityName}`}
                            onClick={() => {
                              if (window.confirm(`确认删除“${row.activityName}”（${row.activityAmount} ${row.activityUnit}）？`)) {
                                setLinkedRecordCode(undefined)
                                actions.deleteActivity.mutate(
                                  { inventoryCode: row.inventoryCode, recordCode: row.recordCode },
                                  {
                                    onSuccess: () => {
                                      setSaved(null)
                                      setDetail(null)
                                      setLinkedRecordCode(undefined)
                                    },
                                  },
                                )
                              }
                            }}
                          >
                            <Trash2 />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
        <div className="flex items-center justify-end gap-3 text-sm">
          <span className="text-muted-foreground">
            共 {activities.data?.total ?? 0} 条 · 第 {Math.floor(offset / 200) + 1} 页
          </span>
          <Button size="sm" variant="outline" disabled={offset === 0 || activities.isFetching} onClick={() => setOffset(Math.max(0, offset - 200))}>
            上一页
          </Button>
          <Button size="sm" variant="outline" disabled={offset + 200 >= (activities.data?.total ?? 0) || activities.isFetching} onClick={() => setOffset(offset + 200)}>
            下一页
          </Button>
        </div>
      </AdminPageScaffold>
      {!readOnly && (
        <Sheet open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
          <SheetContent className="overflow-y-auto" size="xwide">
            <SheetHeader>
              <SheetTitle>{editing === "new" ? "新增活动数据" : "编辑活动数据"}</SheetTitle>
            </SheetHeader>
            <div className="px-4 pb-4">
              <ActivityForm
                catalog={catalog.data}
                sources={sources.data?.items ?? []}
                initial={formInitial}
                lockedCategoryCode={fixedCategoryCode}
                pending={actions.createActivity.isPending || actions.updateActivity.isPending}
                submitLabel={editing === "new" ? "保存活动数据" : "更新活动数据"}
                onSubmit={save}
              />
            </div>
          </SheetContent>
        </Sheet>
      )}
      <Sheet open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)}>
        <SheetContent className="overflow-y-auto" size="xwide">
          <SheetHeader>
            <SheetTitle>活动数据详情</SheetTitle>
          </SheetHeader>
          <div className="space-y-4 px-4 pb-4">
            <AdminPanel>
              <div className="grid gap-3 text-sm md:grid-cols-3">
                <DetailItem label="活动名称" value={detail?.activityName} />
                <DetailItem label="所属区域" value={detail?.facilityName || catalog.data?.areas.find((area) => area.code === detail?.facilityCode)?.name} />
                <DetailItem
                  label="排放源"
                  value={
                    detail?.sourceName ||
                    sources.data?.items.find((source) => source.inventoryCode === detail?.inventoryCode && source.sourceCode === detail?.sourceCode)?.sourceName ||
                    "未命名排放源"
                  }
                />
                <DetailItem label="分类" value={detail ? categoryLabel(catalog.data, detail.isoCategoryCode) : ""} />
                <DetailItem label="期间" value={detail ? `${detail.periodStart} 至 ${detail.periodEnd}` : ""} />
                <DetailItem label="活动量" value={detail ? `${formatGhgAmount(detail.activityAmount)} ${detail.activityUnit}` : ""} />
                <DetailItem label="数据来源" value={detail ? sourceLabel(detail.dataSourceType) : ""} />
              </div>
            </AdminPanel>
            <AdminPanel>
              <div className="mb-3 font-medium text-sm">分类字段</div>
              <div className="grid gap-3 text-sm md:grid-cols-3">
                {catalog.data?.categories
                  .find((item) => item.code === detail?.isoCategoryCode)
                  ?.activityFields.map((field) => (
                    <DetailItem
                      key={field.code}
                      label={field.label}
                      value={choiceLabel(field.code, ghgObjectLabel(field.code, detail?.activityDetails[field.code], catalog.data, entryOptions.data?.energy))}
                    />
                  ))}
              </div>
            </AdminPanel>
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground text-xs">系统记录编号：{detail?.recordCode}</span>
              {!readOnly && detail && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditing(detail)
                    setDetail(null)
                  }}
                >
                  编辑本条活动
                </Button>
              )}
            </div>
            <ActivityFactorSelection key={detail ? `${detail.inventoryCode}:${detail.recordCode}` : "empty"} activity={detail} readOnly={readOnly} />
            <AdminPanel>
              {readOnly ? (
                <ReadonlyAllocationList allocations={allocations.data?.items ?? []} loading={allocations.isLoading} />
              ) : (
                <AllocationEditor
                  catalog={catalog.data}
                  activity={detail ?? undefined}
                  allocations={allocations.data?.items ?? []}
                  pending={actions.replaceAllocations.isPending}
                  onSubmit={(allocationRows) => {
                    if (!detail) return
                    actions.replaceAllocations.mutate({
                      inventoryCode: detail.inventoryCode,
                      recordCode: detail.recordCode,
                      allocations: allocationRows,
                    })
                  }}
                />
              )}
            </AdminPanel>
          </div>
        </SheetContent>
      </Sheet>
    </PageContainer>
  )
}

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-medium">{value || "-"}</div>
    </div>
  )
}

function ActivityFactorSelection({ activity, readOnly = false }: { activity?: GhgActivity | null; readOnly?: boolean }) {
  const factorActions = useCalculationFactorActions()
  const candidates = useActivityFactorCandidates({ inventoryCode: activity?.inventoryCode, recordCode: activity?.recordCode })
  const [selectedId, setSelectedId] = useState("")
  const activeId = selectedId
  const currentParameters = candidates.data?.currentParameters ?? []
  return (
    <AdminPanel title="因子参数">
      <div className="space-y-4">
        <div className="grid gap-3 text-sm md:grid-cols-3">
          <DetailItem label="活动范围" value={getScopeLabel(activity?.ghgScope)} />
          <DetailItem label="活动单位" value={activity?.activityUnit} />
        </div>
        {currentParameters.length > 0 && (
          <AdminDataTable>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>参数</TableHead>
                  <TableHead className="text-right">当前值</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead>质量</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentParameters.map((parameter) => (
                  <TableRow key={parameter.parameterCode}>
                    <TableCell>
                      <div className="font-medium">{parameter.parameterName}</div>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatGhgAmount(parameter.value)} {parameter.unit}
                    </TableCell>
                    <TableCell>{parameter.sourceName}</TableCell>
                    <TableCell>
                      <StatusBadge status={parameter.qualityGrade === "A" ? "approved" : "pending"} label={parameter.qualityGrade || "未标记"} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminDataTable>
        )}
        {currentParameters.length > 0 && (
          <details className="text-muted-foreground text-xs">
            <summary className="cursor-pointer">参数标识</summary>
            <div className="mt-2 space-y-1">
              {activity?.parameterSetCode && <div>参数集：{activity.parameterSetCode}</div>}
              {currentParameters.map((parameter) => (
                <div key={parameter.parameterCode}>
                  {parameter.parameterName}：{parameter.parameterCode}
                </div>
              ))}
            </div>
          </details>
        )}
        {candidates.isLoading && <div className="text-muted-foreground text-sm">正在加载候选因子</div>}
        {candidates.isError && <div className="text-destructive text-sm">候选因子加载失败</div>}
        {!readOnly && !candidates.isLoading && !candidates.isError && (
          <div className="grid items-end gap-3 md:grid-cols-[1fr_auto]">
            <CarbonFormField label="候选因子">
              <Select value={activeId} onValueChange={setSelectedId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择计算因子" />
                </SelectTrigger>
                <SelectContent>
                  {(candidates.data?.items ?? []).map((factor) => (
                    <SelectItem key={factor.id} value={String(factor.id)}>
                      {getCategoryLabel(factor.category)} / {getSubCategoryLabel(factor.subCategory)} / {formatGhgAmount(factor.factorValue)} {factor.factorUnit} / {factor.year}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CarbonFormField>
            <Button
              disabled={!activity || !activeId || factorActions.applyToActivity.isPending}
              onClick={() => {
                if (!activity || !activeId) return
                factorActions.applyToActivity.mutate({
                  inventoryCode: activity.inventoryCode,
                  recordCode: activity.recordCode,
                  factorId: Number(activeId),
                })
              }}
            >
              采用因子
            </Button>
          </div>
        )}
        {!candidates.isLoading && !candidates.isError && (candidates.data?.items ?? []).length === 0 && (
          <div className="text-muted-foreground text-sm">当前活动暂无匹配的启用因子</div>
        )}
      </div>
    </AdminPanel>
  )
}

function ReadonlyAllocationList({
  allocations,
  loading,
}: {
  allocations: Array<{
    allocationCode: string
    allocationRatio: string
    areaName: string
    equipmentName?: string | null
    measurementBoundaryId?: number | null
  }>
  loading?: boolean
}) {
  return (
    <div className="space-y-3">
      <div className="font-medium text-sm">归集结果</div>
      <AdminDataTable>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>区域</TableHead>
              <TableHead>设备</TableHead>
              <TableHead>计量边界</TableHead>
              <TableHead className="text-right">比例</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <AdminTableStateRow colSpan={4}>正在加载归集结果</AdminTableStateRow>}
            {!loading && allocations.length === 0 && <AdminTableStateRow colSpan={4}>暂无归集结果</AdminTableStateRow>}
            {allocations.map((item) => (
              <TableRow key={item.allocationCode}>
                <TableCell>{item.areaName}</TableCell>
                <TableCell>{item.equipmentName ?? "-"}</TableCell>
                <TableCell>{item.measurementBoundaryId ?? "-"}</TableCell>
                <TableCell className="text-right font-mono tabular-nums">{item.allocationRatio}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminDataTable>
    </div>
  )
}
