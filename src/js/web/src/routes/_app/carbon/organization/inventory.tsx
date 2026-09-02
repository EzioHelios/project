import { createFileRoute } from "@tanstack/react-router"
import { Archive, Calculator, Eye, FileCheck2, FileText, RotateCcw } from "lucide-react"
import { useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatDateTime, formatPercent, formatTonnes, InventoryStatusBadge, OrganizationRunFilterBar, type Scope2Method } from "@/components/carbon/organization-inventory-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import {
  useGhgActivities,
  useGhgCalculationRuns,
  useGhgInventoryActions,
  useGhgInventoryReadiness,
  useGhgInventoryReportActions,
  useGhgInventoryReports,
} from "@/lib/api/hooks/ghg-inventory"
import type { GhgInventoryReportResponse } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/organization/inventory")({ component: OrganizationInventoryPage })

function OrganizationInventoryPage() {
  const runs = useGhgCalculationRuns()
  const activities = useGhgActivities({})
  const reports = useGhgInventoryReports()
  const actions = useGhgInventoryActions()
  const reportActions = useGhgInventoryReportActions()
  const [chosenRunCode, setChosenRunCode] = useState<string>()
  const [scope2Method, setScope2Method] = useState<Scope2Method>("location")
  const [rejectingReport, setRejectingReport] = useState<{ reportCode: string; version: number }>()
  const [rejectComment, setRejectComment] = useState("")
  const [selectedReport, setSelectedReport] = useState<GhgInventoryReportResponse>()
  const runCode = chosenRunCode ?? runs.data?.items[0]?.runCode
  const selectedRun = runs.data?.items.find((item) => item.runCode === runCode) ?? runs.data?.items[0]
  const inventoryCode = selectedRun?.inventoryCode ?? activities.data?.items[0]?.inventoryCode
  const readiness = useGhgInventoryReadiness({
    inventoryCode,
    reportingPeriodId: selectedRun?.reportingPeriodId ?? undefined,
    organizationBoundaryId: selectedRun?.organizationBoundaryId ?? undefined,
  })
  const ready = readiness.data
  const pendingReports = reports.data?.items.filter((item) => item.status === "submitted").length ?? 0
  const publishedReports = reports.data?.items.filter((item) => item.status === "published").length ?? 0
  const canCreateReport = Boolean(selectedRun?.status === "completed" && selectedRun.reportingOrgId && selectedRun.reportingPeriodId && selectedRun.organizationBoundaryId)

  const calculate = () => {
    if (!selectedRun) return
    actions.calculate.mutate({
      inventoryCode: selectedRun.inventoryCode,
      reportingProfileCode: selectedRun.reportingProfileCode,
      reportingPeriodId: selectedRun.reportingPeriodId ?? undefined,
      reportingOrgId: selectedRun.reportingOrgId ?? undefined,
      organizationBoundaryId: selectedRun.organizationBoundaryId ?? undefined,
      defaultScope2Method: scope2Method,
    })
  }
  const createReport = () => {
    if (!selectedRun) return
    reportActions.create.mutate({ runCode: selectedRun.runCode, title: `${selectedRun.reportingPeriodName ?? selectedRun.inventoryCode} 组织温室气体盘查报告` })
  }

  return (
    <AdminPageScaffold
      title="碳盘查"
      status={<InventoryStatusBadge status={ready?.readyForCalculation ? "pass" : "warning"} />}
      meta={
        selectedRun ? (
          <>
            <span>{selectedRun.reportingOrgName}</span>
            <span>{selectedRun.reportingPeriodName}</span>
            <span>{selectedRun.organizationBoundaryName}</span>
          </>
        ) : undefined
      }
      topActions={
        <>
          <Button size="sm" variant="outline" disabled={!ready?.readyForCalculation || actions.calculate.isPending || !selectedRun} onClick={calculate}>
            <Calculator />
            {actions.calculate.isPending ? "核算中" : "执行核算"}
          </Button>
          <Button size="sm" disabled={!canCreateReport || reportActions.create.isPending} onClick={createReport}>
            <FileText />
            生成盘查报告
          </Button>
        </>
      }
      filters={
        <OrganizationRunFilterBar
          runs={runs.data}
          runCode={runCode}
          scope2Method={scope2Method}
          onRunCodeChange={setChosenRunCode}
          onScope2MethodChange={setScope2Method}
          onRefresh={() => void Promise.all([readiness.refetch(), runs.refetch(), reports.refetch()])}
          refreshing={readiness.isFetching || runs.isFetching || reports.isFetching}
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="盘查活动数据" value={ready?.activityCount ?? 0} unit="条" />
          <MetricTile
            label="核算准备度"
            value={ready?.checks.length ? `${ready.checks.filter((item) => item.status === "pass").length}/${ready.checks.length}` : "-"}
            tone={ready?.readyForCalculation ? "success" : "warning"}
          />
          <MetricTile label="待审批报告" value={pendingReports} unit="份" tone={pendingReports ? "warning" : "default"} />
          <MetricTile label="已发布报告" value={publishedReports} unit="份" tone={publishedReports ? "success" : "default"} />
        </MetricStrip>
      }
    >
      <div className="grid gap-3">
        <AdminPanel title="核算准备检查" contentClassName="p-0">
          {!ready && !readiness.isLoading ? (
            <AdminEmptyState title="请先建立盘查任务和组织边界" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>检查项</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">完成</TableHead>
                  <TableHead className="text-right">覆盖率</TableHead>
                  <TableHead className="text-right">阻断项</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(ready?.checks ?? []).map((check) => (
                  <TableRow key={check.code}>
                    <TableCell className="font-medium">{check.name}</TableCell>
                    <TableCell>
                      <InventoryStatusBadge status={check.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {check.completedCount}/{check.totalCount}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatPercent(check.coveragePct)}</TableCell>
                    <TableCell className="text-right tabular-nums">{check.blockingCount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </AdminPanel>
        <AdminPanel title="盘查报告台账" contentClassName="p-0">
          {(reports.data?.items.length ?? 0) === 0 && !reports.isLoading ? (
            <AdminEmptyState title="尚未生成盘查报告" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>报告</TableHead>
                  <TableHead>版本</TableHead>
                  <TableHead>报告期/核算运行</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">排放总量</TableHead>
                  <TableHead>审批记录</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(reports.data?.items ?? []).map((report) => (
                  <TableRow key={`${report.reportCode}:${report.version}`}>
                    <TableCell>
                      <div className="font-medium">{report.title}</div>
                      <div className="text-xs text-muted-foreground">{report.reportCode}</div>
                    </TableCell>
                    <TableCell>v{report.version}</TableCell>
                    <TableCell>
                      <div>{report.inventoryCode}</div>
                      <div className="text-xs text-muted-foreground">{report.runCode}</div>
                    </TableCell>
                    <TableCell>
                      <InventoryStatusBadge status={report.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatTonnes(readMetric(report.metricsSnapshot, "totalCo2eKg"))} tCO₂e</TableCell>
                    <TableCell>
                      <div>{report.reviews.length} 条</div>
                      <div className="text-xs text-muted-foreground">{formatDateTime(report.publishedAt ?? report.approvedAt ?? report.submittedAt)}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setSelectedReport(report)}>
                          <Eye />
                          查看
                        </Button>
                        {report.status === "draft" && (
                          <Button size="sm" variant="outline" onClick={() => reportActions.submit.mutate({ reportCode: report.reportCode, version: report.version })}>
                            提交
                          </Button>
                        )}
                        {report.status === "submitted" && (
                          <>
                            <Button size="sm" variant="outline" onClick={() => setRejectingReport({ reportCode: report.reportCode, version: report.version })}>
                              退回
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => reportActions.approve.mutate({ reportCode: report.reportCode, version: report.version })}>
                              <FileCheck2 />
                              批准
                            </Button>
                          </>
                        )}
                        {report.status === "approved" && (
                          <Button size="sm" onClick={() => reportActions.publish.mutate({ reportCode: report.reportCode, version: report.version })}>
                            发布
                          </Button>
                        )}
                        {report.status === "rejected" && (
                          <Button size="sm" variant="outline" onClick={() => reportActions.resubmit.mutate({ reportCode: report.reportCode, version: report.version })}>
                            <RotateCcw />
                            重新提交
                          </Button>
                        )}
                        {report.status === "published" && (
                          <Button size="sm" variant="outline" onClick={() => reportActions.archive.mutate({ reportCode: report.reportCode, version: report.version })}>
                            <Archive />
                            归档
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </AdminPanel>
      </div>
      <Dialog open={Boolean(rejectingReport)} onOpenChange={(open) => !open && setRejectingReport(undefined)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>退回盘查报告</DialogTitle>
          </DialogHeader>
          <Textarea value={rejectComment} onChange={(event) => setRejectComment(event.target.value)} placeholder="填写需要修订的内容" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectingReport(undefined)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={!rejectComment.trim() || reportActions.reject.isPending}
              onClick={() =>
                rejectingReport &&
                reportActions.reject.mutate(
                  { ...rejectingReport, comment: rejectComment.trim() },
                  {
                    onSuccess: () => {
                      setRejectingReport(undefined)
                      setRejectComment("")
                    },
                  },
                )
              }
            >
              确认退回
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Sheet open={Boolean(selectedReport)} onOpenChange={(open) => !open && setSelectedReport(undefined)}>
        <SheetContent size="xwide" className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>盘查报告详情</SheetTitle>
          </SheetHeader>
          {selectedReport && (
            <div className="space-y-5 px-4 pb-6">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-4">
                <div>
                  <div className="font-medium">{selectedReport.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {selectedReport.reportCode} · v{selectedReport.version}
                  </div>
                </div>
                <InventoryStatusBadge status={selectedReport.status} />
              </div>
              <ReportFactGrid report={selectedReport} />
              <div>
                <div className="mb-2 text-sm font-medium">审批轨迹</div>
                {selectedReport.reviews.length === 0 ? (
                  <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">暂无审批记录</div>
                ) : (
                  <Table className="table-fixed">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-20">操作</TableHead>
                        <TableHead className="w-36">状态变化</TableHead>
                        <TableHead className="w-32">操作人</TableHead>
                        <TableHead>意见</TableHead>
                        <TableHead className="w-36 text-right">时间</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedReport.reviews.map((review, index) => (
                        <TableRow key={`${review.action}:${review.actedAt}:${index}`}>
                          <TableCell className="font-medium">{reportActionLabel(review.action)}</TableCell>
                          <TableCell>
                            {reportStatusLabel(review.fromStatus)} → {reportStatusLabel(review.toStatus)}
                          </TableCell>
                          <TableCell className="whitespace-normal break-words">{review.actor}</TableCell>
                          <TableCell className="whitespace-normal break-words">{review.comment || "-"}</TableCell>
                          <TableCell className="whitespace-normal text-right tabular-nums">{formatDateTime(review.actedAt)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </AdminPageScaffold>
  )
}

function ReportFactGrid({ report }: { report: GhgInventoryReportResponse }) {
  const evidence = report.evidenceSnapshot
  const facts = [
    ["核算运行", report.runCode],
    ["报告方案", reportingProfileLabel(report.reportingProfileCode)],
    ["排放总量", `${formatTonnes(readMetric(report.metricsSnapshot, "totalCo2eKg"))} tCO₂e`],
    ["证据覆盖率", formatPercent(readMetric(evidence, "coveragePct"))],
    ["活动数据", `${readMetric(evidence, "activityCount")} 条`],
    ["已关联活动", `${readMetric(evidence, "linkedActivityCount")} 条`],
    ["证据文件关联", `${readMetric(evidence, "evidenceLinkCount")} 条`],
    ["发布时间", formatDateTime(report.publishedAt)],
  ]
  return (
    <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label} className="border-l-2 border-border pl-3 text-sm">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 font-medium tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  )
}

function reportActionLabel(action: string) {
  return ({ submit: "提交", resubmit: "重新提交", approve: "批准", reject: "退回", publish: "发布", archive: "归档" } as Record<string, string>)[action] ?? action
}

function reportStatusLabel(status: string) {
  return ({ draft: "草稿", submitted: "待审批", approved: "已批准", rejected: "已驳回", published: "已发布", archived: "已归档" } as Record<string, string>)[status] ?? status
}

function readMetric(snapshot: Record<string, unknown>, key: string) {
  const aliases: Record<string, string[]> = {
    totalCo2eKg: ["totalCo2eKg", "total_co2e_kg", "defaultTotalCo2eKg", "default_total_co2e_kg"],
    coveragePct: ["coveragePct", "coverage_pct"],
    activityCount: ["activityCount", "activity_count"],
    linkedActivityCount: ["linkedActivityCount", "linked_activity_count"],
    evidenceLinkCount: ["evidenceLinkCount", "evidence_link_count"],
  }
  const value = (aliases[key] ?? [key]).map((alias) => snapshot[alias]).find((item) => item != null)
  return typeof value === "string" || typeof value === "number" ? value : 0
}

function reportingProfileLabel(value: string) {
  return (
    (
      {
        CORPORATE_ISO14064_GHGP: "组织温室气体盘查（ISO 14064-1 / GHG Protocol）",
      } as Record<string, string>
    )[value] ?? value
  )
}
