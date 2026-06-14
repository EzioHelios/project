import type * as React from "react"

import { AdminPageHeader } from "@/components/admin-ui/page-header"
import { cn } from "@/lib/utils"

type AdminPageScaffoldProps = React.HTMLAttributes<HTMLDivElement> & {
  title?: React.ReactNode
  header?: React.ReactNode
  topActions?: React.ReactNode
  status?: React.ReactNode
  meta?: React.ReactNode
  tabs?: React.ReactNode
  filters?: React.ReactNode
  metrics?: React.ReactNode
  children: React.ReactNode
}

export function AdminPageScaffold({ title, header, topActions, status, meta, tabs, filters, metrics, children, className, ...props }: AdminPageScaffoldProps) {
  const resolvedHeader = header ?? (title ? <AdminPageHeader title={title} status={status} actions={topActions} meta={meta} /> : null)

  return (
    <div className={cn("admin-page-scaffold", className)} {...props}>
      {resolvedHeader && <div className="admin-page-scaffold-header">{resolvedHeader}</div>}
      {tabs && <div className="admin-page-scaffold-tabs">{tabs}</div>}
      {filters && <div className="admin-page-scaffold-filters">{filters}</div>}
      {metrics && <div className="admin-page-scaffold-metrics">{metrics}</div>}
      <div className="admin-page-scaffold-content">{children}</div>
    </div>
  )
}
