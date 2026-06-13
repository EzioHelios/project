import * as React from "react"

import { AdminFilterBar, type AdminFilterField } from "@/components/admin-ui/filter-bar"
import { cn } from "@/lib/utils"

type ContextBarProps = React.HTMLAttributes<HTMLDivElement> & {
  actions?: React.ReactNode
  defaultVisibleCount?: number
}

export function ContextBar({ className, actions, children, defaultVisibleCount, ...props }: ContextBarProps) {
  const fields: AdminFilterField[] = React.Children.toArray(children).map((node, index) => ({
    key: `context-filter-${index}`,
    node,
  }))

  return <AdminFilterBar fields={fields} actions={actions} defaultVisibleCount={defaultVisibleCount} className={cn("admin-context-bar", className)} {...props} />
}
