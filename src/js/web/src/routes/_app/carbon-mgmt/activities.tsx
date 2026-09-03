import { createFileRoute, Link } from "@tanstack/react-router"
import { Edit, FileUp, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { z } from "zod"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { ActivityForm, AllocationEditor, activityDefaults, CarbonFormField, categoryLabel, choiceLabel, sourceLabel, statusLabel } from "@/components/carbon/ghg-maintenance"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
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

const searchSchema = z.object({ category: z.coerce.string().optional() })

export const Route = createFileRoute("/_app/carbon-mgmt/activities")({
  validateSearch: (search) => searchSchema.parse(search),
  component: GhgActivityLedgerPage,
})

function GhgActivityLedgerPage() {
  const { category } = Route.useSearch()
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [inventoryCode, setInventoryCode] = useState("")
  const [categoryCode, setCategoryCode] = useState(category ?? "all")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [keyword, setKeyword] = useState("")
  const [editing, setEditing] = useState<GhgActivity | "new" | null>(null)
  const [detail, setDetail] = useState<GhgActivity | null>(null)
  const [generateOpen, setGenerateOpen] = useState(false)
  const activities = useGhgActivities({
    inventoryCode: inventoryCode || undefined,
    categoryCode: categoryCode === "all" ? undefined : categoryCode,
    qualityStatus: qualityStatus === "all" ? undefined : qualityStatus,
  })
  const sources = useGhgEmissionSources({
    inventoryCode: inventoryCode || undefined,
    categoryCode: categoryCode === "all" ? undefined : categoryCode,
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
  const selectedCategory = catalog.data?.categories.find((item) => item.code === categoryCode)
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
    return activityDefaults(catalog.data, sources.data?.items[0])
  }, [catalog.data, editing, sources.data?.items])

  const save = (body: GhgActivityWrite) => {
    if (editing && editing !== "new") {
      actions.updateActivity.mutate({ recordCode: editing.recordCode, body }, { onSuccess: () => setEditing(null) })
      return
    }
    actions.createActivity.mutate(body, { onSuccess: () => setEditing(null) })
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title={selectedCategory ? `${selectedCategory.code} ${selectedCategory.name}活动数据` : "温室气体活动台账"}
        topActions={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setGenerateOpen(true)}>
              <Sparkles />
              生成活动数据
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/carbon-mgmt/import">
                <FileUp />
                批量导入
              </Link>
            </Button>
            <Button size="sm" onClick={() => setEditing("new")} disabled={(sources.data?.items ?? []).length === 0}>
              <Plus />
              新增活动
            </Button>
          </div>
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
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>记录 / 活动</TableHead>
                <TableHead>区域 / 设备</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>周期</TableHead>
                <TableHead className="text-right">活动量</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>归集</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.isLoading && <AdminTableStateRow colSpan={10}>正在加载活动台账</AdminTableStateRow>}
              {activities.isError && (
                <AdminTableStateRow colSpan={10} tone="danger">
                  活动台账加载失败
                </AdminTableStateRow>
              )}
              {!activities.isLoading && !activities.isError && rows.length === 0 && <AdminTableStateRow colSpan={10}>当前筛选条件下没有活动记录</AdminTableStateRow>}
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
                      <Button size="sm" variant="ghost" onClick={() => setEditing(row)}>
                        <Edit />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => actions.deleteActivity.mutate({ inventoryCode: row.inventoryCode, recordCode: row.recordCode })}>
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPageScaffold>
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
              pending={actions.createActivity.isPending || actions.updateActivity.isPending}
              submitLabel={editing === "new" ? "保存活动数据" : "更新活动数据"}
              onSubmit={save}
            />
          </div>
        </SheetContent>
      </Sheet>
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
            <ActivityFactorSelection activity={detail} />
            <AdminPanel>
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
            </AdminPanel>
          </div>
        </SheetContent>
      </Sheet>
      <GenerateDialog
        catalog={catalog.data}
        inventoryOptions={inventoryOptions}
        open={generateOpen}
        pending={actions.generateActivities.isPending}
        onOpenChange={setGenerateOpen}
        onSubmit={(body) => actions.generateActivities.mutate(body, { onSuccess: () => setGenerateOpen(false) })}
      />
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

function ActivityFactorSelection({ activity }: { activity?: GhgActivity | null }) {
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
        {!candidates.isLoading && !candidates.isError && (
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

function GenerateDialog({
  catalog,
  inventoryOptions,
  open,
  pending,
  onOpenChange,
  onSubmit,
}: {
  catalog: ReturnType<typeof useGhgCatalog>["data"]
  inventoryOptions: { code: string; label: string; reportingPeriodId?: number | null }[]
  open: boolean
  pending?: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (body: { inventoryCode: string; reportingPeriodId: number; organizationBoundaryId?: number; sourceTypes: string[] }) => void
}) {
  const period = catalog?.periods[0]
  const [reportingPeriodId, setReportingPeriodId] = useState(period?.id ?? 0)
  const selectedPeriod = catalog?.periods.find((item) => item.id === reportingPeriodId) ?? period
  const selectedInventory = inventoryOptions.find((item) => item.reportingPeriodId === selectedPeriod?.id) ?? inventoryOptions[0]
  const sourceTypes = ["energy_electricity", "employee_commute"]
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>生成组织碳活动数据</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <CarbonFormField label="报告期">
            <Select value={String(reportingPeriodId || selectedPeriod?.id || "")} onValueChange={(value) => setReportingPeriodId(Number(value))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(catalog?.periods ?? []).map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CarbonFormField>
          <div className="rounded-md border border-border/70 p-3 text-sm">
            <div className="font-medium">盘查任务：{selectedInventory?.code ?? "请先维护排放源或活动数据"}</div>
            <div className="mt-2 space-y-1 text-muted-foreground text-sm">
              <div>购入电力：从能源事实汇总生成 2.1 活动数据</div>
              <div>员工通勤：从经营活动台账生成 3.3 活动数据</div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            disabled={pending || !selectedPeriod || !selectedInventory}
            onClick={() => {
              if (!selectedPeriod || !selectedInventory) return
              onSubmit({ inventoryCode: selectedInventory.code, reportingPeriodId: selectedPeriod.id, sourceTypes })
            }}
          >
            生成
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
