import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, FileText, PackageCheck, ShieldCheck, TriangleAlert } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import type { ApiEnvelope } from "@/components/carbon/analytics-panels"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useGhgInventoryReports } from "@/lib/api/hooks/ghg-inventory"
import {
  carbonVerificationCreateExport,
  carbonVerificationCreateFinding,
  carbonVerificationCreateProject,
  carbonVerificationDownloadEvidence,
  carbonVerificationDownloadExport,
  carbonVerificationEnsureDefaultTemplate,
  carbonVerificationGetAuditTrail,
  carbonVerificationGetMaterialPackage,
  carbonVerificationGetReportContext,
  carbonVerificationGetSummary,
  carbonVerificationListEvidence,
  carbonVerificationListExports,
  carbonVerificationListFindings,
  carbonVerificationListIssues,
  carbonVerificationListProjects,
  carbonVerificationListTemplates,
  carbonVerificationRefreshProject,
  carbonVerificationReviewEvidence,
  carbonVerificationUpdateFinding,
  carbonVerificationUpdateProject,
  carbonVerificationUpdateTemplate,
  carbonVerificationUploadEvidence,
} from "@/lib/generated/api"

type VerificationSummary = {
  project: {
    id: number
    project_no: string
    project_name: string
    report_code: string
    report_version: number
    run_code: string
    conclusion_status: string
  }
  enterprise?: { name?: string | null; unify_code?: string | null; industry?: string | null } | null
  reporting_period: { year?: number | null; period_start?: string | null; period_end?: string | null }
  totals: { total_kg_co2e: number; total_t_co2e: number; missing_result_count: number }
  scope_summary: { scope: string; record_count: number; kg_co2e: number; t_co2e: number }[]
  record_count: number
  issue_count: number
  readiness: string
  template: { name: string; path: string }
}

type VerificationAuditTrail = {
  items: {
    record_type: string
    record_code: string
    action: string
    comment?: string | null
    operator?: string | null
    created_at?: string | null
  }[]
  total: number
}

type EvidenceManifest = {
  items: {
    evidence_code: string
    record_type: string
    record_code: string
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
    record_code: string
    scope: string
    display_name: string
    period?: string | null
    material_status: string
  }[]
  summary: { evidence_count: number; linked_activity_count: number; missing_evidence_count: number; record_count: number }
}

type VerificationIssue = {
  issue_type: string
  severity: string
  title: string
  record_type: string
  record_code: string
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
  record_code?: string | null
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
  formal_readiness: {
    status: string
    blocking_count: number
    warning_count: number
    checks: { code: string; label: string; status: string; detail?: string | null }[]
  }
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
  report_purpose?: string | null
  technical_spec_code?: string | null
  implementation_status?: string | null
  schema_version?: string | null
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
  inventory_report_id?: number | null
  report_code?: string | null
  report_version?: number | null
  report_title?: string | null
  report_status?: string | null
  run_code?: string | null
  inventory_code?: string | null
  template_name?: string | null
  template_version?: string | null
  planned_start?: string | null
  planned_end?: string | null
  started_at?: string | null
  completed_at?: string | null
  lead_reviewer?: string | null
  responsible_person?: string | null
  verifier_org?: string | null
  assurance_level: string
  materiality_threshold_pct?: string | null
  verification_basis?: string | null
  sampling_strategy?: string | null
  site_visit_required: boolean
  site_visit_status: string
  conclusion_status: string
  readiness_status: string
  conclusion?: string | null
  finding_summary?: Record<string, number> | null
  artifact_counts: {
    finding_count: number
    open_finding_count: number
    evidence_count: number
    export_count: number
  }
}

