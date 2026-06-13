import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FileText, PackageCheck, ShieldCheck, TriangleAlert } from "lucide-react"
import { toast } from "sonner"

import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type VerificationSummary = {
  enterprise?: { name?: string | null; unify_code?: string | null; industry?: string | null } | null
  reporting_period: { year?: number | null; period_start?: string | null; period_end?: string | null }
  totals: { total_kg_co2e: number; total_t_co2e: number; missing_result_count: number }
  scope_summary: { scope: string; record_count: number; kg_co2e: number; t_co2e: number }[]
  record_count: number
  issue_count: number
  readiness: string
  template: { name: string; path: string }
}

type EvidenceManifest = {
  items: {
    evidence_code: string
    record_type: string
    record_id: number
    scope: string
    display_name: string
    period?: string | null
    path: string
    material_status: string
  }[]
  missing: {
    record_type: string
    record_id: number
    scope: string
    display_name: string
    period?: string | null
    material_status: string
  }[]
  summary: { evidence_count: number; missing_evidence_count: number; record_count: number }
}

type VerificationIssue = {
  issue_type: string
  severity: string
  title: string
  record_type: string
  record_id: number
  scope: string
  display_name: string
  period?: string | null
  action: string
}

type VerificationIssues = {
  items: VerificationIssue[]
  total: number
  summary: Record<string, number>
}

type MaterialPackage = {
  package_code: string
  readiness: string
  groups: {
    code: string
    title: string
    material_group: string
    required: boolean
    item_count: number
    status: string
  }[]
  manifest: { path: string; type: string; source: unknown }[]
}

type ReportContext = {
  template: { name: string; path: string; format: string }
  standard: { name: string; code: string; source_name: string }
  inventory: {
    totals: { total_t_co2e: number; total_kg_co2e: number }
    source_summary: { scope: string; record_label: string; record_count: number; t_co2e: number }[]
  }
  export_fields: { field: string; source: string }[]
}

type ExportJobs = {
  items: ExportJob[]
  total: number
  limit: number
  offset: number
}

type ExportJob = {
  id: number
  job_no: string
  export_type: string
  report_year?: number | null
  scope_filter?: string | null
  status_filter?: string | null
  status: string
  file_size_bytes?: number | null
  file_sha256?: string | null
  completed_at?: string | null
  created_at?: string | null
  download_url?: string | null
}

