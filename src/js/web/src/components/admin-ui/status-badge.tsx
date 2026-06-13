import type * as React from "react"

import { cn } from "@/lib/utils"

export type OperationalStatus = "draft" | "pending" | "in_progress" | "approved" | "locked" | "rejected" | "archived" | "inactive"
export type QualityStatus = "A" | "B" | "C" | "D" | "E"

const statusMeta: Record<OperationalStatus, { label: string; className: string }> = {
  draft: { label: "草稿", className: "border-border bg-muted/45 text-muted-foreground" },
  pending: { label: "待处理", className: "border-[hsl(var(--status-warning))]/35 bg-[hsl(var(--status-warning))]/10 text-[hsl(var(--status-warning-foreground-admin))]" },
  in_progress: { label: "处理中", className: "border-[hsl(var(--status-info))]/35 bg-[hsl(var(--status-info))]/10 text-[hsl(var(--status-info-foreground-admin))]" },
  approved: { label: "已通过", className: "border-[hsl(var(--status-success))]/35 bg-[hsl(var(--status-success))]/10 text-[hsl(var(--status-success-foreground-admin))]" },
  locked: { label: "已锁定", className: "border-slate-300 bg-slate-100 text-slate-700" },
  rejected: { label: "已驳回", className: "border-[hsl(var(--status-danger))]/35 bg-[hsl(var(--status-danger))]/10 text-[hsl(var(--status-danger-foreground-admin))]" },
  archived: { label: "已归档", className: "border-border bg-muted/35 text-muted-foreground" },
  inactive: { label: "停用", className: "border-border bg-background text-muted-foreground" },
}

const qualityMeta: Record<QualityStatus, { label: string; className: string }> = {
  A: { label: "A 级", className: "border-[hsl(var(--quality-a))]/35 bg-[hsl(var(--quality-a))]/10 text-[hsl(var(--quality-a))]" },
  B: { label: "B 级", className: "border-[hsl(var(--quality-b))]/35 bg-[hsl(var(--quality-b))]/10 text-[hsl(var(--quality-b))]" },
  C: { label: "C 级", className: "border-[hsl(var(--quality-c))]/35 bg-[hsl(var(--quality-c))]/10 text-[hsl(var(--quality-c))]" },
  D: { label: "D 级", className: "border-[hsl(var(--quality-d))]/35 bg-[hsl(var(--quality-d))]/10 text-[hsl(var(--quality-d))]" },
  E: { label: "E 级", className: "border-[hsl(var(--quality-e))]/35 bg-[hsl(var(--quality-e))]/10 text-[hsl(var(--quality-e))]" },
}

type StatusBadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  status: OperationalStatus
  label?: string
}

export function StatusBadge({ status, label, className, ...props }: StatusBadgeProps) {
  const meta = statusMeta[status]
  return (
    <span className={cn("inline-flex h-6 items-center rounded-sm border px-2 font-medium text-xs leading-none", meta.className, className)} {...props}>
      {label ?? meta.label}
    </span>
  )
}

type QualityBadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  quality: QualityStatus
  label?: string
}

export function QualityBadge({ quality, label, className, ...props }: QualityBadgeProps) {
  const meta = qualityMeta[quality]
  return (
    <span className={cn("inline-flex h-6 items-center rounded-sm border px-2 font-medium text-xs leading-none", meta.className, className)} {...props}>
      {label ?? meta.label}
    </span>
  )
}

export { qualityMeta, statusMeta }
