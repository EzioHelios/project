import type { ReactNode } from "react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import type { GhgActivity, GhgActivityWrite, GhgCatalog, GhgEmissionSource, GhgEmissionSourceWrite } from "@/lib/api/hooks/ghg-inventory"
import type { GhgActivityAllocationResponse } from "@/lib/generated/api"

type FieldProps = { label: string; children: ReactNode }

export function CarbonFormField({ label, children }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      {children}
    </div>
  )
}

export function categoryLabel(catalog: GhgCatalog | undefined, code: string) {
  const category = catalog?.categories.find((item) => item.code === code)
  return category ? `${category.code} ${category.name}` : code
}

export function statusLabel(status: string) {
  return (
    (
      {
        active: "启用",
        inactive: "停用",
        approved: "已确认",
        draft: "草稿",
        archived: "已归档",
        pass: "通过",
        warning: "警告",
        failed: "失败",
      } as Record<string, string>
    )[status] ?? status
  )
}

export function scopeLabel(scope: string) {
  return ({ scope1: "范围一", scope2: "范围二", scope3: "范围三" } as Record<string, string>)[scope] ?? scope
}

export function sourceLabel(source: string) {
  return (
    (
      { measured: "实测", metered: "计量系统", ledger: "台账", manual: "人工台账", xlsx_import: "表格导入", supplier: "供应商", estimated: "估算", erp: "ERP" } as Record<
        string,
        string
      >
    )[source] ?? source
  )
}

export function choiceLabel(fieldCode: string, value: unknown) {
  const text = String(value ?? "")
  if (!text) return "-"
  return (
    (
      {
        "energy_type:electricity": "电力",
        "energy_type:purchased_heat": "外购热力",
        "energy_type:steam": "蒸汽",
        "energy_type:cooling": "外购冷量",
        "scope2_method:location": "基于位置",
        "scope2_method:market": "基于市场",
        "scope2_method:not_applicable": "不适用",
        "transport_direction:upstream": "上游",
        "transport_direction:downstream": "下游",
        "transport_direction:commute": "员工通勤",
        "transport_direction:business_travel": "商务旅行",
        "transport_direction:visitor": "客户和访客",
        "transport_included:yes": "是",
        "transport_included:no": "否",
      } as Record<string, string>
    )[`${fieldCode}:${text}`] ?? text
  )
}

export function sourceDefaults(catalog: GhgCatalog | undefined, categoryCode = "2.1"): GhgEmissionSourceWrite {
  const period = catalog?.periods[0]
  const organization = catalog?.organizations.find((item) => item.code === period?.organizationCode) ?? catalog?.organizations[0]
  const area = catalog?.areas.find((item) => item.level === 0) ?? catalog?.areas[0]
  const category = catalog?.categories.find((item) => item.code === categoryCode) ?? catalog?.categories[0]
  return {
    inventoryCode: period?.code ?? `INV-${new Date().getFullYear()}`,
    reportingPeriodId: period?.id,
    organizationCode: organization?.code ?? "ORG",
    facilityCode: area?.code ?? "ROOT",
    sourceCode: `SRC-${Date.now().toString(36).toUpperCase()}`,
    sourceName: "",
    isoCategoryCode: category?.code ?? categoryCode,
    sourceMechanism: category?.sourceMechanism,
    originKind: category?.valueChainPosition === "own" ? "internal" : "external",
    defaultAreaId: area?.id,
    defaultAllocationRole: "responsibility",
    sourceSystem: "manual",
    sourcePayload: {},
    status: "active",
  }
}

export function activityDefaults(catalog: GhgCatalog | undefined, source?: GhgEmissionSource): GhgActivityWrite {
  const period = catalog?.periods.find((item) => item.code === source?.inventoryCode) ?? catalog?.periods[0]
  const category = catalog?.categories.find((item) => item.code === source?.isoCategoryCode) ?? catalog?.categories.find((item) => item.code === "2.1") ?? catalog?.categories[0]
  const sourcePayload = Object.fromEntries((category?.activityFields ?? []).map((field) => [field.code, field.choices[0] ?? ""]))
  return {
    recordCode: `ACT-${Date.now().toString(36).toUpperCase()}`,
    inventoryCode: source?.inventoryCode ?? period?.code ?? `INV-${new Date().getFullYear()}`,
    reportingPeriodId: period?.id,
    organizationBoundaryId: source?.organizationBoundaryId,
    organizationCode: source?.organizationCode ?? period?.organizationCode ?? catalog?.organizations[0]?.code ?? "ORG",
    facilityCode: source?.facilityCode ?? catalog?.areas[0]?.code ?? "ROOT",
    sourceCode: source?.sourceCode ?? "",
    activityCode: "manual-activity",
    activityName: "",
    periodStart: period?.periodStart ?? `${new Date().getFullYear()}-01-01`,
    periodEnd: period?.periodEnd ?? `${new Date().getFullYear()}-12-31`,
    isoCategoryCode: category?.code ?? "2.1",
    activityAmount: "0",
    activityUnit: category?.code === "2.1" ? "kWh" : "unit",
    dataSourceType: "manual",
    measurementMethod: "人工维护活动数据",
    qualityStatus: "pass",
    status: "approved",
    sourceSystem: "manual",
    sourcePayload,
  }
}

