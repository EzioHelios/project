import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Archive, Calculator, CheckCircle2, Download, FileSpreadsheet } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"

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
  parent_batch_id?: number | null
  parent_batch_no?: string | null
  parent_batch_name?: string | null
  revision_no?: number
  revision_reason?: string | null
  is_revision?: boolean
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

type RevisionDiff = {
  status: string
  batch: AccountingBatch
  parent_batch: AccountingBatch
  totals: {
    parent_t_co2e: number
    current_t_co2e: number
    delta_t_co2e: number
    added_count: number
    removed_count: number
    changed_count: number
    change_count: number
  }
  scope_deltas: {
    scope: string
    before_t_co2e: number
    after_t_co2e: number
    delta_t_co2e: number
    before_included_record_count: number
    after_included_record_count: number
  }[]
  changes: {
    change_type: string
    record_type?: string | null
    record_id?: number | null
    scope?: string | null
    record_label?: string | null
    display_name?: string | null
    before_kg_co2e?: number | null
    after_kg_co2e?: number | null
    delta_kg_co2e?: number | null
    before_quality_status?: string | null
    after_quality_status?: string | null
  }[]
}

const QUERY_KEY = ["carbon-accounting-inventory"]

export function CarbonAccountingResultsPanel() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [revisionOpen, setRevisionOpen] = useState(false)
  const [boundaryId, setBoundaryId] = useState("")
  const [revisionBoundaryId, setRevisionBoundaryId] = useState("")
  const [revisionReason, setRevisionReason] = useState("")
  const [revisionBatch, setRevisionBatch] = useState<AccountingBatch | null>(null)
  const [rejectBatch, setRejectBatch] = useState<AccountingBatch | null>(null)
  const [rejectReason, setRejectReason] = useState("")
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
  const revisionBoundaries = useMemo(
    () => (revisionBatch ? boundaries.filter((item) => item.reporting_org_id === revisionBatch.reporting_org_id && item.period_id === revisionBatch.period_id) : []),
    [boundaries, revisionBatch],
  )
  const summary = summaryQuery.data?.data
  const items = itemsQuery.data?.data.items ?? []
  const revisionDiffQuery = useQuery<ApiEnvelope<RevisionDiff>>({
    queryKey: [...QUERY_KEY, "revision-diff", activeBatchId],
    queryFn: () => fetchCarbonApi<RevisionDiff>(`/api/carbon/accounting/batches/${activeBatchId}/revision-diff`),
    enabled: Boolean(activeBatchId && activeBatch?.is_revision),
  })

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

  const createRevision = useMutation({
    mutationFn: (payload: { batchId: number; boundaryId: number; reason: string }) =>
      postCarbonApi<AccountingBatch>(`/api/carbon/accounting/batches/${payload.batchId}/create-revision`, {
        boundary_id: payload.boundaryId,
        revision_reason: payload.reason || "清单修订",
      }),
    onSuccess: async (response) => {
      toast.success("修订批次已创建")
      setRevisionOpen(false)
      setRevisionBatch(null)
      setRevisionBoundaryId("")
      setRevisionReason("")
      setSelectedBatchId(response.data.id)
      await invalidateInventory(qc)
    },
    onError: toastError("创建修订批次失败"),
  })

  const submitRevision = useMutation({
    mutationFn: (batchId: number) => postCarbonApi<AccountingBatch>(`/api/carbon/accounting/batches/${batchId}/submit-revision`, {}),
    onSuccess: async () => {
      toast.success("修订批次已提交审批")
      await invalidateInventory(qc)
    },
    onError: toastError("提交修订审批失败"),
  })

  const approveRevision = useMutation({
    mutationFn: (batchId: number) => postCarbonApi<AccountingBatch>(`/api/carbon/accounting/batches/${batchId}/approve-revision`, {}),
    onSuccess: async () => {
      toast.success("修订批次已通过并锁定")
      await invalidateInventory(qc)
    },
    onError: toastError("通过修订审批失败"),
  })

  const rejectRevision = useMutation({
    mutationFn: (payload: { batchId: number; reason: string }) =>
      postCarbonApi<AccountingBatch>(`/api/carbon/accounting/batches/${payload.batchId}/reject-revision`, { reason: payload.reason }),
    onSuccess: async () => {
      toast.success("修订批次已驳回")
      setRejectBatch(null)
      setRejectReason("")
      await invalidateInventory(qc)
    },
    onError: toastError("驳回修订审批失败"),
  })

  const exportRevisionExplanation = useMutation({
    mutationFn: (batchId: number) => downloadRevisionExplanation(batchId),
    onSuccess: () => toast.success("修订说明已导出"),
    onError: toastError("导出修订说明失败"),
  })

  const openRevision = (batch: AccountingBatch) => {
    setRevisionBatch(batch)
    setRevisionBoundaryId(String(batch.boundary_id))
    setRevisionReason("")
    setRevisionOpen(true)
  }

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
        <Dialog
          open={revisionOpen}
          onOpenChange={(open) => {
            setRevisionOpen(open)
            if (!open) setRevisionBatch(null)
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>创建修订批次</DialogTitle>
            </DialogHeader>
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label>来源批次</Label>
                <div className="rounded-md border px-3 py-2 text-sm">{revisionBatch?.batch_no ?? "-"}</div>
              </div>
              <div className="grid gap-2">
                <Label>组织边界</Label>
                <Select value={revisionBoundaryId} onValueChange={setRevisionBoundaryId}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择已发布边界" />
                  </SelectTrigger>
                  <SelectContent>
                    {revisionBoundaries.map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.boundary_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>修订原因</Label>
                <Textarea value={revisionReason} onChange={(event) => setRevisionReason(event.target.value)} rows={4} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRevisionOpen(false)}>
                取消
              </Button>
              <Button
                disabled={!revisionBatch || !revisionBoundaryId || createRevision.isPending}
                onClick={() =>
                  revisionBatch
                    ? createRevision.mutate({
                        batchId: revisionBatch.id,
                        boundaryId: Number.parseInt(revisionBoundaryId, 10),
                        reason: revisionReason.trim(),
                      })
                    : undefined
                }
              >
                保存
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog
          open={Boolean(rejectBatch)}
          onOpenChange={(open) => {
            if (!open) {
              setRejectBatch(null)
              setRejectReason("")
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>驳回修订审批</DialogTitle>
            </DialogHeader>
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label>修订批次</Label>
                <div className="rounded-md border px-3 py-2 text-sm">{rejectBatch?.batch_no ?? "-"}</div>
              </div>
              <div className="grid gap-2">
                <Label>驳回原因</Label>
                <Textarea value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} rows={4} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRejectBatch(null)}>
                取消
              </Button>
              <Button
                disabled={!rejectBatch || rejectRevision.isPending}
                onClick={() =>
                  rejectBatch
                    ? rejectRevision.mutate({
                        batchId: rejectBatch.id,
                        reason: rejectReason.trim() || "修订审批驳回",
                      })
                    : undefined
                }
              >
                驳回
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>批次编号</TableHead>
                <TableHead>版本</TableHead>
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
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <Badge variant={item.is_revision ? "secondary" : "outline"}>R{item.revision_no ?? 1}</Badge>
                      {item.parent_batch_no ? <span className="text-muted-foreground text-xs">{item.parent_batch_no}</span> : null}
                    </div>
                  </TableCell>
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
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={item.status === "locked" || item.status === "pending_revision" || rebuildBatch.isPending}
                        onClick={() => rebuildBatch.mutate(item.id)}
                      >
                        重建
                      </Button>
                      {item.is_revision ? (
                        <RevisionActions
                          batch={item}
                          submitPending={submitRevision.isPending}
                          approvePending={approveRevision.isPending}
                          rejectPending={rejectRevision.isPending}
                          exportPending={exportRevisionExplanation.isPending}
                          onSubmit={() => submitRevision.mutate(item.id)}
                          onApprove={() => approveRevision.mutate(item.id)}
                          onExport={() => exportRevisionExplanation.mutate(item.id)}
                          onReject={() => {
                            setRejectBatch(item)
                            setRejectReason("")
                          }}
                        />
                      ) : (
                        <>
                          <Button
                            size="sm"
                            disabled={item.status === "locked" || item.inventory_status === "empty" || lockBatch.isPending}
                            onClick={() => lockBatch.mutate(item.id)}
                          >
                            锁定
                          </Button>
                          <Button size="sm" variant="outline" disabled={item.status !== "locked" || createRevision.isPending} onClick={() => openRevision(item)}>
                            修订
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!batches.length ? <EmptyRow colSpan={8} label="暂无核算批次" /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {activeBatch?.is_revision ? <RevisionDiffCard diff={revisionDiffQuery.data?.data} loading={revisionDiffQuery.isLoading} /> : null}

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

function RevisionDiffCard({ diff, loading }: { diff?: RevisionDiff; loading: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>修订差异</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant={diff?.status === "ready" ? "default" : "outline"}>{revisionDiffStatusLabel(diff?.status, loading)}</Badge>
          {diff?.parent_batch?.batch_no ? <Badge variant="secondary">来源 {diff.parent_batch.batch_no}</Badge> : null}
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <DiffMetric label="原清单" value={formatNumber(diff?.totals.parent_t_co2e)} unit="tCO2e" />
          <DiffMetric label="修订后" value={formatNumber(diff?.totals.current_t_co2e)} unit="tCO2e" />
          <DiffMetric label="差异" value={formatSignedNumber(diff?.totals.delta_t_co2e)} unit="tCO2e" />
          <DiffMetric label="变更记录" value={String(diff?.totals.change_count ?? 0)} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>范围</TableHead>
                <TableHead className="text-right">原值</TableHead>
                <TableHead className="text-right">修订后</TableHead>
                <TableHead className="text-right">差异</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(diff?.scope_deltas ?? []).map((item) => (
                <TableRow key={item.scope}>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell className="text-right">{formatNumber(item.before_t_co2e)}</TableCell>
                  <TableCell className="text-right">{formatNumber(item.after_t_co2e)}</TableCell>
                  <TableCell className="text-right">{formatSignedNumber(item.delta_t_co2e)}</TableCell>
                </TableRow>
              ))}
              {!diff?.scope_deltas?.length ? <EmptyRow colSpan={4} label="暂无范围差异" /> : null}
            </TableBody>
          </Table>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>类型</TableHead>
                <TableHead>对象</TableHead>
                <TableHead className="text-right">tCO2e</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(diff?.changes ?? []).slice(0, 8).map((item) => (
                <TableRow key={`${item.record_type}-${item.record_id}-${item.change_type}`}>
                  <TableCell>
                    <Badge variant="outline">{changeTypeLabel(item.change_type)}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-[240px] truncate">{item.display_name || item.record_label || "-"}</div>
                  </TableCell>
                  <TableCell className="text-right">{formatSignedNumber((item.delta_kg_co2e ?? 0) / 1000)}</TableCell>
                </TableRow>
              ))}
              {!diff?.changes?.length ? <EmptyRow colSpan={3} label="暂无记录差异" /> : null}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}

function RevisionActions({
  batch,
  submitPending,
  approvePending,
  rejectPending,
  exportPending,
  onSubmit,
  onApprove,
  onExport,
  onReject,
}: {
  batch: AccountingBatch
  submitPending: boolean
  approvePending: boolean
  rejectPending: boolean
  exportPending: boolean
  onSubmit: () => void
  onApprove: () => void
  onExport: () => void
  onReject: () => void
}) {
  if (batch.status === "pending_revision") {
    return (
      <>
        <Button size="sm" variant="outline" disabled={batch.inventory_status === "empty" || exportPending} onClick={onExport}>
          <Download className="mr-1 h-3.5 w-3.5" />
          说明
        </Button>
        <Button size="sm" disabled={approvePending} onClick={onApprove}>
          通过
        </Button>
        <Button size="sm" variant="outline" disabled={rejectPending} onClick={onReject}>
          驳回
        </Button>
      </>
    )
  }
  if (isRevisionEditable(batch.status)) {
    return (
      <>
        <Button size="sm" variant="outline" disabled={batch.inventory_status === "empty" || exportPending} onClick={onExport}>
          <Download className="mr-1 h-3.5 w-3.5" />
          说明
        </Button>
        <Button size="sm" disabled={batch.inventory_status === "empty" || submitPending} onClick={onSubmit}>
          提交审批
        </Button>
      </>
    )
  }
  if (batch.status === "locked") {
    return (
      <Button size="sm" variant="outline" disabled={exportPending} onClick={onExport}>
        <Download className="mr-1 h-3.5 w-3.5" />
        说明
      </Button>
    )
  }
  return null
}

function DiffMetric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-md border p-3">
      <span className="block text-muted-foreground text-xs">{label}</span>
      <span className="font-semibold text-lg">
        {value} {unit ? <span className="font-normal text-muted-foreground text-xs">{unit}</span> : null}
      </span>
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

async function downloadRevisionExplanation(batchId: number) {
  const response = await fetch(`/api/carbon/accounting/batches/${batchId}/export-revision-explanation`, { method: "POST" })
  if (!response.ok) {
    const text = await response.text()
    let message = `HTTP ${response.status}`
    try {
      const payload = JSON.parse(text) as { msg?: string; detail?: string }
      message = payload.msg || payload.detail || message
    } catch {
      message = text || message
    }
    throw new Error(message)
  }
  const blob = await response.blob()
  const filename = filenameFromDisposition(response.headers.get("content-disposition")) ?? `carbon-inventory-revision-${batchId}.zip`
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function filenameFromDisposition(disposition: string | null) {
  if (!disposition) return null
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) return decodeURIComponent(encoded)
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return plain || null
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

function formatSignedNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  const formatted = formatNumber(Math.abs(value))
  if (value > 0) return `+${formatted}`
  if (value < 0) return `-${formatted}`
  return formatted
}

function statusLabel(value?: string | null) {
  if (value === "draft") return "草稿"
  if (value === "rebuilt") return "已重建"
  if (value === "pending_revision") return "修订待审批"
  if (value === "rejected") return "已驳回"
  if (value === "locked") return "已锁定"
  if (value === "archived") return "已归档"
  return value || "-"
}

function isRevisionEditable(value?: string | null) {
  return value === "draft" || value === "rebuilt" || value === "rejected"
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

function revisionDiffStatusLabel(value?: string | null, loading?: boolean) {
  if (loading) return "加载中"
  if (value === "ready") return "已生成"
  if (value === "empty_revision_inventory") return "待重建"
  if (value === "parent_inventory_empty") return "来源无清单"
  return value || "无数据"
}

function changeTypeLabel(value?: string | null) {
  if (value === "added") return "新增"
  if (value === "removed") return "移除"
  if (value === "changed") return "变更"
  return value || "-"
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "-"
  return `${start || "-"} 至 ${end || "-"}`
}