export function VerificationEvidencePanel() {
  const evidenceQuery = useQuery<ApiEnvelope<EvidenceManifest>>({
    queryKey: ["carbon-verification", "evidence"],
    queryFn: () => fetchCarbonApi<EvidenceManifest>("/api/carbon/verification/evidence?limit=200"),
  })
  const data = evidenceQuery.data?.data

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "凭证数", value: data?.summary.evidence_count ?? 0, icon: FileText },
          { label: "缺失凭证", value: data?.summary.missing_evidence_count ?? 0, icon: TriangleAlert },
          { label: "关联记录", value: data?.summary.record_count ?? 0, icon: ShieldCheck },
        ]}
      />
      <Card>
        <CardHeader>
          <CardTitle>凭证清单</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>凭证编号</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>期间</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>路径</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.items ?? []).map((item) => (
                <TableRow key={item.evidence_code}>
                  <TableCell>{item.evidence_code}</TableCell>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.display_name}</TableCell>
                  <TableCell>{item.period ?? "-"}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.material_status} />
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate">{item.path}</TableCell>
                </TableRow>
              ))}
              {!data?.items?.length ? <EmptyRow colSpan={6} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export function VerificationIssuesPanel() {
  const issuesQuery = useQuery<ApiEnvelope<VerificationIssues>>({
    queryKey: ["carbon-verification", "issues"],
    queryFn: () => fetchCarbonApi<VerificationIssues>("/api/carbon/verification/issues?limit=200"),
  })
  const data = issuesQuery.data?.data

  return (
    <Card>
      <CardHeader>
        <CardTitle>核查问题</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>问题</TableHead>
              <TableHead>等级</TableHead>
              <TableHead>范围</TableHead>
              <TableHead>对象</TableHead>
              <TableHead>期间</TableHead>
              <TableHead>处理动作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.items ?? []).map((item) => (
              <TableRow key={`${item.record_type}-${item.record_id}-${item.issue_type}`}>
                <TableCell>{item.title}</TableCell>
                <TableCell>
                  <SeverityBadge severity={item.severity} />
                </TableCell>
                <TableCell>{item.scope}</TableCell>
                <TableCell>{item.display_name}</TableCell>
                <TableCell>{item.period ?? "-"}</TableCell>
                <TableCell>{item.action}</TableCell>
              </TableRow>
            ))}
            {!data?.items?.length ? <EmptyRow colSpan={6} /> : null}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function VerificationMaterialPackagePanel() {
  const packageQuery = useQuery<ApiEnvelope<MaterialPackage>>({
    queryKey: ["carbon-verification", "material-package"],
    queryFn: () => fetchCarbonApi<MaterialPackage>("/api/carbon/verification/material-package?limit=200"),
  })
  const data = packageQuery.data?.data

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "材料组", value: data?.groups.length ?? 0, icon: PackageCheck },
          { label: "包状态", value: readinessLabel(data?.readiness), icon: ShieldCheck },
          { label: "清单文件", value: data?.manifest.length ?? 0, icon: FileText },
        ]}
      />
      <Card>
        <CardHeader>
          <CardTitle>材料包目录</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>材料</TableHead>
                <TableHead>分组</TableHead>
                <TableHead>数量</TableHead>
                <TableHead>必需</TableHead>
                <TableHead>状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.groups ?? []).map((group) => (
                <TableRow key={group.code}>
                  <TableCell>{group.title}</TableCell>
                  <TableCell>{group.material_group}</TableCell>
                  <TableCell>{group.item_count}</TableCell>
                  <TableCell>{group.required ? "是" : "否"}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={group.status} />
                  </TableCell>
                </TableRow>
              ))}
              {!data?.groups?.length ? <EmptyRow colSpan={5} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>导出清单</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>路径</TableHead>
                <TableHead>类型</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.manifest ?? []).map((item) => (
                <TableRow key={item.path}>
                  <TableCell>{item.path}</TableCell>
                  <TableCell>{item.type}</TableCell>
                </TableRow>
              ))}
              {!data?.manifest?.length ? <EmptyRow colSpan={2} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export function VerificationReportPanel() {
  const queryClient = useQueryClient()
  const summaryQuery = useQuery<ApiEnvelope<VerificationSummary>>({
    queryKey: ["carbon-verification", "summary"],
    queryFn: () => fetchCarbonApi<VerificationSummary>("/api/carbon/verification/summary"),
  })
  const reportQuery = useQuery<ApiEnvelope<ReportContext>>({
    queryKey: ["carbon-verification", "report"],
    queryFn: () => fetchCarbonApi<ReportContext>("/api/carbon/verification/report?limit=200"),
  })
  const jobsQuery = useQuery<ApiEnvelope<ExportJobs>>({
    queryKey: ["carbon-verification", "export-jobs"],
    queryFn: () => fetchCarbonApi<ExportJobs>("/api/carbon/verification/export-jobs?limit=20"),
  })
  const createExport = useMutation({
    mutationFn: () =>
      postCarbonApi<ExportJob>("/api/carbon/verification/export-jobs", {
        export_type: "material_package",
        year: summaryQuery.data?.data.reporting_period.year ?? undefined,
      }),
    onSuccess: () => {
      toast.success("核查材料包已生成")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "export-jobs"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "导出失败")
    },
  })
  const summary = summaryQuery.data?.data
  const report = reportQuery.data?.data
  const jobs = jobsQuery.data?.data.items ?? []

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "排放量(tCO2e)", value: formatNumber(summary?.totals.total_t_co2e), icon: ShieldCheck },
          { label: "核算记录", value: summary?.record_count ?? 0, icon: FileText },
          { label: "问题数", value: summary?.issue_count ?? 0, icon: TriangleAlert },
        ]}
      />
      <div className="flex justify-end">
        <Button onClick={() => createExport.mutate()} disabled={createExport.isPending}>
          {createExport.isPending ? "生成中" : "生成核查材料包"}
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>报告数据</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>范围</TableHead>
                <TableHead>排放源</TableHead>
                <TableHead>记录数</TableHead>
                <TableHead className="text-right">tCO2e</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(report?.inventory.source_summary ?? []).map((item) => (
                <TableRow key={`${item.scope}-${item.record_label}`}>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.record_label}</TableCell>
                  <TableCell>{item.record_count}</TableCell>
                  <TableCell className="text-right">{formatNumber(item.t_co2e)}</TableCell>
                </TableRow>
              ))}
              {!report?.inventory.source_summary?.length ? <EmptyRow colSpan={4} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>模板字段</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>字段</TableHead>
                <TableHead>来源</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(report?.export_fields ?? []).map((item) => (
                <TableRow key={item.field}>
                  <TableCell>{item.field}</TableCell>
                  <TableCell>{item.source}</TableCell>
                </TableRow>
              ))}
              {!report?.export_fields?.length ? <EmptyRow colSpan={2} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>导出记录</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>任务号</TableHead>
                <TableHead>年度</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>完成时间</TableHead>
                <TableHead>文件</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell className="max-w-[280px] truncate">{job.job_no}</TableCell>
                  <TableCell>{job.report_year ?? "全部"}</TableCell>
                  <TableCell>
                    <ExportJobStatusBadge status={job.status} />
                  </TableCell>
                  <TableCell>{formatBytes(job.file_size_bytes)}</TableCell>
                  <TableCell>{job.completed_at ?? job.created_at ?? "-"}</TableCell>
                  <TableCell>
                    {job.download_url ? (
                      <Button asChild variant="outline" size="sm">
                        <a href={job.download_url}>下载</a>
                      </Button>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {!jobs.length ? <EmptyRow colSpan={6} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string | number; icon: typeof FileText }[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <item.icon className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="text-lg font-semibold">{item.value}</div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function EmptyRow({ colSpan }: { colSpan: number }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="h-20 text-center text-muted-foreground">
        暂无数据
      </TableCell>
    </TableRow>
  )
}

function VerificationStatusBadge({ status }: { status?: string }) {
  if (status === "ready") return <Badge>就绪</Badge>
  if (status === "attention") return <Badge variant="secondary">待完善</Badge>
  if (status === "blocked") return <Badge variant="destructive">阻塞</Badge>
  if (status === "missing_evidence") return <Badge variant="secondary">缺凭证</Badge>
  if (status === "missing_factor") return <Badge variant="destructive">缺因子</Badge>
  if (status === "missing_result") return <Badge variant="destructive">缺结果</Badge>
  if (status === "pending_review") return <CarbonStatusBadge status="pending" />
  if (status === "rejected") return <CarbonStatusBadge status="rejected" />
  return <Badge variant="outline">{status || "无数据"}</Badge>
}

function SeverityBadge({ severity }: { severity?: string }) {
  if (severity === "high") return <Badge variant="destructive">高</Badge>
  if (severity === "medium") return <Badge variant="secondary">中</Badge>
  return <Badge variant="outline">低</Badge>
}

function ExportJobStatusBadge({ status }: { status?: string }) {
  if (status === "completed") return <Badge>已完成</Badge>
  if (status === "running") return <Badge variant="secondary">生成中</Badge>
  if (status === "failed") return <Badge variant="destructive">失败</Badge>
  return <Badge variant="outline">{status || "-"}</Badge>
}

function readinessLabel(value?: string) {
  if (value === "ready") return "就绪"
  if (value === "attention") return "待完善"
  if (value === "blocked") return "阻塞"
  if (value === "empty") return "无数据"
  return value || "-"
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 4 })
}

function formatBytes(value?: number | null) {
  if (!value) return "-"
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

async function postCarbonApi<T>(url: string, body: Record<string, unknown>) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}
