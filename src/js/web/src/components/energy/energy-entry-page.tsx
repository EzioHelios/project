import { useState } from "react"
import { toast } from "sonner"
import { AdminFilterBar, AdminPageScaffold, AdminPanel } from "@/components/admin-ui"
import { PaginationBar, type Row, request } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/ui/page-layout"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { type EnergyFilters, type EnergyRow, emptyEnergyFilters, energyEndpoint, useEnergyEntry } from "@/hooks/use-energy-entry"
import { useAuthStore } from "@/lib/auth"
import { EnergyEntryForm } from "./entry-form"
import { EnergyEntryImport } from "./entry-import"
import { EnergyTable, EnergyTotals, EntrySelect, energyName } from "./entry-table"
import { dateLabel, granularityLabel, moneyLabel, numberLabel, sourceLabel } from "./entry-utils"

export function EnergyEntryPage() {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  return <EnergyEntryWorkspace key={teamId ?? "no-team"} />
}
function EnergyEntryWorkspace() {
  const [draft, setDraft] = useState<EnergyFilters>(emptyEnergyFilters)
  const [filters, setFilters] = useState<EnergyFilters>(emptyEnergyFilters)
  const [ids, setIds] = useState<number[] | null>(null)
  const [scope, setScope] = useState("")
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState<EnergyRow | null | undefined>(undefined)
  const [detail, setDetail] = useState<EnergyRow | null>(null)
  const [deleting, setDeleting] = useState<EnergyRow | null>(null)
  const [pendingDelete, setPendingDelete] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [feedback, setFeedback] = useState("")
  const [highlightId, setHighlightId] = useState<number>()
  const [exporting, setExporting] = useState(false)
  const { references, list, refresh } = useEnergyEntry(filters, ids, page)
  const refs = references.data ?? { types: [], areas: [], devices: [], conversions: [] }
  const context = (row: EnergyRow) =>
    `${row.area_name || "未指定区域"} / ${row.equipment_name || "区域汇总"} · ${dateLabel(row.period_start)} · ${energyName(row.energy_type_code, refs.types)}`
  const apply = () => {
    setFilters(draft)
    setPage(0)
    setIds(null)
    setScope("")
    setHighlightId(undefined)
  }
  const reset = () => {
    setDraft(emptyEnergyFilters)
    setFilters(emptyEnergyFilters)
    setPage(0)
    setIds(null)
    setScope("")
  }
  const save = async (data: Row) => {
    const before = editing
    const saved = (
      await request<EnergyRow>(before?.id ? `${energyEndpoint}/${before.id}` : energyEndpoint, {
        method: before?.id ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
      })
    ).data
    const message = before
      ? `已更新：${context(saved)}；用量 ${numberLabel(before.amount)} ${before.unit} → ${numberLabel(saved.amount)} ${saved.unit}；费用 ${moneyLabel(before.cost_cny)} → ${moneyLabel(saved.cost_cny)} 元。`
      : `已新增：${context(saved)}；用量 ${numberLabel(saved.amount)} ${saved.unit}；费用 ${moneyLabel(saved.cost_cny)} 元。`
    setFeedback(message)
    toast.success(before ? "能源数据已更新" : "能源数据已新增", { description: message })
    setEditing(undefined)
    setDetail(saved)
    setHighlightId(saved.id)
    if (!before && saved.id) {
      setIds([saved.id])
      setScope("本次保存")
      setDraft(emptyEnergyFilters)
      setFilters(emptyEnergyFilters)
      setPage(0)
    }
    await refresh()
  }
  const remove = async () => {
    if (!deleting?.id) return
    setPendingDelete(true)
    try {
      await request(`${energyEndpoint}/${deleting.id}`, { method: "DELETE" })
      setFeedback(`已删除：${context(deleting)}；用量 ${numberLabel(deleting.amount)} ${deleting.unit}，费用 ${moneyLabel(deleting.cost_cny)} 元。下方列表与合计已更新。`)
      if (detail?.id === deleting.id) setDetail(null)
      setDeleting(null)
      if (list.data?.items.length === 1 && page > 0) setPage(page - 1)
      await refresh()
      toast.success("能源数据已删除")
    } catch (error) {
      toast.error("删除失败", { description: error instanceof Error ? error.message : "请重试" })
    } finally {
      setPendingDelete(false)
    }
  }
  const exportAll = async () => {
    setExporting(true)
    try {
      const response = await fetch(`${energyEndpoint}/export`)
      if (!response.ok) throw new Error("导出失败，请稍后重试")
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "能源数据台账.csv"
      link.click()
      URL.revokeObjectURL(url)
      toast.success("能源台账已导出")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出失败")
    } finally {
      setExporting(false)
    }
  }
  const options = (rows: Row[], key = "id") => rows.map((row) => ({ value: String(row[key]), label: String(row.name) }))
  return (
    <PageContainer>
      <AdminPageScaffold
        title="能源数据维护"
        topActions={
          <>
            <Button variant="outline" data-testid="energy-interval-import-trigger" disabled={!references.data} onClick={() => setImportOpen(true)}>
              导入能源数据
            </Button>
            <Button variant="outline" disabled={exporting} onClick={() => void exportAll()}>
              导出全部
            </Button>
            <Button disabled={!references.data} onClick={() => setEditing(null)}>
              新增能源数据
            </Button>
          </>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "keyword",
                node: (
                  <Input
                    aria-label="搜索能源数据"
                    placeholder="搜索区域、设备或记录编码"
                    value={draft.keyword}
                    onChange={(event) => setDraft({ ...draft, keyword: event.target.value })}
                  />
                ),
              },
              { key: "month", node: <Input aria-label="筛选月份" type="month" value={draft.month} onChange={(event) => setDraft({ ...draft, month: event.target.value })} /> },
              {
                key: "energy",
                node: (
                  <EntrySelect
                    label="筛选能源"
                    value={draft.energy_type_code}
                    options={[{ value: "", label: "全部能源" }, ...options(refs.types, "code")]}
                    onChange={(value) => setDraft({ ...draft, energy_type_code: value })}
                  />
                ),
              },
              {
                key: "area",
                node: (
                  <EntrySelect
                    label="筛选区域"
                    value={draft.area_id}
                    options={[{ value: "", label: "全部区域" }, ...options(refs.areas)]}
                    onChange={(value) => setDraft({ ...draft, area_id: value, equipment_id: "" })}
                  />
                ),
              },
              {
                key: "device",
                node: (
                  <EntrySelect
                    label="筛选设备"
                    value={draft.equipment_id}
                    options={[{ value: "", label: "全部设备" }, ...options(refs.devices.filter((row) => !draft.area_id || String(row.area_id) === draft.area_id))]}
                    onChange={(value) => setDraft({ ...draft, equipment_id: value })}
                  />
                ),
              },
            ]}
            actions={
              <>
                <Button variant="secondary" onClick={apply}>
                  查询
                </Button>
                <Button variant="outline" onClick={reset}>
                  重置
                </Button>
                <Button variant="outline" onClick={() => void refresh()} disabled={list.isFetching}>
                  刷新
                </Button>
              </>
            }
          />
        }
        metrics={!list.isError && !list.isLoading && <EnergyTotals totals={list.data?.totals ?? []} types={refs.types} label={scope || "筛选合计"} />}
      >
        {references.isError && (
          <p role="alert" className="text-sm text-destructive">
            选择项加载失败：{references.error.message}
            <Button variant="link" onClick={() => void references.refetch()}>
              重试
            </Button>
          </p>
        )}
        {feedback && (
          <output className="border-l-2 border-primary px-3 py-2 text-sm tabular-nums" data-testid="energy-entry-feedback">
            {feedback}
          </output>
        )}
        <AdminPanel
          title={scope ? `${scope} · ${list.data?.total ?? 0} 条` : "能源记录"}
          actions={
            ids !== null && (
              <Button
                variant="outline"
                onClick={() => {
                  setIds(null)
                  setScope("")
                  setPage(0)
                }}
              >
                返回全部记录
              </Button>
            )
          }
        >
          <EnergyTable
            rows={list.data?.items ?? []}
            types={refs.types}
            highlightId={highlightId}
            message={
              list.isLoading
                ? "正在加载能源数据…"
                : list.isError
                  ? `读取失败：${list.error.message}`
                  : !list.data?.items.length
                    ? "当前范围没有记录，可调整筛选、新增或导入能源数据。"
                    : undefined
            }
            actions={(row) => (
              <>
                <Button variant="ghost" size="sm" onClick={() => setDetail(row)}>
                  详情
                </Button>
                <Button variant="outline" size="sm" disabled={!references.data} onClick={() => setEditing(row)}>
                  编辑
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleting(row)}>
                  删除
                </Button>
              </>
            )}
          />
          {list.data && <PaginationBar page={list.data} pageIndex={page} pageSize={20} pageSizeOptions={[20]} onPageChange={setPage} onPageSizeChange={() => setPage(0)} />}
        </AdminPanel>
      </AdminPageScaffold>
      {editing !== undefined && <EnergyEntryForm row={editing} defaults={filters} references={refs} onClose={() => setEditing(undefined)} onSave={save} />}
      {importOpen && (
        <EnergyEntryImport
          types={refs.types}
          defaults={filters}
          onClose={() => setImportOpen(false)}
          onImported={async (result) => {
            setIds(result.imported_ids)
            setScope("本次导入")
            setPage(0)
            setFilters(emptyEnergyFilters)
            setDraft(emptyEnergyFilters)
            setFeedback(`本次实际导入 ${result.imported_count} 条，${result.skipped_count} 条未导入。列表仅显示本次新增记录。`)
            await refresh()
          }}
        />
      )}
      <Sheet open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>能源数据详情</SheetTitle>
          </SheetHeader>
          {detail && (
            <div className="space-y-3 p-4">
              <dl className="space-y-3 text-sm">
                {[
                  ["区域", detail.area_name],
                  ["设备", detail.equipment_name || "区域汇总"],
                  ["能源种类", energyName(detail.energy_type_code, refs.types)],
                  ["时间粒度", granularityLabel(detail.granularity)],
                  ["开始时间", detail.period_start.replace("T", " ")],
                  ["结束时间", detail.period_end.replace("T", " ")],
                  ["能源用量", `${numberLabel(detail.amount)} ${detail.unit}`],
                  ["费用（元）", moneyLabel(detail.cost_cny)],
                  ["记录编码", detail.source_record_id],
                  ["数据来源", sourceLabel(detail.source_system)],
                  ["来源名称", detail.source_name || sourceLabel(detail.source_system)],
                  ["备注", detail.remark],
                ].map(([label, value]) => (
                  <div key={label} className="grid grid-cols-[6rem_1fr] gap-2">
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd className="break-all">{value || "—"}</dd>
                  </div>
                ))}
              </dl>
              <Button
                onClick={() => {
                  setEditing(detail)
                  setDetail(null)
                }}
              >
                编辑此记录
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && !pendingDelete && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除能源数据</DialogTitle>
            <DialogDescription>
              {deleting && `${context(deleting)}；用量 ${numberLabel(deleting.amount)} ${deleting.unit}。删除后将从能源列表和汇总中移除，无法撤销。`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)} disabled={pendingDelete}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void remove()} disabled={pendingDelete}>
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}
