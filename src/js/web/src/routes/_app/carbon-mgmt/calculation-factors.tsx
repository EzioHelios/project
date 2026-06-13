/**
 * 计算因子库
 * API: /api/carbon/emission-factors
 */
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { getActivityUnitLabel, getCategoryLabel, getImportMethodLabel, getScopeLabel, getSourceSystemLabel, getSubCategoryLabel } from "@/lib/carbon-factor-labels"

type EmissionFactor = {
  id: number
  scope: string
  category: string
  sub_category: string
  unit: string
  factor_value: string | number
  factor_unit: string
  year: number
  source: string
  source_system?: string | null
  source_snapshot_id?: string | null
  projection_status?: string | null
  review_status?: string | null
  is_active: boolean
}

export const Route = createFileRoute("/_app/carbon-mgmt/calculation-factors")({
  component: CalculationFactorsPage,
})

function formatNumber(value: number | undefined) {
  return Number(value ?? 0).toLocaleString("zh-CN")
}

function statusBadge(factor: EmissionFactor) {
  if (!factor.is_active) return <Badge variant="outline">停用</Badge>
  if (factor.review_status === "pending") return <Badge variant="secondary">待审核</Badge>
  if (factor.review_status === "rejected") return <Badge variant="destructive">已驳回</Badge>
  return <Badge>启用</Badge>
}

function CodeCell({ label, code }: { label: string; code?: string | null }) {
  return (
    <div className="min-w-0">
      <div className="truncate font-medium">{label}</div>
      {code && code !== label && <div className="truncate text-muted-foreground text-[11px]">{code}</div>}
    </div>
  )
}

function CalculationFactorsPage() {
  const [keyword, setKeyword] = useState("")
  const [scope, setScope] = useState("all")
  const [active, setActive] = useState("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const factorsQuery = useQuery({
    queryKey: ["carbon-mgmt", "calculation-factors", keyword, scope, active, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<EmissionFactor>("/api/carbon/emission-factors", {
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        scope: scope === "all" ? undefined : scope,
        is_active: active === "all" ? undefined : active === "active",
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const factors = factorsQuery.data?.items ?? []
  const activeCount = factors.filter((factor) => factor.is_active).length
  const sourceCount = new Set(factors.map((factor) => factor.source_system || factor.source).filter(Boolean)).size

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="计算因子库" />

      <PageSection>
        <MetricStrip className="md:grid-cols-3 xl:grid-cols-3">
          <MetricTile label="计算因子" value={formatNumber(factorsQuery.data?.total)} meta="可用于活动量与因子核算" />
          <MetricTile label="本页启用" value={formatNumber(activeCount)} meta="当前页参与核算" tone="success" />
          <MetricTile label="本页来源" value={formatNumber(sourceCount)} meta="当前页官方库/人工维护" />
        </MetricStrip>
      </PageSection>

      <PageSection>
        <AdminPanel title="因子列表" actions={<div className="text-muted-foreground text-sm">共 {formatNumber(factorsQuery.data?.total)} 条</div>} contentClassName="space-y-3">
          <AdminTableToolbar
            search={
              <Input
                value={keyword}
                onChange={(event) => {
                  setKeyword(event.target.value)
                  setPageIndex(0)
                }}
                placeholder="搜索：范围/类别/子类/单位/来源"
              />
            }
            filters={
              <>
                <Select
                  value={scope}
                  onValueChange={(value) => {
                    setScope(value)
                    setPageIndex(0)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="范围" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部范围</SelectItem>
                    <SelectItem value="scope1">范围1</SelectItem>
                    <SelectItem value="scope2">范围2</SelectItem>
                    <SelectItem value="scope3">范围3</SelectItem>
                    <SelectItem value="Scope1">范围1</SelectItem>
                    <SelectItem value="Scope2">范围2</SelectItem>
                    <SelectItem value="Scope3">范围3</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={active}
                  onValueChange={(value) => {
                    setActive(value)
                    setPageIndex(0)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="状态" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="active">启用</SelectItem>
                    <SelectItem value="inactive">停用</SelectItem>
                  </SelectContent>
                </Select>
              </>
            }
          />
          {factorsQuery.isLoading && <div className="text-muted-foreground text-sm">正在加载...</div>}
          {factorsQuery.isError && <div className="text-destructive text-sm">加载失败，请检查后端接口。</div>}
          {!factorsQuery.isLoading && !factorsQuery.isError && (
            <AdminDataTable>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>范围</TableHead>
                    <TableHead>类别</TableHead>
                    <TableHead>子类</TableHead>
                    <TableHead>活动单位</TableHead>
                    <TableHead className="text-right">因子值</TableHead>
                    <TableHead>因子单位</TableHead>
                    <TableHead>年份</TableHead>
                    <TableHead>来源</TableHead>
                    <TableHead>导入方式</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {factors.length === 0 && <AdminTableStateRow colSpan={10}>暂无数据</AdminTableStateRow>}
                  {factors.map((factor) => (
                    <TableRow key={factor.id}>
                      <TableCell>
                        <CodeCell label={getScopeLabel(factor.scope)} code={factor.scope} />
                      </TableCell>
                      <TableCell>
                        <CodeCell label={getCategoryLabel(factor.category)} code={factor.category} />
                      </TableCell>
                      <TableCell>
                        <CodeCell label={getSubCategoryLabel(factor.sub_category)} code={factor.sub_category} />
                      </TableCell>
                      <TableCell>
                        <CodeCell label={getActivityUnitLabel(factor.unit)} code={factor.unit} />
                      </TableCell>
                      <TableCell className="text-right">{String(factor.factor_value)}</TableCell>
                      <TableCell>{factor.factor_unit}</TableCell>
                      <TableCell>{factor.year}</TableCell>
                      <TableCell className="max-w-[240px] truncate">
                        <CodeCell
                          label={factor.source || getSourceSystemLabel(factor.source_system)}
                          code={factor.source_system && factor.source_system !== factor.source ? factor.source_system : undefined}
                        />
                      </TableCell>
                      <TableCell>
                        {factor.projection_status ? <Badge variant="secondary">{getImportMethodLabel(factor.projection_status)}</Badge> : <Badge variant="outline">未标记</Badge>}
                      </TableCell>
                      <TableCell>{statusBadge(factor)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminDataTable>
          )}
          <PaginationBar
            page={factorsQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
            pageIndex={pageIndex}
            pageSize={pageSize}
            onPageChange={setPageIndex}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPageIndex(0)
            }}
          />
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
