import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { GitCompare, Save } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
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

  useEffect(() => {
    if (!selection.data) return
    setForm({
      operationalBoundary: selection.data.operationalBoundary,
      areas: selection.data.areas.map((item) => ({ areaId: item.areaId, included: item.included, exclusionReason: item.exclusionReason })),
      equipment: selection.data.equipment.map((item) => ({ equipmentId: item.equipmentId, areaId: item.areaId, included: item.included, exclusionReason: item.exclusionReason })),
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
      {!selection.data || !form ? (
        <AdminEmptyState title="暂无可配置的核算边界" />
      ) : (
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
      )}
      <Sheet open={diffOpen} onOpenChange={setDiffOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>边界版本对比</SheetTitle>
          </SheetHeader>
          <div className="space-y-2 px-4 pb-6">
            {(diff.data?.changes ?? []).length === 0 ? (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">当前版本无差异</div>
            ) : (
              (diff.data?.changes ?? []).map((item) => (
                <div key={item.key} className="rounded-md border p-3 text-sm">
                  <div className="font-medium">{item.key}</div>
                  <div className="mt-1 grid grid-cols-2 gap-3 text-muted-foreground">
                    <span>{formatDiffValue(item.before)}</span>
                    <span>{formatDiffValue(item.after)}</span>
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
  return Array.isArray(value) ? value.join("、") || "-" : String(value)
}