export function SourceForm({
  catalog,
  initial,
  pending,
  submitLabel,
  onSubmit,
}: {
  catalog?: GhgCatalog
  initial: GhgEmissionSourceWrite
  pending?: boolean
  submitLabel: string
  onSubmit: (value: GhgEmissionSourceWrite) => void
}) {
  const [form, setForm] = useState<GhgEmissionSourceWrite>(initial)
  useEffect(() => setForm(initial), [initial])
  const category = catalog?.categories.find((item) => item.code === form.isoCategoryCode)
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(form)
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <CarbonFormField label="盘查任务">
          <Select value={form.inventoryCode} onValueChange={(inventoryCode) => setForm((current) => ({ ...current, inventoryCode }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.periods ?? []).map((period) => (
                <SelectItem key={period.id} value={period.code}>
                  {period.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="ISO 二级分类">
          <Select
            value={form.isoCategoryCode}
            onValueChange={(isoCategoryCode) => {
              const selected = catalog?.categories.find((item) => item.code === isoCategoryCode)
              setForm((current) => ({
                ...current,
                isoCategoryCode,
                sourceMechanism: selected?.sourceMechanism,
                originKind: selected?.valueChainPosition === "own" ? "internal" : "external",
              }))
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.categories ?? []).map((item, index) => (
                <SelectItem key={`${item.code}-${index}`} value={item.code}>
                  {item.code} {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="排放源编号">
          <Input value={form.sourceCode} onChange={(event) => setForm((current) => ({ ...current, sourceCode: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="排放源名称">
          <Input value={form.sourceName} onChange={(event) => setForm((current) => ({ ...current, sourceName: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="组织编号">
          <Select value={form.organizationCode} onValueChange={(organizationCode) => setForm((current) => ({ ...current, organizationCode }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.organizations ?? []).map((organization) => (
                <SelectItem key={organization.code} value={organization.code}>
                  {organization.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="归集区域">
          <Select value={form.facilityCode} onValueChange={(facilityCode) => setForm((current) => ({ ...current, facilityCode }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.areas ?? []).map((area) => (
                <SelectItem key={area.code} value={area.code}>
                  {area.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="默认区域">
          <OptionalNumberSelect
            value={form.defaultAreaId}
            options={(catalog?.areas ?? []).map((area) => ({ value: area.id, label: area.name }))}
            onChange={(defaultAreaId) => setForm((current) => ({ ...current, defaultAreaId }))}
          />
        </CarbonFormField>
        <CarbonFormField label="默认设备">
          <OptionalNumberSelect
            value={form.defaultEquipmentId}
            options={(catalog?.equipment ?? []).map((item) => ({ value: item.id, label: item.name }))}
            onChange={(defaultEquipmentId) => setForm((current) => ({ ...current, defaultEquipmentId }))}
          />
        </CarbonFormField>
        <CarbonFormField label="来源类型">
          <Select value={form.sourceSystem ?? "manual"} onValueChange={(sourceSystem) => setForm((current) => ({ ...current, sourceSystem }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="manual">人工维护</SelectItem>
              <SelectItem value="generated">系统生成</SelectItem>
              <SelectItem value="xlsx_import">表格导入</SelectItem>
              <SelectItem value="erp">ERP</SelectItem>
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="状态">
          <Select value={form.status ?? "active"} onValueChange={(status) => setForm((current) => ({ ...current, status }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">启用</SelectItem>
              <SelectItem value="inactive">停用</SelectItem>
            </SelectContent>
          </Select>
        </CarbonFormField>
      </div>
      <div className="rounded-md border border-border/70 bg-muted/20 p-3 text-muted-foreground text-xs">
        {category ? `${scopeLabel(category.ghgScope)} · ${category.isoCategory} · ${category.sourceMechanism}` : "请选择分类"}
      </div>
      <div className="flex justify-end gap-2">
        <Button disabled={pending} type="submit">
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

export function ActivityForm({
  catalog,
  sources,
  initial,
  pending,
  submitLabel,
  onSubmit,
}: {
  catalog?: GhgCatalog
  sources: GhgEmissionSource[]
  initial: GhgActivityWrite
  pending?: boolean
  submitLabel: string
  onSubmit: (value: GhgActivityWrite) => void
}) {
  const [form, setForm] = useState<GhgActivityWrite>(initial)
  useEffect(() => setForm(initial), [initial])
  const category = catalog?.categories.find((item) => item.code === form.isoCategoryCode)
  const source = sources.find((item) => item.sourceCode === form.sourceCode && item.inventoryCode === form.inventoryCode)
  const sourceOptionValue = (item: GhgEmissionSource) => `${item.inventoryCode}::${item.sourceCode}`
  const fields = category?.activityFields ?? []
  const updatePayload = (key: string, value: string) => setForm((current) => ({ ...current, sourcePayload: { ...(current.sourcePayload ?? {}), [key]: value } }))
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(form)
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <CarbonFormField label="排放源">
          <Select
            value={source ? sourceOptionValue(source) : "none"}
            onValueChange={(sourceValue) => {
              const selected = sources.find((item) => sourceOptionValue(item) === sourceValue)
              setForm((current) => ({
                ...current,
                inventoryCode: selected?.inventoryCode ?? current.inventoryCode,
                organizationCode: selected?.organizationCode ?? current.organizationCode,
                organizationBoundaryId: selected?.organizationBoundaryId ?? current.organizationBoundaryId,
                facilityCode: selected?.facilityCode ?? current.facilityCode,
                sourceCode: selected?.sourceCode ?? current.sourceCode,
                isoCategoryCode: selected?.isoCategoryCode ?? current.isoCategoryCode,
              }))
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none" disabled>
                请选择排放源
              </SelectItem>
              {sources.map((item) => (
                <SelectItem key={sourceOptionValue(item)} value={sourceOptionValue(item)}>
                  {item.sourceName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="活动分类">
          <Input value={category ? `${category.code} ${category.name}` : form.isoCategoryCode} readOnly />
        </CarbonFormField>
        <CarbonFormField label="记录编号">
          <Input value={form.recordCode} onChange={(event) => setForm((current) => ({ ...current, recordCode: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="活动名称">
          <Input value={form.activityName} onChange={(event) => setForm((current) => ({ ...current, activityName: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="开始日期">
          <Input type="date" value={form.periodStart} onChange={(event) => setForm((current) => ({ ...current, periodStart: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="结束日期">
          <Input type="date" value={form.periodEnd} onChange={(event) => setForm((current) => ({ ...current, periodEnd: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="活动量">
          <Input value={form.activityAmount} onChange={(event) => setForm((current) => ({ ...current, activityAmount: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="单位">
          <Input value={form.activityUnit} onChange={(event) => setForm((current) => ({ ...current, activityUnit: event.target.value }))} required />
        </CarbonFormField>
        <CarbonFormField label="数据来源">
          <Select value={form.dataSourceType} onValueChange={(dataSourceType) => setForm((current) => ({ ...current, dataSourceType }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="measured">实测</SelectItem>
              <SelectItem value="ledger">台账</SelectItem>
              <SelectItem value="manual">人工台账</SelectItem>
              <SelectItem value="xlsx_import">表格导入</SelectItem>
              <SelectItem value="supplier">供应商</SelectItem>
              <SelectItem value="estimated">估算</SelectItem>
            </SelectContent>
          </Select>
        </CarbonFormField>
        <CarbonFormField label="状态">
          <Select value={form.status ?? "approved"} onValueChange={(status) => setForm((current) => ({ ...current, status }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="approved">已确认</SelectItem>
              <SelectItem value="draft">草稿</SelectItem>
              <SelectItem value="archived">归档</SelectItem>
            </SelectContent>
          </Select>
        </CarbonFormField>
      </div>
      <Separator />
      <div className="grid gap-4 md:grid-cols-2">
        {fields.map((field) => (
          <CarbonFormField key={field.code} label={`${field.label}${field.required ? " *" : ""}`}>
            {field.choices.length ? (
              <Select value={String(form.sourcePayload?.[field.code] ?? "") || "none"} onValueChange={(value) => updatePayload(field.code, value === "none" ? "" : value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">未选择</SelectItem>
                  {field.choices.map((choice) => (
                    <SelectItem key={choice} value={choice}>
                      {choiceLabel(field.code, choice)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input value={String(form.sourcePayload?.[field.code] ?? "")} onChange={(event) => updatePayload(field.code, event.target.value)} required={field.required} />
            )}
          </CarbonFormField>
        ))}
      </div>
      <CarbonFormField label="测量方法">
        <Textarea value={form.measurementMethod} onChange={(event) => setForm((current) => ({ ...current, measurementMethod: event.target.value }))} required />
      </CarbonFormField>
      <CarbonFormField label="备注">
        <Textarea value={form.remarks ?? ""} onChange={(event) => setForm((current) => ({ ...current, remarks: event.target.value }))} />
      </CarbonFormField>
      {source && (
        <div className="rounded-md border border-border/70 bg-muted/20 p-3 text-muted-foreground text-xs">
          当前排放源：{source.sourceName} · {statusLabel(source.status)}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <Button disabled={pending} type="submit">
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

export function AllocationEditor({
  catalog,
  activity,
  allocations,
  pending,
  onSubmit,
}: {
  catalog?: GhgCatalog
  activity?: GhgActivity
  allocations: GhgActivityAllocationResponse[]
  pending?: boolean
  onSubmit: (rows: AllocationFormRow[]) => void
}) {
  const [rows, setRows] = useState<AllocationFormRow[]>([])
  useEffect(() => {
    setRows(
      allocations.length
        ? allocations.map((item) => ({
            allocationCode: item.allocationCode,
            areaId: item.areaId,
            equipmentId: item.equipmentId ?? undefined,
            measurementBoundaryId: item.measurementBoundaryId ?? undefined,
            allocationRole: item.allocationRole,
            allocationRatio: item.allocationRatio,
            sourceKind: item.sourceKind,
          }))
        : [{ areaId: catalog?.areas[0]?.id ?? 0, allocationRole: "responsibility", allocationRatio: "1", sourceKind: "manual" }],
    )
  }, [allocations, catalog?.areas])
  const areaOptions = catalog?.areas ?? []
  const equipmentOptions = catalog?.equipment ?? []
  const boundaryOptions = catalog?.measurementBoundaries ?? []
  const disabled = !activity
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border/70 bg-muted/20 p-3 text-sm">
        <div className="font-medium">{activity?.activityName ?? "请选择活动数据"}</div>
        <div className="text-muted-foreground text-xs">
          {activity ? `${activity.recordCode} · ${categoryLabel(catalog, activity.isoCategoryCode)}` : "先在活动台账中打开一条记录"}
        </div>
      </div>
      {rows.map((row, index) => (
        <div className="grid gap-3 rounded-md border border-border/70 p-3 md:grid-cols-4" key={`${row.allocationCode ?? "new"}-${index}`}>
          <CarbonFormField label="区域">
            <NumberSelect
              disabled={disabled}
              value={row.areaId}
              options={areaOptions.map((area) => ({ value: area.id, label: area.name }))}
              onChange={(areaId) => setRows((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, areaId } : item)))}
            />
          </CarbonFormField>
          <CarbonFormField label="设备">
            <OptionalNumberSelect
              disabled={disabled}
              value={row.equipmentId}
              options={equipmentOptions.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(equipmentId) => setRows((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, equipmentId } : item)))}
            />
          </CarbonFormField>
          <CarbonFormField label="计量边界">
            <OptionalNumberSelect
              disabled={disabled}
              value={row.measurementBoundaryId}
              options={boundaryOptions.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(measurementBoundaryId) => setRows((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, measurementBoundaryId } : item)))}
            />
          </CarbonFormField>
          <CarbonFormField label="比例">
            <Input
              disabled={disabled}
              value={row.allocationRatio}
              onChange={(event) => setRows((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, allocationRatio: event.target.value } : item)))}
            />
          </CarbonFormField>
        </div>
      ))}
      <div className="flex justify-end gap-2">
        <Button
          disabled={disabled}
          onClick={() => setRows((current) => [...current, { areaId: areaOptions[0]?.id ?? 0, allocationRole: "responsibility", allocationRatio: "1", sourceKind: "manual" }])}
          type="button"
          variant="outline"
        >
          增加归集
        </Button>
        <Button disabled={disabled || pending} onClick={() => onSubmit(rows)} type="button">
          保存归集
        </Button>
      </div>
    </div>
  )
}

export type AllocationFormRow = {
  allocationCode?: string
  areaId: number
  equipmentId?: number
  measurementBoundaryId?: number
  allocationRole: string
  allocationRatio: string
  sourceKind?: string
}

function NumberSelect({
  value,
  options,
  onChange,
  disabled,
}: {
  value: number
  options: Array<{ value: number; label: string }>
  onChange: (value: number) => void
  disabled?: boolean
}) {
  return (
    <Select disabled={disabled || options.length === 0} value={value ? String(value) : "none"} onValueChange={(item) => item !== "none" && onChange(Number(item))}>
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none" disabled>
          请选择区域
        </SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={String(option.value)}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function OptionalNumberSelect({
  value,
  options,
  onChange,
  disabled,
}: {
  value?: number | null
  options: Array<{ value: number; label: string }>
  onChange: (value: number | undefined) => void
  disabled?: boolean
}) {
  return (
    <Select disabled={disabled} value={value ? String(value) : "none"} onValueChange={(item) => onChange(item === "none" ? undefined : Number(item))}>
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">不指定</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={String(option.value)}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
