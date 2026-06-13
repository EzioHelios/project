import type * as React from "react"

import { cn } from "@/lib/utils"

type AdminPageScaffoldProps = React.HTMLAttributes<HTMLDivElement> & {
  header?: React.ReactNode
  tabs?: React.ReactNode
  filters?: React.ReactNode
  metrics?: React.ReactNode
  children: React.ReactNode
}

export function AdminPageScaffold({ header, tabs, filters, metrics, children, className, ...props }: AdminPageScaffoldProps) {
  return (
    <div className={cn("admin-page-scaffold", className)} {...props}>
      {header && <div className="admin-page-scaffold-header">{header}</div>}
      {tabs && <div className="admin-page-scaffold-tabs">{tabs}</div>}
      {filters && <div className="admin-page-scaffold-filters">{filters}</div>}
      {metrics && <div className="admin-page-scaffold-metrics">{metrics}</div>}
      <div className="admin-page-scaffold-content">{children}</div>
    </div>
  )
}
