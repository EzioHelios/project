import { createFileRoute, Link } from "@tanstack/react-router"
import { Database, FileInput, FileUp, ListChecks, RefreshCw, Sparkles } from "lucide-react"
import type { ReactNode } from "react"
import { useState } from "react"

import { AdminFilterBar, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { CarbonFormField } from "@/components/carbon/ghg-maintenance"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useGhgCatalog, useGhgInventoryActions, useGhgInventoryWorkbench } from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon-mgmt/workbench")({ component: GhgInventoryWorkbenchPage })

function GhgInventoryWorkbenchPage() {
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [periodId, setPeriodId] = useState<number | undefined>()
  const selectedPeriod = catalog.data?.periods.find((item) => item.id === periodId) ?? catalog.data?.periods[0]
  const workbench = useGhgInventoryWorkbench({ reportingPeriodId: selectedPeriod?.id })
  const data = workbench.data
  const [generateOpen, setGenerateOpen] = useState(false)
  const blockingCount = (data?.unallocatedCount ?? 0) + (data?.missingParameterCount ?? 0)
  const inventoryCode = data?.inventoryCode

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title="组织碳数据工作台"
        status={<StatusBadge status={blockingCount ? "pending" : "approved"} label={blockingCount ? "待补数据" : "可核算"} />}
        topActions={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setGenerateOpen(true)}>
              <Sparkles />
              生成活动数据
            </Button>
            <Button asChild size="sm">
              <Link to="/carbon-mgmt/activities">
                <ListChecks />
                活动台账
              </Link>
            </Button>
          </div>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "period",
                node: (
                  <CarbonFormField label="报告期">
                    <Select value={String(selectedPeriod?.id ?? "")} onValueChange={(value) => setPeriodId(Number(value))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(catalog.data?.periods ?? []).map((period) => (
                          <SelectItem key={period.id} value={String(period.id)}>
                            {period.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
            ]}
            actions={
              <Button size="sm" variant="outline" disabled={workbench.isFetching} onClick={() => void workbench.refetch()}>
                <RefreshCw className={workbench.isFetching ? "animate-spin" : ""} />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip className="xl:grid-cols-6">
            <MetricTile label="排放源" value={data?.sourceCount ?? 0} unit="项" />
            <MetricTile label="活动数据" value={data?.activityCount ?? 0} unit="条" />
            <MetricTile label="待归集" value={data?.unallocatedCount ?? 0} unit="条" tone={data?.unallocatedCount ? "warning" : "default"} />
            <MetricTile label="待配参数" value={data?.missingParameterCount ?? 0} unit="条" tone={data?.missingParameterCount ? "warning" : "default"} />
            <MetricTile label="质量警告" value={data?.warningCount ?? 0} unit="条" tone={data?.warningCount ? "warning" : "default"} />
            <MetricTile label="待补证据" value={data?.missingEvidenceCount ?? 0} unit="条" tone={data?.missingEvidenceCount ? "warning" : "default"} />
          </MetricStrip>
        }
      >
        <div className="grid gap-4 md:grid-cols-3">
          <WorkbenchCard icon={<Database />} title="排放源维护" to="/carbon-mgmt/sources" value={`${data?.sourceCount ?? 0} 项`} />
          <WorkbenchCard icon={<FileInput />} title="活动数据维护" to="/carbon-mgmt/activities" value={`${data?.activityCount ?? 0} 条`} />
          <WorkbenchCard icon={<FileUp />} title="批量导入" to="/carbon-mgmt/import" value="模板导入" />
        </div>
        <AdminPanel className="mt-4">
          <div className="grid gap-3 text-sm md:grid-cols-4">
            <TaskItem title="区域设备归集" count={data?.unallocatedCount ?? 0} to="/carbon-mgmt/activities" />
            <TaskItem title="因子参数" count={data?.missingParameterCount ?? 0} to="/carbon-mgmt/calculation-factors" />
            <TaskItem title="质量状态" count={data?.warningCount ?? 0} to="/carbon-mgmt/activities" />
            <TaskItem title="证据材料" count={data?.missingEvidenceCount ?? 0} to="/carbon/verification" />
          </div>
        </AdminPanel>
      </AdminPageScaffold>
      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>生成活动数据</DialogTitle>
          </DialogHeader>
          <div className="rounded-md border border-border/70 p-3 text-sm">
            <div className="font-medium">{selectedPeriod?.name ?? "请选择报告期"}</div>
            <div className="mt-2 text-muted-foreground">执行后会从购入电力能源事实和员工通勤台账生成组织碳活动数据，重复执行更新同一批记录。</div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenerateOpen(false)}>
              取消
            </Button>
            <Button
              disabled={!selectedPeriod || !inventoryCode || actions.generateActivities.isPending}
              onClick={() => {
                if (!selectedPeriod || !inventoryCode) return
                actions.generateActivities.mutate(
                  { inventoryCode, reportingPeriodId: selectedPeriod.id, sourceTypes: ["energy_electricity", "employee_commute"] },
                  { onSuccess: () => setGenerateOpen(false) },
                )
              }}
            >
              生成
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}

function WorkbenchCard({ icon, title, value, to }: { icon: ReactNode; title: string; value: string; to: string }) {
  return (
    <Link to={to} className="rounded-md border border-border/70 bg-card p-4 transition-colors hover:bg-muted/30">
      <div className="flex items-center justify-between">
        <div className="text-muted-foreground [&_svg]:size-5">{icon}</div>
        <div className="font-mono text-muted-foreground text-xs tabular-nums">{value}</div>
      </div>
      <div className="mt-4 font-medium">{title}</div>
    </Link>
  )
}

function TaskItem({ title, count, to }: { title: string; count: number; to: string }) {
  return (
    <Link to={to} className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2 hover:bg-muted/30">
      <span>{title}</span>
      <StatusBadge status={count ? "pending" : "approved"} label={count ? `${count} 项` : "完成"} />
    </Link>
  )
}
