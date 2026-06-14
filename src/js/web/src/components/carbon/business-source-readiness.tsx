import { useQuery } from "@tanstack/react-query"

import { AdminPanel, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { Badge } from "@/components/ui/badge"

type BusinessSourceReadiness = {
  status: string
  total_record_count?: number
  real_source_record_count?: number
  write_validation_record_count?: number
  [key: string]: number | string | undefined
}

const statusLabels: Record<string, string> = {
  real_source_ready: "真实来源",
  real_source_with_validation_writes: "真实来源",
  source_missing: "来源缺失",
}

export function BusinessSourceReadinessPanel({
  endpoint,
  queryKey,
  testId,
  primaryLabel,
  primaryKey,
}: {
  endpoint: string
  queryKey: string[]
  testId: string
  primaryLabel: string
  primaryKey: string
}) {
  const query = useQuery<ApiEnvelope<BusinessSourceReadiness>>({
    queryKey,
    queryFn: () => fetchCarbonApi<BusinessSourceReadiness>(endpoint),
  })
  const data = query.data?.data
  const status = data?.status ?? "source_missing"
  return (
    <AdminPanel contentClassName="grid gap-3 md:grid-cols-5" data-testid={testId}>
      <div className="rounded-md border p-3">
        <div className="text-xs text-muted-foreground">来源状态</div>
        <div className="mt-2">
          <SourceStatusBadge value={status} />
        </div>
      </div>
      <MetricTile label="企业来源记录" value={formatCount(data?.real_source_record_count)} />
      <MetricTile label="验证写入记录" value={formatCount(data?.write_validation_record_count)} />
      <MetricTile label="业务记录" value={formatCount(data?.total_record_count)} />
      <MetricTile label={primaryLabel} value={formatCount(data?.[primaryKey])} />
    </AdminPanel>
  )
}

function SourceStatusBadge({ value }: { value: string }) {
  return <Badge variant={value === "source_missing" ? "destructive" : "outline"}>{statusLabels[value] ?? value}</Badge>
}

function formatCount(value: number | string | undefined) {
  if (value === undefined || value === "") return "-"
  return Number(value || 0).toLocaleString("zh-CN")
}
