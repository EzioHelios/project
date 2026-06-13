import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar } from "@/components/admin-ui"
import { CarbonRecordActions } from "@/components/carbon/record-actions"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type PendingRow = {
  record_type: string
  record_id: number
  status?: string
  source_kind?: string
  computed_co2e?: number | null
  factor_source?: string | null
}

const basePathByType: Record<string, string> = {
  Scope1MobileCombustion: "/api/carbon/scope1-mobile-combustion",
  Scope1StationaryCombustion: "/api/carbon/scope1-stationary-combustion",
  Scope1RefrigerantLeak: "/api/carbon/scope1-refrigerant-leak",
  Scope2ElectricityBill: "/api/carbon/scope2-electricity-bill",
  Scope2MeterAggregate: "/api/carbon/scope2-meter-aggregate",
  Scope3WasteDisposal: "/api/carbon/scope3-waste-disposal",
  Scope3ThirdPartyTransport: "/api/carbon/scope3-third-party-transport",
}

export const Route = createFileRoute("/_app/carbon-mgmt/pending")({
  component: PendingWorkbenchPage,
})

function PendingWorkbenchPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="待审核工作台" />
      <PageSection>
        <PendingReviewPanel />
      </PageSection>
    </PageContainer>
  )
}

export function PendingReviewPanel() {
  const [keyword, setKeyword] = useState("")
  const [recordType, setRecordType] = useState("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const listQuery = useQuery({
    queryKey: ["carbon-mgmt", "pending", keyword, recordType, pageIndex, pageSize],
    queryFn: async () => requestPage<PendingRow>("/api/carbon/pending", { limit: pageSize, offset: pageIndex * pageSize }),
  })

  const items = useMemo(() => {
    const source = listQuery.data?.items ?? []
    return source.filter((row) => {
      const matchesType = recordType === "all" ? true : row.record_type === recordType
      const needle = keyword.trim().toLowerCase()
      const matchesKeyword = !needle || JSON.stringify(row).toLowerCase().includes(needle)
      return matchesType && matchesKeyword
    })
  }, [keyword, listQuery.data?.items, recordType])

  const filteredPage = {
    items,
    total: items.length,
    limit: pageSize,
    offset: pageIndex * pageSize,
  }

  return (
    <AdminPanel title="待审核记录" contentClassName="space-y-3">
      <AdminTableToolbar
        search={
          <div className="min-w-[260px] flex-1">
            <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索：记录类型/来源/备注…" />
          </div>
        }
        filters={
          <div className="w-[220px]">
            <Select value={recordType} onValueChange={setRecordType}>
              <SelectTrigger>
                <SelectValue placeholder="记录类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部记录</SelectItem>
                {Object.keys(basePathByType).map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
        actions={
          <Button variant="outline" size="sm" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
            查询
          </Button>
        }
      />
      <AdminDataTable>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>记录类型</TableHead>
              <TableHead>来源</TableHead>
              <TableHead className="text-right">核算结果</TableHead>
              <TableHead>因子来源</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && <AdminTableStateRow colSpan={6}>暂无待审核记录</AdminTableStateRow>}
            {items.map((row) => (
              <TableRow key={`${row.record_type}-${row.record_id}`}>
                <TableCell>{row.record_type}</TableCell>
                <TableCell>{row.source_kind ?? "-"}</TableCell>
                <TableCell className="text-right">{row.computed_co2e === null || row.computed_co2e === undefined ? "-" : `${row.computed_co2e} kgCO2e`}</TableCell>
                <TableCell>{row.factor_source ?? "-"}</TableCell>
                <TableCell>
                  <CarbonStatusBadge status={row.status} />
                </TableCell>
                <TableCell className="text-right">
                  <CarbonRecordActions id={row.record_id} status={row.status} basePath={basePathByType[row.record_type]} invalidateKey={["carbon-mgmt", "pending"]} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminDataTable>

      <PaginationBar
        page={filteredPage}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPageChange={setPageIndex}
        onPageSizeChange={(value) => {
          setPageSize(value)
          setPageIndex(0)
        }}
      />
    </AdminPanel>
  )
}