export function VerificationProjectsPanel({ selectedProjectId, onProjectSelect }: { selectedProjectId?: number; onProjectSelect: (projectId: number) => void }) {
  const queryClient = useQueryClient()
  const reports = useGhgInventoryReports()
  const [projectName, setProjectName] = useState("")
  const [reportId, setReportId] = useState<number>()
  const projectsQuery = useQuery<ApiEnvelope<VerificationProjects>>({
    queryKey: ["carbon-verification", "projects"],
    queryFn: () => generatedEnvelope<VerificationProjects>(carbonVerificationListProjects({ query: { limit: 100 } })),
  })
  const createProject = useMutation({
    mutationFn: () => {
      if (!projectName.trim() || !reportId) throw new Error("请选择已发布报告并填写项目名称")
      return generatedEnvelope<VerificationProject>(
        carbonVerificationCreateProject({
          body: {
            project_name: projectName.trim(),
            inventory_report_id: reportId,
            assurance_level: "internal_review",
            verification_basis: "ISO 14064-3:2019",
          },
        }),
      )
    },
    onSuccess: (result) => {
      toast.success("核查项目已创建")
      const id = result.data?.id
      if (id) onProjectSelect(id)
      setProjectName("")
      setReportId(undefined)
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "创建核查项目失败")
    },
  })
  const updateProject = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      generatedEnvelope<VerificationProject>(carbonVerificationUpdateProject({ path: { project_id: id }, body: data })),
    onSuccess: () => {
      toast.success("核查项目已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "更新核查项目失败")
    },
  })
  const refreshProject = useMutation({
    mutationFn: (id: number) => generatedEnvelope<VerificationProject>(carbonVerificationRefreshProject({ path: { project_id: id } })),
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
      generatedEnvelope<ExportJob>(
        carbonVerificationCreateExport({
          body: {
            project_id: project.id,
            export_type: "material_package",
            year: project.verification_year ?? undefined,
          },
        }),
      ),
    onSuccess: () => {
      toast.success("项目材料包生成任务已提交")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "export-jobs"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "生成项目材料包失败")
    },
  })
  const data = projectsQuery.data?.data
  const projects = data?.items ?? []
  const selectedProject = projects.find((item) => item.id === selectedProjectId)

  useEffect(() => {
    if (selectedProjectId || !projects.length) return
    const defaultProject = projects.find((item) => item.inventory_report_id && item.status !== "archived")
    if (defaultProject) onProjectSelect(defaultProject.id)
  }, [onProjectSelect, projects, selectedProjectId])

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "项目数", value: data?.summary.total ?? 0, icon: ShieldCheck },
          { label: "进行中", value: data?.summary.active_count ?? 0, icon: FileText },
          { label: "已完成", value: data?.summary.completed_count ?? 0, icon: CheckCircle2 },
        ]}
      />
      <div className="space-y-2">
        <div className="grid w-full gap-2 md:grid-cols-2">
          <select
            className="h-9 min-w-0 rounded-md border bg-background px-3 text-sm"
            value={reportId ?? ""}
            onChange={(event) => setReportId(event.target.value ? Number(event.target.value) : undefined)}
          >
            <option value="">选择已发布盘查报告</option>
            {(reports.data?.items ?? [])
              .filter((item) => item.status === "published")
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} · v{item.version}
                </option>
              ))}
          </select>
          <input
            className="h-9 min-w-0 rounded-md border bg-background px-3 text-sm"
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            placeholder="核查项目名称"
          />
        </div>
        <div className="flex justify-start">
          <Button onClick={() => createProject.mutate()} disabled={createProject.isPending || !reportId || !projectName.trim()}>
            创建核查项目
          </Button>
        </div>
      </div>
      {selectedProject ? (
        <VerificationProjectPlanEditor
          project={selectedProject}
          disabled={updateProject.isPending}
          onSave={(patch) => updateProject.mutate({ id: selectedProject.id, data: patch })}
        />
      ) : null}
      <AdminPanel title="项目台账" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>项目</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>模板</TableHead>
                <TableHead>清单</TableHead>
                <TableHead>材料</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>就绪</TableHead>
                <TableHead className="w-[260px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map((project) => (
                <TableRow
                  key={project.id}
                  data-state={selectedProjectId === project.id ? "selected" : undefined}
                  className={project.inventory_report_id ? "cursor-pointer" : "text-muted-foreground"}
                  onClick={() => {
                    if (project.inventory_report_id) onProjectSelect(project.id)
                  }}
                >
                  <TableCell>
                    <div className="font-medium">{project.project_name}</div>
                    <div className="text-xs text-muted-foreground">{project.project_no}</div>
                  </TableCell>
                  <TableCell>
                    <div>{project.reporting_org_name ?? project.report_title ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{project.period_name ?? project.verification_year ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    <div>{project.template_name ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{project.template_version ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    <ReportBindingBadge project={project} />
                  </TableCell>
                  <TableCell>
                    {project.artifact_counts.evidence_count} 证据 / {project.artifact_counts.finding_count} 发现 / {project.artifact_counts.export_count} 导出
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
              {!projects.length ? <EmptyRow colSpan={8} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

function VerificationProjectPlanEditor({ project, onSave, disabled }: { project: VerificationProject; onSave: (patch: Record<string, unknown>) => void; disabled?: boolean }) {
  return (
    <AdminPanel title="核查方案">
      <form
        key={project.id}
        className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"
        onSubmit={(event) => {
          event.preventDefault()
          const form = new FormData(event.currentTarget)
          onSave({
            assurance_level: form.get("assurance_level"),
            materiality_threshold_pct: form.get("materiality_threshold_pct") || null,
            verification_basis: form.get("verification_basis") || null,
            sampling_strategy: form.get("sampling_strategy") || null,
            conclusion: form.get("conclusion") || null,
            site_visit_required: form.get("site_visit_required") === "on",
            site_visit_status: form.get("site_visit_status"),
          })
        }}
      >
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">保证等级</span>
          <select name="assurance_level" defaultValue={project.assurance_level} className="h-9 w-full rounded-md border bg-background px-3">
            <option value="internal_review">内部复核</option>
            <option value="limited">有限保证</option>
            <option value="reasonable">合理保证</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">重要性水平（%）</span>
          <input
            name="materiality_threshold_pct"
            type="number"
            min="0.0001"
            max="100"
            step="0.0001"
            defaultValue={project.materiality_threshold_pct ?? ""}
            className="h-9 w-full rounded-md border bg-background px-3"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">核查依据</span>
          <input name="verification_basis" defaultValue={project.verification_basis ?? "ISO 14064-3:2019"} className="h-9 w-full rounded-md border bg-background px-3" />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">现场核查状态</span>
          <select name="site_visit_status" defaultValue={project.site_visit_status} className="h-9 w-full rounded-md border bg-background px-3">
            <option value="not_planned">未计划</option>
            <option value="planned">已计划</option>
            <option value="completed">已完成</option>
            <option value="waived">已豁免</option>
          </select>
        </label>
        <label className="space-y-1 text-sm md:col-span-2">
          <span className="text-muted-foreground">抽样策略</span>
          <input name="sampling_strategy" defaultValue={project.sampling_strategy ?? ""} className="h-9 w-full rounded-md border bg-background px-3" />
        </label>
        <label className="space-y-1 text-sm md:col-span-2">
          <span className="text-muted-foreground">核查结论</span>
          <input name="conclusion" defaultValue={project.conclusion ?? ""} className="h-9 w-full rounded-md border bg-background px-3" />
        </label>
        <div className="flex items-end justify-between gap-3">
          <label className="flex h-9 items-center gap-2 text-sm">
            <input name="site_visit_required" type="checkbox" defaultChecked={project.site_visit_required} />
            需要现场核查
          </label>
          <Button type="submit" disabled={disabled || project.status === "completed" || project.status === "archived"}>
            保存方案
          </Button>
        </div>
      </form>
    </AdminPanel>
  )
}

export function VerificationEvidencePanel({ projectId }: { projectId?: number }) {
  const queryClient = useQueryClient()
  const evidenceQuery = useQuery<ApiEnvelope<EvidenceManifest>>({
    queryKey: ["carbon-verification", "evidence", projectId],
    queryFn: () => generatedEnvelope<EvidenceManifest>(carbonVerificationListEvidence({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const uploadEvidence = useMutation({
    mutationFn: ({ record, file }: { record: EvidenceManifest["missing"][number]; file: File }) => {
      if (!projectId) throw new Error("请先选择核查项目")
      return generatedEnvelope(
        carbonVerificationUploadEvidence({
          query: {
            project_id: projectId,
            record_type: record.record_type,
            record_code: record.record_code,
            evidence_role: "activity_evidence",
            document_type: file.type || "application/octet-stream",
          },
          body: { file },
        }),
      )
    },
    onSuccess: () => {
      toast.success("证据文件已上传")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "evidence"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "issues"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "上传证据失败")
    },
  })
  const reviewEvidence = useMutation({
    mutationFn: ({ evidenceCode, decision }: { evidenceCode: string; decision: "approved" | "rejected" }) => {
      if (!projectId) throw new Error("请先选择核查项目")
      return generatedEnvelope(carbonVerificationReviewEvidence({ path: { evidence_code: evidenceCode }, query: { project_id: projectId }, body: { decision } }))
    },
    onSuccess: () => {
      toast.success("证据复核状态已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "evidence"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "issues"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
  })
  const data = evidenceQuery.data?.data

  if (!projectId) return <ProjectSelectionRequired />

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "凭证数", value: data?.summary.evidence_count ?? 0, icon: FileText },
          { label: "已关联活动", value: data?.summary.linked_activity_count ?? 0, icon: PackageCheck },
          { label: "缺失凭证", value: data?.summary.missing_evidence_count ?? 0, icon: TriangleAlert },
        ]}
      />
      <AdminPanel title="凭证清单" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>凭证编号</TableHead>
                <TableHead>范围</TableHead>
                <TableHead>对象</TableHead>
                <TableHead>期间</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>文件</TableHead>
                <TableHead className="w-[180px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.items ?? []).map((item) => (
                <TableRow key={`${item.evidence_code}-${item.record_type}-${item.record_code}`}>
                  <TableCell>{item.evidence_code}</TableCell>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.display_name}</TableCell>
                  <TableCell>{item.period ?? "-"}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.material_status} />
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate">{item.path || item.file_name || "-"}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" onClick={() => void downloadEvidence(item.evidence_code)}>
                        下载
                      </Button>
                      {item.material_status !== "ready" ? (
                        <Button variant="outline" size="sm" onClick={() => reviewEvidence.mutate({ evidenceCode: item.evidence_code, decision: "approved" })}>
                          通过
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.items?.length ? <EmptyRow colSpan={7} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="缺失凭证" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
                <TableRow key={`${item.record_type}-${item.record_code}`}>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell>{item.display_name}</TableCell>
                  <TableCell>{item.period ?? "-"}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.material_status} />
                  </TableCell>
                  <TableCell>
                    <label className="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm hover:bg-muted">
                      上传
                      <input
                        className="sr-only"
                        type="file"
                        accept=".pdf,.xlsx,.docx,.png,.jpg,.jpeg,.csv,.txt"
                        disabled={!projectId || uploadEvidence.isPending}
                        onChange={(event) => {
                          const file = event.target.files?.[0]
                          if (file) uploadEvidence.mutate({ record: item, file })
                          event.currentTarget.value = ""
                        }}
                      />
                    </label>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.missing?.length ? <EmptyRow colSpan={5} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

export function VerificationTracePanel({ projectId }: { projectId?: number }) {
  const summaryQuery = useQuery<ApiEnvelope<VerificationSummary>>({
    queryKey: ["carbon-verification", "summary", projectId],
    queryFn: () => generatedEnvelope<VerificationSummary>(carbonVerificationGetSummary({ query: { project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const evidenceQuery = useQuery<ApiEnvelope<EvidenceManifest>>({
    queryKey: ["carbon-verification", "evidence", projectId],
    queryFn: () => generatedEnvelope<EvidenceManifest>(carbonVerificationListEvidence({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const findingsQuery = useQuery<ApiEnvelope<VerificationFindings>>({
    queryKey: ["carbon-verification", "findings", projectId],
    queryFn: () => generatedEnvelope<VerificationFindings>(carbonVerificationListFindings({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  if (!projectId) return <ProjectSelectionRequired />
  const summary = summaryQuery.data?.data
  const evidence = evidenceQuery.data?.data
  const findings = findingsQuery.data?.data
  const stages = [
    { name: "盘查报告", reference: summary?.project.report_code, status: summary ? "ready" : "blocked" },
    { name: "核算运行", reference: summary?.project.run_code, status: summary ? "ready" : "blocked" },
    {
      name: "证据资料",
      reference: `${evidence?.summary.linked_activity_count ?? 0}/${evidence?.summary.record_count ?? 0}`,
      status: evidence?.summary.missing_evidence_count === 0 ? "ready" : "attention",
    },
    {
      name: "核查发现",
      reference: `${findings?.summary.open_count ?? 0} 项待处理`,
      status: findings?.summary.open_count === 0 ? "ready" : "attention",
    },
    {
      name: "核查结论",
      reference: summary?.project.conclusion_status ?? "pending",
      status: summary?.project.conclusion_status === "approved" ? "ready" : "attention",
    },
  ]
  return (
    <AdminPanel title="核查链路" contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>阶段</TableHead>
              <TableHead>业务编号</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stages.map((stage) => (
              <TableRow key={stage.name}>
                <TableCell className="font-medium">{stage.name}</TableCell>
                <TableCell>{stage.reference ?? "-"}</TableCell>
                <TableCell>
                  <VerificationStatusBadge status={stage.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

export function VerificationAuditPanel({ projectId }: { projectId?: number }) {
  const query = useQuery<ApiEnvelope<VerificationAuditTrail>>({
    queryKey: ["carbon-verification", "audit-trail", projectId],
    queryFn: () => generatedEnvelope<VerificationAuditTrail>(carbonVerificationGetAuditTrail({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  if (!projectId) return <ProjectSelectionRequired />
  const items = query.data?.data.items ?? []
  return (
    <AdminPanel title="审核日志" contentClassName="p-0">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>时间</TableHead>
              <TableHead>对象</TableHead>
              <TableHead>编号</TableHead>
              <TableHead>动作</TableHead>
              <TableHead>操作人</TableHead>
              <TableHead>意见</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, index) => (
              <TableRow key={`${item.record_type}-${item.record_code}-${item.created_at}-${index}`}>
                <TableCell>{formatDateTime(item.created_at)}</TableCell>
                <TableCell>{auditObjectLabel(item.record_type)}</TableCell>
                <TableCell>{item.record_code}</TableCell>
                <TableCell>{item.action}</TableCell>
                <TableCell>{item.operator ?? "-"}</TableCell>
                <TableCell>{item.comment ?? "-"}</TableCell>
              </TableRow>
            ))}
            {!items.length ? <EmptyRow colSpan={6} /> : null}
          </TableBody>
        </Table>
      </AdminDataTable>
    </AdminPanel>
  )
}

export function VerificationIssuesPanel({ projectId }: { projectId?: number }) {
  const queryClient = useQueryClient()
  const issuesQuery = useQuery<ApiEnvelope<VerificationIssues>>({
    queryKey: ["carbon-verification", "issues", projectId],
    queryFn: () => generatedEnvelope<VerificationIssues>(carbonVerificationListIssues({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const findingsQuery = useQuery<ApiEnvelope<VerificationFindings>>({
    queryKey: ["carbon-verification", "findings", projectId],
    queryFn: () => generatedEnvelope<VerificationFindings>(carbonVerificationListFindings({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const createFinding = useMutation({
    mutationFn: (issue: VerificationIssue) =>
      generatedEnvelope<VerificationFinding>(
        carbonVerificationCreateFinding({
          body: {
            project_id: projectId,
            issue_type: issue.issue_type,
            severity: issue.severity,
            title: issue.title,
            description: issue.display_name,
            action_required: issue.action,
            record_type: issue.record_type,
            record_code: issue.record_code,
            scope: issue.scope,
            display_name: issue.display_name,
            period: issue.period,
            source_name: "carbon_verification.auto_issue",
            source_payload: issue,
          },
        }),
      ),
    onSuccess: () => {
      toast.success("已升级为核查发现")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "findings"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "创建核查发现失败")
    },
  })
  const updateFinding = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      generatedEnvelope<VerificationFinding>(carbonVerificationUpdateFinding({ path: { finding_id: id }, body: data })),
    onSuccess: () => {
      toast.success("核查发现已更新")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "findings"] })
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "projects"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "更新核查发现失败")
    },
  })
  const data = issuesQuery.data?.data
  const findings = findingsQuery.data?.data

  if (!projectId) return <ProjectSelectionRequired />

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "自动问题", value: data?.total ?? 0, icon: TriangleAlert },
          { label: "核查发现", value: findings?.summary.total ?? 0, icon: ShieldCheck },
          { label: "待整改", value: findings?.summary.open_count ?? 0, icon: CheckCircle2 },
        ]}
      />
      <AdminPanel title="自动问题" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
                <TableRow key={`${item.record_type}-${item.record_code}-${item.issue_type}`}>
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
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="核查发现" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

export function VerificationMaterialPackagePanel({ projectId }: { projectId?: number }) {
  const packageQuery = useQuery<ApiEnvelope<MaterialPackage>>({
    queryKey: ["carbon-verification", "material-package", projectId],
    queryFn: () => generatedEnvelope<MaterialPackage>(carbonVerificationGetMaterialPackage({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const data = packageQuery.data?.data

  if (!projectId) return <ProjectSelectionRequired />

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "材料组", value: data?.groups.length ?? 0, icon: PackageCheck },
          { label: "包状态", value: readinessLabel(data?.readiness), icon: ShieldCheck },
          { label: "清单文件", value: data?.manifest.length ?? 0, icon: FileText },
        ]}
      />
      <AdminPanel title="材料包目录" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="导出清单" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

export function VerificationReportPanel({ projectId }: { projectId?: number }) {
  const queryClient = useQueryClient()
  const summaryQuery = useQuery<ApiEnvelope<VerificationSummary>>({
    queryKey: ["carbon-verification", "summary", projectId],
    queryFn: () => generatedEnvelope<VerificationSummary>(carbonVerificationGetSummary({ query: { project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const reportQuery = useQuery<ApiEnvelope<ReportContext>>({
    queryKey: ["carbon-verification", "report", projectId],
    queryFn: () => generatedEnvelope<ReportContext>(carbonVerificationGetReportContext({ query: { limit: 200, project_id: projectId } })),
    enabled: Boolean(projectId),
  })
  const jobsQuery = useQuery<ApiEnvelope<ExportJobs>>({
    queryKey: ["carbon-verification", "export-jobs", projectId],
    queryFn: () => generatedEnvelope<ExportJobs>(carbonVerificationListExports({ query: { limit: 20, project_id: projectId } })),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const items = query.state.data?.data.items ?? []
      return items.some((item) => item.status === "queued" || item.status === "running") ? 3000 : false
    },
  })
  const templatesQuery = useQuery<ApiEnvelope<TemplateVersions>>({
    queryKey: ["carbon-verification", "templates"],
    queryFn: () => generatedEnvelope<TemplateVersions>(carbonVerificationListTemplates({ query: { limit: 50 } })),
  })
  const createExport = useMutation({
    mutationFn: () =>
      generatedEnvelope<ExportJob>(
        carbonVerificationCreateExport({
          body: {
            project_id: projectId,
            export_type: "material_package",
            year: summaryQuery.data?.data.reporting_period.year ?? undefined,
          },
        }),
      ),
    onSuccess: () => {
      toast.success("核查材料包生成任务已提交")
      void queryClient.invalidateQueries({ queryKey: ["carbon-verification", "export-jobs"] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "导出失败")
    },
  })
  const downloadExport = useMutation({
    mutationFn: (jobId: number) => downloadExportFile(jobId),
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "下载失败")
    },
  })
  const ensureTemplate = useMutation({
    mutationFn: () => generatedEnvelope<TemplateVersion>(carbonVerificationEnsureDefaultTemplate()),
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
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      generatedEnvelope<TemplateVersion>(carbonVerificationUpdateTemplate({ path: { template_id: id }, body: data })),
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
  const formalReadiness = report?.formal_readiness

  if (!projectId) return <ProjectSelectionRequired />

  return (
    <div className="space-y-4">
      <MetricGrid
        items={[
          { label: "排放量(tCO2e)", value: formatNumber(summary?.totals.total_t_co2e), icon: ShieldCheck },
          { label: "核算记录", value: summary?.record_count ?? 0, icon: FileText },
          { label: "问题数", value: summary?.issue_count ?? 0, icon: TriangleAlert },
        ]}
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => createExport.mutate()} disabled={createExport.isPending}>
          生成核查材料包
        </Button>
      </div>
      <AdminPanel title="正式报告就绪检查" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>检查项</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>待完善内容</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(formalReadiness?.checks ?? []).map((item) => (
                <TableRow key={item.code}>
                  <TableCell>{item.label}</TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell>{item.detail ?? "—"}</TableCell>
                </TableRow>
              ))}
              {reportQuery.isPending ? <AdminTableStateRow colSpan={3}>加载中</AdminTableStateRow> : null}
              {!reportQuery.isPending && !formalReadiness?.checks.length ? <EmptyRow colSpan={3} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="报告数据" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
              {reportQuery.isPending ? <AdminTableStateRow colSpan={4}>加载中</AdminTableStateRow> : null}
              {!reportQuery.isPending && !report?.inventory.source_summary?.length ? <EmptyRow colSpan={4} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel
        title="报告模板版本"
        actions={
          <Button variant="outline" size="sm" onClick={() => ensureTemplate.mutate()} disabled={ensureTemplate.isPending}>
            登记默认模板
          </Button>
        }
        contentClassName="p-0"
      >
        <AdminDataTable className="rounded-none border-0">
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
                    <div className="text-xs text-muted-foreground">{item.report_purpose === "national_ets" ? "全国碳市场行业报告" : "组织温室气体盘查报告"}</div>
                  </TableCell>
                  <TableCell>{item.version}</TableCell>
                  <TableCell>
                    <div>{item.standard_name ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{item.standard_code ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    <div>{item.applicable_scope ?? item.applicable_industry ?? "-"}</div>
                    <div className="text-xs text-muted-foreground">{item.implementation_status === "supported" ? "可正式导出" : "已登记，待完成适配"}</div>
                  </TableCell>
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
              {templatesQuery.isPending ? <AdminTableStateRow colSpan={7}>加载中</AdminTableStateRow> : null}
              {!templatesQuery.isPending && !templateRows.length ? <EmptyRow colSpan={7} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
      <AdminPanel title="导出记录" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
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
                  <TableCell>{job.job_no}</TableCell>
                  <TableCell>{job.report_year ?? "全部"}</TableCell>
                  <TableCell>
                    <ExportJobStatusBadge status={job.status} />
                  </TableCell>
                  <TableCell>{formatBytes(job.file_size_bytes)}</TableCell>
                  <TableCell>{job.completed_at ?? job.created_at ?? "-"}</TableCell>
                  <TableCell>
                    {job.download_url ? (
                      <Button variant="outline" size="sm" onClick={() => downloadExport.mutate(job.id)} disabled={downloadExport.isPending}>
                        下载
                      </Button>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {jobsQuery.isPending ? <AdminTableStateRow colSpan={6}>加载中</AdminTableStateRow> : null}
              {!jobsQuery.isPending && !jobs.length ? <EmptyRow colSpan={6} /> : null}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string | number; icon: typeof FileText }[] }) {
  return (
    <MetricStrip className="md:grid-cols-3 xl:grid-cols-3">
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} />
      ))}
    </MetricStrip>
  )
}

function EmptyRow({ colSpan }: { colSpan: number }) {
  return <AdminTableStateRow colSpan={colSpan}>暂无数据</AdminTableStateRow>
}

function ProjectSelectionRequired() {
  return (
    <AdminPanel title="核查项目">
      <div className="py-8 text-center text-sm text-muted-foreground">请先在“核查项目”中选择一项记录</div>
    </AdminPanel>
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

function ReportBindingBadge({ project }: { project: VerificationProject }) {
  if (!project.inventory_report_id) return <Badge variant="secondary">未绑定</Badge>
  if (project.report_status === "published") return <Badge>已发布 v{project.report_version}</Badge>
  return (
    <div className="flex flex-col gap-1">
      <Badge variant="destructive">报告未发布</Badge>
      <span className="text-xs text-muted-foreground">{project.report_code ?? "-"}</span>
    </div>
  )
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => onUpdate(project.id, { status: "completed", conclusion_status: "approved" })}
          disabled={disabled || project.readiness_status !== "ready"}
        >
          批准并完成
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

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

function auditObjectLabel(value: string) {
  if (value === "inventory_report") return "盘查报告"
  if (value === "verification_finding") return "核查发现"
  return value
}

type GeneratedApiResult = {
  data?: unknown
  error?: unknown
  response: Response
}

async function generatedEnvelope<T>(request: Promise<GeneratedApiResult>): Promise<ApiEnvelope<T>> {
  const result = await request
  if (result.error) throw apiError(result.error, result.response.status)
  const envelope = result.data as ApiEnvelope<T> | undefined
  if (!envelope) throw new Error(`HTTP ${result.response.status}`)
  if (envelope.code >= 400) throw new Error(envelope.msg || `HTTP ${envelope.code}`)
  return envelope
}

function apiError(error: unknown, status: number) {
  if (error instanceof Error) return error
  if (typeof error === "object" && error !== null) {
    const payload = error as { msg?: string; detail?: string }
    return new Error(payload.msg || payload.detail || `HTTP ${status}`)
  }
  return new Error(typeof error === "string" ? error : `HTTP ${status}`)
}

async function downloadEvidence(evidenceCode: string) {
  const response = await carbonVerificationDownloadEvidence({ path: { evidence_code: evidenceCode }, parseAs: "blob" })
  await saveGeneratedDownload(response, `${evidenceCode}.bin`)
}

async function downloadExportFile(jobId: number) {
  const response = await carbonVerificationDownloadExport({ path: { job_id: jobId }, parseAs: "blob" })
  await saveGeneratedDownload(response, "carbon-verification-export.zip")
}

async function saveGeneratedDownload(result: GeneratedApiResult, fallbackFilename: string) {
  if (result.error) throw apiError(result.error, result.response.status)
  if (!(result.data instanceof Blob)) throw new Error("下载文件响应无效")
  const filename = filenameFromDisposition(result.response.headers.get("content-disposition")) ?? fallbackFilename
  const blobUrl = URL.createObjectURL(result.data)
  const anchor = document.createElement("a")
  anchor.href = blobUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(blobUrl)
}

function filenameFromDisposition(disposition: string | null) {
  if (!disposition) return null
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) return decodeURIComponent(encoded)
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return plain || null
}
