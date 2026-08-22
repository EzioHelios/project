import { createFileRoute, Link } from "@tanstack/react-router"
import { FileUp, RefreshCw } from "lucide-react"
import type { ReactNode } from "react"
import { useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useGhgActivities, useGhgCatalog } from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon-mgmt/activities")({ component: GhgActivityLedgerPage })

function GhgActivityLedgerPage() {
  const catalog = useGhgCatalog()
  const [inventoryCode, setInventoryCode] = useState("")
  const [categoryCode, setCategoryCode] = useState("all")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [keyword, setKeyword] = useState("")
  const activities = useGhgActivities({
    inventoryCode: inventoryCode || undefined,
    categoryCode: categoryCode === "all" ? undefined : categoryCode,
    qualityStatus: qualityStatus === "all" ? undefined : qualityStatus,
  })
  const rows = (activities.data?.items ?? []).filter(
    (row) => !keyword.trim() || `${row.recordCode}${row.activityName}${row.sourceCode}`.toLowerCase().includes(keyword.trim().toLowerCase()),
  )
  const approved = rows.filter((row) => row.status === "approved").length
  const allocated = rows.filter((row) => row.allocationStatus === "complete").length
  const failures = rows.filter((row) => row.qualityStatus === "failed").length

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title="温室气体活动台账"
        topActions={
          <Button asChild size="sm">
            <Link to="/carbon-mgmt/import">
              <FileUp />
              导入活动数据
            </Link>
          </Button>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "search",
                node: (
                  <FilterField label="搜索">
                    <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="记录、活动或排放源" />
                  </FilterField>
                ),
              },
              {
                key: "inventory",
                node: (
                  <FilterField label="盘查任务">
                    <Select value={inventoryCode || "all"} onValueChange={(value) => setInventoryCode(value === "all" ? "" : value)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部盘查任务</SelectItem>
                        {(catalog.data?.periods ?? []).map((period) => (
                          <SelectItem key={period.id} value={period.code}>
                            {period.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
              {
                key: "category",
                node: (
                  <FilterField label="ISO 二级分类">
                    <Select value={categoryCode} onValueChange={setCategoryCode}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部分类</SelectItem>
                        {(catalog.data?.categories ?? []).map((category) => (
                          <SelectItem key={category.code} value={category.code}>
                            {category.code} {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
              {
                key: "quality",
                node: (
                  <FilterField label="数据质量">
                    <Select value={qualityStatus} onValueChange={setQualityStatus}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部状态</SelectItem>
                        <SelectItem value="pass">通过</SelectItem>
                        <SelectItem value="warning">警告</SelectItem>
                        <SelectItem value="failed">失败</SelectItem>
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
            ]}
            actions={
              <Button size="sm" variant="outline" disabled={activities.isFetching} onClick={() => void activities.refetch()}>
                <RefreshCw className={activities.isFetching ? "animate-spin" : ""} />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip>
            <MetricTile label="活动记录" value={rows.length} unit="条" />
            <MetricTile label="已批准" value={approved} unit="条" tone="success" />
            <MetricTile label="完成归集" value={allocated} unit="条" tone={allocated === rows.length && rows.length ? "success" : "warning"} />
            <MetricTile label="阻断记录" value={failures} unit="条" tone={failures ? "danger" : "default"} />
          </MetricStrip>
        }
      >
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>记录 / 活动</TableHead>
                <TableHead>区域 / 设备</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>周期</TableHead>
                <TableHead className="text-right">活动量</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>归集</TableHead>
                <TableHead>状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.isLoading && <AdminTableStateRow colSpan={9}>正在加载活动台账</AdminTableStateRow>}
              {activities.isError && (
                <AdminTableStateRow colSpan={9} tone="danger">
                  活动台账加载失败
                </AdminTableStateRow>
              )}
              {!activities.isLoading && !activities.isError && rows.length === 0 && <AdminTableStateRow colSpan={9}>当前筛选条件下没有活动记录</AdminTableStateRow>}
              {rows.map((row) => (
                <TableRow key={`${row.inventoryCode}-${row.recordCode}`}>
                  <TableCell>
                    <div className="font-medium">{row.activityName}</div>
                    <div className="text-muted-foreground text-xs">{row.recordCode}</div>
                  </TableCell>
                  <TableCell>
                    <div>{row.allocatedAreaNames.join("、") || "未归集"}</div>
                    <div className="text-muted-foreground text-xs">{row.allocatedEquipmentNames.join("、") || "区域级归集"}</div>
                  </TableCell>
                  <TableCell>
                    <div>
                      {row.isoCategoryCode} {catalog.data?.categories.find((item) => item.code === row.isoCategoryCode)?.name}
                    </div>
                    <div className="text-muted-foreground text-xs">
                      {row.ghgScope.toUpperCase()}
                      {row.scope3Category ? ` / 类别 ${row.scope3Category}` : ""}
                    </div>
                  </TableCell>
                  <TableCell>
                    {row.periodStart} 至 {row.periodEnd}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums">
                    {Number(row.activityAmount).toLocaleString("zh-CN")} {row.activityUnit}
                  </TableCell>
                  <TableCell>{sourceLabel(row.dataSourceType)}</TableCell>
                  <TableCell>
                    <StatusBadge
                      status={row.qualityStatus === "pass" ? "approved" : row.qualityStatus === "failed" ? "rejected" : "pending"}
                      label={row.qualityStatus === "pass" ? "通过" : row.qualityStatus === "failed" ? "失败" : "警告"}
                    />
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      status={row.allocationStatus === "complete" ? "approved" : "rejected"}
                      label={row.allocationStatus === "complete" ? `${row.allocationCount} 项` : "待归集"}
                    />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.status === "approved" ? "approved" : "draft"} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPageScaffold>
    </PageContainer>
  )
}

function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      {children}
    </div>
  )
}

function sourceLabel(source: string) {
  return ({ measured: "实测", ledger: "台账", manual: "人工台账", xlsx_import: "表格导入", supplier: "供应商", estimated: "估算" } as Record<string, string>)[source] ?? source
}
