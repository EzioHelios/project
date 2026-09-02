import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { GitCompare, Save } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { OrganizationBoundaryPanel } from "@/components/carbon/organization-boundary-panel"
import { InventoryStatusBadge, OrganizationRunFilterBar, organizationCarbonSearchSchema } from "@/components/carbon/organization-inventory-common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useGhgCalculationRuns, useGhgCatalog, useOrganizationBoundaryActions, useOrganizationBoundaryDiff, useOrganizationBoundarySelection } from "@/lib/api/hooks/ghg-inventory"
import type { BoundaryAreaSelection, BoundaryEquipmentSelection, SaveBoundarySelectionRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/organization/boundary")({
  validateSearch: (search) => organizationCarbonSearchSchema.parse(search),
  component: OrganizationBoundaryPage,
})

function OrganizationBoundaryPage() {
  const navigate = useNavigate({ from: Route.fullPath })
  const search = Route.useSearch()
  const runs = useGhgCalculationRuns({ status: "completed" })
  const catalog = useGhgCatalog()
  const actions = useOrganizationBoundaryActions()
  const runCode = search.run ?? runs.data?.items[0]?.runCode
  const selectedRun = runs.data?.items.find((item) => item.runCode === runCode)
  const [activeBoundaryId, setActiveBoundaryId] = useState<number>()
  const boundaryId = activeBoundaryId ?? selectedRun?.organizationBoundaryId ?? undefined
  const selection = useOrganizationBoundarySelection(boundaryId)
  const diff = useOrganizationBoundaryDiff(boundaryId)
  const [form, setForm] = useState<SaveBoundarySelectionRequest>()
  const [diffOpen, setDiffOpen] = useState(false)
  const appliedSelectionKeyRef = useRef("")

  useEffect(() => {
    const data = selection.data
    const selectionKey = data ? JSON.stringify(data) : ""
    if (selectionKey === appliedSelectionKeyRef.current) return
    appliedSelectionKeyRef.current = selectionKey
    if (!data) {
      setForm(undefined)
      return
    }
    setForm({
      operationalBoundary: data.operationalBoundary,
      areas: data.areas.map((item) => ({ areaId: item.areaId, included: item.included, exclusionReason: item.exclusionReason })),
      equipment: data.equipment.map((item) => ({ equipmentId: item.equipmentId, areaId: item.areaId, included: item.included, exclusionReason: item.exclusionReason })),
    })
  }, [selection.data])

  const areaSelection = useMemo(() => new Map((form?.areas ?? []).map((item) => [item.areaId, item])), [form?.areas])
  const equipmentSelection = useMemo(() => new Map((form?.equipment ?? []).map((item) => [item.equipmentId, item])), [form?.equipment])
  const isDraft = selection.data?.boundary.status === "draft"

  const updateArea = (areaId: number, patch: Partial<BoundaryAreaSelection>) => {
    setForm((current) => {
      if (!current) return current
      const existing = current.areas?.find((item) => item.areaId === areaId) ?? { areaId, included: true }
      const next = { ...existing, ...patch }
      return { ...current, areas: [...(current.areas ?? []).filter((item) => item.areaId !== areaId), next] }
    })
  }
  const updateEquipment = (equipmentId: number, areaId: number, patch: Partial<BoundaryEquipmentSelection>) => {
    setForm((current) => {
      if (!current) return current
      const existing = current.equipment?.find((item) => item.equipmentId === equipmentId) ?? { equipmentId, areaId, included: true }
      const next = { ...existing, ...patch }
      return { ...current, equipment: [...(current.equipment ?? []).filter((item) => item.equipmentId !== equipmentId), next] }
    })
  }
  const toggleOperational = (field: "scopes" | "scope2Methods" | "isoCategories" | "scope3Categories", value: string | number, checked: boolean) => {
    setForm((current) => {
      if (!current) return current
      const values = (current.operationalBoundary[field] ?? []) as Array<string | number>
      return { ...current, operationalBoundary: { ...current.operationalBoundary, [field]: checked ? [...values, value] : values.filter((item) => item !== value) } }
    })
  }

  const discardDraft = async (draftBoundaryId: number) => {
    setActiveBoundaryId(undefined)
    try {
      await actions.discard.mutateAsync(draftBoundaryId)
    } catch {
      setActiveBoundaryId(draftBoundaryId)
    }
  }

  return (
    <AdminPageScaffold
      title="核算边界"
      status={<InventoryStatusBadge status={selection.data?.boundary.status} />}
      meta={
        selection.data ? (
          <>
            <span>{selection.data.boundary.boundaryName}</span>
            <span>V{selection.data.boundary.version}</span>
            <span>{selectedRun?.reportingPeriodName}</span>
          </>
        ) : undefined
      }
      filters={
        <OrganizationRunFilterBar
          runs={runs.data}
          runCode={runCode}
          scope2Method={search.scope2}
          onRunCodeChange={(run) => {
            setActiveBoundaryId(undefined)
            void navigate({ search: (previous) => ({ ...previous, run }) })
          }}
          onScope2MethodChange={(scope2) => void navigate({ search: (previous) => ({ ...previous, scope2 }) })}
          onRefresh={() => void selection.refetch()}
          refreshing={selection.isFetching}
          actions={
            <>
              <Button variant="outline" size="sm" disabled={!boundaryId} onClick={() => setDiffOpen(true)}>
                <GitCompare />
                版本对比
              </Button>
              {!isDraft && boundaryId && (
                <Button size="sm" onClick={() => void actions.workingCopy.mutateAsync(boundaryId).then((draft) => setActiveBoundaryId(draft.boundary.id))}>
                  创建工作草稿
                </Button>
              )}
              {isDraft && form && boundaryId && (
                <Button variant="outline" size="sm" disabled={actions.save.isPending} onClick={() => actions.save.mutate({ boundaryId, selection: form })}>
                  <Save />
                  保存
                </Button>
              )}
              {isDraft && boundaryId && (
                <Button variant="ghost" size="sm" disabled={actions.discard.isPending} onClick={() => void discardDraft(boundaryId)}>
                  放弃草稿
                </Button>
              )}
              {isDraft && boundaryId && (
                <Button size="sm" disabled={actions.publish.isPending} onClick={() => actions.publish.mutate(boundaryId)}>
                  发布
                </Button>
              )}
            </>
          }
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="纳入区域" value={(form?.areas ?? []).filter((item) => item.included).length} unit="个" />
          <MetricTile label="纳入设备" value={(form?.equipment ?? []).filter((item) => item.included).length} unit="台" />
          <MetricTile label="核算范围" value={form?.operationalBoundary.scopes?.length ?? 0} unit="项" />
          <MetricTile label="ISO 类别" value={form?.operationalBoundary.isoCategories?.length ?? 0} unit="类" />
        </MetricStrip>
      }
    >
      <div className="grid gap-3">
        <OrganizationBoundaryPanel />
        {!selection.data || !form ? (
          <AdminEmptyState title="暂无可配置的核算边界" />
        ) : (
          <>
            <AdminPanel title="边界口径">
              <div className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                <BoundaryFact label="控制方法" value={boundaryMethodLabel(selection.data.boundary.boundaryMethod)} />
                <BoundaryFact label="边界类型" value={boundaryTypeLabel(selection.data.boundary.boundaryType)} />
                <BoundaryFact label="报告期" value={selectedRun?.reportingPeriodName ?? "-"} />
                <BoundaryFact label="版本状态" value={`V${selection.data.boundary.version} · ${selection.data.boundary.status === "published" ? "已发布" : "工作草稿"}`} />
                <BoundaryFact label="边界编号" value={selection.data.boundary.boundaryNo} />
                <BoundaryFact label="边界名称" value={selection.data.boundary.boundaryName} />
                <BoundaryFact label="发布时间" value={selection.data.boundary.publishedAt ? formatBoundaryDate(selection.data.boundary.publishedAt) : "尚未发布"} />
                <BoundaryFact label="核算运行" value={selectedRun?.runCode ?? "-"} />
              </div>
            </AdminPanel>
            <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.75fr)]">
              <AdminPanel title="区域与设备边界" contentClassName="p-0">
                <div className="divide-y">
                  {(catalog.data?.areas ?? []).map((area) => {
                    const areaItem = areaSelection.get(area.id)
                    const areaIncluded = areaItem?.included ?? false
                    const equipment = (catalog.data?.equipment ?? []).filter((item) => item.areaId === area.id)
                    return (
                      <div key={area.id} className="py-2">
                        <div className="flex items-center gap-3 px-4" style={{ paddingLeft: `${16 + area.level * 18}px` }}>
                          <input
                            type="checkbox"
                            className="size-4 accent-primary"
                            checked={areaIncluded}
                            disabled={!isDraft}
                            onChange={(event) => updateArea(area.id, { included: event.target.checked, exclusionReason: event.target.checked ? null : "不属于本期运营边界" })}
                          />
                          <span className="min-w-0 flex-1 font-medium">{area.name}</span>
                          <span className="text-xs text-muted-foreground">{area.code}</span>
                        </div>
                        {!areaIncluded && areaItem && (
                          <div className="px-4 pt-2" style={{ paddingLeft: `${46 + area.level * 18}px` }}>
                            <Input
                              disabled={!isDraft}
                              value={areaItem.exclusionReason ?? ""}
                              onChange={(event) => updateArea(area.id, { exclusionReason: event.target.value })}
                              placeholder="排除原因"
                            />
                          </div>
                        )}
                        {equipment.map((item) => {
                          const equipmentItem = equipmentSelection.get(item.id)
                          const included = equipmentItem?.included ?? false
                          return (
                            <div key={item.id} className="mt-2 flex items-center gap-3 px-4 pl-14 text-sm">
                              <input
                                type="checkbox"
                                className="size-4 accent-primary"
                                checked={included}
                                disabled={!isDraft}
                                onChange={(event) =>
                                  updateEquipment(item.id, area.id, { included: event.target.checked, exclusionReason: event.target.checked ? null : "不属于本期运营边界" })
                                }
                              />
                              <span className="min-w-0 flex-1">{item.name}</span>
                              <span className="text-xs text-muted-foreground">{item.code}</span>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              </AdminPanel>
              <div className="grid content-start gap-3">
                <SelectionPanel
                  title="GHG Protocol 范围"
                  options={[...Array(3)].map((_, index) => ({ value: `scope${index + 1}`, label: `Scope ${index + 1}` }))}
                  values={form.operationalBoundary.scopes ?? []}
                  disabled={!isDraft}
                  onChange={(value, checked) => toggleOperational("scopes", value, checked)}
                />
                <SelectionPanel
                  title="Scope 2 核算方法"
                  options={[
                    { value: "location", label: "地点法" },
                    { value: "market", label: "市场法" },
                  ]}
                  values={form.operationalBoundary.scope2Methods ?? []}
                  disabled={!isDraft}
                  onChange={(value, checked) => toggleOperational("scope2Methods", value, checked)}
                />
                <SelectionPanel
                  title="ISO 14064-1 六类别"
                  options={[...Array(6)].map((_, index) => ({ value: String(index + 1), label: `类别 ${index + 1}` }))}
                  values={form.operationalBoundary.isoCategories ?? []}
                  disabled={!isDraft}
                  onChange={(value, checked) => toggleOperational("isoCategories", value, checked)}
                />
                <SelectionPanel
                  title="Scope 3 类别"
                  options={[...Array(15)].map((_, index) => ({ value: index + 1, label: `类别 ${index + 1}` }))}
                  values={form.operationalBoundary.scope3Categories ?? []}
                  disabled={!isDraft}
                  columns="grid-cols-3"
                  onChange={(value, checked) => toggleOperational("scope3Categories", value, checked)}
                />
              </div>
            </div>
          </>
        )}
      </div>
      <Sheet open={diffOpen} onOpenChange={setDiffOpen}>
        <SheetContent size="wide" className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>边界版本对比</SheetTitle>
          </SheetHeader>
          <div className="space-y-2 px-4 pb-6">
            {(diff.data?.changes ?? []).length === 0 ? (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">当前版本无差异</div>
            ) : (
              (diff.data?.changes ?? []).map((item) => (
                <div key={item.key} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{formatBoundaryDiffLabel(item.key, catalog.data?.areas ?? [], catalog.data?.equipment ?? [])}</div>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{boundaryChangeTypeLabel(item.changeType)}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <BoundaryDiffValue label="对比版本" value={formatDiffValue(item.before)} />
                    <BoundaryDiffValue label="当前版本" value={formatDiffValue(item.after)} />
                  </div>
                </div>
              ))
            )}
          </div>
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function BoundaryFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l-2 border-border pl-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 truncate font-medium tabular-nums" title={value}>
        {value}
      </div>
    </div>
  )
}

function BoundaryDiffValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words font-medium">{value}</div>
    </div>
  )
}

function boundaryMethodLabel(value: string) {
  return (
    (
      {
        operational_control: "运营控制法",
        financial_control: "财务控制法",
        equity_share: "股权比例法",
      } as Record<string, string>
    )[value] ?? value
  )
}

function boundaryTypeLabel(value: string) {
  return ({ organization: "组织边界", organizational: "组织边界", operational: "运营边界" } as Record<string, string>)[value] ?? value
}

function formatBoundaryDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

function SelectionPanel({
  title,
  options,
  values,
  disabled,
  onChange,
  columns = "grid-cols-2",
}: {
  title: string
  options: Array<{ value: string | number; label: string }>
  values: Array<string | number>
  disabled: boolean
  onChange: (value: string | number, checked: boolean) => void
  columns?: string
}) {
  return (
    <AdminPanel title={title}>
      <div className={`grid gap-2 ${columns}`}>
        {options.map((item) => (
          <label key={item.value} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={values.includes(item.value)}
              disabled={disabled}
              onChange={(event) => onChange(item.value, event.target.checked)}
            />
            {item.label}
          </label>
        ))}
      </div>
    </AdminPanel>
  )
}

function formatDiffValue(value: string | number | boolean | string[] | null | undefined) {
  if (value == null) return "-"
  if (Array.isArray(value)) return value.join("、") || "-"
  if (typeof value === "boolean") return value ? "纳入" : "排除"
  if (typeof value === "string") {
    const facilityValue = /^(true|false):(.*)$/i.exec(value)
    if (facilityValue) {
      const included = facilityValue[1].toLowerCase() === "true"
      const reason = facilityValue[2]
      return included ? "纳入核算边界" : `排除${reason ? ` · ${reason}` : ""}`
    }
  }
  return String(value)
}

function formatBoundaryDiffLabel(key: string, areas: Array<{ id: number; name: string; code: string }>, equipment: Array<{ id: number; name: string; code: string }>) {
  const operationalLabels: Record<string, string> = {
    "operationalBoundary.scopes": "GHG Protocol 范围",
    "operationalBoundary.scope2Methods": "Scope 2 核算方法",
    "operationalBoundary.isoCategories": "ISO 14064-1 六类别",
    "operationalBoundary.scope3Categories": "Scope 3 类别",
  }
  if (operationalLabels[key]) return operationalLabels[key]
  const [kind, rawId] = key.split(":")
  const id = Number(rawId)
  const item = kind === "area" ? areas.find((area) => area.id === id) : equipment.find((asset) => asset.id === id)
  if (!item) return kind === "area" ? "区域边界" : kind === "equipment" ? "设备边界" : "边界配置"
  return `${kind === "area" ? "区域" : "设备"} · ${item.name}（${item.code}）`
}

function boundaryChangeTypeLabel(value: string) {
  return ({ added: "新增", removed: "移除", changed: "变更" } as Record<string, string>)[value] ?? "变更"
}
