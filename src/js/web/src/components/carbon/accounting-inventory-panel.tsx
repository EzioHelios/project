import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Archive, Calculator, CheckCircle2, FileSpreadsheet } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type PageResult<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

type BoundaryVersion = {
  id: number
  boundary_no: string
  boundary_name: string
  reporting_org_id: number
  period_id: number
  status?: string | null
}

type AccountingBatch = {
  id: number
  batch_no: string
  batch_name: string
  reporting_org_id: number
  period_id: number
  boundary_id: number
  organization_name?: string | null
  period_name?: string | null
  period_start?: string | null
  period_end?: string | null
  boundary_no?: string | null
  boundary_name?: string | null
  status: string
  inventory_status: string
  total_co2e?: number | null
  record_count: number
  included_record_count: number
  missing_result_count: number
  rebuilt_at?: string | null
  locked_at?: string | null
}

type InventorySummary = {
  batch: AccountingBatch
  totals: {
    total_kg_co2e: number
    total_t_co2e: number
    record_count: number
    included_record_count: number
    missing_result_count: number
  }
  scope_summary: {
    scope: string
    record_count: number
    included_record_count: number
    kg_co2e: number
    t_co2e: number
  }[]
  quality_summary: Record<string, number>
}

type InventoryItem = {
  id: number
  batch_id: number
  record_type: string
  record_id: number
  scope: string
  record_label: string
  display_name?: string | null
  period?: string | null
  source_kind?: string | null
  activity_amount?: number | null
  activity_unit?: string | null
  computed_co2e?: number | null
  factor_source?: string | null
  quality_status: string
  included: boolean
  exclusion_reason?: string | null
}

const QUERY_KEY = ["carbon-accounting-inventory"]

