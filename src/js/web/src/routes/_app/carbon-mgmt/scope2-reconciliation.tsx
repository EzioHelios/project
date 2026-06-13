import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { toast } from "sonner"

import { AdminPageHeader, AdminPanel, AdminTableToolbar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

type ReconciliationResponse = {
  billing_month: string
  manual_bill_total_kwh: number
  meter_aggregate_total_kwh: number
  difference_kwh: number
  difference_rate?: number | null
  missing_meter_count: number
}

type ApiResponse<T> = { code: number; msg?: string; data: T }

async function fetchJson<T>(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiResponse<T>
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-reconciliation")({
  component: Scope2ReconciliationPage,
})

function Scope2ReconciliationPage() {
  const [billingMonth, setBillingMonth] = useState("")

  const reconciliationQuery = useQuery({
    queryKey: ["carbon-mgmt", "scope2-reconciliation", billingMonth],
    enabled: Boolean(billingMonth.trim()),
    queryFn: async () => (await fetchJson<ReconciliationResponse>(`/api/carbon/scope2-reconciliation?billing_month=${billingMonth.trim()}`)).data,
  })

  const rebuildMut = useMutation({
    mutationFn: async () =>
      fetchJson<{ rebuilt_count: number; ready_count: number; invalid_count: number }>("/api/carbon/scope2-meter-aggregate/rebuild", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ billing_month: billingMonth.trim() }),
      }),
    onSuccess: async () => {
      toast.success("月度聚合已重建")
      await reconciliationQuery.refetch()
    },
    onError: (error) => toast.error("重建失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const data = reconciliationQuery.data

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="[范围2] 数据对账" />
      <PageSection>
        <AdminPanel title="月度对账" contentClassName="space-y-4">
          <AdminTableToolbar
            filters={
              <div className="w-[180px]">
                <Input value={billingMonth} onChange={(event) => setBillingMonth(event.target.value)} placeholder="账期 YYYY-MM" />
              </div>
            }
            actions={
              <>
                <Button variant="outline" size="sm" onClick={() => reconciliationQuery.refetch()} disabled={!billingMonth.trim() || reconciliationQuery.isFetching}>
                  查询
                </Button>
                <Button onClick={() => rebuildMut.mutate()} disabled={!billingMonth.trim() || rebuildMut.isPending}>
                  执行月聚合
                </Button>
              </>
            }
          />
          <MetricStrip className="xl:grid-cols-5">
            <MetricTile label="账期" value={data?.billing_month ?? "-"} />
            <MetricTile label="人工账单总电量" value={data ? data.manual_bill_total_kwh : "-"} unit={data ? "kWh" : undefined} />
            <MetricTile label="电表聚合总电量" value={data ? data.meter_aggregate_total_kwh : "-"} unit={data ? "kWh" : undefined} />
            <MetricTile
              label="差异值"
              value={data ? data.difference_kwh : "-"}
              unit={data ? "kWh" : undefined}
              tone={data && Math.abs(data.difference_kwh) > 0 ? "warning" : "default"}
            />
            <MetricTile label="差异率 / 缺失电表" value={data ? `${data.difference_rate ?? "-"}% / ${data.missing_meter_count}` : "-"} />
          </MetricStrip>
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
