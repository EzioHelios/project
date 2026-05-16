import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { type ApiEnvelope, DiagnosticsPanel, FlowGraph, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import { JumpLinks } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type FlowData = {
  title: string
  unit: string
  nodes: { id: string; name: string; value?: number; category?: string }[]
  links: { source: string; target: string; value: number }[]
  diagnostics?: Record<string, unknown>
}

type BalanceData = {
  billing_month?: string | null
  table: { label: string; value: number; unit: string }[]
  diagnostics: { label: string; value: string | number }[]
}

type TopLinksData = {
  items: { source: string; target: string; value: number }[]
}

export const Route = createFileRoute("/_app/energy-carbon/flows")({
  component: EnergyFlowsPage,
})

function EnergyFlowsPage() {
  const [billingMonth, setBillingMonth] = useState("")
  const [queryMonth, setQueryMonth] = useState("")

  const flowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["energy-carbon", "flows", "energy", queryMonth],
    queryFn: () => {
      const suffix = queryMonth ? `?billing_month=${queryMonth}` : ""
      return fetchCarbonApi<FlowData>(`/api/energy-carbon/flows/energy${suffix}`)
    },
  })
  const balanceQuery = useQuery<ApiEnvelope<BalanceData>>({
    queryKey: ["energy-carbon", "flows", "balance", queryMonth],
    queryFn: () => {
      const suffix = queryMonth ? `?billing_month=${queryMonth}` : ""
      return fetchCarbonApi<BalanceData>(`/api/energy-carbon/flows/energy-balance${suffix}`)
    },
  })
  const topLinksQuery = useQuery<ApiEnvelope<TopLinksData>>({
    queryKey: ["energy-carbon", "flows", "top-links", queryMonth],
    queryFn: () => {
      const suffix = queryMonth ? `?billing_month=${queryMonth}` : ""
      return fetchCarbonApi<TopLinksData>(`/api/energy-carbon/flows/energy-top-links${suffix}`)
    },
  })

  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能碳中心" title="能流分析" description="这一页的主角只有一个：可读的能流图。平衡表、异常说明和关键链路都围绕它展开。" />

      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[220px_1fr_auto]">
          <Input type="month" value={billingMonth} onChange={(event) => setBillingMonth(event.target.value)} />
          <JumpLinks
            items={[
              { label: "回到综能监测", to: "/energy-carbon/energy" },
              { label: "查看范围2核算", to: "/carbon-mgmt/scope2" },
            ]}
          />
          <div className="flex justify-end">
            <Button onClick={() => setQueryMonth(billingMonth)}>查询</Button>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <FlowGraph
          title={flowQuery.data?.data.title ?? "仓库 / 园区能流图"}
          description="主链路固定为外部购电 -> 区域 -> 电表 -> 核算结果。图下方再解释平衡、损耗和回退来源。"
          unit={flowQuery.data?.data.unit}
          nodes={flowQuery.data?.data.nodes ?? []}
          links={flowQuery.data?.data.links ?? []}
          height={640}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,0.88fr)_minmax(0,0.92fr)]">
        <DiagnosticsPanel title="能量平衡表" items={(balanceQuery.data?.data.table ?? []).map((item) => ({ label: item.label, value: `${item.value} ${item.unit}` }))} />
        <DiagnosticsPanel
          title="异常与回退说明"
          items={[...(balanceQuery.data?.data.diagnostics ?? []), { label: "当前账期", value: balanceQuery.data?.data.billing_month || "自动取最近账期" }]}
        />
        <RankingList
          title="关键链路贡献"
          description="优先看能量值最高的链路，快速定位主耗能节点。"
          items={(topLinksQuery.data?.data.items ?? []).map((item) => ({
            name: `${item.source} -> ${item.target}`,
            value: item.value,
          }))}
          unit="kWh"
          height={300}
        />
      </PageSection>
    </PageContainer>
  )
}