export function CarbonAccountingResultsPanel() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [boundaryId, setBoundaryId] = useState("")
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null)

  const boundariesQuery = useQuery<ApiEnvelope<PageResult<BoundaryVersion>>>({
    queryKey: [...QUERY_KEY, "boundaries"],
    queryFn: () => fetchCarbonApi<PageResult<BoundaryVersion>>("/api/carbon/organization-boundary/boundaries?status=published&limit=100"),
  })
  const batchesQuery = useQuery<ApiEnvelope<PageResult<AccountingBatch>>>({
    queryKey: [...QUERY_KEY, "batches"],
    queryFn: () => fetchCarbonApi<PageResult<AccountingBatch>>("/api/carbon/accounting/batches?limit=50"),
  })

  const batches = batchesQuery.data?.data.items ?? []
  const boundaries = boundariesQuery.data?.data.items ?? []
  const activeBatchId = selectedBatchId ?? batches[0]?.id ?? null

  const summaryQuery = useQuery<ApiEnvelope<InventorySummary>>({
    queryKey: [...QUERY_KEY, "summary", activeBatchId],
    queryFn: () => fetchCarbonApi<InventorySummary>(`/api/carbon/accounting/batches/${activeBatchId}/summary`),
    enabled: Boolean(activeBatchId),
  })
  const itemsQuery = useQuery<ApiEnvelope<PageResult<InventoryItem>>>({
    queryKey: [...QUERY_KEY, "items", activeBatchId],
    queryFn: () => fetchCarbonApi<PageResult<InventoryItem>>(`/api/carbon/accounting/inventories?batch_id=${activeBatchId}&limit=200`),
    enabled: Boolean(activeBatchId),
  })

  const activeBatch = useMemo(
    () => batches.find((item) => item.id === activeBatchId) ?? summaryQuery.data?.data.batch ?? null,
    [activeBatchId, batches, summaryQuery.data?.data.batch],
  )
  const summary = summaryQuery.data?.data
  const items = itemsQuery.data?.data.items ?? []

  const createBatch = useMutation({
    mutationFn: () => postCarbonApi<AccountingBatch>("/api/carbon/accounting/batches", { boundary_id: Number.parseInt(boundaryId, 10) }),
    onSuccess: async (response) => {
      toast.success("核算批次已创建")
      setCreateOpen(false)
      setBoundaryId("")
      setSelectedBatchId(response.data.id)
      await invalidateInventory(qc)
    },
    onError: toastError("创建核算批次失败"),
  })

  const rebuildBatch = useMutation({
    mutationFn: (batchId: number) => postCarbonApi<InventorySummary>(`/api/carbon/accounting/batches/${batchId}/rebuild-inventory`, {}),
    onSuccess: async () => {
      toast.success("组织排放清单已重建")
      await invalidateInventory(qc)
    },
    onError: toastError("重建清单失败"),
  })

  const lockBatch = useMutation({
    mutationFn: (batchId: number) => requestCarbonApi<AccountingBatch>(`/api/carbon/accounting/batches/${batchId}/lock`, { method: "PATCH" }),
    onSuccess: async () => {
      toast.success("核算批次已锁定")
      await invalidateInventory(qc)
    },
    onError: toastError("锁定批次失败"),
  })

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "清单总量(tCO2e)", value: formatNumber(summary?.totals.total_t_co2e ?? (activeBatch?.total_co2e ?? 0) / 1000), icon: Calculator },
          { label: "纳入记录", value: String(summary?.totals.included_record_count ?? activeBatch?.included_record_count ?? 0), icon: FileSpreadsheet },
          { label: "缺失结果", value: String(summary?.totals.missing_result_count ?? activeBatch?.missing_result_count ?? 0), icon: Archive },
          { label: "批次状态", value: statusLabel(activeBatch?.status), icon: CheckCircle2 },
        ]}
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>核算批次</CardTitle>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm">创建批次</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>创建核算批次</DialogTitle>
              </DialogHeader>
              <div className="grid gap-2">
                <Label>组织边界</Label>
                <Select value={boundaryId} onValueChange={setBoundaryId}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择已发布边界" />
                  </SelectTrigger>
                  <SelectContent>
                    {boundaries.map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.boundary_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateOpen(false)}>
                  取消
                </Button>
                <Button disabled={!boundaryId || createBatch.isPending} onClick={() => createBatch.mutate()}>
                  保存
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>批次编号</TableHead>
                <TableHead>组织边界</TableHead>
                <TableHead>报告期</TableHead>
                <TableHead>总量(tCO2e)</TableHead>
                <TableHead>记录</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batches.map((item) => (
                <TableRow key={item.id} data-state={item.id === activeBatchId ? "selected" : undefined}>
                  <TableCell>{item.batch_no}</TableCell>
                  <TableCell>{item.boundary_name || item.boundary_no || "-"}</TableCell>
                  <TableCell>{item.period_name || dateRange(item.period_start, item.period_end)}</TableCell>
                  <TableCell>{formatNumber((item.total_co2e ?? 0) / 1000)}</TableCell>
                  <TableCell>
                    {item.included_record_count}/{item.record_count}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <CarbonStatusBadge status={item.status} />
                      <InventoryStatusBadge status={item.inventory_status} />
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => setSelectedBatchId(item.id)}>
                        查看
                      </Button>
                      <Button size="sm" variant="outline" disabled={item.status === "locked" || rebuildBatch.isPending} onClick={() => rebuildBatch.mutate(item.id)}>
                        重建
                      </Button>
                      <Button size="sm" disabled={item.status === "locked" || item.inventory_status === "empty" || lockBatch.isPending} onClick={() => lockBatch.mutate(item.id)}>
                        锁定
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!batches.length ? <EmptyRow colSpan={7} label="暂无核算批次" /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle>范围汇总</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>范围</TableHead>
                  <TableHead>记录</TableHead>
                  <TableHead className="text-right">tCO2e</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(summary?.scope_summary ?? []).map((item) => (
                  <TableRow key={item.scope}>
                    <TableCell>{item.scope}</TableCell>
                    <TableCell>
                      {item.included_record_count}/{item.record_count}
                    </TableCell>
                    <TableCell className="text-right">{formatNumber(item.t_co2e)}</TableCell>
                  </TableRow>
                ))}
                {!summary?.scope_summary?.length ? <EmptyRow colSpan={3} label="暂无范围汇总" /> : null}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>质量状态</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.entries(summary?.quality_summary ?? {}).map(([status, count]) => (
              <Badge key={status} variant={status === "ready" ? "default" : "secondary"}>
                {qualityLabel(status)} {count}
              </Badge>
            ))}
            {!Object.keys(summary?.quality_summary ?? {}).length ? <span className="text-muted-foreground text-sm">暂无质量状态</span> : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>排放清单</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>范围</TableHead>
                <TableHead>记录类型</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>期间</TableHead>
                <TableHead>活动量</TableHead>
                <TableHead>CO2e(kg)</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>因子来源</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.record_label}</TableCell>
                  <TableCell>{item.display_name || "-"}</TableCell>
                  <TableCell>{item.period || "-"}</TableCell>
                  <TableCell>
                    {formatNumber(item.activity_amount)} {item.activity_unit || ""}
                  </TableCell>
                  <TableCell>{formatNumber(item.computed_co2e)}</TableCell>
                  <TableCell>
                    <InventoryStatusBadge status={item.quality_status} />
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate">{item.factor_source || item.exclusion_reason || "-"}</TableCell>
                </TableRow>
              ))}
              {!items.length ? <EmptyRow colSpan={8} label="暂无排放清单" /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string; icon: typeof Calculator }[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <Card key={item.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="h-4 w-4" />
              </span>
              <span>
                <span className="block text-muted-foreground text-xs">{item.label}</span>
                <span className="block font-semibold text-xl">{item.value}</span>
              </span>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function InventoryStatusBadge({ status }: { status?: string | null }) {
  if (status === "ready" || status === "locked") return <Badge>{qualityLabel(status)}</Badge>
  if (status === "issues" || status === "missing_result" || status === "calculation_issue") return <Badge variant="destructive">{qualityLabel(status)}</Badge>
  if (status === "excluded") return <Badge variant="secondary">{qualityLabel(status)}</Badge>
  return <Badge variant="outline">{qualityLabel(status)}</Badge>
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="h-20 text-center text-muted-foreground">
        {label}
      </TableCell>
    </TableRow>
  )
}

async function postCarbonApi<T>(url: string, payload: Record<string, unknown>) {
  return requestCarbonApi<T>(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  })
}

async function requestCarbonApi<T>(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}

async function invalidateInventory(qc: ReturnType<typeof useQueryClient>) {
  await qc.invalidateQueries({ queryKey: QUERY_KEY })
}

function toastError(title: string) {
  return (error: unknown) => toast.error(title, { description: error instanceof Error ? error.message : "请稍后重试" })
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 3 })
}

function statusLabel(value?: string | null) {
  if (value === "draft") return "草稿"
  if (value === "rebuilt") return "已重建"
  if (value === "locked") return "已锁定"
  if (value === "archived") return "已归档"
  return value || "-"
}

function qualityLabel(value?: string | null) {
  if (value === "empty") return "未生成"
  if (value === "ready") return "就绪"
  if (value === "issues") return "有问题"
  if (value === "locked") return "已锁定"
  if (value === "missing_result") return "缺结果"
  if (value === "calculation_issue") return "计算问题"
  if (value === "excluded") return "边界外"
  return value || "-"
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "-"
  return `${start || "-"} 至 ${end || "-"}`
}
