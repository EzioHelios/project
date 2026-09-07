import { createFileRoute, Link } from "@tanstack/react-router"
import { Download, Edit, Eye, FileUp, Plus, RefreshCw, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { z } from "zod"

import { AdminDataTable, AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { ActivityForm, AllocationEditor, activityDefaults, CarbonFormField, categoryLabel, choiceLabel, sourceLabel, statusLabel } from "@/components/carbon/ghg-maintenance"
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
  useGhgActivityAllocations,
  useGhgCatalog,
  useGhgEmissionSources,
  useGhgInventoryActions,
} from "@/lib/api/hooks/ghg-inventory"
import { getCategoryLabel, getScopeLabel, getSubCategoryLabel } from "@/lib/carbon-factor-labels"
import { normalizeGhgCategoryCode } from "@/lib/ghg-categories"

const searchSchema = z.object({ category: z.preprocess(normalizeGhgCategoryCode, z.string().optional()) })

export const Route = createFileRoute("/_app/carbon-mgmt/activities")({
  validateSearch: (search) => searchSchema.parse(search),
  component: GhgActivityLedgerPage,
})

function GhgActivityLedgerPage() {
  const { category } = Route.useSearch()
  return <GhgActivityLedger initialCategoryCode={category} readOnly />
}

export function GhgActivityLedger({ fixedCategoryCode, initialCategoryCode, readOnly = false }: { fixedCategoryCode?: string; initialCategoryCode?: string; readOnly?: boolean }) {
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [inventoryCode, setInventoryCode] = useState("")
  const [categoryCode, setCategoryCode] = useState(initialCategoryCode ?? fixedCategoryCode ?? "all")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [keyword, setKeyword] = useState("")
  const [editing, setEditing] = useState<GhgActivity | "new" | null>(null)
  const [detail, setDetail] = useState<GhgActivity | null>(null)

  useEffect(() => {
    setCategoryCode(initialCategoryCode ?? fixedCategoryCode ?? "all")
  }, [fixedCategoryCode, initialCategoryCode])

  const activeCategoryCode = fixedCategoryCode ?? categoryCode
  const selectedCategory = catalog.data?.categories.find((item) => item.code === activeCategoryCode)
  const dynamicFields = selectedCategory?.activityFields ?? []
  const availableMethods = useMemo(
    () => (catalog.data?.methods ?? []).filter((method) => selectedCategory?.defaultMethods.includes(method.code) && method.executable),
    [catalog.data?.methods, selectedCategory],
  )
  const activities = useGhgActivities({
    inventoryCode: inventoryCode || undefined,
    categoryCode: activeCategoryCode === "all" ? undefined : activeCategoryCode,
    qualityStatus: qualityStatus === "all" ? undefined : qualityStatus,
  })
  const sources = useGhgEmissionSources({
    inventoryCode: inventoryCode || undefined,
    categoryCode: activeCategoryCode === "all" ? undefined : activeCategoryCode,
    status: "active",
  })
  const allocations = useGhgActivityAllocations({ inventoryCode: detail?.inventoryCode, recordCode: detail?.recordCode })
  const rows = (activities.data?.items ?? []).filter(
    (row) => !keyword.trim() || `${row.recordCode}${row.activityName}${row.sourceCode}`.toLowerCase().includes(keyword.trim().toLowerCase()),
  )
  const inventoryOptions = useMemo(() => {
    const byCode = new Map<string, { code: string; label: string; reportingPeriodId?: number | null }>()
    for (const item of [...(sources.data?.items ?? []), ...(activities.data?.items ?? [])]) {
      if (!item.inventoryCode || byCode.has(item.inventoryCode)) continue
      const periodName = catalog.data?.periods.find((period) => period.id === item.reportingPeriodId)?.name
      byCode.set(item.inventoryCode, {
        code: item.inventoryCode,
        label: periodName ? `${periodName}（${item.inventoryCode}）` : item.inventoryCode,
        reportingPeriodId: item.reportingPeriodId,
      })
    }
    return [...byCode.values()].sort((a, b) => a.label.localeCompare(b.label, "zh-CN"))
  }, [activities.data?.items, catalog.data?.periods, sources.data?.items])

  const approved = rows.filter((row) => row.status === "approved").length
  const allocated = rows.filter((row) => row.allocationStatus === "complete").length
  const failures = rows.filter((row) => row.qualityStatus === "failed").length
  const selectedPeriod = catalog.data?.periods.find((item) => item.code === inventoryCode) ?? catalog.data?.periods[0]
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

  const save = (body: GhgActivityWrite) => {
    if (readOnly) return
    if (editing && editing !== "new") {
      actions.updateActivity.mutate({ recordCode: editing.recordCode, body }, { onSuccess: () => setEditing(null) })
      return
    }
    actions.createActivity.mutate(body, { onSuccess: () => setEditing(null) })
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
        title={selectedCategory ? `${selectedCategory.code} ${selectedCategory.name}活动数据` : "温室气体活动总账"}
        status={
          readOnly ? (
            <StatusBadge status="pending" label="只读查询" />
          ) : (
            <StatusBadge status={availableMethods.length ? "approved" : "pending"} label={availableMethods.length ? "可维护" : "方法待配置"} />
          )
        }
        topActions={
          readOnly ? undefined : (
            <div className="flex gap-2">
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
              <Button size="sm" onClick={() => setEditing("new")} disabled={(sources.data?.items ?? []).length === 0 || !selectedCategory}>
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
                    <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="记录、活动或排放源" />
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
        {!readOnly && selectedCategory && (sources.data?.items ?? []).length === 0 && !sources.isLoading && <AdminEmptyState title="当前分类暂无启用排放源" />}
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>记录 / 活动</TableHead>
                <TableHead>区域 / 设备</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>周期</TableHead>
                {dynamicFields.map((field) => (
                  <TableHead key={field.code}>{field.label}</TableHead>
                ))}
                <TableHead className="text-right">活动量</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>归集</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.isLoading && <AdminTableStateRow colSpan={10 + dynamicFields.length}>正在加载活动台账</AdminTableStateRow>}
              {activities.isError && (
                <AdminTableStateRow colSpan={10 + dynamicFields.length} tone="danger">
                  活动台账加载失败
                </AdminTableStateRow>
              )}
              {!activities.isLoading && !activities.isError && rows.length === 0 && (
                <AdminTableStateRow colSpan={10 + dynamicFields.length}>当前筛选条件下没有活动记录</AdminTableStateRow>
              )}
              {rows.map((row) => (
                <TableRow key={`${row.inventoryCode}-${row.recordCode}`} className="cursor-pointer" onClick={() => setDetail(row)}>
                  <TableCell>
                    <div className="font-medium">{row.activityName}</div>
                    <div className="text-muted-foreground text-xs">{row.recordCode}</div>
                  </TableCell>
                  <TableCell>
                    <div>{row.allocatedAreaNames.join("、") || "未归集"}</div>
                    <div className="text-muted-foreground text-xs">{row.allocatedEquipmentNames.join("、") || "区域级归集"}</div>
                  </TableCell>
                  <TableCell>
                    <div>{categoryLabel(catalog.data, row.isoCategoryCode)}</div>
                    <div className="text-muted-foreground text-xs">{row.ghgScope.toUpperCase()}</div>
                  </TableCell>
                  <TableCell>
                    {row.periodStart} 至 {row.periodEnd}
                  </TableCell>
                  {dynamicFields.map((field) => (
                    <TableCell key={field.code}>{choiceLabel(field.code, row.activityDetails[field.code])}</TableCell>
                  ))}
                  <TableCell className="text-right font-mono tabular-nums">
                    {Number(row.activityAmount).toLocaleString("zh-CN")} {row.activityUnit}
                  </TableCell>
                  <TableCell>{sourceLabel(row.dataSourceType)}</TableCell>
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
                  <TableCell>
                    <StatusBadge status={row.status === "approved" ? "approved" : "draft"} label={statusLabel(row.status)} />
                  </TableCell>
                  <TableCell className="text-right" onClick={(event) => event.stopPropagation()}>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setDetail(row)}>
                        <Eye />
                      </Button>
                      {!readOnly && (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => setEditing(row)}>
                            <Edit />
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => actions.deleteActivity.mutate({ inventoryCode: row.inventoryCode, recordCode: row.recordCode })}>
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
                <DetailItem label="记录编号" value={detail?.recordCode} />
                <DetailItem label="排放源" value={detail?.sourceCode} />
                <DetailItem label="分类" value={detail ? categoryLabel(catalog.data, detail.isoCategoryCode) : ""} />
                <DetailItem label="期间" value={detail ? `${detail.periodStart} 至 ${detail.periodEnd}` : ""} />
                <DetailItem label="活动量" value={detail ? `${Number(detail.activityAmount).toLocaleString("zh-CN")} ${detail.activityUnit}` : ""} />
                <DetailItem label="数据来源" value={detail ? sourceLabel(detail.dataSourceType) : ""} />
              </div>
            </AdminPanel>
            <AdminPanel>
              <div className="mb-3 font-medium text-sm">分类字段</div>
              <div className="grid gap-3 text-sm md:grid-cols-3">
                {catalog.data?.categories
                  .find((item) => item.code === detail?.isoCategoryCode)
                  ?.activityFields.map((field) => (
                    <DetailItem key={field.code} label={field.label} value={choiceLabel(field.code, detail?.activityDetails[field.code])} />
                  ))}
              </div>
            </AdminPanel>
            <ActivityFactorSelection activity={detail} readOnly={readOnly} />
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
  const activeId = selectedId || String(candidates.data?.items[0]?.id ?? "")
  const currentParameters = candidates.data?.currentParameters ?? []
  return (
    <AdminPanel title="因子参数">
      <div className="space-y-4">
        <div className="grid gap-3 text-sm md:grid-cols-3">
          <DetailItem label="参数集" value={activity?.parameterSetCode || (currentParameters.length ? `${activity?.recordCode}-PS1` : undefined)} />
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
                      <div className="text-muted-foreground text-xs">{parameter.parameterCode}</div>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {parameter.value} {parameter.unit}
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
                      {getCategoryLabel(factor.category)} / {getSubCategoryLabel(factor.subCategory)} / {factor.factorValue} {factor.factorUnit} / {factor.year}
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
