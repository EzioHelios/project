import { Link, useNavigate } from "@tanstack/react-router"
import { CheckCircle2, Download, Eye, FileText, Pencil, Plus, RefreshCw, Send, Trash2, Undo2 } from "lucide-react"
import { useEffect, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { CarbonFormField } from "@/components/carbon/ghg-maintenance"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import {
  type GhgCalculationRunList,
  type GhgInventoryReport,
  useGhgCalculationRuns,
  useGhgInventoryReport,
  useGhgInventoryReportActions,
  useGhgInventoryReports,
} from "@/lib/api/hooks/ghg-inventory"

type CalculationRun = GhgCalculationRunList["items"][number]

const reportStatusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "已提交",
  approved: "已通过",
  rejected: "已退回",
  published: "已发布",
  archived: "已归档",
}

const reportStatusTone: Record<string, Parameters<typeof StatusBadge>[0]["status"]> = {
  draft: "draft",
  submitted: "pending",
  approved: "approved",
  rejected: "rejected",
  published: "locked",
  archived: "archived",
}

export function InventoryReportLedgerPage() {
  const navigate = useNavigate()
  const reportsQuery = useGhgInventoryReports()
  const runsQuery = useGhgCalculationRuns({ status: "completed" })
  const [keyword, setKeyword] = useState("")
  const [status, setStatus] = useState("all")
  const [selected, setSelected] = useState<GhgInventoryReport | null>(null)
  const [editing, setEditing] = useState<GhgInventoryReport | null>(null)
  const [creating, setCreating] = useState(false)
  const reports = reportsQuery.data?.items ?? []
  const filtered = reports.filter((item) => {
    const matchesKeyword = !keyword.trim() || `${item.reportCode} ${item.title} ${item.runCode}`.toLowerCase().includes(keyword.trim().toLowerCase())
    const matchesStatus = status === "all" || item.status === status
    return matchesKeyword && matchesStatus
  })
  const publishedCount = reports.filter((item) => item.status === "published").length
  const draftCount = reports.filter((item) => item.status === "draft" || item.status === "rejected").length

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title="核算报告"
        topActions={
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus />
            生成报告
          </Button>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "search",
                node: (
                  <CarbonFormField label="搜索">
                    <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="报告名称、编号或核算运行" />
                  </CarbonFormField>
                ),
              },
              {
                key: "status",
                node: (
                  <CarbonFormField label="状态">
                    <Select value={status} onValueChange={setStatus}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部状态</SelectItem>
                        <SelectItem value="draft">草稿</SelectItem>
                        <SelectItem value="submitted">已提交</SelectItem>
                        <SelectItem value="approved">已通过</SelectItem>
                        <SelectItem value="published">已发布</SelectItem>
                        <SelectItem value="archived">已归档</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
            ]}
            actions={
              <Button variant="outline" size="sm" onClick={() => void Promise.all([reportsQuery.refetch(), runsQuery.refetch()])}>
                <RefreshCw className="h-4 w-4" />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip>
            <MetricTile label="报告总数" value={reports.length} unit="份" />
            <MetricTile label="草稿/退回" value={draftCount} unit="份" tone={draftCount ? "warning" : "default"} />
            <MetricTile label="已发布" value={publishedCount} unit="份" tone="success" />
            <MetricTile label="已完成核算" value={runsQuery.data?.items.length ?? 0} unit="次" />
          </MetricStrip>
        }
      >
        <AdminPanel title="历史核算报告" contentClassName="p-0">
          <AdminDataTable className="rounded-none border-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>报告名称</TableHead>
                  <TableHead>报告编号</TableHead>
                  <TableHead>核算运行</TableHead>
                  <TableHead>版本</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">排放量(tCO₂e)</TableHead>
                  <TableHead className="w-[340px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((item) => (
                  <TableRow key={`${item.reportCode}-${item.version}`}>
                    <TableCell>
                      <div className="font-medium">{item.title}</div>
                      <div className="text-muted-foreground text-xs">{item.changeSummary || "本版本未填写变更说明"}</div>
                    </TableCell>
                    <TableCell>{item.reportCode}</TableCell>
                    <TableCell>
                      <Link
                        className="text-primary underline-offset-4 hover:underline"
                        to="/carbon/organization/records"
                        search={{ run: item.runCode, scope2: "location", grain: "month", page: 1, pageSize: 25, sortBy: "period_start", sortOrder: "desc" }}
                      >
                        {item.runCode}
                      </Link>
                    </TableCell>
                    <TableCell>v{item.version}</TableCell>
                    <TableCell>
                      <ReportStatusBadge status={item.status} />
                    </TableCell>
                    <TableCell className="text-right">{formatSnapshotTonnes(item.metricsSnapshot)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        <Button variant="ghost" size="sm" onClick={() => setSelected(item)}>
                          <Eye className="h-4 w-4" />
                          查看
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditing(item)} disabled={!isEditable(item)}>
                          <Pencil className="h-4 w-4" />
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            void navigate({ to: "/carbon/organization/reports/$reportCode/$version", params: { reportCode: item.reportCode, version: String(item.version) } })
                          }
                        >
                          <FileText className="h-4 w-4" />
                          详情
                        </Button>
                        <ReportExportButtons report={item} />
                        <ReportActionButtons report={item} />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {reportsQuery.isPending ? <AdminTableStateRow colSpan={7}>加载中</AdminTableStateRow> : null}
                {!reportsQuery.isPending && !filtered.length ? <AdminTableStateRow colSpan={7}>暂无核算报告</AdminTableStateRow> : null}
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>
      </AdminPageScaffold>
      <CreateReportDialog open={creating} onOpenChange={setCreating} runs={runsQuery.data?.items ?? []} />
      <EditReportDialog report={editing} onOpenChange={(open) => !open && setEditing(null)} />
      <ReportDetailSheet report={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </PageContainer>
  )
}

