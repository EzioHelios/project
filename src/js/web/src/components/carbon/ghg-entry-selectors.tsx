import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { GhgCatalog, GhgEnergyOption, GhgUnitOption } from "@/lib/api/hooks/ghg-inventory"
import { getActivityUnitLabel, getSubCategoryLabel } from "@/lib/carbon-factor-labels"
import type { GhgActivityFieldResponse } from "@/lib/generated/api"

type Option = { value: string; label: string }

const transportOptions: Option[] = [
  { value: "road", label: "公路运输" },
  { value: "rail", label: "铁路运输" },
  { value: "sea", label: "水路运输" },
  { value: "air", label: "航空运输" },
  { value: "柴油乘用车", label: "柴油乘用车" },
  { value: "汽油乘用车", label: "汽油乘用车" },
  { value: "电动乘用车", label: "电动乘用车" },
  { value: "bus", label: "公交车" },
  { value: "subway", label: "地铁" },
  { value: "walking", label: "步行" },
  { value: "cycling", label: "自行车" },
]

export function ghgFieldOptions(field: GhgActivityFieldResponse, catalog?: GhgCatalog, energy: GhgEnergyOption[] = []): Option[] | undefined {
  if (field.code === "facility_or_device" || field.code === "vehicle_or_machine") {
    return (catalog?.equipment ?? []).map((item) => ({ value: item.code, label: item.name }))
  }
  if (field.code === "meter_point") {
    return (catalog?.meterPoints ?? []).map((item) => ({ value: item.code, label: item.unit ? `${item.name}（${item.unit}）` : item.name }))
  }
  if (field.code === "fuel_or_material") return energy.filter((item) => item.category === "fuel").map((item) => ({ value: item.code, label: item.name }))
  if (field.code === "transport_mode") return transportOptions
  return undefined
}

export function ghgObjectLabel(fieldCode: string, value: unknown, catalog?: GhgCatalog, energy: GhgEnergyOption[] = []) {
  const text = String(value ?? "")
  if (!text) return "-"
  const options = ghgFieldOptions({ code: fieldCode, label: "", choices: [], required: false }, catalog, energy)
  const option = options?.find((item) => item.value === text || item.label === text)
  if (option) return option.label
  if (["facility_or_device", "vehicle_or_machine", "meter_point"].includes(fieldCode)) {
    return (
      catalog?.equipment.find((item) => item.code === text || String(item.id) === text)?.name ??
      catalog?.measurementBoundaries.find((item) => item.code === text || String(item.id) === text)?.name ??
      text
    )
  }
  if (fieldCode === "fuel_or_material" || fieldCode === "gas_code") return getSubCategoryLabel(text)
  return text
}

export function GhgValueSelect({
  value,
  options,
  onChange,
  required,
  label,
}: {
  value: string
  options: Option[]
  onChange: (value: string) => void
  required?: boolean
  label: string
}) {
  const unique = options.filter((option, index, items) => option.value && items.findIndex((other) => other.value === option.value) === index)
  return (
    <Select value={value || "__none"} onValueChange={(next) => onChange(next === "__none" ? "" : next)} required={required}>
      <SelectTrigger aria-label={label}>
        <SelectValue placeholder={`选择${label}`} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__none" disabled={required}>
          未选择
        </SelectItem>
        {value && !unique.some((option) => option.value === value) && <SelectItem value={value}>{value}（当前值）</SelectItem>}
        {unique.length === 0 && (
          <SelectItem value="__empty" disabled>
            暂无可选{label}
          </SelectItem>
        )}
        {unique.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const numericFields = new Set([
  "work_hours",
  "recovery_amount",
  "abatement_runtime",
  "opening_stock",
  "purchases",
  "charges",
  "closing_stock",
  "transfers",
  "recovery",
  "distance_km",
  "cargo_ton",
  "passenger_count",
  "spend_cny",
  "sales_quantity",
  "use_lifetime",
  "attribution_ratio",
  "coverage_ratio",
  "area_ha",
  "baseline_stock",
  "reporting_stock",
])

export function GhgTypedField({
  field,
  value,
  catalog,
  energy,
  onChange,
}: {
  field: GhgActivityFieldResponse
  value: string
  catalog?: GhgCatalog
  energy: GhgEnergyOption[]
  onChange: (value: string) => void
}) {
  const options = ghgFieldOptions(field, catalog, energy)
  if (options)
    return (
      <GhgValueSelect
        value={value}
        options={value && !options.some((option) => option.value === value) ? [...options, { value, label: ghgObjectLabel(field.code, value, catalog, energy) }] : options}
        onChange={onChange}
        required={field.required}
        label={field.label}
      />
    )
  return (
    <Input
      aria-label={field.label}
      type={numericFields.has(field.code) ? "number" : "text"}
      step="any"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={field.required}
    />
  )
}

export function ghgUnitOptions(categoryCode: string, energyCode: string, energy: GhgEnergyOption[], conversions: GhgUnitOption[], current: string): Option[] {
  const aliases: Record<string, string> = { electricity: "purchased_electricity", purchased_heat: "purchased_heat", steam: "steam", cooling: "cooling" }
  const resolvedCode = energy.some((item) => item.code === energyCode) ? energyCode : (aliases[energyCode] ?? energyCode)
  const selected = energy.find((item) => item.code === resolvedCode)
  const units = selected
    ? [selected.original_unit, ...conversions.filter((item) => item.energy_type_code === resolvedCode).flatMap((item) => [item.from_unit, item.to_unit])]
    : categoryCode === "2.1"
      ? energyCode === "electricity" || energyCode === "purchased_electricity"
        ? ["kWh", "MWh"]
        : energyCode === "steam"
          ? ["GJ", "t"]
          : ["GJ"]
      : categoryCode.startsWith("3.")
        ? ["km", "t·km", "person·km", "L", "kg"]
        : categoryCode === "1.4"
          ? ["kg", "t"]
          : ["kg", "t", "L", "m³", "Nm3", "万Nm3", "GJ", "unit"]
  return [...new Set([...units, current].filter((value): value is string => Boolean(value)))].map((unit) => ({
    value: unit,
    label: getActivityUnitLabel(unit) === unit ? unit : `${getActivityUnitLabel(unit)}（${unit}）`,
  }))
}
