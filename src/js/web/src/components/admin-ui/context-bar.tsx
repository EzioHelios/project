import type * as React from "react"

import { cn } from "@/lib/utils"

type ContextBarProps = React.HTMLAttributes<HTMLDivElement> & {
  actions?: React.ReactNode
}

export function ContextBar({ className, actions, children, ...props }: ContextBarProps) {
  return (
    <div className={cn("admin-context-bar", className)} {...props}>
      <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-2 xl:grid-cols-6">{children}</div>
      {actions && <div className="flex shrink-0 justify-end gap-2">{actions}</div>}
    </div>
  )
}
