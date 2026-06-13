import type * as React from "react"

import { cn } from "@/lib/utils"

type AdminPageHeaderProps = React.HTMLAttributes<HTMLDivElement> & {
  title: React.ReactNode
  status?: React.ReactNode
  actions?: React.ReactNode
  meta?: React.ReactNode
}

export function AdminPageHeader({ title, status, actions, meta, className, ...props }: AdminPageHeaderProps) {
  return (
    <div className={cn("flex min-h-10 flex-wrap items-center justify-between gap-3 border-border/70 border-b pb-2.5", className)} {...props}>
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h1 className="truncate font-heading font-semibold text-foreground text-xl leading-7 tracking-normal">{title}</h1>
          {status}
        </div>
        {meta && <div className="mt-1 flex flex-wrap items-center gap-2 text-muted-foreground text-xs leading-5">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">{actions}</div>}
    </div>
  )
}
