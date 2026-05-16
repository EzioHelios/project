import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { CarbonRecordActions } from "@/components/carbon/record-actions"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
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

function sourceLabel(sourceKind?: string) {
  if (sourceKind === "meter_aggregate") return "电表聚合"
  if (sourceKind === "manual_bill") return "账单补录"
  return sourceKind || "-"
}

function calcStatusLabel(calcStatus?: string) {
  if (calcStatus === "ready") return "可核算"
  if (calcStatus === "insufficient_data") return "采样不足"
  if (calcStatus === "invalid_delta") return "读数异常"
  return calcStatus || "-"
}

export function Scope2RecordsPanel({ defaultSourceKind = "meter_aggregate" }: { defaultSourceKind?: "meter_aggregate" | "manual_bill" | "all" }) {
  const [billingMonth, setBillingMonth] = useState("")
  const [sourceKind, setSourceKind] = useState(defaultSourceKind)
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

  const rebuildMut = useMutation({
    mutationFn: async () =>
      fetchJson<{ rebuilt_count: number; ready_count: number; invalid_count: number }>("/api/carbon/scope2-meter-aggregate/rebuild", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ billing_month: billingMonth.trim() }),
      }),
    onSuccess: async (result) => {
      toast.success("月聚合执行完成", {
        description: `已重建 ${result.data.rebuilt_count} 条，${result.data.ready_count} 条可核算`,
      })
      await listQuery.refetch()
    },
    onError: (error) => toast.error("执行月聚合失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const page = listQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }

  return (
    <Card>
      <CardHeader className="space-y-3">
        <CardTitle>核算记录</CardTitle>
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-[180px]">
            <Input value={billingMonth} onChange={(event) => setBillingMonth(event.target.value)} placeholder="账期 YYYY-MM" />
          </div>
          <div className="w-[180px]">
            <Select value={sourceKind} onValueChange={(value) => setSourceKind(value as "meter_aggregate" | "manual_bill" | "all")}>
              <SelectTrigger>
                <SelectValue placeholder="来源类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="meter_aggregate">电表聚合</SelectItem>
                <SelectItem value="manual_bill">账单补录</SelectItem>
                <SelectItem value="all">全部来源</SelectItem>
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
          <Button
            variant="outline"
            onClick={() => {
              setBillingMonth("")
              setSourceKind(defaultSourceKind)
              setStatus("all")
              setPageIndex(0)
            }}
          >
            重置
          </Button>
          <Button onClick={() => rebuildMut.mutate()} disabled={!billingMonth.trim() || rebuildMut.isPending}>
            执行月聚合
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>来源类型</TableHead>
              <TableHead>电表 / 户号</TableHead>
              <TableHead>账期</TableHead>
              <TableHead className="text-right">总电量(kWh)</TableHead>
              <TableHead className="text-right">核算结果</TableHead>
              <TableHead>聚合状态</TableHead>
              <TableHead>审核状态</TableHead>
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
                <TableCell>{sourceLabel(row.source_kind)}</TableCell>
                <TableCell>{row.display_name ?? "-"}</TableCell>
                <TableCell>{row.billing_month}</TableCell>
                <TableCell className="text-right">{row.total_kwh ?? "-"}</TableCell>
                <TableCell className="text-right">{row.computed_co2e === null || row.computed_co2e === undefined ? "-" : `${row.computed_co2e} kgCO2e`}</TableCell>
                <TableCell>{calcStatusLabel(row.calc_status)}</TableCell>
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
  )
}
