import { Link } from "@tanstack/react-router"
import { AdminDataTable, AdminTableStateRow } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { GhgActivity, GhgCatalog } from "@/lib/api/hooks/ghg-inventory"

export function GhgRecordResults({ records, catalog, onSelect }: { records: GhgActivity[]; catalog?: GhgCatalog; onSelect?: (row: GhgActivity) => void }) {
  return (
    <AdminDataTable>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead>活动 / 排放源</TableHead>
            <TableHead>所属区域 / 设备</TableHead>
            <TableHead className="w-28">期间</TableHead>
            <TableHead className="w-32 text-right">数量</TableHead>
            <TableHead className="w-24">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.length === 0 && <AdminTableStateRow colSpan={5}>本次没有保存活动记录</AdminTableStateRow>}
          {records.map((row) => (
            <TableRow key={`${row.inventoryCode}:${row.recordCode}`}>
              <TableCell className="whitespace-normal break-words align-top">
                <div className="font-medium">{row.activityName}</div>
                <div className="text-muted-foreground text-xs">{row.sourceName || "未命名排放源"}</div>
              </TableCell>
              <TableCell className="whitespace-normal break-words align-top">
                <div>{row.facilityName || catalog?.areas.find((area) => area.code === row.facilityCode)?.name || "未指定区域"}</div>
                <div className="text-muted-foreground text-xs">{[...row.allocatedAreaNames, ...row.allocatedEquipmentNames].join(" / ") || "未归集"}</div>
              </TableCell>
              <TableCell className="whitespace-normal align-top">
                <div>{row.periodStart}</div>
                <div className="text-muted-foreground text-xs">至 {row.periodEnd}</div>
              </TableCell>
              <TableCell className="whitespace-normal text-right align-top tabular-nums">
                {formatGhgAmount(row.activityAmount)} {row.activityUnit}
              </TableCell>
              <TableCell>
                {onSelect ? (
                  <Button size="sm" variant="link" className="px-0" onClick={() => onSelect(row)}>
                    查看记录
                  </Button>
                ) : (
                  <Button asChild size="sm" variant="link" className="px-0">
                    <Link
                      to="/carbon-mgmt/category/$categoryCode"
                      params={{ categoryCode: row.isoCategoryCode }}
                      search={{ inventory: row.inventoryCode, record: row.recordCode, batch: row.batchCode || undefined }}
                    >
                      查看与修改
                    </Link>
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

export function formatGhgAmount(value: string | number) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString("zh-CN", { maximumFractionDigits: 10 }) : String(value)
}

export function GhgAmountSummary({ summary }: { summary: Array<{ activityUnit: string; activityAmount: string; recordCount: number }> }) {
  return (
    <section className="flex flex-wrap gap-x-6 gap-y-2 text-sm" aria-label="分单位汇总">
      {summary.map((item) => (
        <div key={item.activityUnit}>
          <span className="font-medium tabular-nums">
            {formatGhgAmount(item.activityAmount)} {item.activityUnit}
          </span>
          <span className="ml-2 text-muted-foreground">{item.recordCount} 条</span>
        </div>
      ))}
    </section>
  )
}
