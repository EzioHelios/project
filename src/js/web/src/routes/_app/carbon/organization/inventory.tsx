import { createFileRoute } from "@tanstack/react-router"
import { Calculator, FileCheck2, FileText } from "lucide-react"
import { useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { OrganizationBoundaryPanel } from "@/components/carbon/organization-boundary-panel"
import { formatDateTime, formatPercent, formatTonnes, InventoryStatusBadge, OrganizationRunFilterBar, type Scope2Method } from "@/components/carbon/organization-inventory-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
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
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </AdminPanel>
        <OrganizationBoundaryPanel />
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
    </AdminPageScaffold>
  )
}

function readMetric(snapshot: Record<string, unknown>, key: string) {
  const value = snapshot[key] ?? (key === "totalCo2eKg" ? snapshot.defaultTotalCo2eKg : undefined)
  return typeof value === "string" || typeof value === "number" ? value : 0
}
