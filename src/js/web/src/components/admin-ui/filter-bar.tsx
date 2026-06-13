import { ChevronDown, ChevronUp } from "lucide-react"
import type * as React from "react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type AdminFilterField = {
  key: string
  node: React.ReactNode
  className?: string
}

type AdminFilterBarProps = React.HTMLAttributes<HTMLDivElement> & {
  fields: AdminFilterField[]
  actions?: React.ReactNode
  defaultVisibleCount?: number
}

export function AdminFilterBar({ fields, actions, defaultVisibleCount = 4, className, ...props }: AdminFilterBarProps) {
  const [expanded, setExpanded] = useState(false)
  const visibleCount = Math.max(1, defaultVisibleCount)
  const hasOverflow = fields.length > visibleCount
  const visibleFields = expanded || !hasOverflow ? fields : fields.slice(0, visibleCount)

  return (
    <div className={cn("admin-filter-bar", expanded && "admin-filter-bar-expanded", className)} {...props}>
      <div className="admin-filter-fields">
        {visibleFields.map((field) => (
          <div className={cn("admin-filter-field", field.className)} key={field.key}>
            {field.node}
          </div>
        ))}
      </div>
      <div className="admin-filter-actions">
        {hasOverflow && (
          <Button type="button" variant="ghost" size="sm" className="admin-filter-toggle" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
            {expanded ? (
              <>
                收起
                <ChevronUp className="h-4 w-4" />
              </>
            ) : (
              <>
                显示全部
                <ChevronDown className="h-4 w-4" />
              </>
            )}
          </Button>
        )}
        {actions}
      </div>
    </div>
  )
}
