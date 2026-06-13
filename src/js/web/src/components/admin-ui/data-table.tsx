import type * as React from "react"

import { TableCell, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

type AdminDataTableProps = React.HTMLAttributes<HTMLDivElement> & {
  density?: "compact" | "default"
}

export function AdminDataTable({ density = "compact", className, children, ...props }: AdminDataTableProps) {
  return (
    <div className={cn("overflow-x-auto rounded-md border border-border/70 bg-card", density === "compact" && "admin-table-density-compact", className)} {...props}>
      {children}
    </div>
  )
}

type AdminTableStateRowProps = {
  colSpan: number
  children: React.ReactNode
  tone?: "default" | "danger"
}

export function AdminTableStateRow({ colSpan, children, tone = "default" }: AdminTableStateRowProps) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className={cn("h-24 text-center text-sm", tone === "danger" ? "text-destructive" : "text-muted-foreground")}>
        {children}
      </TableCell>
    </TableRow>
  )
}
