import type { ReactNode } from "react"
import { AdminDataTable, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import type { Row } from "@/components/platform/data-admin-pages"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { EnergyRow, EnergyTotal } from "@/hooks/use-energy-entry"
import { moneyLabel, numberLabel, periodLabel, sourceLabel } from "./entry-utils"

export function EntrySelect({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
  disabled?: boolean
}) {
  return (
    <Select value={value || "__none"} onValueChange={(next) => onChange(next === "__none" ? "" : next)} disabled={disabled}>
      <SelectTrigger aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value || "__none"} value={option.value || "__none"}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
export function energyName(code: string, types: Row[]) {
  return String(types.find((type) => type.code === code)?.name ?? "未匹配能源")
}
export function EnergyTotals({ totals, types, label }: { totals: EnergyTotal[]; types: Row[]; label: string }) {
  return (
    <MetricStrip aria-label={label}>
      {totals.map((total) => (
        <MetricTile
          key={`${total.energy_type_code}-${total.unit}`}
          label={`${label} · ${energyName(total.energy_type_code, types)}`}
          value={numberLabel(total.amount)}
          unit={total.unit}
          meta={`${total.count} 条${total.cost_cny == null ? "" : ` · 费用 ${moneyLabel(total.cost_cny)} 元`}`}
        />
      ))}
    </MetricStrip>
  )
}
export function EnergyTable({
  rows,
  types,
  actions,
  message,
  highlightId,
  preview = false,
}: {
  rows: EnergyRow[]
  types: Row[]
  actions?: (row: EnergyRow) => ReactNode
  message?: string
  highlightId?: number
  preview?: boolean
}) {
  return (
    <AdminDataTable>
      <Table>
        <TableHeader>
          <TableRow>
            {preview && <TableHead>文件行</TableHead>}
            <TableHead>区域 / 设备</TableHead>
            <TableHead>期间</TableHead>
            <TableHead>能源种类</TableHead>
            <TableHead className="text-right">能源用量</TableHead>
            <TableHead>单位</TableHead>
            <TableHead className="text-right">费用（元）</TableHead>
            <TableHead>{preview ? "预检结果" : "来源"}</TableHead>
            {actions && <TableHead className="text-right">操作</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {message ? (
            <AdminTableStateRow colSpan={9}>{message}</AdminTableStateRow>
          ) : (
            rows.map((row, index) => (
              <TableRow key={row.id ?? row.row_number ?? index} data-state={row.id === highlightId ? "selected" : undefined} data-record-id={row.id}>
                {preview && <TableCell>{row.row_number}</TableCell>}
                <TableCell>
                  <div>{row.area_name || "未指定区域"}</div>
                  <div className="text-muted-foreground text-xs">{row.equipment_name || "区域汇总"}</div>
                </TableCell>
                <TableCell>{periodLabel(row)}</TableCell>
                <TableCell>{row.energy_type_code ? energyName(row.energy_type_code, types) : String(row.energy_type_name || "未匹配能源")}</TableCell>
                <TableCell className="text-right tabular-nums">{numberLabel(row.amount)}</TableCell>
                <TableCell>{row.unit}</TableCell>
                <TableCell className="text-right tabular-nums">{moneyLabel(row.cost_cny)}</TableCell>
                <TableCell>{preview ? (row.status === "error" ? row.message : "将新增") : sourceLabel(row.source_system)}</TableCell>
                {actions && <TableCell className="space-x-2 whitespace-nowrap text-right">{actions(row)}</TableCell>}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}
