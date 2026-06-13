/**
 * 碳业务审核操作日志 - 列表/筛选
 * API: /api/carbon/audit-logs
 */
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar } from "@/components/admin-ui"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type AuditRow = {
  id: number
  record_type: string
  record_id: number
  action: string
  operator_id?: string | null
  comment?: string | null
  created_at: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/audit")({
  component: AuditPage,
})

function AuditPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="审核操作日志" />
      <PageSection>
        <AuditLogPanel />
      </PageSection>
    </PageContainer>
  )
}

export function AuditLogPanel() {
  const [recordType, setRecordType] = useState<string>("all")
  const [action, setAction] = useState<string>("all")
  const [keyword, setKeyword] = useState("")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["carbon-mgmt", "audit", recordType, action, keyword, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<AuditRow>("/api/carbon/audit-logs", {
        record_type: recordType === "all" ? undefined : recordType,
        action: action === "all" ? undefined : action,
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })
  const rows = data?.items ?? []

  return (
    <AdminPanel title="日志列表" contentClassName="space-y-3">
      <AdminTableToolbar
        fields={[
          {
            key: "keyword",
            node: (
              <Input
                value={keyword}
                onChange={(e) => {
                  setKeyword(e.target.value)
                  setPageIndex(0)
                }}
                placeholder="搜索：记录ID/说明…"
              />
            ),
          },
          {
            key: "recordType",
            node: (
              <Select
                value={recordType}
                onValueChange={(value) => {
                  setRecordType(value)
                  setPageIndex(0)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="记录类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="Scope1MobileCombustion">Scope1MobileCombustion</SelectItem>
                  <SelectItem value="Scope1StationaryCombustion">Scope1StationaryCombustion</SelectItem>
                  <SelectItem value="Scope1RefrigerantLeak">Scope1RefrigerantLeak</SelectItem>
                  <SelectItem value="Scope2ElectricityBill">Scope2ElectricityBill</SelectItem>
                  <SelectItem value="Scope3WasteDisposal">Scope3WasteDisposal</SelectItem>
                  <SelectItem value="Scope3ThirdPartyTransport">Scope3ThirdPartyTransport</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "action",
            node: (
              <Select
                value={action}
                onValueChange={(value) => {
                  setAction(value)
                  setPageIndex(0)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="操作" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部操作</SelectItem>
                  <SelectItem value="submit">submit</SelectItem>
                  <SelectItem value="approve">approve</SelectItem>
                  <SelectItem value="reject">reject</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
        ]}
        actions={
          <Button type="button" variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            查询
          </Button>
        }
      />
      {isLoading && <div className="text-sm text-muted-foreground">正在加载…</div>}
      {isError && <div className="text-sm text-destructive">加载失败，请检查后端接口。</div>}
      {!isLoading && !isError && (
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>记录类型</TableHead>
                <TableHead>记录ID</TableHead>
                <TableHead>操作</TableHead>
                <TableHead>说明</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 && <AdminTableStateRow colSpan={5}>暂无数据</AdminTableStateRow>}
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.created_at}</TableCell>
                  <TableCell>{row.record_type}</TableCell>
                  <TableCell>{row.record_id}</TableCell>
                  <TableCell>
                    {row.action === "submit" && <Badge variant="secondary">送审</Badge>}
                    {row.action === "approve" && <Badge>通过</Badge>}
                    {row.action === "reject" && <Badge variant="destructive">驳回</Badge>}
                    {!["submit", "approve", "reject"].includes(row.action) && <Badge variant="outline">{row.action}</Badge>}
                  </TableCell>
                  <TableCell>{row.comment ?? "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      )}
      <PaginationBar
        page={data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPageChange={setPageIndex}
        onPageSizeChange={(size) => {
          setPageSize(size)
          setPageIndex(0)
        }}
      />
    </AdminPanel>
  )
}
