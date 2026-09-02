import { createFileRoute } from "@tanstack/react-router"
import { Edit, Plus, RefreshCw, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageScaffold, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { CarbonFormField, categoryLabel, SourceForm, sourceDefaults, statusLabel } from "@/components/carbon/ghg-maintenance"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type GhgEmissionSource, type GhgEmissionSourceWrite, useGhgCatalog, useGhgEmissionSources, useGhgInventoryActions } from "@/lib/api/hooks/ghg-inventory"

export const Route = createFileRoute("/_app/carbon-mgmt/sources")({ component: GhgEmissionSourcePage })

function GhgEmissionSourcePage() {
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [inventoryCode, setInventoryCode] = useState("")
  const [categoryCode, setCategoryCode] = useState("all")
  const [status, setStatus] = useState("active")
  const [keyword, setKeyword] = useState("")
  const [editing, setEditing] = useState<GhgEmissionSource | "new" | null>(null)
  const sources = useGhgEmissionSources({
    inventoryCode: inventoryCode || undefined,
    categoryCode: categoryCode === "all" ? undefined : categoryCode,
    status: status === "all" ? undefined : status,
    keyword,
  })
  const rows = sources.data?.items ?? []
  const activeCount = rows.filter((row) => row.status === "active").length
  const linkedCount = rows.filter((row) => row.activityCount > 0).length
  const formInitial = useMemo<GhgEmissionSourceWrite>(() => {
    if (editing && editing !== "new") {
      return {
        inventoryCode: editing.inventoryCode,
        reportingPeriodId: editing.reportingPeriodId,
        organizationBoundaryId: editing.organizationBoundaryId,
        organizationCode: editing.organizationCode,
        facilityCode: editing.facilityCode,
        sourceCode: editing.sourceCode,
        sourceName: editing.sourceName,
        isoCategoryCode: editing.isoCategoryCode,
        sourceMechanism: editing.sourceMechanism,
        originKind: editing.originKind,
        defaultAreaId: editing.defaultAreaId,
        defaultEquipmentId: editing.defaultEquipmentId,
        defaultMeasurementBoundaryId: editing.defaultMeasurementBoundaryId,
        defaultAllocationRole: editing.defaultAllocationRole,
        externalFacilityCode: editing.externalFacilityCode,
        externalFacilityName: editing.externalFacilityName,
        validFrom: editing.validFrom,
        validTo: editing.validTo,
        sourceSystem: editing.sourceSystem,
        sourcePayload: editing.sourcePayload,
        status: editing.status,
      }
    }
    return sourceDefaults(catalog.data, categoryCode === "all" ? "2.1" : categoryCode)
  }, [catalog.data, categoryCode, editing])

  const save = (body: GhgEmissionSourceWrite) => {
    if (editing && editing !== "new") {
      actions.updateSource.mutate({ sourceCode: editing.sourceCode, body }, { onSuccess: () => setEditing(null) })
      return
    }
    actions.createSource.mutate(body, { onSuccess: () => setEditing(null) })
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title="排放源维护"
        topActions={
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus />
            新增排放源
          </Button>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "search",
                node: (
                  <CarbonFormField label="搜索">
                    <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="排放源编号或名称" />
                  </CarbonFormField>
                ),
              },
              {
                key: "inventory",
                node: (
                  <CarbonFormField label="盘查任务">
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
                  </CarbonFormField>
                ),
              },
              {
                key: "category",
                node: (
                  <CarbonFormField label="ISO 二级分类">
                    <Select value={categoryCode} onValueChange={setCategoryCode}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部分类</SelectItem>
                        {(catalog.data?.categories ?? []).map((category, index) => (
                          <SelectItem key={`${category.code}-${index}`} value={category.code}>
                            {category.code} {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
                        <SelectItem value="active">启用</SelectItem>
                        <SelectItem value="inactive">停用</SelectItem>
                      </SelectContent>
                    </Select>
                  </CarbonFormField>
                ),
              },
            ]}
            actions={
              <Button size="sm" variant="outline" disabled={sources.isFetching} onClick={() => void sources.refetch()}>
                <RefreshCw className={sources.isFetching ? "animate-spin" : ""} />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip>
            <MetricTile label="排放源" value={rows.length} unit="项" />
            <MetricTile label="启用" value={activeCount} unit="项" tone="success" />
            <MetricTile label="已关联活动" value={linkedCount} unit="项" tone={linkedCount ? "success" : "warning"} />
            <MetricTile label="未关联活动" value={Math.max(rows.length - linkedCount, 0)} unit="项" tone={rows.length - linkedCount ? "warning" : "default"} />
          </MetricStrip>
        }
      >
        <AdminDataTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>排放源</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>组织 / 区域</TableHead>
                <TableHead>来源</TableHead>
                <TableHead className="text-right">活动记录</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sources.isLoading && <AdminTableStateRow colSpan={7}>正在加载排放源</AdminTableStateRow>}
              {sources.isError && (
                <AdminTableStateRow colSpan={7} tone="danger">
                  排放源加载失败
                </AdminTableStateRow>
              )}
              {!sources.isLoading && !sources.isError && rows.length === 0 && <AdminTableStateRow colSpan={7}>当前筛选条件下没有排放源</AdminTableStateRow>}
              {rows.map((row) => (
                <TableRow key={`${row.inventoryCode}-${row.sourceCode}`}>
                  <TableCell>
                    <div className="font-medium">{row.sourceName}</div>
                    <div className="text-muted-foreground text-xs">{row.sourceCode}</div>
                  </TableCell>
                  <TableCell>{categoryLabel(catalog.data, row.isoCategoryCode)}</TableCell>
                  <TableCell>
                    <div>{row.organizationCode}</div>
                    <div className="text-muted-foreground text-xs">{row.facilityCode}</div>
                  </TableCell>
                  <TableCell>{row.sourceSystem}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{row.activityCount}</TableCell>
                  <TableCell>
                    <StatusBadge status={row.status === "active" ? "approved" : "draft"} label={statusLabel(row.status)} />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setEditing(row)}>
                        <Edit />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => actions.deleteSource.mutate({ inventoryCode: row.inventoryCode, sourceCode: row.sourceCode })}>
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPageScaffold>
      <Sheet open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="overflow-y-auto" size="wide">
          <SheetHeader>
            <SheetTitle>{editing === "new" ? "新增排放源" : "维护排放源"}</SheetTitle>
          </SheetHeader>
          <div className="px-4 pb-4">
            <SourceForm
              catalog={catalog.data}
              initial={formInitial}
              pending={actions.createSource.isPending || actions.updateSource.isPending}
              submitLabel={editing === "new" ? "保存排放源" : "更新排放源"}
              onSubmit={save}
            />
          </div>
        </SheetContent>
      </Sheet>
    </PageContainer>
  )
}
