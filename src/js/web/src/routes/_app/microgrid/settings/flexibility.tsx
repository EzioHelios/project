import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, RefreshCw } from "lucide-react"
import { AdminEmptyState, AdminPageScaffold, AdminPanel, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatNumber, MicrogridSettingsTabs } from "@/components/microgrid/microgrid-page"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useMicrogridFlexibilityContracts } from "@/lib/api/hooks/microgrid"

export const Route = createFileRoute("/_app/microgrid/settings/flexibility")({ component: MicrogridFlexibilitySettingsPage })

function MicrogridFlexibilitySettingsPage() {
  const contracts = useMicrogridFlexibilityContracts()
  const active = contracts.data?.filter((contract) => contract.enabled) ?? []

  return (
    <AdminPageScaffold
      title="柔性契约"
      meta={`${active.length} 项生效`}
      topActions={
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/microgrid/operations">
              <ArrowLeft />
              返回监控
            </Link>
          </Button>
          <Button disabled={contracts.isFetching} onClick={() => void contracts.refetch()} size="sm" variant="outline">
            <RefreshCw className={contracts.isFetching ? "animate-spin" : ""} />
            刷新
          </Button>
        </div>
      }
      tabs={<MicrogridSettingsTabs />}
      filters={
        <ContextBar>
          <div className="min-w-48">
            <span className="text-muted-foreground text-xs">执行原则</span>
            <div className="font-medium text-sm">安全下限优先</div>
          </div>
          <div className="min-w-56">
            <span className="text-muted-foreground text-xs">配置作用域</span>
            <div className="font-medium text-sm">已发布场景快照</div>
          </div>
        </ContextBar>
      }
      metrics={
        <MetricStrip>
          <MetricTile label="契约总数" value={contracts.data?.length ?? 0} unit="项" />
          <MetricTile label="生效契约" value={active.length} unit="项" />
          <MetricTile label="充电任务" value={active.filter((item) => item.contractType === "energy_deadline").length} unit="项" />
          <MetricTile label="最低服务" value={active.filter((item) => item.contractType === "minimum_service").length} unit="项" />
        </MetricStrip>
      }
    >
      {!contracts.isLoading && active.length === 0 ? (
        <AdminEmptyState title="尚无柔性契约" description="请先配置可调资源并发布场景。" />
      ) : (
        <AdminPanel title="调度边界" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>资源</TableHead>
                <TableHead>契约类型</TableHead>
                <TableHead>允许时窗</TableHead>
                <TableHead className="text-right">功率范围</TableHead>
                <TableHead className="text-right">目标电量</TableHead>
                <TableHead className="text-right">优先级</TableHead>
                <TableHead className="text-right">违约成本</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {active.map((contract) => (
                <TableRow key={contract.id}>
                  <TableCell>
                    <div className="font-medium">{contract.assetName}</div>
                    <div className="text-muted-foreground text-xs">{contract.assetCode}</div>
                  </TableCell>
                  <TableCell>{contract.contractType === "energy_deadline" ? "截止电量" : "最低服务"}</TableCell>
                  <TableCell>
                    {formatMinute(contract.startMinute)}–{formatMinute(contract.endMinute)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatNumber(contract.minimumPowerKw)}–{formatNumber(contract.maximumPowerKw)} kW
                  </TableCell>
                  <TableCell className="text-right">{contract.targetEnergyKwh ? `${formatNumber(contract.targetEnergyKwh)} kWh` : "-"}</TableCell>
                  <TableCell className="text-right">{contract.priority}</TableCell>
                  <TableCell className="text-right">¥ {formatNumber(contract.penaltyCnyPerKwh, 2)}/kWh</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminPanel>
      )}
    </AdminPageScaffold>
  )
}

function formatMinute(value: number) {
  if (value === 1440) return "24:00"
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`
}
