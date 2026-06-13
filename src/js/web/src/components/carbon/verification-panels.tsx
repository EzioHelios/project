import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, FileText, PackageCheck, ShieldCheck, TriangleAlert } from "lucide-react"
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
    record_id?: number | null
    scope?: string | null
    display_name: string
    period?: string | null
    path?: string | null
    material_status: string
    attachment_type?: string | null
    file_name?: string | null
    sha256?: string | null
    source?: string | null
  }[]
  missing: {
    record_type: string
    record_id: number
    scope: string
    display_name: string
    period?: string | null
    material_status: string
  }[]
  summary: { evidence_count: number; attachment_count: number; missing_evidence_count: number; record_count: number }
}

type VerificationAttachment = {
  id: number
  attachment_no: string
  material_group: string
  attachment_type: string
  title: string
  source_object_type: string
  source_object_id?: number | null
  source_object_label?: string | null
  source_scope?: string | null
  source_period?: string | null
  file_name?: string | null
  file_path?: string | null
  file_size_bytes?: number | null
  sha256?: string | null
  status: string
  material_status: string
}

type VerificationAttachments = {
  items: VerificationAttachment[]
  total: number
  summary: {
    total: number
    by_status: Record<string, number>
    by_group: Record<string, number>
    ready_count: number
    pending_count: number
  }
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

type VerificationFinding = {
  id: number
  finding_no: string
  issue_type: string
  finding_type: string
  severity: string
  title: string
  description?: string | null
  action_required?: string | null
  record_type?: string | null
  record_id?: number | null
  scope?: string | null
  display_name?: string | null
  period?: string | null
  status: string
  owner?: string | null
  due_date?: string | null
  correction_comment?: string | null
  correction_evidence?: string | null
  reviewer?: string | null
  reviewed_at?: string | null
  closed_at?: string | null
}

type VerificationFindings = {
  items: VerificationFinding[]
  total: number
  summary: {
    total: number
    by_status: Record<string, number>
    by_severity: Record<string, number>
    open_count: number
    readiness: string
  }
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
  template: TemplateVersion
  standard: { name: string; code: string; source_name: string }
  inventory: {
    totals: { total_t_co2e: number; total_kg_co2e: number }
    source_summary: { scope: string; record_label: string; record_count: number; t_co2e: number }[]
  }
  export_fields: { field: string; source: string }[]
}

type TemplateVersions = {
  items: TemplateVersion[]
  active?: TemplateVersion | null
  total: number
  limit: number
  offset: number
}

type TemplateVersion = {
  id?: number | null
  template_code: string
  template_name: string
  name: string
  version: string
  format: string
  template_format: string
  path: string
  template_path: string
  applicable_industry?: string | null
  applicable_scope?: string | null
  standard_name?: string | null
  standard_code?: string | null
  source_name?: string | null
  status: string
  is_default: boolean
  effective_from?: string | null
  effective_to?: string | null
  confidence_level?: string | null
  remark?: string | null
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
  project_id?: number | null
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

type VerificationProjects = {
  items: VerificationProject[]
  total: number
  summary: {
    total: number
    by_status: Record<string, number>
    active_count: number
    completed_count: number
  }
}

type VerificationProject = {
  id: number
  project_no: string
  project_name: string
  project_type: string
  status: string
  verification_year?: number | null
  reporting_org_name?: string | null
  period_name?: string | null
  boundary_name?: string | null
  batch_name?: string | null
  template_name?: string | null
  template_version?: string | null
  planned_start?: string | null
  planned_end?: string | null
  started_at?: string | null
  completed_at?: string | null
  lead_reviewer?: string | null
  responsible_person?: string | null
  verifier_org?: string | null
  readiness_status: string
  conclusion?: string | null
  finding_summary?: Record<string, number> | null
  artifact_counts: {
    finding_count: number
    open_finding_count: number
    attachment_count: number
    export_count: number
  }
}

export function VerificationProjectsPanel() {
  const queryClient = useQueryClient()
  const projectsQuery = useQuery<ApiEnvelope<VerificationProjects>>({
    queryKey: ["carbon-verification", "projects"],
    queryFn: () => fetchCarbonApi<VerificationProjects>("/api/carbon/verification/projects?limit=100"),
  })
  const createProject = useMutation({
    mutationFn: () => {
      const name = window.prompt("请输入核查项目名称", `组织碳盘查核查项目 ${new Date().getFullYear()}`)
      if (!name?.trim()) throw new Error("已取消创建")
      const batchId = window.prompt("请输入核算批次ID（可选）", "")
      return postCarbonApi<VerificationProject>("/api/carbon/verification/projects", {
        project_name: name.trim(),
        accounting_batch_id: batchId?.trim() ? Number(batchId.trim()) : undefined,
      })
    },
    onSuccess: () => {
      toast.success("核查项目已创建")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "创建核查项目失败")
    },
  })
  const updateProject = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => patchCarbonApi<VerificationProject>(`/api/carbon/verification/projects/${id}`, data),
    onSuccess: () => {
      toast.success("核查项目已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "更新核查项目失败")
    },
  })
  const refreshProject = useMutation({
    mutationFn: (id: number) => postCarbonApi<VerificationProject>(`/api/carbon/verification/projects/${id}/refresh`, {}),
    onSuccess: () => {
      toast.success("项目状态已刷新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "刷新项目状态失败")
    },
  })
  const createExport = useMutation({
    mutationFn: (project: VerificationProject) =>
      postCarbonApi<ExportJob>("/api/carbon/verification/export-jobs", {
        project_id: project.id,
        export_type: "material_package",
        year: project.verification_year ?? undefined,
      }),
    onSuccess: () => {
      toast.success("项目材料包已生成")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "export-jobs"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "生成项目材料包失败")
    },
  })
  const data = projectsQuery.data?.data
  const projects = data?.items ?? []

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "项目数", value: data?.summary.total ?? 0, icon: ShieldCheck },
          { label: "进行中", value: data?.summary.active_count ?? 0, icon: FileText },
          { label: "已完成", value: data?.summary.completed_count ?? 0, icon: CheckCircle2 },
        ]}
      />
      <div className="flex justify-end">
        <Button onClick={() => createProject.mutate()} disabled={createProject.isPending}>
          创建核查项目
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>项目台账</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>项目</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>模板</TableHead>
                <TableHead>材料</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>就绪</TableHead>
                <TableHead className="w-[260px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell>
                    <div className="font-medium">{project.project_name}</div>
                    <div className="text-xs text-muted-foreground">{project.project_no}</div>
                  </TableCell>
                  <TableCell>
                    <div>{project.reporting_org_name ?? project.batch_name ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{project.period_name ?? project.verification_year ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    <div>{project.template_name ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{project.template_version ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    {project.artifact_counts.attachment_count} 附件 / {project.artifact_counts.finding_count} 发现 / {project.artifact_counts.export_count} 导出
                  </TableCell>
                  <TableCell>
                    <ProjectStatusBadge status={project.status} />
                  </TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={project.readiness_status} />
                  </TableCell>
                  <TableCell>
                    <ProjectActions
                      project={project}
                      onUpdate={(id, patch) => updateProject.mutate({ id, data: patch })}
                      onRefresh={(id) => refreshProject.mutate(id)}
                      onExport={(item) => createExport.mutate(item)}
                      disabled={updateProject.isPending || refreshProject.isPending || createExport.isPending}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {!projects.length ? <EmptyRow colSpan={7} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export function VerificationEvidencePanel() {
  const queryClient = useQueryClient()
  const evidenceQuery = useQuery<ApiEnvelope<EvidenceManifest>>({
    queryKey: ["carbon-verification", "evidence"],
    queryFn: () => fetchCarbonApi<EvidenceManifest>("/api/carbon/verification/evidence?limit=200"),
  })
  const attachmentsQuery = useQuery<ApiEnvelope<VerificationAttachments>>({
    queryKey: ["carbon-verification", "attachments"],
    queryFn: () => fetchCarbonApi<VerificationAttachments>("/api/carbon/verification/attachments?limit=200"),
  })
  const createAttachment = useMutation({
    mutationFn: (record: EvidenceManifest["missing"][number]) => {
      const filePath = window.prompt("请输入凭证文件路径或URL", "")
      if (filePath === null) throw new Error("已取消登记")
      return postCarbonApi<VerificationAttachment>("/api/carbon/verification/attachments", {
        title: `${record.display_name} 凭证`,
        source_object_type: record.record_type,
        source_object_id: record.record_id,
        source_object_label: record.display_name,
        source_scope: record.scope,
        source_period: record.period,
        file_path: filePath.trim() || undefined,
        status: filePath.trim() ? "ready" : "pending_upload",
        source_name: "carbon_verification.evidence_panel",
      })
    },
    onSuccess: () => {
      toast.success("凭证已登记")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "evidence"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "attachments"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "issues"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "登记凭证失败")
    },
  })
  const data = evidenceQuery.data?.data
  const attachments = attachmentsQuery.data?.data

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "凭证数", value: data?.summary.evidence_count ?? 0, icon: FileText },
          { label: "独立附件", value: attachments?.summary.total ?? data?.summary.attachment_count ?? 0, icon: PackageCheck },
          { label: "缺失凭证", value: data?.summary.missing_evidence_count ?? 0, icon: TriangleAlert },
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
                  <TableCell className="max-w-[260px] truncate">{item.path || item.file_name || "-"}</TableCell>
                </TableRow>
              ))}
              {!data?.items?.length ? <EmptyRow colSpan={6} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>缺失凭证</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>范围</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>期间</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="w-[120px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.missing ?? []).map((item) => (
                <TableRow key={`${item.record_type}-${item.record_id}`}>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.display_name}</TableCell>
                  <TableCell>{item.period ?? "-"}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.material_status} />
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" onClick={() => createAttachment.mutate(item)} disabled={createAttachment.isPending}>
                      登记
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.missing?.length ? <EmptyRow colSpan={5} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>附件台账</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>编号</TableHead>
                <TableHead>标题</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>文件</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(attachments?.items ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-[180px] truncate">{item.attachment_no}</TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell>{item.source_object_label ?? item.source_object_type}</TableCell>
                  <TableCell>{attachmentTypeLabel(item.attachment_type)}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.material_status} />
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate">{item.file_path || item.file_name || "-"}</TableCell>
                </TableRow>
              ))}
              {!attachments?.items?.length ? <EmptyRow colSpan={6} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export function VerificationIssuesPanel() {
  const queryClient = useQueryClient()
  const issuesQuery = useQuery<ApiEnvelope<VerificationIssues>>({
    queryKey: ["carbon-verification", "issues"],
    queryFn: () => fetchCarbonApi<VerificationIssues>("/api/carbon/verification/issues?limit=200"),
  })
  const findingsQuery = useQuery<ApiEnvelope<VerificationFindings>>({
    queryKey: ["carbon-verification", "findings"],
    queryFn: () => fetchCarbonApi<VerificationFindings>("/api/carbon/verification/findings?limit=200"),
  })
  const createFinding = useMutation({
    mutationFn: (issue: VerificationIssue) =>
      postCarbonApi<VerificationFinding>("/api/carbon/verification/findings", {
        issue_type: issue.issue_type,
        severity: issue.severity,
        title: issue.title,
        description: issue.display_name,
        action_required: issue.action,
        record_type: issue.record_type,
        record_id: issue.record_id,
        scope: issue.scope,
        display_name: issue.display_name,
        period: issue.period,
        source_name: "carbon_verification.auto_issue",
        source_payload: issue,
      }),
    onSuccess: () => {
      toast.success("已升级为核查发现")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "findings"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "创建核查发现失败")
    },
  })
  const updateFinding = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => patchCarbonApi<VerificationFinding>(`/api/carbon/verification/findings/${id}`, data),
    onSuccess: () => {
      toast.success("核查发现已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "findings"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "更新核查发现失败")
    },
  })
  const data = issuesQuery.data?.data
  const findings = findingsQuery.data?.data

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "自动问题", value: data?.total ?? 0, icon: TriangleAlert },
          { label: "核查发现", value: findings?.summary.total ?? 0, icon: ShieldCheck },
          { label: "待整改", value: findings?.summary.open_count ?? 0, icon: CheckCircle2 },
        ]}
      />
      <Card>
        <CardHeader>
          <CardTitle>自动问题</CardTitle>
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
                <TableHead className="w-[96px]">发现</TableHead>
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
                  <TableCell>
                    <Button variant="outline" size="sm" onClick={() => createFinding.mutate(item)} disabled={createFinding.isPending}>
                      升级
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.items?.length ? <EmptyRow colSpan={7} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>核查发现</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>编号</TableHead>
                <TableHead>发现</TableHead>
                <TableHead>等级</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>整改要求</TableHead>
                <TableHead className="w-[190px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(findings?.items ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-[180px] truncate">{item.finding_no}</TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell>
                    <SeverityBadge severity={item.severity} />
                  </TableCell>
                  <TableCell>{item.display_name ?? item.record_type ?? "-"}</TableCell>
                  <TableCell>
                    <FindingStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell>{item.action_required ?? "-"}</TableCell>
                  <TableCell>
                    <FindingActions finding={item} onUpdate={(id, patch) => updateFinding.mutate({ id, data: patch })} disabled={updateFinding.isPending} />
                  </TableCell>
                </TableRow>
              ))}
              {!findings?.items?.length ? <EmptyRow colSpan={7} /> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
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
  const templatesQuery = useQuery<ApiEnvelope<TemplateVersions>>({
    queryKey: ["carbon-verification", "templates"],
    queryFn: () => fetchCarbonApi<TemplateVersions>("/api/carbon/verification/templates?limit=50"),
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
  const ensureTemplate = useMutation({
    mutationFn: () => postCarbonApi<TemplateVersion>("/api/carbon/verification/templates/ensure-default", {}),
    onSuccess: () => {
      toast.success("默认模板已登记")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "templates"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "report"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "summary"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "登记默认模板失败")
    },
  })
  const updateTemplate = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => patchCarbonApi<TemplateVersion>(`/api/carbon/verification/templates/${id}`, data),
    onSuccess: () => {
      toast.success("模板版本已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "templates"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "report"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "summary"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "更新模板版本失败")
    },
  })
  const summary = summaryQuery.data?.data
  const report = reportQuery.data?.data
  const jobs = jobsQuery.data?.data.items ?? []
  const templates = templatesQuery.data?.data
  const templateRows = templates?.items.length ? templates.items : templates?.active ? [templates.active] : []

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
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>报告模板版本</CardTitle>
          <Button variant="outline" size="sm" onClick={() => ensureTemplate.mutate()} disabled={ensureTemplate.isPending}>
            登记默认模板
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>模板</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>标准</TableHead>
                <TableHead>适用范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>默认</TableHead>
                <TableHead className="w-[190px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templateRows.map((item) => (
                <TableRow key={item.id ?? `${item.template_code}-${item.version}`}>
                  <TableCell>
                    <div className="font-medium">{item.template_name || item.name}</div>
                    <div className="max-w-[320px] truncate text-xs text-muted-foreground">{item.template_path || item.path}</div>
                  </TableCell>
                  <TableCell>{item.version}</TableCell>
                  <TableCell>
                    <div>{item.standard_name ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{item.standard_code ?? "-"}</div>
                  </TableCell>
                  <TableCell>{item.applicable_scope ?? item.applicable_industry ?? "-"}</TableCell>
                  <TableCell>
                    <TemplateStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell>{item.is_default ? "是" : "否"}</TableCell>
                  <TableCell>
                    <TemplateActions
                      template={item}
                      onEnsure={() => ensureTemplate.mutate()}
                      onUpdate={(id, patch) => updateTemplate.mutate({ id, data: patch })}
                      disabled={ensureTemplate.isPending || updateTemplate.isPending}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {!templateRows.length ? <EmptyRow colSpan={7} /> : null}
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
  if (status === "pending_upload") return <Badge variant="secondary">待上传</Badge>
  if (status === "missing_evidence") return <Badge variant="secondary">缺凭证</Badge>
  if (status === "missing_factor") return <Badge variant="destructive">缺因子</Badge>
  if (status === "missing_result") return <Badge variant="destructive">缺结果</Badge>
  if (status === "pending_review") return <CarbonStatusBadge status="pending" />
  if (status === "rejected") return <CarbonStatusBadge status="rejected" />
  return <Badge variant="outline">{status || "无数据"}</Badge>
}

function attachmentTypeLabel(value?: string | null) {
  if (value === "invoice") return "发票"
  if (value === "meter_record") return "计量记录"
  if (value === "calibration_certificate") return "校准证书"
  if (value === "inspection_report") return "检测报告"
  if (value === "other") return "其他"
  return "支撑材料"
}

function SeverityBadge({ severity }: { severity?: string }) {
  if (severity === "high") return <Badge variant="destructive">高</Badge>
  if (severity === "medium") return <Badge variant="secondary">中</Badge>
  return <Badge variant="outline">低</Badge>
}

function FindingStatusBadge({ status }: { status?: string }) {
  if (status === "open") return <Badge variant="secondary">待整改</Badge>
  if (status === "rectifying") return <Badge variant="secondary">整改中</Badge>
  if (status === "resolved") return <Badge>待复核</Badge>
  if (status === "closed") return <Badge variant="outline">已关闭</Badge>
  return <Badge variant="outline">{status || "-"}</Badge>
}

function FindingActions({ finding, onUpdate, disabled }: { finding: VerificationFinding; onUpdate: (id: number, patch: Record<string, unknown>) => void; disabled?: boolean }) {
  if (finding.status === "closed") return <span className="text-muted-foreground">-</span>
  if (finding.status === "resolved") {
    return (
      <Button variant="outline" size="sm" onClick={() => onUpdate(finding.id, { status: "closed", reviewer: "internal_review" })} disabled={disabled}>
        关闭
      </Button>
    )
  }
  if (finding.status === "rectifying") {
    return (
      <Button variant="outline" size="sm" onClick={() => onUpdate(finding.id, { status: "resolved", correction_comment: "已完成整改" })} disabled={disabled}>
        已整改
      </Button>
    )
  }
  return (
    <Button variant="outline" size="sm" onClick={() => onUpdate(finding.id, { status: "rectifying" })} disabled={disabled}>
      整改中
    </Button>
  )
}

function ProjectActions({
  project,
  onUpdate,
  onRefresh,
  onExport,
  disabled,
}: {
  project: VerificationProject
  onUpdate: (id: number, patch: Record<string, unknown>) => void
  onRefresh: (id: number) => void
  onExport: (project: VerificationProject) => void
  disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {project.status === "draft" ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(project.id, { status: "in_progress" })} disabled={disabled}>
          启动
        </Button>
      ) : null}
      {project.status === "in_progress" ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(project.id, { status: "review" })} disabled={disabled}>
          送审
        </Button>
      ) : null}
      {project.status === "review" ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(project.id, { status: "in_progress" })} disabled={disabled}>
          退回
        </Button>
      ) : null}
      {project.status === "in_progress" || project.status === "review" ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(project.id, { status: "completed" })} disabled={disabled}>
          完成
        </Button>
      ) : null}
      {project.status === "completed" ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(project.id, { status: "archived" })} disabled={disabled}>
          归档
        </Button>
      ) : null}
      <Button variant="outline" size="sm" onClick={() => onRefresh(project.id)} disabled={disabled}>
        刷新
      </Button>
      <Button variant="outline" size="sm" onClick={() => onExport(project)} disabled={disabled}>
        生成包
      </Button>
    </div>
  )
}

