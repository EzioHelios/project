import { useMemo, useState } from "react"
import { AdminDataTable, AdminPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

function formatValue(value: unknown) {
  if (value === null || value === undefined) return "-"
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : String(value)
  if (typeof value === "boolean") return value ? "是" : "否"
  if (typeof value === "string") return value.length > 60 ? `${value.slice(0, 60)}…` : value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value)
}

function safeKeys(obj: Record<string, unknown>) {
  return Object.keys(obj).sort((a, b) => a.localeCompare(b))
}

export function KeyValueGrid({ data }: { data: unknown }) {
  const entries = useMemo(() => {
    if (!isRecord(data)) return []
    return safeKeys(data).map((k) => [k, data[k]] as const)
  }, [data])

  if (entries.length === 0) {
    return <div className="text-sm text-muted-foreground">暂无数据</div>
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-start justify-between gap-4 rounded-md border border-border/60 bg-card/60 px-3 py-2">
          <div className="min-w-0 text-xs text-muted-foreground">{k}</div>
          <div className="text-right text-sm font-medium">{formatValue(v)}</div>
        </div>
      ))}
    </div>
  )
}

export function AutoTable({ data, maxColumns = 8 }: { data: unknown; maxColumns?: number }) {
  const { rows, columns } = useMemo(() => {
    if (!Array.isArray(data)) return { rows: [] as Record<string, unknown>[], columns: [] as string[] }
    const rowObjs = data.filter(isRecord)
    const keys = new Set<string>()
    for (const r of rowObjs) {
      for (const k of Object.keys(r)) keys.add(k)
    }
    const cols = Array.from(keys)
      .sort((a, b) => a.localeCompare(b))
      .slice(0, maxColumns)
    return { rows: rowObjs, columns: cols }
  }, [data, maxColumns])

  if (rows.length === 0 || columns.length === 0) {
    return <div className="text-sm text-muted-foreground">暂无可展示的表格数据</div>
  }

  return (
    <AdminDataTable>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((c) => (
              <TableHead key={c}>{c}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, idx) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: 该表格为只读展示
            <TableRow key={idx}>
              {columns.map((c) => (
                <TableCell key={c} className="max-w-[260px] truncate">
                  {formatValue(r[c])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

export function RawJsonCollapsible({ data, title = "原始返回值" }: { data: unknown; title?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium">{title}</div>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm">
            {open ? "收起" : "展开"}
          </Button>
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent className="mt-3">
        {Array.isArray(data) ? <AutoTable data={data} maxColumns={10} /> : <KeyValueGrid data={data} />}
      </CollapsibleContent>
    </Collapsible>
  )
}

export function DataCard({
  title,
  data,
  prefer = "auto",
  rawTitle,
  showRaw = false,
}: {
  title: string
  data: unknown
  prefer?: "auto" | "kv" | "table"
  rawTitle?: string
  showRaw?: boolean
}) {
  const mode = useMemo(() => {
    if (prefer === "kv") return "kv"
    if (prefer === "table") return "table"
    if (Array.isArray(data)) return "table"
    return "kv"
  }, [data, prefer])

  return (
    <AdminPanel title={title} contentClassName="space-y-4">
      {mode === "table" ? <AutoTable data={data} /> : <KeyValueGrid data={data} />}
      {showRaw && <RawJsonCollapsible data={data} title={rawTitle ?? "原始返回值"} />}
    </AdminPanel>
  )
}
