import { RefreshCw } from "lucide-react"
import type * as React from "react"

import { AdminEmptyState, AdminPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export type AssetRow = Record<string, unknown>

export function fieldValue(row: AssetRow, key: string) {
  return row[key]
}

export function textOf(row: AssetRow, key: string, fallback = "—") {
  const value = fieldValue(row, key)
  return value === null || value === undefined || value === "" ? fallback : String(value)
}

export function numberOf(row: AssetRow, key: string) {
  const value = Number(fieldValue(row, key) ?? 0)
  return Number.isFinite(value) ? value : 0
}

export function formatNumber(value: unknown, digits = 2) {
  const number = Number(value ?? 0)
  return Number.isFinite(number) ? number.toLocaleString("zh-CN", { maximumFractionDigits: digits }) : "—"
}

export function marketQuoteMetricLabel(metric: unknown) {
  if (metric === "daily-close-v1") return "日收盘价"
  if (metric === "daily-average-v1") return "日成交均价"
  if (metric === "monthly-average-vintage-2025-v1") return "月度均价（2025年电量）"
  if (metric === "manual-observed-v1") return "登记价格"
  return "价格"
}

export function RefreshButton({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  return (
    <Button size="sm" variant="outline" onClick={onClick} disabled={loading}>
      <RefreshCw className={loading ? "animate-spin" : ""} />
      刷新
    </Button>
  )
}

export function AssetTable({
  title,
  rows,
  columns,
  actions,
  emptyTitle = "暂无记录",
}: {
  title: string
  rows: AssetRow[]
  columns: Array<{ key: string; label: string; render?: (row: AssetRow) => React.ReactNode; align?: "left" | "right" }>
  actions?: React.ReactNode
  emptyTitle?: string
}) {
  return (
    <AdminPanel title={title} actions={actions} contentClassName="p-0">
      {rows.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                  {column.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow key={String(row.id ?? index)}>
                {columns.map((column) => (
                  <TableCell key={column.key} className={column.align === "right" ? "text-right tabular-nums" : undefined}>
                    {column.render ? column.render(row) : textOf(row, column.key)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <AdminEmptyState title={emptyTitle} />
      )}
    </AdminPanel>
  )
}