function ProjectStatusBadge({ status }: { status?: string }) {
  if (status === "draft") return <Badge variant="outline">草稿</Badge>
  if (status === "in_progress") return <Badge variant="secondary">进行中</Badge>
  if (status === "review") return <Badge>复核中</Badge>
  if (status === "completed") return <Badge>已完成</Badge>
  if (status === "archived") return <Badge variant="outline">已归档</Badge>
  return <Badge variant="outline">{status || "-"}</Badge>
}

function TemplateActions({
  template,
  onEnsure,
  onUpdate,
  disabled,
}: {
  template: TemplateVersion
  onEnsure: () => void
  onUpdate: (id: number, patch: Record<string, unknown>) => void
  disabled?: boolean
}) {
  if (!template.id) {
    return (
      <Button variant="outline" size="sm" onClick={onEnsure} disabled={disabled}>
        登记
      </Button>
    )
  }
  return (
    <div className="flex flex-wrap gap-2">
      {!template.is_default ? (
        <Button variant="outline" size="sm" onClick={() => onUpdate(template.id as number, { is_default: true, status: "active" })} disabled={disabled}>
          设默认
        </Button>
      ) : null}
      <Button variant="outline" size="sm" onClick={() => onUpdate(template.id as number, { status: template.status === "active" ? "disabled" : "active" })} disabled={disabled}>
        {template.status === "active" ? "停用" : "启用"}
      </Button>
    </div>
  )
}

function TemplateStatusBadge({ status }: { status?: string }) {
  if (status === "active") return <Badge>启用</Badge>
  if (status === "disabled") return <Badge variant="secondary">停用</Badge>
  if (status === "draft") return <Badge variant="outline">草稿</Badge>
  return <Badge variant="outline">{status || "-"}</Badge>
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

async function patchCarbonApi<T>(url: string, body: Record<string, unknown>) {
  const res = await fetch(url, {
    method: "PATCH",
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
