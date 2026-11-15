import { useState } from "react"
import type { Row } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { type EnergyRow, energyUnits, monthRange } from "@/hooks/use-energy-entry"
import { EntrySelect } from "./entry-table"

export function EnergyEntryForm({
  row,
  defaults,
  references,
  onClose,
  onSave,
}: {
  row: EnergyRow | null
  defaults: { month: string; area_id: string; energy_type_code: string }
  references: { types: Row[]; areas: Row[]; devices: Row[]; conversions: Row[] }
  onClose: () => void
  onSave: (data: Row) => Promise<void>
}) {
  const month = defaults.month || new Date().toISOString().slice(0, 7)
  const [form, setForm] = useState<Record<string, string>>(() => {
    const initial = row ?? {
      ...monthRange(month),
      area_id: defaults.area_id,
      energy_type_code: defaults.energy_type_code,
      unit: energyUnits(defaults.energy_type_code, references.types, references.conversions)[0] ?? "",
      granularity: "month",
      source_system: "manual_entry",
      source_record_id: `ENTRY-${crypto.randomUUID()}`,
      data_quality: "manual",
    }
    return Object.fromEntries(Object.entries(initial).map(([key, value]) => [key, value == null ? "" : String(value)]))
  })
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  const update = (values: Record<string, string>) => setForm((current) => ({ ...current, ...values }))
  const units = energyUnits(form.energy_type_code, references.types, references.conversions)
  const devices = references.devices.filter((item) => !form.area_id || String(item.area_id) === form.area_id)
  const submit = async () => {
    if (!form.energy_type_code || !form.unit || !form.period_start || !form.period_end || form.amount?.trim() === "" || form.amount == null) {
      setError("请填写能源种类、期间、用量及单位")
      return
    }
    if (!Number.isFinite(Number(form.amount)) || Number(form.amount) < 0 || (form.cost_cny && (!Number.isFinite(Number(form.cost_cny)) || Number(form.cost_cny) < 0))) {
      setError("能源用量和费用必须为不小于零的数值")
      return
    }
    if (new Date(form.period_end) < new Date(form.period_start)) {
      setError("结束日期不能早于开始日期")
      return
    }
    setPending(true)
    setError("")
    try {
      await onSave({
        ...row,
        ...form,
        equipment_id: form.equipment_id ? Number(form.equipment_id) : null,
        area_id: form.area_id || null,
        amount: Number(form.amount),
        cost_cny: form.cost_cny ? Number(form.cost_cny) : null,
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "保存失败，请重试")
    } finally {
      setPending(false)
    }
  }
  return (
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{row ? "编辑能源数据" : "新增能源数据"}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
          className="space-y-4"
        >
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>区域</Label>
              <EntrySelect
                label="区域"
                value={form.area_id}
                options={[{ value: "", label: "未指定区域" }, ...references.areas.map((item) => ({ value: String(item.id), label: String(item.name) }))]}
                onChange={(value) =>
                  update({
                    area_id: value,
                    area_name: String(references.areas.find((item) => String(item.id) === value)?.name ?? ""),
                    equipment_id: "",
                    equipment_code: "",
                    equipment_name: "",
                  })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label>设备</Label>
              <EntrySelect
                label="设备"
                value={form.equipment_id}
                options={[
                  { value: "", label: "区域汇总（不指定设备）" },
                  ...devices.map((item) => ({ value: String(item.id), label: `${item.name} · ${item.area_name || "未指定区域"}` })),
                ]}
                onChange={(value) => {
                  const device = devices.find((item) => String(item.id) === value)
                  update({
                    equipment_id: value,
                    equipment_code: String(device?.code ?? ""),
                    equipment_name: String(device?.name ?? ""),
                    ...(device?.area_id ? { area_id: String(device.area_id), area_name: String(device.area_name ?? "") } : {}),
                  })
                }}
              />
            </div>
            <div className="grid gap-2">
              <Label>能源种类</Label>
              <EntrySelect
                label="能源种类"
                value={form.energy_type_code}
                options={[{ value: "", label: "请选择能源种类" }, ...references.types.map((item) => ({ value: String(item.code), label: String(item.name) }))]}
                onChange={(value) => update({ energy_type_code: value, unit: energyUnits(value, references.types, references.conversions)[0] ?? "" })}
              />
            </div>
            <div className="grid gap-2">
              <Label>单位</Label>
              <EntrySelect
                label="单位"
                value={form.unit}
                options={[{ value: "", label: "请选择单位" }, ...units.map((unit) => ({ value: unit, label: unit }))]}
                onChange={(unit) => update({ unit })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="energy-entry-amount">能源用量</Label>
              <Input id="energy-entry-amount" type="number" min="0" step="any" required value={form.amount ?? ""} onChange={(event) => update({ amount: event.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="energy-entry-cost">费用（元）</Label>
              <Input id="energy-entry-cost" type="number" min="0" step="any" value={form.cost_cny ?? ""} onChange={(event) => update({ cost_cny: event.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="energy-entry-month">月份</Label>
              <Input
                id="energy-entry-month"
                type="month"
                value={form.period_start?.slice(0, 7) ?? ""}
                onChange={(event) => event.target.value && update({ ...monthRange(event.target.value), granularity: "month" })}
              />
            </div>
            <div className="grid gap-2">
              <Label>时间粒度</Label>
              <EntrySelect
                label="时间粒度"
                value={form.granularity}
                options={[
                  { value: "month", label: "月" },
                  { value: "day", label: "日" },
                  { value: "hour", label: "小时" },
                  { value: "year", label: "年" },
                ]}
                onChange={(granularity) => update({ granularity })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="energy-entry-start">开始时间</Label>
              <Input
                id="energy-entry-start"
                type="datetime-local"
                step="1"
                required
                value={form.period_start ?? ""}
                onChange={(event) => update({ period_start: event.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="energy-entry-end">结束时间</Label>
              <Input id="energy-entry-end" type="datetime-local" step="1" required value={form.period_end ?? ""} onChange={(event) => update({ period_end: event.target.value })} />
            </div>
            <div className="grid gap-2 sm:col-span-2">
              <Label htmlFor="energy-entry-remark">备注</Label>
              <Textarea id="energy-entry-remark" value={form.remark ?? ""} onChange={(event) => update({ remark: event.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={pending}>
              取消
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? "正在保存" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
