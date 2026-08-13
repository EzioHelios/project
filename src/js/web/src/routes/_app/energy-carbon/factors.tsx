import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { useState } from "react"
import { AdminDataTable, AdminFilterBar, AdminPageHeader, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
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

      <PageSection>
        <MetricStrip>
          <MetricTile label="排放因子" value={statsQuery.data?.data.emission_total ?? 0} />
          <MetricTile label="启用因子" value={statsQuery.data?.data.active_total ?? 0} tone="success" />
          <MetricTile label="官方库批次" value={statsQuery.data?.data.library_total ?? 0} />
          <MetricTile label="原始记录" value={statsQuery.data?.data.raw_total ?? 0} />
        </MetricStrip>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)_340px]">
        <DistributionChart title="范围分布" items={usageQuery.data?.data.scope_distribution ?? []} />
        <RankingList title="因子来源分布" items={usageQuery.data?.data.factor_source_distribution ?? []} unit="次" height={300} />
        <DistributionChart title="缺失因子分布" items={usageQuery.data?.data.missing_by_scope ?? []} />
      </PageSection>

      <PageSection>
        <AdminFilterBar
          fields={[
            {
              key: "scope",
              node: (
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
              ),
            },
          ]}
          actions={
            <Button variant="outline" asChild>
              <Link to="/carbon-mgmt/factors">进入详细检索</Link>
            </Button>
          }
        />
      </PageSection>

      <PageSection>
        <AdminDataTable>
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
              {(factorsQuery.data?.data.items ?? []).length === 0 && <AdminTableStateRow colSpan={9}>暂无因子数据</AdminTableStateRow>}
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
        </AdminDataTable>
      </PageSection>
    </PageContainer>
  )
}
