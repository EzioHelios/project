import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { CarbonRecordActions } from "@/components/carbon/record-actions"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Scope2RecordRow = {
  record_type: string
  record_id: number
  display_name?: string | null
  billing_month: string
  total_kwh?: number | null
  source_kind?: string
  status?: string
  computed_co2e?: number | null
  calc_status?: string
}

const basePathByType: Record<string, string> = {
  Scope2ElectricityBill: "/api/carbon/scope2-electricity-bill",
  Scope2MeterAggregate: "/api/carbon/scope2-meter-aggregate",
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-records")({
  component: Scope2RecordsPage,
})

function Scope2RecordsPage() {
  const [billingMonth, setBillingMonth] = useState("")
  const [sourceKind, setSourceKind] = useState("all")
  const [status, setStatus] = useState("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const listQuery = useQuery({
    queryKey: ["carbon-mgmt", "scope2-records", billingMonth, sourceKind, status, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<Scope2RecordRow>("/api/carbon/scope2-records", {
        billing_month: billingMonth.trim() || undefined,
        source_kind: sourceKind === "all" ? undefined : sourceKind,
        status: status === "all" ? undefined : status,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const page = listQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="碳核算模型" title="Scope2 核算记录" description="统一查看人工账单与电表月聚合形成的 Scope2 核算记录。" />
      <PageSection>
        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>记录列表</CardTitle>
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-[180px]">
                <Input value={billingMonth} onChange={(event) => setBillingMonth(event.target.value)} placeholder="账期 YYYY-MM" />
              </div>
              <div className="w-[180px]">
                <Select value={sourceKind} onValueChange={setSourceKind}>
                  <SelectTrigger>
                    <SelectValue placeholder="来源类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部来源</SelectItem>
                    <SelectItem value="manual_bill">人工账单</SelectItem>
                    <SelectItem value="meter_aggregate">电表聚合</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-[160px]">
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue placeholder="状态" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="draft">草稿</SelectItem>
                    <SelectItem value="pending">待审核</SelectItem>
                    <SelectItem value="approved">已通过</SelectItem>
                    <SelectItem value="rejected">已驳回</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button variant="secondary" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
                查询
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>记录类型</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>账期</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead className="text-right">总电量(kWh)</TableHead>
                  <TableHead className="text-right">核算结果</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                      暂无记录
                    </TableCell>
                  </TableRow>
                )}
                {page.items.map((row) => (
                  <TableRow key={`${row.record_type}-${row.record_id}`}>
                    <TableCell>{row.record_type}</TableCell>
                    <TableCell>{row.display_name ?? "-"}</TableCell>
                    <TableCell>{row.billing_month}</TableCell>
                    <TableCell>{row.source_kind}</TableCell>
                    <TableCell className="text-right">{row.total_kwh ?? "-"}</TableCell>
                    <TableCell className="text-right">{row.computed_co2e === null || row.computed_co2e === undefined ? "-" : `${row.computed_co2e} kgCO2e`}</TableCell>
                    <TableCell>
                      <CarbonStatusBadge status={row.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <CarbonRecordActions id={row.record_id} status={row.status} basePath={basePathByType[row.record_type]} invalidateKey={["carbon-mgmt", "scope2-records"]} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <PaginationBar
              page={page}
              pageIndex={pageIndex}
              pageSize={pageSize}
              onPageChange={setPageIndex}
              onPageSizeChange={(value) => {
                setPageSize(value)
                setPageIndex(0)
              }}
            />
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
