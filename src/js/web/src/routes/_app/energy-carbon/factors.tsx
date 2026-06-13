import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { useState } from "react"
import { AdminPageHeader } from "@/components/admin-ui"
import { type ApiEnvelope, DistributionChart, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import { JumpLinks } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type FactorStats = {
  emission_total: number
  active_total: number
  library_total: number
  raw_total: number
}

type FactorUsage = {
  scope_distribution: { name: string; value: number }[]
  missing_by_scope: { name: string; value: number }[]
  factor_source_distribution: { name: string; value: number }[]
}

type FactorRow = {
  id: number
  scope?: string | null
  category?: string | null
  sub_category?: string | null
  year?: string | null
  unit?: string | null
  factor_value?: number | null
  factor_unit?: string | null
  source?: string | null
  is_active?: boolean | null
}

type FactorPage = {
  items: FactorRow[]
  total: number
}

export const Route = createFileRoute("/_app/energy-carbon/factors")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon-mgmt/factors" })
  },
  component: EnergyCarbonFactorsPage,
})

function EnergyCarbonFactorsPage() {
  const [scope, setScope] = useState("all")

  const statsQuery = useQuery<ApiEnvelope<FactorStats>>({
    queryKey: ["energy-carbon", "factors", "stats"],
    queryFn: () => fetchCarbonApi<FactorStats>("/api/energy-carbon/factors/stats"),
  })
  const usageQuery = useQuery<ApiEnvelope<FactorUsage>>({
    queryKey: ["energy-carbon", "factors", "usage"],
    queryFn: () => fetchCarbonApi<FactorUsage>("/api/energy-carbon/factors/usage"),
  })
  const factorsQuery = useQuery<ApiEnvelope<FactorPage>>({
    queryKey: ["energy-carbon", "factors", scope],
    queryFn: () => {
      const suffix = scope === "all" ? "" : `?scope_filter=${scope}`
      return fetchCarbonApi<FactorPage>(`/api/energy-carbon/factors${suffix}`)
    },
  })

  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader
        title="因子库管理"
        actions={
          <JumpLinks
            items={[
              { label: "排放因子库", to: "/carbon-mgmt/factors" },
              { label: "计算因子库", to: "/carbon-mgmt/calculation-factors" },
            ]}
          />
        }
      />

      <PageSection className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "排放因子", value: statsQuery.data?.data.emission_total ?? 0 },
          { label: "启用因子", value: statsQuery.data?.data.active_total ?? 0 },
          { label: "官方库批次", value: statsQuery.data?.data.library_total ?? 0 },
          { label: "原始记录", value: statsQuery.data?.data.raw_total ?? 0 },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border border-border/60 bg-card px-4 py-4 shadow-sm">
            <div className="text-xs text-muted-foreground">{item.label}</div>
            <div className="mt-2 text-2xl font-semibold">{item.value}</div>
          </div>
        ))}
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)_340px]">
        <DistributionChart title="范围分布" description="当前平台实际命中的因子主要分布在哪些范围。" items={usageQuery.data?.data.scope_distribution ?? []} />
        <RankingList
          title="因子来源分布"
          description="优先确认当前命中的因子主要来自哪些口径。"
          items={usageQuery.data?.data.factor_source_distribution ?? []}
          unit="次"
          height={300}
        />
        <DistributionChart title="缺失因子分布" description="用来识别最需要补强的范围。" items={usageQuery.data?.data.missing_by_scope ?? []} />
      </PageSection>

      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[220px_1fr_auto]">
          <Select value={scope} onValueChange={setScope}>
            <SelectTrigger>
              <SelectValue placeholder="范围筛选" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部范围</SelectItem>
              <SelectItem value="scope1">范围1</SelectItem>
              <SelectItem value="scope2">范围2</SelectItem>
              <SelectItem value="scope3">范围3</SelectItem>
            </SelectContent>
          </Select>
          <div className="text-sm text-muted-foreground">主视图优先看平台实际核算用到的排放因子；更细的官方原始库检索仍然在专业因子页里继续使用。</div>
          <div className="flex justify-end">
            <Button variant="outline" asChild>
              <Link to="/carbon-mgmt/factors">进入详细检索</Link>
            </Button>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <div className="rounded-lg border border-border/60 bg-card shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>因子项</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>类别</TableHead>
                <TableHead>年份</TableHead>
                <TableHead className="text-right">因子值</TableHead>
                <TableHead>单位</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(factorsQuery.data?.data.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                    暂无因子数据
                  </TableCell>
                </TableRow>
              )}
              {(factorsQuery.data?.data.items ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.sub_category || "-"}</TableCell>
                  <TableCell>{item.id}</TableCell>
                  <TableCell>{item.scope || "-"}</TableCell>
                  <TableCell>{item.category || "-"}</TableCell>
                  <TableCell>{item.year || "-"}</TableCell>
                  <TableCell className="text-right">{item.factor_value ?? "-"}</TableCell>
                  <TableCell>{item.unit || item.factor_unit || "-"}</TableCell>
                  <TableCell>{item.source || "-"}</TableCell>
                  <TableCell>{item.is_active ? "启用" : "停用"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </PageSection>
    </PageContainer>
  )
}
