import { createFileRoute, Link } from "@tanstack/react-router"
import { Download, FileUp, RefreshCw } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useGhgActivities, useGhgCatalog, useGhgInventoryActions } from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon-mgmt/category/$categoryCode")({ component: GhgCategoryLedgerPage })

function GhgCategoryLedgerPage() {
  const { categoryCode } = Route.useParams()
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [inventoryCode, setInventoryCode] = useState("")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [keyword, setKeyword] = useState("")
  const category = catalog.data?.categories.find((item) => item.code === categoryCode)
  const availableMethods = useMemo(
    () => (catalog.data?.methods ?? []).filter((method) => category?.defaultMethods.includes(method.code) && method.executable),
    [catalog.data?.methods, category],
  )
  const activities = useGhgActivities({
    inventoryCode: inventoryCode || undefined,
    categoryCode,
    qualityStatus: qualityStatus === "all" ? undefined : qualityStatus,
  })
  const rows = (activities.data?.items ?? []).filter(
    (row) => !keyword.trim() || `${row.recordCode}${row.activityName}${row.sourceCode}`.toLowerCase().includes(keyword.trim().toLowerCase()),
  )
  const allocated = rows.filter((row) => row.allocationStatus === "complete").length
  const evidenceWarnings = rows.filter((row) => row.qualityStatus !== "pass").length
  const selectedPeriod = catalog.data?.periods.find((item) => item.code === inventoryCode) ?? catalog.data?.periods[0]
  const selectedOrganization = catalog.data?.organizations.find((item) => item.code === selectedPeriod?.organizationCode) ?? catalog.data?.organizations[0]
  const selectedArea = catalog.data?.areas.find((item) => item.level === 0) ?? catalog.data?.areas[0]
  const selectedProfile = catalog.data?.reportingProfiles[0]
  const defaultMethod = availableMethods[0]
  const importContextReady = Boolean(selectedPeriod && selectedOrganization && selectedArea && selectedProfile && defaultMethod)

  if (!catalog.isLoading && !category) {
    return (
      <PageContainer className="flex-1" maxWidth="4xl">
        <AdminPageScaffold title="活动数据分类">
          <AdminEmptyState title="未找到该活动分类" />
        </AdminPageScaffold>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title={category ? `${category.code} ${category.name}` : "活动数据分类"}
        status={
          category ? (
            <div className="flex items-center gap-2">
              <Badge variant="outline">{category.isoCategory}</Badge>
              <StatusBadge status={availableMethods.length ? "approved" : "pending"} label={availableMethods.length ? "可核算" : "方法待配置"} />
            </div>
          ) : undefined
        }
        topActions={
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!importContextReady || actions.downloadTemplate.isPending}
              onClick={() => {
                if (!selectedPeriod || !selectedOrganization || !selectedArea || !selectedProfile || !defaultMethod) return
                actions.downloadTemplate.mutate({
                  inventoryCode: selectedPeriod.code,
                  reportingPeriodId: selectedPeriod.id,
                  organizationCode: selectedOrganization.code,
                  facilityCode: selectedArea.code,
                  isoCategoryCode: categoryCode,
                  reportingProfileCode: selectedProfile.code,
                  methodCode: defaultMethod.code,
                })
              }}
            >
              <Download />
              下载本类模板
            </Button>
            {availableMethods.length > 0 && (
              <Button asChild size="sm">
                <Link to="/carbon-mgmt/import" search={{ category: categoryCode }}>
                  <FileUp />
                  导入本类数据
                </Link>
              </Button>
            )}
          </div>
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
            <MetricTile label="完成归集" value={allocated} unit="条" tone={allocated === rows.length && rows.length ? "success" : "warning"} />
            <MetricTile label="质量警告" value={evidenceWarnings} unit="条" tone={evidenceWarnings ? "warning" : "default"} />
            <MetricTile label="核算方法" value={availableMethods.length} unit="种" tone={availableMethods.length ? "success" : "warning"} />
          </MetricStrip>
        }
      >
        {!availableMethods.length && !catalog.isLoading && (
          <AdminEmptyState title="该分类尚未配置可执行核算方法" description="已有数据仍可查看；完成方法、参数与因子配置后开放模板和导入。" />
        )}
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>记录 / 活动</TableHead>
                <TableHead>区域 / 设备</TableHead>
                <TableHead>周期</TableHead>
                {(category?.activityFields ?? []).map((field) => (
                  <TableHead key={field.code}>{field.label}</TableHead>
                ))}
                <TableHead className="text-right">活动量</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>归集</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.isLoading && <AdminTableStateRow colSpan={(category?.activityFields.length ?? 0) + 8}>正在加载活动台账</AdminTableStateRow>}
              {activities.isError && (
                <AdminTableStateRow colSpan={(category?.activityFields.length ?? 0) + 8} tone="danger">
                  活动台账加载失败
                </AdminTableStateRow>
              )}
              {!activities.isLoading && !activities.isError && rows.length === 0 && (
                <AdminTableStateRow colSpan={(category?.activityFields.length ?? 0) + 8}>当前分类暂无活动记录</AdminTableStateRow>
              )}
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
                    {row.periodStart} 至 {row.periodEnd}
                  </TableCell>
                  {(category?.activityFields ?? []).map((field) => (
                    <TableCell key={field.code}>{detailValue(field.code, row.activityDetails[field.code])}</TableCell>
                  ))}
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

function detailValue(fieldCode: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "number") return value.toLocaleString("zh-CN")
  const text = String(value)
  return (
    (
      {
        "energy_type:electricity": "电力",
        "scope2_method:location": "基于位置",
        "scope2_method:market": "基于市场",
        "scope2_method:not_applicable": "不适用",
        "transport_direction:upstream": "上游",
        "transport_direction:downstream": "下游",
        "transport_direction:commute": "员工通勤",
        "transport_direction:business_travel": "商务旅行",
        "transport_direction:visitor": "客户和访客",
        "transport_included:yes": "是",
        "transport_included:no": "否",
      } as Record<string, string>
    )[`${fieldCode}:${text}`] ?? text
  )
}

function sourceLabel(source: string) {
  return ({ measured: "实测", ledger: "台账", manual: "人工台账", xlsx_import: "表格导入", supplier: "供应商", estimated: "估算" } as Record<string, string>)[source] ?? source
}
