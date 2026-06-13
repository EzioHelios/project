import type * as React from "react"

import { AdminFilterBar, type AdminFilterField } from "@/components/admin-ui/filter-bar"
import { cn } from "@/lib/utils"

type AdminTableToolbarProps = React.HTMLAttributes<HTMLDivElement> & {
  fields?: AdminFilterField[]
  search?: React.ReactNode
  filters?: React.ReactNode
  actions?: React.ReactNode
  defaultVisibleCount?: number
}

export function AdminTableToolbar({ fields, search, filters, actions, children, defaultVisibleCount, className, ...props }: AdminTableToolbarProps) {
  if (fields?.length) {
    return <AdminFilterBar fields={fields} actions={actions} defaultVisibleCount={defaultVisibleCount} className={cn("admin-table-filter-bar", className)} {...props} />
  }

  return (
    <div className={cn("admin-toolbar flex flex-wrap items-center gap-3 px-3 py-2", className)} {...props}>
      {search && <div className="min-w-[240px] flex-1">{search}</div>}
      {filters && <div className="flex flex-wrap items-center gap-2">{filters}</div>}
      {children}
      {actions && <div className="ml-auto flex flex-wrap items-center justify-end gap-2">{actions}</div>}
    </div>
  )
}
