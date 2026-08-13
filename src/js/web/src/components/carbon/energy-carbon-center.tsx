import { Link } from "@tanstack/react-router"
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, type LucideIcon } from "lucide-react"
import type * as React from "react"

import { AdminEmptyState, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export function formatEcNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

export function severityLabel(severity?: string | null) {
  if (severity === "high") return "高"
  if (severity === "medium") return "中"
  if (severity === "low") return "低"
  return "未标注"
}

export function sourceLabel(value?: string | null) {
  if (value === "meter_aggregate") return "电表聚合"
  if (value === "historical_estimate") return "历史估算"
  if (value === "manual_bill") return "账单补录"
  if (value === "raw_meter_fallback") return "明细回退"
  if (value === "activity_data") return "业务录入"
  if (value === "demo_seed") return "系统初始化"
  if (value === "alarm") return "设备告警"
  if (value === "video") return "视频告警"
  if (value === "carbon") return "碳告警"
  return value || "未标注"
}

export function statusBadge(status?: string | null) {
  if (status === "稳定" || status === "已通过" || status === "已处理") {
    return <Badge variant="success">{status}</Badge>
  }
  if (status === "高风险" || status === "待处理" || status === "待审核" || status === "驳回") {
    return <Badge variant="destructive">{status}</Badge>
  }
  if (status === "异常" || status === "缺失") {
    return <Badge variant="warning">{status}</Badge>
  }
  return <Badge variant="secondary">{status || "未标注"}</Badge>
}

export function QuickLinkGrid({ items }: { items: { label: string; to: string; icon?: LucideIcon }[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={cn("group rounded-lg border border-border/60 bg-card px-4 py-4 transition-colors", "hover:border-primary/40 hover:bg-accent/40")}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              {item.icon && <item.icon className="h-4 w-4 text-primary" />}
              <span>{item.label}</span>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
          </div>
        </Link>
      ))}
    </div>
  )
}

export function HealthMatrix({
  title,
  items,
}: {
  title: string
  items: {
    id: number | string
    name: string
    status: string
    health_ratio?: number
    alert_unhandled?: number
    equipment_online?: number
    equipment_total?: number
  }[]
}) {
  return (
    <AdminPanel title={title} contentClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {items.length === 0 && <AdminEmptyState title="暂无区域健康度数据" className="md:col-span-2 xl:col-span-3" />}
      {items.map((item) => (
        <div key={item.id} className="rounded-md border border-border/60 bg-card/60 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="font-medium">{item.name}</div>
            {statusBadge(item.status)}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div>
              <div className="text-xs text-muted-foreground">健康度</div>
              <div className="font-medium">{formatEcNumber(item.health_ratio, 1)}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">未处理告警</div>
              <div className="font-medium">{item.alert_unhandled ?? 0}</div>
            </div>
            <div className="col-span-2">
              <div className="text-xs text-muted-foreground">设备在线</div>
              <div className="font-medium">
                {item.equipment_online ?? 0}/{item.equipment_total ?? 0}
              </div>
            </div>
          </div>
        </div>
      ))}
    </AdminPanel>
  )
}

export function FacetNavigation({
  title,
  items,
  selectedKey,
  onSelect,
}: {
  title: string
  items: { key: string; label: string; count?: number }[]
  selectedKey: string
  onSelect: (key: string) => void
}) {
  return (
    <AdminPanel title={title} contentClassName="space-y-2">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onSelect(item.key)}
          className={cn(
            "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
            selectedKey === item.key ? "border-primary bg-primary/5 text-foreground" : "border-border/60 bg-card/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
          )}
        >
          <span>{item.label}</span>
          {item.count !== undefined && <Badge variant="secondary">{item.count}</Badge>}
        </button>
      ))}
    </AdminPanel>
  )
}

export function DetailPanel({ title, items, footer }: { title: string; items: { label: string; value: string | number | null | undefined }[]; footer?: React.ReactNode }) {
  return (
    <AdminPanel title={title} className="h-full" contentClassName="space-y-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-start justify-between gap-4 text-sm">
          <span className="text-muted-foreground">{item.label}</span>
          <span className="text-right font-medium">{item.value === null || item.value === undefined || item.value === "" ? "-" : String(item.value)}</span>
        </div>
      ))}
      {footer && (
        <>
          <Separator />
          {footer}
        </>
      )}
    </AdminPanel>
  )
}

