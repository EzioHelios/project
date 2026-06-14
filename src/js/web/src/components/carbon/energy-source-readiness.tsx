import { useQuery } from "@tanstack/react-query"
import { Upload } from "lucide-react"

import { AdminPanel } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

type EnergySourceReadiness = {
  counts: Record<string, number>
  statuses: Record<string, string>
  items: { key: string; label: string; count: number; status: string }[]
}

const statusLabels: Record<string, string> = {
  ready: "真实来源",
  partial: "部分来源",
  source_missing: "来源缺失",
}

const importDatasetBySourceKey: Record<string, string> = {
  energy_interval_facts: "energy_interval_facts",
  scope1_stationary_combustion: "scope1_stationary_combustion",
  scope2_electricity_bills: "scope2_electricity_bills",
  production_output_facts: "production_output_facts",
}

function sourceStatusBadge(status?: string | null) {
  const label = statusLabels[status || ""] ?? status ?? "-"
  if (status === "ready") return <Badge variant="secondary">{label}</Badge>
  if (status === "partial") return <Badge className="bg-amber-500 hover:bg-amber-500">{label}</Badge>
  return <Badge variant="outline">{label}</Badge>
}

export function EnergySourceReadinessPanel({ focus = "energy_operations" }: { focus?: string }) {
  const query = useQuery<ApiEnvelope<EnergySourceReadiness>>({
    queryKey: ["energy", "source-readiness"],
    queryFn: () => fetchCarbonApi<EnergySourceReadiness>("/api/energy/source-readiness"),
  })
  const data = query.data?.data
  const focusStatus = data?.statuses?.[focus]
  const missingItems = (data?.items ?? []).filter((item) => item.status !== "ready")
  const firstMissingDataset = missingItems.map((item) => importDatasetBySourceKey[item.key]).find(Boolean) ?? "energy_interval_facts"
  const importHref = `/energy/consumption?tab=import&dataset=${encodeURIComponent(firstMissingDataset)}`
  return (
    <AdminPanel
      title="来源状态"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {sourceStatusBadge(focusStatus)}
          {missingItems.length ? (
            <Button data-testid="energy-source-readiness-import-link" size="sm" variant="outline" asChild>
              <a href={importHref}>
                <Upload className="mr-2 h-4 w-4" />
                数据导入
              </a>
            </Button>
          ) : null}
        </div>
      }
      contentClassName="p-0"
    >
      <div className="grid divide-y text-sm md:grid-cols-4 md:divide-x md:divide-y-0">
        {(data?.items ?? []).map((item) => (
          <div key={item.key} className="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <div className="font-medium">{item.label}</div>
              <div className="mt-1 text-xs text-muted-foreground">{item.count.toLocaleString("zh-CN")} 行</div>
            </div>
            {sourceStatusBadge(item.status)}
          </div>
        ))}
        {!data?.items?.length ? <div className="px-4 py-3 text-muted-foreground">暂无来源状态</div> : null}
      </div>
      {missingItems.length ? (
        <div className="flex flex-wrap gap-2 border-t px-4 py-3 text-sm" data-testid="energy-source-readiness-missing-datasets">
          {missingItems.map((item) => (
            <Badge key={item.key} variant="outline">
              缺 {item.label}
            </Badge>
          ))}
        </div>
      ) : null}
    </AdminPanel>
  )
}
