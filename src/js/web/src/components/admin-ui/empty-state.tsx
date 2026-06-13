import type * as React from "react"

import { cn } from "@/lib/utils"

type AdminEmptyStateProps = React.HTMLAttributes<HTMLDivElement> & {
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
}

export function AdminEmptyState({ title, description, actions, className, ...props }: AdminEmptyStateProps) {
  return (
    <div
      className={cn("flex min-h-32 flex-col items-center justify-center rounded-md border border-dashed border-border/80 bg-muted/25 px-4 py-8 text-center", className)}
      {...props}
    >
      <div className="font-medium text-sm">{title}</div>
      {description && <div className="mt-1 max-w-md text-muted-foreground text-xs leading-5">{description}</div>}
      {actions && <div className="mt-4 flex flex-wrap justify-center gap-2">{actions}</div>}
    </div>
  )
}
