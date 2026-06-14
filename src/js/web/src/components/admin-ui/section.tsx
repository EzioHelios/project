import type * as React from "react"

import { cn } from "@/lib/utils"

type AdminPanelProps = Omit<React.HTMLAttributes<HTMLElement>, "title"> & {
  title?: React.ReactNode
  actions?: React.ReactNode
  contentClassName?: string
}

export function AdminPanel({ title, actions, className, contentClassName, children, ...props }: AdminPanelProps) {
  return (
    <section className={cn("admin-panel overflow-hidden", className)} {...props}>
      {(title || actions) && (
        <div className="admin-panel-header">
          <div className="min-w-0">{title && <h2 className="admin-panel-title">{title}</h2>}</div>
          {actions && <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("admin-panel-content", contentClassName)}>{children}</div>
    </section>
  )
}

type AdminSectionHeaderProps = React.HTMLAttributes<HTMLDivElement> & {
  title: React.ReactNode
  actions?: React.ReactNode
}

export function AdminSectionHeader({ title, actions, className, ...props }: AdminSectionHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3", className)} {...props}>
      <div className="min-w-0">
        <h3 className="font-semibold text-sm leading-6">{title}</h3>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
