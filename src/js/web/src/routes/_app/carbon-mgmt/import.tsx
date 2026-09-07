import { createFileRoute, Link } from "@tanstack/react-router"
import { Calculator, Download, FileCheck2, FileUp, ListChecks } from "lucide-react"
import type { ReactNode } from "react"
import { useEffect, useMemo, useState } from "react"
import { z } from "zod"

import { AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { type GhgImportBatch, type GhgImportContext, useGhgCatalog, useGhgInventoryActions } from "@/lib/api/hooks/ghg-inventory"
import { normalizeGhgCategoryCode } from "@/lib/ghg-categories"

const importSearchSchema = z.object({ category: z.preprocess(normalizeGhgCategoryCode, z.string().optional()) })

export const Route = createFileRoute("/_app/carbon-mgmt/import")({
  validateSearch: (search) => importSearchSchema.parse(search),
  component: GhgInventoryImportPage,
})

function GhgInventoryImportPage() {
  const { category: lockedCategoryCode } = Route.useSearch()
  const catalog = useGhgCatalog()
  const actions = useGhgInventoryActions()
  const [context, setContext] = useState<GhgImportContext>({
    inventoryCode: "",
    organizationCode: "",
    facilityCode: "",
    isoCategoryCode: "",
    reportingProfileCode: "",
    methodCode: "",
  })
  const [file, setFile] = useState<File>()
  const [preview, setPreview] = useState<GhgImportBatch>()
  const [acknowledgeWarnings, setAcknowledgeWarnings] = useState(false)
  const [warningAcknowledgement, setWarningAcknowledgement] = useState("")

  useEffect(() => {
    const data = catalog.data
    if (!data || context.organizationCode) return
    const period = data.periods[0]
    const organization = data.organizations.find((item) => item.code === period?.organizationCode) ?? data.organizations[0]
    const category = data.categories.find((item) => item.code === lockedCategoryCode) ?? data.categories.find((item) => item.code === "1.1") ?? data.categories[0]
    const method = category?.defaultMethods.find((code) => data.methods.find((item) => item.code === code)?.executable)
    setContext({
      inventoryCode: period?.code ?? `INV-${new Date().getFullYear()}`,
      reportingPeriodId: period?.id,
      organizationCode: organization?.code ?? "ORG",
      facilityCode: data.areas.find((item) => item.level === 0)?.code ?? data.areas[0]?.code ?? "ROOT",
      isoCategoryCode: category?.code ?? "1.1",
      reportingProfileCode: data.reportingProfiles[0]?.code ?? "CORPORATE_ISO14064_GHGP",
      methodCode: method ?? "F01_NCV",
    })
  }, [catalog.data, context.organizationCode, lockedCategoryCode])

  useEffect(() => {
    if (!lockedCategoryCode || !catalog.data || context.isoCategoryCode === lockedCategoryCode) return
    const category = catalog.data.categories.find((item) => item.code === lockedCategoryCode)
    if (!category) return
    const methodCode = category.defaultMethods.find((code) => catalog.data.methods.find((item) => item.code === code)?.executable) ?? ""
    setContext((current) => ({ ...current, isoCategoryCode: lockedCategoryCode, methodCode }))
    setPreview(undefined)
    setFile(undefined)
  }, [catalog.data, context.isoCategoryCode, lockedCategoryCode])

  const selectedCategory = catalog.data?.categories.find((item) => item.code === context.isoCategoryCode)
  const availableMethods = useMemo(
    () => (catalog.data?.methods ?? []).filter((method) => selectedCategory?.defaultMethods.includes(method.code) && method.executable),
    [catalog.data?.methods, selectedCategory],
  )
  const selectedMethod = availableMethods.find((item) => item.code === context.methodCode)
  const ready = Boolean(context.inventoryCode && context.organizationCode && context.facilityCode && context.isoCategoryCode && context.reportingProfileCode && context.methodCode)
  const metrics = preview?.preview.metrics ?? { rowCount: 0, validCount: 0, warningCount: 0, errorCount: 0, missingEvidenceCount: 0 }

  const updateCategory = (isoCategoryCode: string) => {
    const category = catalog.data?.categories.find((item) => item.code === isoCategoryCode)
    const methodCode = category?.defaultMethods.find((code) => catalog.data?.methods.find((item) => item.code === code)?.executable) ?? ""
    setContext((current) => ({ ...current, isoCategoryCode, methodCode }))
    setPreview(undefined)
    setFile(undefined)
    setAcknowledgeWarnings(false)
    setWarningAcknowledgement("")
  }

  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <AdminPageScaffold
        title={lockedCategoryCode && selectedCategory ? `${selectedCategory.code} ${selectedCategory.name}数据导入` : "活动数据导入"}
        status={
          preview ? (
            <StatusBadge
              status={preview.status === "committed" ? "approved" : preview.status === "blocked" ? "rejected" : "pending"}
              label={preview.status === "committed" ? "已入库" : preview.status === "blocked" ? "预检未通过" : "待确认"}
            />
          ) : undefined
        }
        topActions={
          <div className="flex gap-2">
            <Button asChild size="sm" variant="outline">
              <Link to="/carbon-mgmt/activities" search={lockedCategoryCode ? { category: lockedCategoryCode } : {}}>
                <ListChecks />
                活动台账
              </Link>
            </Button>
            <Button disabled={!ready || actions.downloadTemplate.isPending} onClick={() => actions.downloadTemplate.mutate(context)} size="sm" variant="outline">
              <Download />
              下载分类模板
            </Button>
          </div>
        }
        filters={
          <AdminFilterBar
            defaultVisibleCount={4}
            fields={[
              {
                key: "period",
                node: (
                  <FilterField label="盘查期">
                    <Select
                      value={context.reportingPeriodId ? String(context.reportingPeriodId) : "custom"}
                      onValueChange={(value) => {
                        const period = catalog.data?.periods.find((item) => String(item.id) === value)
                        setContext((current) => ({
                          ...current,
                          reportingPeriodId: period?.id,
                          inventoryCode: period?.code ?? current.inventoryCode,
                          organizationCode: period?.organizationCode ?? current.organizationCode,
                        }))
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(catalog.data?.periods ?? []).map((period) => (
                          <SelectItem key={period.id} value={String(period.id)}>
                            {period.name}
                          </SelectItem>
                        ))}
                        <SelectItem value="custom">自定义盘查任务</SelectItem>
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
              {
                key: "organization",
                node: (
                  <FilterField label="组织">
                    <Select value={context.organizationCode} onValueChange={(organizationCode) => setContext((current) => ({ ...current, organizationCode }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(catalog.data?.organizations ?? []).map((organization) => (
                          <SelectItem key={organization.code} value={organization.code}>
                            {organization.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
              {
                key: "facility",
                node: (
                  <FilterField label="归集区域">
                    <Select value={context.facilityCode} onValueChange={(facilityCode) => setContext((current) => ({ ...current, facilityCode }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(catalog.data?.areas ?? []).map((area) => (
                          <SelectItem key={area.code} value={area.code}>
                            {area.name}
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
                  <FilterField label="活动分类">
                    {lockedCategoryCode ? (
                      <Input value={selectedCategory ? `${selectedCategory.code} ${selectedCategory.name}` : lockedCategoryCode} readOnly />
                    ) : (
                      <Select value={context.isoCategoryCode} onValueChange={updateCategory}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(catalog.data?.categories ?? []).map((category) => {
                            const executable = category.defaultMethods.some((code) => catalog.data?.methods.find((item) => item.code === code)?.executable)
                            return (
                              <SelectItem key={category.code} value={category.code} disabled={!executable}>
                                {category.code} {category.name}
                              </SelectItem>
                            )
                          })}
                        </SelectContent>
                      </Select>
                    )}
                  </FilterField>
                ),
              },
              {
                key: "profile",
                node: (
                  <FilterField label="报告配置">
                    <Select value={context.reportingProfileCode} onValueChange={(reportingProfileCode) => setContext((current) => ({ ...current, reportingProfileCode }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(catalog.data?.reportingProfiles ?? []).map((profile) => (
                          <SelectItem key={profile.code} value={profile.code}>
                            {profile.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
              {
                key: "method",
                node: (
                  <FilterField label="计算方法">
                    <Select value={context.methodCode} onValueChange={(methodCode) => setContext((current) => ({ ...current, methodCode }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {availableMethods.map((method) => (
                          <SelectItem key={method.code} value={method.code}>
                            {method.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>
                ),
              },
            ]}
          />
        }
        metrics={
          <MetricStrip className="xl:grid-cols-5">
            <MetricTile label="活动记录" value={metrics.rowCount} unit="条" />
            <MetricTile label="有效记录" value={metrics.validCount} unit="条" tone={metrics.validCount ? "success" : "default"} />
            <MetricTile label="警告" value={metrics.warningCount} unit="项" tone={metrics.warningCount ? "warning" : "default"} />
            <MetricTile label="阻断错误" value={metrics.errorCount} unit="项" tone={metrics.errorCount ? "danger" : "default"} />
            <MetricTile label="缺少证据" value={metrics.missingEvidenceCount} unit="条" tone={metrics.missingEvidenceCount ? "warning" : "default"} />
          </MetricStrip>
        }
      >
        <AdminPanel
          title="上传与预检"
          actions={
            selectedMethod ? (
              <Badge variant="outline">
                {selectedMethod.name} · {selectedMethod.code}
              </Badge>
            ) : undefined
          }
        >
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-72 flex-1 space-y-1.5">
              <Label htmlFor="ghg-workbook">分类工作簿</Label>
              <Input
                id="ghg-workbook"
                type="file"
                accept=".xlsx"
                onChange={(event) => {
                  setFile(event.target.files?.[0])
                  setPreview(undefined)
                  setAcknowledgeWarnings(false)
                  setWarningAcknowledgement("")
                }}
              />
            </div>
            <Button
              disabled={!ready || !file || actions.preview.isPending}
              onClick={() => file && actions.preview.mutate({ context, file }, { onSuccess: (data) => setPreview(data) })}
            >
              <FileCheck2 />
              {actions.preview.isPending ? "正在预检" : "执行预检"}
            </Button>
          </div>
        </AdminPanel>

        {!preview ? (
          <AdminEmptyState title="等待工作簿预检" description="选择盘查上下文并上传对应分类模板。" />
        ) : (
          <Tabs defaultValue="activities">
            <TabsList>
              <TabsTrigger value="activities">活动数据</TabsTrigger>
              <TabsTrigger value="allocations">区域设备归集</TabsTrigger>
              <TabsTrigger value="parameters">方法与参数</TabsTrigger>
              <TabsTrigger value="evidence">证据覆盖</TabsTrigger>
              <TabsTrigger value="issues">校验问题 {preview.errorCount + preview.warningCount ? `(${preview.errorCount + preview.warningCount})` : ""}</TabsTrigger>
            </TabsList>
            <TabsContent value="activities">
              <ActivityPreviewTable preview={preview} />
            </TabsContent>
            <TabsContent value="allocations">
              <AllocationPreviewTable preview={preview} />
            </TabsContent>
            <TabsContent value="parameters">
              <ParameterPreviewTable preview={preview} methodFormula={selectedMethod?.formula} />
            </TabsContent>
            <TabsContent value="evidence">
              <EvidencePreviewTable preview={preview} />
            </TabsContent>
            <TabsContent value="issues">
              <IssueTable preview={preview} />
            </TabsContent>
            <div className="flex flex-wrap items-center justify-end gap-3 border-border/70 border-t pt-4">
              {preview.warningCount > 0 && preview.errorCount === 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" className="size-4 accent-primary" checked={acknowledgeWarnings} onChange={(event) => setAcknowledgeWarnings(event.target.checked)} />
                    确认保留警告
                  </label>
                  <Input value={warningAcknowledgement} onChange={(event) => setWarningAcknowledgement(event.target.value)} placeholder="填写确认原因" />
                </div>
              )}
              <Button
                disabled={
                  preview.status === "committed" ||
                  preview.errorCount > 0 ||
                  (preview.warningCount > 0 && (!acknowledgeWarnings || !warningAcknowledgement.trim())) ||
                  actions.commit.isPending
                }
                onClick={() => actions.commit.mutate({ batchCode: preview.batchCode, acknowledgeWarnings, warningAcknowledgement }, { onSuccess: setPreview })}
              >
                <FileUp />
                {preview.status === "committed" ? "已完成导入" : "确认导入"}
              </Button>
              {preview.status === "committed" && (
                <Button
                  variant="outline"
                  disabled={actions.calculate.isPending}
                  onClick={() =>
                    actions.calculate.mutate({
                      inventoryCode: preview.inventoryCode,
                      reportingProfileCode: preview.reportingProfileCode,
                      reportingPeriodId: context.reportingPeriodId,
                    })
                  }
                >
                  <Calculator />
                  执行核算
                </Button>
              )}
            </div>
          </Tabs>
        )}
      </AdminPageScaffold>
    </PageContainer>
  )
}

function AllocationPreviewTable({ preview }: { preview: GhgImportBatch }) {
  return (
    <AdminPanel title="区域设备归集" contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>活动记录</TableHead>
            <TableHead>区域</TableHead>
            <TableHead>设备 / 计量边界</TableHead>
            <TableHead>归集角色</TableHead>
            <TableHead className="text-right">归集比例</TableHead>
            <TableHead>来源</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.preview.allocations.length ? (
            preview.preview.allocations.map((row) => (
              <TableRow key={`${row._row_number}-${row.allocationCode}`}>
                <TableCell>
                  <div className="font-medium">{row.recordCode}</div>
                  <div className="text-muted-foreground text-xs">{row.sourceCode}</div>
                </TableCell>
                <TableCell>{row.areaCode}</TableCell>
                <TableCell>
                  <div>{row.equipmentCode ?? "区域级归集"}</div>
                  <div className="text-muted-foreground text-xs">{row.measurementBoundaryCode ?? "-"}</div>
                </TableCell>
                <TableCell>{allocationRoleLabel(row.allocationRole ?? "")}</TableCell>
                <TableCell className="text-right font-mono tabular-nums">{formatAllocationRatio(row.allocationRatio)}</TableCell>
                <TableCell>{sourceModeLabel(row.sourceKind ?? "")}</TableCell>
              </TableRow>
            ))
          ) : (
            <AdminTableStateRow colSpan={6}>未配置区域设备归集</AdminTableStateRow>
          )}
        </TableBody>
      </Table>
    </AdminPanel>
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

function ActivityPreviewTable({ preview }: { preview: GhgImportBatch }) {
  return (
    <AdminPanel title="活动数据预览" contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>行号 / 记录</TableHead>
            <TableHead>活动</TableHead>
            <TableHead>组织 / 设施</TableHead>
            <TableHead>期间</TableHead>
            <TableHead className="text-right">活动量</TableHead>
            <TableHead>数据来源</TableHead>
            <TableHead>证据</TableHead>
            <TableHead>状态</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.preview.activities.map((row) => {
            const rowIssues = preview.preview.issues.filter((issue) => issue.sheetName === "03_活动数据" && issue.rowNumber === row._row_number)
            const parameterRows = new Set(
              preview.preview.parameters.filter((parameter) => parameter.parameterSetCode === row.parameterSetCode).map((parameter) => parameter._row_number),
            )
            const parameterIssues = preview.preview.issues.filter(
              (issue) => issue.sheetName === "04_参数与因子" && typeof issue.rowNumber === "number" && parameterRows.has(issue.rowNumber),
            )
            const evidenceCount = preview.preview.links.filter((link) => link.recordType === "activity" && link.recordCode === row.recordCode).length
            const hasError =
              [...rowIssues, ...parameterIssues].some((issue) => issue.severity === "error") ||
              preview.preview.issues.some((issue) => issue.severity === "error" && issue.rowNumber === null)
            const hasWarning = evidenceCount === 0 || [...rowIssues, ...parameterIssues].some((issue) => issue.severity === "warning")
            return (
              <TableRow key={`${row._row_number}-${row.recordCode}`}>
                <TableCell>
                  <div className="font-medium">{row.recordCode}</div>
                  <div className="text-muted-foreground text-xs">第 {row._row_number} 行</div>
                </TableCell>
                <TableCell>{row.activityName}</TableCell>
                <TableCell>
                  <div>{row.organizationCode}</div>
                  <div className="text-muted-foreground text-xs">{row.facilityCode}</div>
                </TableCell>
                <TableCell>
                  {row.periodStart} 至 {row.periodEnd}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums">
                  {row.activityAmount} {row.activityUnit}
                </TableCell>
                <TableCell>{sourceModeLabel(row.dataSourceType ?? "")}</TableCell>
                <TableCell>{evidenceCount ? `${evidenceCount} 份` : "未关联"}</TableCell>
                <TableCell>
                  <StatusBadge status={hasError ? "rejected" : hasWarning ? "pending" : "approved"} label={hasError ? "错误" : hasWarning ? "警告" : "有效"} />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}

function ParameterPreviewTable({ preview, methodFormula }: { preview: GhgImportBatch; methodFormula?: string }) {
  return (
    <AdminPanel title="方法与参数解析" actions={methodFormula ? <span className="text-muted-foreground text-xs">{methodFormula}</span> : undefined} contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>参数集</TableHead>
            <TableHead>参数</TableHead>
            <TableHead className="text-right">采用值</TableHead>
            <TableHead>来源类型</TableHead>
            <TableHead>来源 / 版本</TableHead>
            <TableHead>标准 / 条款</TableHead>
            <TableHead>证据</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.preview.parameters.map((row) => (
            <TableRow key={`${row._row_number}-${row.parameterSetCode}-${row.parameterCode}`}>
              <TableCell>{row.parameterSetCode}</TableCell>
              <TableCell>
                <div className="font-medium">{row.parameterName}</div>
                <div className="text-muted-foreground text-xs">{row.parameterCode}</div>
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {row.value} {row.unit}
              </TableCell>
              <TableCell>{sourceModeLabel(row.sourceMode ?? "")}</TableCell>
              <TableCell>
                <div>{row.sourceName}</div>
                <div className="text-muted-foreground text-xs">{row.sourceVersion ?? "-"}</div>
              </TableCell>
              <TableCell>
                <div>{row.standardCode ?? "-"}</div>
                <div className="text-muted-foreground text-xs">{row.clauseReference ?? "-"}</div>
              </TableCell>
              <TableCell>{row.evidenceCode ?? "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}

function EvidencePreviewTable({ preview }: { preview: GhgImportBatch }) {
  return (
    <AdminPanel title="证据覆盖" contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>证据编号</TableHead>
            <TableHead>文件</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>出具机构</TableHead>
            <TableHead>有效期</TableHead>
            <TableHead>审核状态</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.preview.evidence.length ? (
            preview.preview.evidence.map((row) => (
              <TableRow key={row.evidenceCode}>
                <TableCell className="font-medium">{row.evidenceCode}</TableCell>
                <TableCell>{row.fileName}</TableCell>
                <TableCell>{row.documentType}</TableCell>
                <TableCell>{row.issuer ?? "-"}</TableCell>
                <TableCell>{row.validTo ?? "-"}</TableCell>
                <TableCell>
                  <StatusBadge status={row.verificationStatus === "verified" ? "approved" : "pending"} label={row.verificationStatus === "verified" ? "已核验" : "待核验"} />
                </TableCell>
              </TableRow>
            ))
          ) : (
            <AdminTableStateRow colSpan={6}>未登记证据文件</AdminTableStateRow>
          )}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}

function IssueTable({ preview }: { preview: GhgImportBatch }) {
  const [severity, setSeverity] = useState("all")
  const issues = preview.preview.issues.filter((issue) => severity === "all" || issue.severity === severity)

  const downloadIssues = () => {
    const header = ["级别", "工作表", "行号", "字段", "错误代码", "问题", "当前值", "修复建议"]
    const rows = issues.map((issue) => [
      issue.severity,
      issue.sheetName,
      issue.rowNumber ?? "",
      issue.fieldCode ?? "",
      issue.issueCode,
      issue.message,
      issue.currentValue ?? "",
      issue.suggestion ?? "",
    ])
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n")
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }))
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${preview.batchCode}_校验问题.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <AdminPanel
      title="校验问题"
      contentClassName="p-0"
      actions={
        <div className="flex items-center gap-2">
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部级别</SelectItem>
              <SelectItem value="error">仅错误</SelectItem>
              <SelectItem value="warning">仅警告</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" disabled={!issues.length} onClick={downloadIssues}>
            <Download />
            下载问题
          </Button>
        </div>
      }
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>级别</TableHead>
            <TableHead>工作表 / 行</TableHead>
            <TableHead>字段</TableHead>
            <TableHead>问题</TableHead>
            <TableHead>当前值</TableHead>
            <TableHead>修复建议</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {issues.length ? (
            issues.map((issue, index) => (
              <TableRow key={`${issue.issueCode}-${issue.rowNumber}-${index}`}>
                <TableCell>
                  <Badge variant={issue.severity === "error" ? "destructive" : "outline"}>
                    {issue.severity === "error" ? "错误" : issue.severity === "warning" ? "警告" : "提示"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {issue.sheetName}
                  {issue.rowNumber ? ` / ${issue.rowNumber}` : ""}
                </TableCell>
                <TableCell>{issue.fieldCode ?? "-"}</TableCell>
                <TableCell>
                  <div>{issue.message}</div>
                  <div className="text-muted-foreground text-xs">{issue.issueCode}</div>
                </TableCell>
                <TableCell>{issue.currentValue ?? "-"}</TableCell>
                <TableCell>{issue.suggestion ?? "-"}</TableCell>
              </TableRow>
            ))
          ) : (
            <AdminTableStateRow colSpan={6}>预检未发现问题</AdminTableStateRow>
          )}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}

function sourceModeLabel(value: string) {
  return (
    (
      {
        measured: "实测",
        ledger: "台账",
        supplier: "供应商",
        estimated: "估算",
        national_default: "国家缺省",
        authority_published: "主管部门发布",
        library: "平台因子库",
        custom_approved: "企业批准",
        migration: "历史数据迁移",
      } as Record<string, string>
    )[value] ?? value
  )
}

function allocationRoleLabel(value: string) {
  return (
    (
      {
        physical_origin: "物理发生地",
        energy_consumption: "能源消费地",
        metering_point: "计量归属",
        waste_generation: "废弃物产生地",
        asset_location: "资产所在地",
        responsibility: "责任归属",
        beneficiary: "受益区域",
        organization_root: "组织根节点",
      } as Record<string, string>
    )[value] ?? value
  )
}

function formatAllocationRatio(value: string | number | null | undefined) {
  const ratio = Number(value ?? 0)
  return Number.isFinite(ratio) ? `${(ratio * 100).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}%` : "-"
}

function csvCell(value: string | number) {
  return `"${String(value).replaceAll('"', '""')}"`
}
