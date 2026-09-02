import { createFileRoute } from "@tanstack/react-router"
import { Download, Edit, Eye, FileUp, Plus, RefreshCw, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { CarbonFormField } from "@/components/carbon/ghg-maintenance"
import { PaginationBar } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import {
  type CalculationFactor,
  type CalculationFactorImportPreview,
  type CalculationFactorWrite,
  factorWriteDefaults,
  useCalculationFactorActions,
  useCalculationFactors,
} from "@/lib/api/hooks/factor-library"
import { getActivityUnitLabel, getCategoryLabel, getImportMethodLabel, getScopeLabel, getSourceSystemLabel, getSubCategoryLabel } from "@/lib/carbon-factor-labels"

export const Route = createFileRoute("/_app/carbon-mgmt/calculation-factors")({
  component: CalculationFactorsPage,
})

type FactorFormState = {
  mode: "new" | "edit"
  factor?: CalculationFactor
}

function CalculationFactorsPage() {
  const actions = useCalculationFactorActions()
  const [keyword, setKeyword] = useState("")
  const [scope, setScope] = useState("all")
  const [category, setCategory] = useState("all")
  const [active, setActive] = useState("all")
  const [owner, setOwner] = useState("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [editing, setEditing] = useState<FactorFormState | null>(null)
  const [detail, setDetail] = useState<CalculationFactor | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const factorsQuery = useCalculationFactors({
    keyword: keyword.trim() || undefined,
    scope,
    category,
    active,
    owner,
    pageIndex,
    pageSize,
  })
  const rows = factorsQuery.data?.items ?? []
  const enterpriseCount = rows.filter((factor) => factor.ownerType === "enterprise").length
  const sharedCount = rows.filter((factor) => factor.ownerType === "shared").length
  const activeCount = rows.filter((factor) => factor.isActive).length

  const initial = useMemo(() => factorWriteDefaults(editing?.factor), [editing?.factor])

  const save = (body: CalculationFactorWrite) => {
    if (editing?.mode === "edit" && editing.factor) {
      actions.update.mutate({ id: editing.factor.id, body }, { onSuccess: () => setEditing(null) })
      return
    }
    actions.create.mutate(body, { onSuccess: () => setEditing(null) })
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title="企业计算因子库"
        topActions={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={actions.downloadTemplate}>
              <Download />
              下载模板
            </Button>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
              <FileUp />
              模板导入
            </Button>
            <Button size="sm" onClick={() => setEditing({ mode: "new" })}>
              <Plus />
              新增因子
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
                    <Input
                      value={keyword}
                      onChange={(event) => {
                        setKeyword(event.target.value)
                        setPageIndex(0)
                      }}
                      placeholder="类别、子类、单位、来源"
                    />
                  </CarbonFormField>
                ),
              },
              {
                key: "scope",
                node: (
                  <CarbonFormField label="范围">
                    <Select
                      value={scope}
                      onValueChange={(value) => {
                        setScope(value)
                        setPageIndex(0)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部范围</SelectItem>
                        <SelectItem value="scope1">范围1</SelectItem>
                        <SelectItem value="scope2">范围2</SelectItem>
                        <SelectItem value="scope3">范围3</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              {
                key: "category",
                node: (
                  <CarbonFormField label="类别">
                    <Select
                      value={category}
                      onValueChange={(value) => {
                        setCategory(value)
                        setPageIndex(0)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部类别</SelectItem>
                        <SelectItem value="electricity">购电</SelectItem>
                        <SelectItem value="fuel">燃料</SelectItem>
                        <SelectItem value="refrigerant">制冷剂</SelectItem>
                        <SelectItem value="transport">运输</SelectItem>
                        <SelectItem value="waste">废弃物</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              {
                key: "owner",
                node: (
                  <CarbonFormField label="归属">
                    <Select
                      value={owner}
                      onValueChange={(value) => {
                        setOwner(value)
                        setPageIndex(0)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部因子</SelectItem>
                        <SelectItem value="enterprise">企业因子</SelectItem>
                        <SelectItem value="shared">共享因子</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
              {
                key: "active",
                node: (
                  <CarbonFormField label="状态">
                    <Select
                      value={active}
                      onValueChange={(value) => {
                        setActive(value)
                        setPageIndex(0)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部状态</SelectItem>
                        <SelectItem value="active">启用</SelectItem>
                        <SelectItem value="inactive">停用</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
            ]}
            actions={
              <Button size="sm" variant="outline" disabled={factorsQuery.isFetching} onClick={() => void factorsQuery.refetch()}>
                <RefreshCw className={factorsQuery.isFetching ? "animate-spin" : ""} />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip>
            <MetricTile label="计算因子" value={factorsQuery.data?.total ?? 0} unit="条" />
            <MetricTile label="企业因子" value={enterpriseCount} unit="条" tone={enterpriseCount ? "success" : "default"} />
            <MetricTile label="共享因子" value={sharedCount} unit="条" />
            <MetricTile label="本页启用" value={activeCount} unit="条" tone="success" />
          </MetricStrip>
        }
      >
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>因子</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>活动单位</TableHead>
                <TableHead className="text-right">因子值</TableHead>
                <TableHead>年份</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>归属</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {factorsQuery.isLoading && <AdminTableStateRow colSpan={9}>正在加载计算因子</AdminTableStateRow>}
              {factorsQuery.isError && (
                <AdminTableStateRow colSpan={9} tone="danger">
                  计算因子加载失败
                </AdminTableStateRow>
              )}
              {!factorsQuery.isLoading && !factorsQuery.isError && rows.length === 0 && <AdminTableStateRow colSpan={9}>当前筛选条件下没有计算因子</AdminTableStateRow>}
              {rows.map((factor) => (
                <TableRow key={factor.id}>
                  <TableCell>
                    <div className="font-medium">{getSubCategoryLabel(factor.subCategory)}</div>
                    <div className="text-muted-foreground text-xs">
                      {getCategoryLabel(factor.category)} / {factor.subCategory}
                    </div>
                  </TableCell>
                  <TableCell>{getScopeLabel(factor.scope)}</TableCell>
                  <TableCell>
                    <div>{getActivityUnitLabel(factor.unit)}</div>
                    <div className="text-muted-foreground text-xs">{factor.unit}</div>
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums">
                    {factor.factorValue} {factor.factorUnit}
                  </TableCell>
                  <TableCell>{factor.year}</TableCell>
                  <TableCell>
                    <div className="max-w-[220px] truncate">{factor.source}</div>
                    <div className="text-muted-foreground text-xs">{getImportMethodLabel(factor.projectionStatus)}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={factor.ownerType === "enterprise" ? "default" : "secondary"}>{factor.ownerType === "enterprise" ? "企业" : "共享"}</Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      status={!factor.isActive ? "draft" : factor.reviewStatus === "approved" ? "approved" : "pending"}
                      label={!factor.isActive ? "停用" : reviewStatusLabel(factor.reviewStatus)}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setDetail(factor)}>
                        <Eye />
                      </Button>
                      <Button size="sm" variant="ghost" disabled={!factor.editable} onClick={() => setEditing({ mode: "edit", factor })}>
                        <Edit />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={!factor.editable || actions.remove.isPending}
                        onClick={() => {
                          if (window.confirm(`删除计算因子：${getSubCategoryLabel(factor.subCategory)} ${factor.year}？`)) actions.remove.mutate(factor.id)
                        }}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
        <PaginationBar
          page={factorsQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPageIndex(0)
          }}
        />
      </AdminPageScaffold>
      <Sheet open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="overflow-y-auto" size="wide">
          <SheetHeader>
            <SheetTitle>{editing?.mode === "edit" ? "编辑企业计算因子" : "新增企业计算因子"}</SheetTitle>
          </SheetHeader>
          <div className="px-4 pb-4">
            <FactorForm
              initial={initial}
              pending={actions.create.isPending || actions.update.isPending}
              submitLabel={editing?.mode === "edit" ? "更新因子" : "保存因子"}
              onSubmit={save}
            />
          </div>
        </SheetContent>
      </Sheet>
      <Sheet open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)}>
        <SheetContent className="overflow-y-auto" size="wide">
          <SheetHeader>
            <SheetTitle>计算因子详情</SheetTitle>
          </SheetHeader>
          <div className="grid gap-3 px-4 pb-4 text-sm md:grid-cols-2">
            <DetailItem label="范围" value={getScopeLabel(detail?.scope)} />
            <DetailItem label="类别" value={getCategoryLabel(detail?.category)} />
            <DetailItem label="子类" value={getSubCategoryLabel(detail?.subCategory)} />
            <DetailItem label="活动单位" value={detail ? `${getActivityUnitLabel(detail.unit)} (${detail.unit})` : ""} />
            <DetailItem label="因子值" value={detail ? `${detail.factorValue} ${detail.factorUnit}` : ""} />
            <DetailItem label="年份" value={detail ? String(detail.year) : ""} />
            <DetailItem label="来源" value={detail?.source} />
            <DetailItem label="来源系统" value={getSourceSystemLabel(detail?.sourceSystem)} />
            <DetailItem label="维护方式" value={getImportMethodLabel(detail?.projectionStatus)} />
            <DetailItem label="审核状态" value={reviewStatusLabel(detail?.reviewStatus)} />
            <DetailItem label="归属" value={detail?.ownerType === "enterprise" ? "企业因子" : "共享因子"} />
            <DetailItem label="是否可编辑" value={detail?.editable ? "可编辑" : "只读"} />
            <DetailItem className="md:col-span-2" label="备注" value={detail?.note} />
          </div>
        </SheetContent>
      </Sheet>
      <ImportDialog
        open={importOpen}
        pending={actions.previewImport.isPending || actions.commitImport.isPending}
        preview={actions.previewImport.data}
        onOpenChange={setImportOpen}
        onPreview={(file) => actions.previewImport.mutate(file)}
        onCommit={(file) => actions.commitImport.mutate(file, { onSuccess: () => setImportOpen(false) })}
      />
    </PageContainer>
  )
}

function FactorForm({
  initial,
  pending,
  submitLabel,
  onSubmit,
}: {
  initial: CalculationFactorWrite
  pending?: boolean
  submitLabel: string
  onSubmit: (body: CalculationFactorWrite) => void
}) {
  const [form, setForm] = useState(initial)
  const update = (patch: Partial<CalculationFactorWrite>) => setForm((current) => ({ ...current, ...patch }))
  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit({ ...form, year: Number(form.year), factorValue: String(form.factorValue) })
      }}
    >
      <CarbonFormField label="范围">
        <Select value={form.scope} onValueChange={(value) => update({ scope: value })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="scope1">范围1</SelectItem>
            <SelectItem value="scope2">范围2</SelectItem>
            <SelectItem value="scope3">范围3</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="类别">
        <Select value={form.category} onValueChange={(value) => update({ category: value })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="electricity">购电</SelectItem>
            <SelectItem value="fuel">燃料</SelectItem>
            <SelectItem value="refrigerant">制冷剂</SelectItem>
            <SelectItem value="transport">运输</SelectItem>
            <SelectItem value="waste">废弃物</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="子类编码">
        <Input value={form.subCategory} onChange={(event) => update({ subCategory: event.target.value })} required />
      </CarbonFormField>
      <CarbonFormField label="活动单位">
        <Input value={form.unit} onChange={(event) => update({ unit: event.target.value })} required />
      </CarbonFormField>
      <CarbonFormField label="因子值">
        <Input type="number" min="0" step="0.000001" value={form.factorValue} onChange={(event) => update({ factorValue: event.target.value })} required />
      </CarbonFormField>
      <CarbonFormField label="因子单位">
        <Input value={form.factorUnit} onChange={(event) => update({ factorUnit: event.target.value })} required />
      </CarbonFormField>
      <CarbonFormField label="年份">
        <Input type="number" min="1900" max="2100" value={form.year} onChange={(event) => update({ year: Number(event.target.value) })} required />
      </CarbonFormField>
      <CarbonFormField label="来源">
        <Input value={form.source} onChange={(event) => update({ source: event.target.value })} required />
      </CarbonFormField>
      <CarbonFormField label="来源系统">
        <Select value={form.sourceSystem ?? "enterprise"} onValueChange={(value) => update({ sourceSystem: value })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="enterprise">企业维护</SelectItem>
            <SelectItem value="custom_approved">企业审定</SelectItem>
            <SelectItem value="manual">人工录入</SelectItem>
            <SelectItem value="ncsc_ghg_efdb">NCSC官方因子库</SelectItem>
            <SelectItem value="ipcc">IPCC</SelectItem>
            <SelectItem value="ecoinvent">ecoinvent</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="维护方式">
        <Select value={form.projectionStatus} onValueChange={(value) => update({ projectionStatus: value })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">人工维护</SelectItem>
            <SelectItem value="direct">直接导入</SelectItem>
            <SelectItem value="derived">换算导入</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="审核状态">
        <Select value={form.reviewStatus} onValueChange={(value) => update({ reviewStatus: value })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="pending">待审核</SelectItem>
            <SelectItem value="approved">已审定</SelectItem>
            <SelectItem value="rejected">已驳回</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="状态">
        <Select value={form.isActive ? "active" : "inactive"} onValueChange={(value) => update({ isActive: value === "active" })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">启用</SelectItem>
            <SelectItem value="inactive">停用</SelectItem>
          </SelectContent>
        </Select>
      </CarbonFormField>
      <CarbonFormField label="来源快照">
        <Input value={form.sourceSnapshotId ?? ""} onChange={(event) => update({ sourceSnapshotId: event.target.value || null })} />
      </CarbonFormField>
      <div className="md:col-span-2">
        <CarbonFormField label="备注">
          <Textarea value={form.note ?? ""} onChange={(event) => update({ note: event.target.value })} rows={3} />
        </CarbonFormField>
      </div>
      <div className="flex justify-end gap-2 md:col-span-2">
        <Button type="submit" disabled={pending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

function ImportDialog({
  open,
  pending,
  preview,
  onOpenChange,
  onPreview,
  onCommit,
}: {
  open: boolean
  pending?: boolean
  preview?: CalculationFactorImportPreview
  onOpenChange: (open: boolean) => void
  onPreview: (file: File) => void
  onCommit: (file: File) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>导入企业计算因子</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          {preview && (
            <div className="space-y-3">
              <MetricStrip>
                <MetricTile label="有效行" value={preview.validCount} unit="行" tone={preview.validCount ? "success" : "default"} />
                <MetricTile label="新增" value={preview.createCount} unit="条" />
                <MetricTile label="更新" value={preview.updateCount} unit="条" />
                <MetricTile label="错误" value={preview.errorCount} unit="项" tone={preview.errorCount ? "danger" : "default"} />
              </MetricStrip>
              <AdminDataTable>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>行号</TableHead>
                      <TableHead>动作</TableHead>
                      <TableHead>因子</TableHead>
                      <TableHead>问题</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.rows.slice(0, 12).map((row) => (
                      <TableRow key={row.rowNumber}>
                        <TableCell>{row.rowNumber}</TableCell>
                        <TableCell>{importActionLabel(row.action)}</TableCell>
                        <TableCell>
                          {row.factor ? `${getScopeLabel(row.factor.scope)} / ${getSubCategoryLabel(row.factor.subCategory)} / ${row.factor.factorValue}` : "-"}
                        </TableCell>
                        <TableCell className={row.issues.length ? "text-destructive" : "text-muted-foreground"}>
                          {row.issues.map((issue) => issue.message).join("；") || "通过"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button variant="outline" disabled={!file || pending} onClick={() => file && onPreview(file)}>
            预检
          </Button>
          <Button disabled={!file || pending || !preview || preview.errorCount > 0} onClick={() => file && onCommit(file)}>
            提交导入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DetailItem({ label, value, className }: { label: string; value?: string | null; className?: string }) {
  return (
    <div className={className}>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-medium">{value || "-"}</div>
    </div>
  )
}

function reviewStatusLabel(status?: string | null) {
  return (
    {
      draft: "草稿",
      pending: "待审核",
      approved: "已审定",
      rejected: "已驳回",
    }[status ?? ""] ?? "未标记"
  )
}

function importActionLabel(action: string) {
  return (
    {
      create: "新增",
      update: "更新",
      invalid: "无效",
    }[action] ?? action
  )
}