export function TaskList({
  title,
  items,
  emptyLabel = "暂无待办",
}: {
  title: string
  items: { label: string; value?: string | number; tone?: "warning" | "default" }[]
  emptyLabel?: string
}) {
  return (
    <AdminPanel title={title} contentClassName="space-y-3">
      {items.length === 0 && <AdminEmptyState title={emptyLabel} />}
      {items.map((item, index) => (
        <div key={`${item.label}-${index}`} className="flex items-start gap-3 rounded-md border border-border/60 bg-card/60 px-3 py-2">
          {item.tone === "warning" ? (
            <AlertTriangle className="mt-0.5 h-4 w-4 text-[hsl(var(--status-warning-foreground-admin))]" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 text-[hsl(var(--status-success-foreground-admin))]" />
          )}
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{item.label}</div>
            {item.value !== undefined && <div className="text-xs text-muted-foreground">{item.value}</div>}
          </div>
        </div>
      ))}
    </AdminPanel>
  )
}

function formatTraceScalar(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "number") return formatEcNumber(value)
  if (typeof value === "boolean") return value ? "是" : "否"
  if (value instanceof Date) return value.toLocaleString("zh-CN")
  return String(value)
}

function formatTraceNestedValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatTraceNestedValue(item)).join("；") || "-"
  }
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, nestedValue]) => `${key}: ${formatTraceNestedValue(nestedValue)}`)
      .join("；")
  }
  return formatTraceScalar(value)
}

function TraceDetail({ detail }: { detail: unknown }) {
  if (detail === null || detail === undefined || detail === "") {
    return <span>-</span>
  }
  if (typeof detail !== "object") {
    return <span>{formatTraceScalar(detail)}</span>
  }
  if (Array.isArray(detail)) {
    const formattedItems = detail.map(formatTraceNestedValue)

    return (
      <div className="space-y-1">
        {formattedItems.map((item) => (
          <div key={item}>{item}</div>
        ))}
      </div>
    )
  }
  return (
    <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[minmax(96px,auto)_1fr]">
      {Object.entries(detail).map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-muted-foreground">{key}</dt>
          <dd className="min-w-0 break-words text-foreground">{formatTraceNestedValue(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

export function TraceTimeline({ items }: { items: { step: string; summary?: string | null; detail?: unknown }[] }) {
  return (
    <AdminPanel title="追溯链路" contentClassName="space-y-4">
      {items.length === 0 && <AdminEmptyState title="暂无追溯链路" />}
      {items.map((item, index) => (
        <div key={`${item.step}-${index}`} className="flex gap-3">
          <div className="flex w-6 flex-col items-center">
            <div className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" />
            {index < items.length - 1 && <div className="mt-1 h-full w-px bg-border" />}
          </div>
          <div className="min-w-0 flex-1 pb-3">
            <div className="flex items-center gap-2">
              <div className="font-medium">{item.step}</div>
              {item.summary && <Badge variant="outline">{item.summary}</Badge>}
            </div>
            <div className="mt-1 text-sm">
              <TraceDetail detail={item.detail} />
            </div>
          </div>
        </div>
      ))}
    </AdminPanel>
  )
}

export function EmptyStateCard({ title }: { title: string }) {
  return <AdminEmptyState title={title} className="min-h-[220px]" />
}

export function JumpLinks({ items }: { items: { label: string; to: string }[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Button key={item.to} variant="outline" size="sm" asChild>
          <Link to={item.to}>
            {item.label}
            <ChevronRight className="h-4 w-4" />
          </Link>
        </Button>
      ))}
    </div>
  )
}

export function IssueSummaryStrip({ items }: { items: { label: string; value: number; tone?: "warning" | "default" }[] }) {
  return (
    <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
      {items.slice(0, 4).map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} tone={item.tone === "warning" ? "warning" : "success"} />
      ))}
    </MetricStrip>
  )
}