export function InventoryReportDetailPage({ reportCode, version }: { reportCode: string; version: number }) {
  const reportQuery = useGhgInventoryReport(reportCode, version)
  const report = reportQuery.data
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title={report?.title ?? "核算报告详情"}
        status={report ? <ReportStatusBadge status={report.status} /> : undefined}
        meta={
          report ? (
            <span>
              {report.reportCode} · v{report.version}
            </span>
          ) : undefined
        }
        topActions={
          report ? (
            <Link to="/carbon/organization/reports">
              <Button variant="outline" size="sm">
                返回台账
              </Button>
            </Link>
          ) : undefined
        }
      >
        {reportQuery.isPending ? <AdminPanel title="报告详情">加载中</AdminPanel> : null}
        {!reportQuery.isPending && !report ? <AdminPanel title="报告详情">盘查报告不存在</AdminPanel> : null}
        {report ? <ReportDetailContent report={report} /> : null}
      </AdminPageScaffold>
    </PageContainer>
  )
}

export function CreateReportDialog({ open, onOpenChange, runs }: { open: boolean; onOpenChange: (open: boolean) => void; runs: CalculationRun[] }) {
  const actions = useGhgInventoryReportActions()
  const navigate = useNavigate()
  const defaultRun = runs[0]
  const [runCode, setRunCode] = useState("")
  const selectedRun = runs.find((item) => item.runCode === (runCode || defaultRun?.runCode))
  const [title, setTitle] = useState("")
  const [changeSummary, setChangeSummary] = useState("基于已完成核算运行生成组织温室气体盘查报告。")
  const resolvedTitle = title.trim() || defaultReportTitle(selectedRun)
  const canSubmit = Boolean(selectedRun?.runCode && resolvedTitle)
  const submit = () => {
    if (!selectedRun || !canSubmit) return
    actions.create.mutate(
      { runCode: selectedRun.runCode, title: resolvedTitle, changeSummary: changeSummary.trim() || undefined },
      {
        onSuccess: (report) => {
          onOpenChange(false)
          setTitle("")
          void navigate({ to: "/carbon/organization/reports/$reportCode/$version", params: { reportCode: report.reportCode, version: String(report.version) } })
        },
      },
    )
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>生成核算报告</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <CarbonFormField label="核算运行">
            <Select value={selectedRun?.runCode ?? ""} onValueChange={setRunCode}>
              <SelectTrigger>
                <SelectValue placeholder="选择已完成核算运行" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((item) => (
                  <SelectItem key={item.runCode} value={item.runCode}>
                    {item.reportingPeriodName ?? item.inventoryCode} · {item.runCode}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CarbonFormField>
          <CarbonFormField label="报告名称">
            <Input aria-label="报告名称" value={title} onChange={(event) => setTitle(event.target.value)} placeholder={defaultReportTitle(selectedRun)} />
          </CarbonFormField>
          <CarbonFormField label="变更说明">
            <Textarea aria-label="变更说明" value={changeSummary} onChange={(event) => setChangeSummary(event.target.value)} rows={4} />
          </CarbonFormField>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={submit} disabled={!canSubmit || actions.create.isPending}>
            {actions.create.isPending ? "生成中" : "生成并查看"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function EditReportDialog({ report, onOpenChange }: { report: GhgInventoryReport | null; onOpenChange: (open: boolean) => void }) {
  const actions = useGhgInventoryReportActions()
  const [title, setTitle] = useState("")
  const [changeSummary, setChangeSummary] = useState("")
  useEffect(() => {
    if (!report) return
    setTitle(report.title)
    setChangeSummary(report.changeSummary ?? "")
  }, [report])
  const submit = () => {
    if (!report || !title.trim()) return
    actions.update.mutate(
      { reportCode: report.reportCode, version: report.version, body: { title: title.trim(), changeSummary: changeSummary.trim() || null } },
      { onSuccess: () => onOpenChange(false) },
    )
  }
  return (
    <Dialog open={Boolean(report)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>编辑核算报告</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <CarbonFormField label="报告名称">
            <Input aria-label="报告名称" value={title} onChange={(event) => setTitle(event.target.value)} />
          </CarbonFormField>
          <CarbonFormField label="变更说明">
            <Textarea aria-label="变更说明" value={changeSummary} onChange={(event) => setChangeSummary(event.target.value)} rows={4} />
          </CarbonFormField>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={submit} disabled={!title.trim() || actions.update.isPending}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ReportDetailSheet({ report, onOpenChange }: { report: GhgInventoryReport | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={Boolean(report)} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>{report?.title ?? "核算报告详情"}</SheetTitle>
        </SheetHeader>
        {report ? <ReportDetailContent report={report} /> : null}
      </SheetContent>
    </Sheet>
  )
}

function ReportDetailContent({ report }: { report: GhgInventoryReport }) {
  const metrics = report.metricsSnapshot
  const evidence = report.evidenceSnapshot
  return (
    <div className="space-y-4 py-4">
      <div className="flex justify-end gap-2">
        <ReportExportButtons report={report} />
      </div>
      <MetricStrip>
        <MetricTile label="报告版本" value={`v${report.version}`} />
        <MetricTile label="核算总量" value={formatSnapshotTonnes(metrics)} unit="tCO₂e" />
        <MetricTile label="活动数据" value={snapshotText(evidence, ["activityCount"])} unit="条" />
        <MetricTile label="证据覆盖率" value={snapshotText(evidence, ["coveragePct"])} unit="%" />
      </MetricStrip>
      <AdminPanel title="报告信息" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableBody>
              {[
                ["报告编号", report.reportCode],
                ["版本", `v${report.version}`],
                ["状态", reportStatusLabels[report.status] ?? report.status],
                ["核算运行", report.runCode],
                ["盘查任务", report.inventoryCode],
                ["报告方案", report.reportingProfileCode],
                ["变更说明", report.changeSummary || "-"],
              ].map(([label, value]) => (
                <TableRow key={label}>
                  <TableCell className="w-40 text-muted-foreground">{label}</TableCell>
                  <TableCell>{value}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="报告快照" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>指标</TableHead>
                <TableHead>数值</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {snapshotRows(metrics, ["defaultTotalCo2eKg", "totalLocationCo2eKg", "totalMarketCo2eKg", "defaultScope2Method"]).map(([key, value]) => (
                <TableRow key={key}>
                  <TableCell>{snapshotLabel(key)}</TableCell>
                  <TableCell>{formatSnapshotRowValue(key, value)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="流转记录" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>动作</TableHead>
                <TableHead>状态变化</TableHead>
                <TableHead>处理人</TableHead>
                <TableHead>时间</TableHead>
                <TableHead>意见</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.reviews.map((item) => (
                <TableRow key={`${item.action}-${item.actedAt}`}>
                  <TableCell>{actionLabel(item.action)}</TableCell>
                  <TableCell>
                    {reportStatusLabels[item.fromStatus] ?? item.fromStatus} → {reportStatusLabels[item.toStatus] ?? item.toStatus}
                  </TableCell>
                  <TableCell>{item.actor}</TableCell>
                  <TableCell>{formatDateTime(item.actedAt)}</TableCell>
                  <TableCell>{item.comment || "-"}</TableCell>
                </TableRow>
              ))}
              {!report.reviews.length ? <AdminTableStateRow colSpan={5}>暂无流转记录</AdminTableStateRow> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

function ReportExportButtons({ report }: { report: GhgInventoryReport }) {
  const actions = useGhgInventoryReportActions()
  const busy = actions.exportReport.isPending
  return (
    <Button variant="ghost" size="sm" disabled={busy} onClick={() => actions.exportReport.mutate({ reportCode: report.reportCode, version: report.version, fileFormat: "docx" })}>
      <Download className="h-4 w-4" />
      导出 Word
    </Button>
  )
}

function ReportActionButtons({ report }: { report: GhgInventoryReport }) {
  const actions = useGhgInventoryReportActions()
  const busy =
    actions.submit.isPending || actions.resubmit.isPending || actions.approve.isPending || actions.reject.isPending || actions.publish.isPending || actions.remove.isPending
  const run = (action: "submit" | "resubmit" | "approve" | "publish") => {
    actions[action].mutate({ reportCode: report.reportCode, version: report.version, comment: undefined })
  }
  const reject = () => {
    const comment = window.prompt("请输入退回意见")
    if (comment?.trim()) actions.reject.mutate({ reportCode: report.reportCode, version: report.version, comment: comment.trim() })
  }
  const remove = () => {
    const confirmed = window.confirm(report.status === "draft" || report.status === "rejected" ? "确认删除该报告草稿？" : "确认将该报告归档？")
    if (confirmed) actions.remove.mutate({ reportCode: report.reportCode, version: report.version })
  }
  return (
    <>
      {report.status === "draft" ? (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => run("submit")}>
          <Send className="h-4 w-4" />
          提交
        </Button>
      ) : null}
      {report.status === "rejected" ? (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => run("resubmit")}>
          <Send className="h-4 w-4" />
          重新提交
        </Button>
      ) : null}
      {report.status === "submitted" ? (
        <>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => run("approve")}>
            <CheckCircle2 className="h-4 w-4" />
            通过
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={reject}>
            <Undo2 className="h-4 w-4" />
            退回
          </Button>
        </>
      ) : null}
      {report.status === "approved" ? (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => run("publish")}>
          <CheckCircle2 className="h-4 w-4" />
          发布
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" disabled={busy || report.status === "archived"} onClick={remove}>
        <Trash2 className="h-4 w-4" />
        {report.status === "draft" || report.status === "rejected" ? "删除" : "归档"}
      </Button>
    </>
  )
}

export function ReportStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={reportStatusTone[status] ?? "pending"} label={reportStatusLabels[status] ?? status} />
}

function isEditable(report: GhgInventoryReport) {
  return report.status === "draft" || report.status === "rejected"
}

function defaultReportTitle(run?: CalculationRun) {
  if (!run) return "组织温室气体盘查报告"
  const periodName = run.reportingPeriodName ?? run.inventoryCode
  if (periodName.endsWith("盘查期")) return periodName.replace(/盘查期$/, "盘查报告")
  if (periodName.endsWith("报告")) return periodName
  return `${periodName}组织温室气体盘查报告`
}

function snapshotValue(snapshot: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = snapshot[key]
    if (value !== null && value !== undefined && value !== "") return value
  }
  return undefined
}

function snapshotText(snapshot: Record<string, unknown>, keys: string[]) {
  const value = snapshotValue(snapshot, keys)
  return value === undefined ? "-" : String(value)
}

function formatSnapshotTonnes(snapshot: Record<string, unknown>) {
  const value = snapshotValue(snapshot, ["defaultTotalCo2eKg", "totalCo2eKg", "totalTCo2e", "total_t_co2e", "totalCo2eT", "total"])
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "-"
  const tonnes = "defaultTotalCo2eKg" in snapshot || "totalCo2eKg" in snapshot ? numeric / 1000 : numeric
  return tonnes.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
}

function snapshotRows(snapshot: Record<string, unknown>, preferred: string[]) {
  const rows = preferred.map((key) => [key, snapshotText(snapshot, [key])] as const).filter(([, value]) => value !== "-")
  if (rows.length) return rows
  return Object.entries(snapshot)
    .slice(0, 12)
    .map(([key, value]) => [key, value === null || value === undefined ? "-" : String(value)] as const)
}

function snapshotLabel(key: string) {
  const labels: Record<string, string> = {
    defaultTotalCo2eKg: "默认口径排放总量(tCO₂e)",
    totalLocationCo2eKg: "范围二地点法总量(tCO₂e)",
    totalMarketCo2eKg: "范围二市场法总量(tCO₂e)",
    defaultScope2Method: "默认范围二口径",
    totalTCo2e: "排放总量(tCO₂e)",
    scope1TCo2e: "Scope 1(tCO₂e)",
    scope2TCo2e: "Scope 2(tCO₂e)",
    scope3TCo2e: "Scope 3(tCO₂e)",
    qualityStatus: "质量状态",
  }
  return labels[key] ?? key
}

function formatSnapshotRowValue(key: string, value: string) {
  if (key.endsWith("Co2eKg")) {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? (numeric / 1000).toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : value
  }
  if (key === "defaultScope2Method") return value === "market" ? "市场法" : "地点法"
  return value
}

function actionLabel(action: string) {
  const labels: Record<string, string> = {
    submit: "提交",
    resubmit: "重新提交",
    approve: "审核通过",
    reject: "退回",
    publish: "发布",
    archive: "归档",
  }
  return labels[action] ?? action
}

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}
