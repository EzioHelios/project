import type * as React from "react"

import { cn } from "@/lib/utils"

type AdminPanelProps = React.HTMLAttributes<HTMLElement> & {
  title?: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  contentClassName?: string
}

export function AdminPanel({ title, description, actions, className, contentClassName, children, ...props }: AdminPanelProps) {
  return (
    <section className={cn("admin-panel overflow-hidden", className)} {...props}>
      {(title || description || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-3 border-border/70 border-b px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="font-semibold text-[0.95rem] text-foreground leading-6">{title}</h2>}
            {description && <p className="mt-0.5 text-muted-foreground text-xs leading-5">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("p-4", contentClassName)}>{children}</div>
    </section>
  )
}

type AdminSectionHeaderProps = React.HTMLAttributes<HTMLDivElement> & {
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
}

export function AdminSectionHeader({ title, description, actions, className, ...props }: AdminSectionHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3", className)} {...props}>
      <div className="min-w-0">
        <h3 className="font-semibold text-sm leading-6">{title}</h3>
        {description && <p className="text-muted-foreground text-xs leading-5">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
