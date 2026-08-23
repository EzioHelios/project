import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Download, LockKeyhole, Play, Save, Upload } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminEmptyState, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { asNumber, asText, formatReductionNumber, ReductionStatusBadge, reductionCategoryLabels, reductionTrackLabels } from "@/components/carbon/reduction-common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  downloadReductionMonitoringTemplate,
  useAssessReductionApplicability,
  useCreateReductionBaseline,
  useCreateReductionFinancialScenario,
  useCreateReductionReview,
  useImportReductionMonitoringWorkbook,
  useLockReductionBaseline,
  useReductionAuditEvents,
  useReductionMethodologies,
  useReductionMethodology,
  useReductionProject,
  useRunReductionCalculation,
  useSaveCcerDossier,
  useSaveReductionMonitoringPlan,
  useSaveReductionProjectBoundary,
  useTransitionReductionProject,
  useUpdateReductionProject,
} from "@/lib/api/hooks/decarbonization"
import type {
  BaselineScenarioRequest,
  CalculationRunRequest,
  CcerDossierRequest,
  FinancialScenarioRequest,
  ProjectBoundaryRequest,
  ProjectReviewRequest,
} from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/reduction/projects/$projectId")({ component: ReductionProjectDetailPage })

function ReductionProjectDetailPage() {
  const { projectId } = Route.useParams()
  const id = Number(projectId)
  const project = useReductionProject(id)
  const audit = useReductionAuditEvents(id)
  const data = project.data
  const methodology = useReductionMethodology(data?.methodologyId ?? 0)
  const update = useUpdateReductionProject(id)
  const transition = useTransitionReductionProject(id)
  const [progress, setProgress] = useState(0)
  const [evaluation, setEvaluation] = useState("")

  if (!data && !project.isLoading) {
    return (
      <AdminPageScaffold title="减排项目">
        <AdminEmptyState title="未找到项目" description="项目不存在或当前租户无访问权限。" />
      </AdminPageScaffold>
    )
  }

  return (
    <AdminPageScaffold
      title={data?.name ?? "减排项目"}
      status={data ? <ReductionStatusBadge status={data.status} /> : undefined}
      meta={
        data ? (
          <>
            <span>{data.code}</span>
            <span>{reductionTrackLabels[data.track] ?? data.track}</span>
            <span>{reductionCategoryLabels[data.category] ?? data.category}</span>
          </>
        ) : undefined
      }
      topActions={
        <Button asChild variant="outline" size="sm">
          <Link to="/carbon/reduction/projects">
            <ArrowLeft className="h-4 w-4" />
            返回项目库
          </Link>
        </Button>
      }
    >
      {data && (
        <Tabs defaultValue="overview" className="grid gap-3">
          <TabsList className="h-auto flex-wrap justify-start">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="boundary">边界与基准线</TabsTrigger>
            <TabsTrigger value="monitoring">监测</TabsTrigger>
            <TabsTrigger value="calculation">计算</TabsTrigger>
            <TabsTrigger value="evidence">证据</TabsTrigger>
            <TabsTrigger value="finance">财务评价</TabsTrigger>
            <TabsTrigger value="review">审核</TabsTrigger>
            {data.track === "ccer_project" && <TabsTrigger value="ccer">CCER</TabsTrigger>}
            <TabsTrigger value="audit">审计记录</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="grid gap-3">
            <MetricStrip>
              <MetricTile label="计划投资" value={formatReductionNumber(data.investmentCny / 10000)} unit="万元" tone="domain" />
              <MetricTile label="预计减排" value={formatReductionNumber(data.expectedReductionTco2E)} unit="tCO₂e" />
              <MetricTile label="监测减排" value={formatReductionNumber(data.monitoredReductionTco2E)} unit="tCO₂e" />
              <MetricTile label="核查减排" value={formatReductionNumber(data.verifiedReductionTco2E)} unit="tCO₂e" tone="success" />
            </MetricStrip>
            <div className="grid gap-3 xl:grid-cols-2">
              <AdminPanel title="项目责任与计划">
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                  <Detail label="责任人" value={data.ownerName} />
                  <Detail label="责任部门" value={data.departmentName ?? "-"} />
                  <Detail label="计划开始" value={data.plannedStart ?? "-"} />
                  <Detail label="计划结束" value={data.plannedEnd ?? "-"} />
                  <Detail label="项目目标" value={data.objective ?? "-"} className="col-span-2" />
                  <Detail label="实施计划" value={data.implementationPlan ?? "-"} className="col-span-2" />
                </dl>
              </AdminPanel>
              <AdminPanel
                title="进度与评价"
                actions={
                  <Button size="sm" onClick={() => update.mutate({ progressPct: progress, evaluationSummary: evaluation })} disabled={update.isPending}>
                    <Save className="h-4 w-4" />
                    保存
                  </Button>
                }
              >
                <div className="grid gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="progress">项目进度（%）</Label>
                    <Input id="progress" type="number" min={0} max={100} value={progress || data.progressPct} onChange={(event) => setProgress(Number(event.target.value))} />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="evaluation">阶段评价</Label>
                    <Textarea id="evaluation" value={evaluation || data.evaluationSummary || ""} onChange={(event) => setEvaluation(event.target.value)} />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => transition.mutate({ targetStatus: "screening" })}>
                      进入筛选
                    </Button>
                    <Button variant="outline" onClick={() => transition.mutate({ targetStatus: "approved" })}>
                      立项通过
                    </Button>
                    <Button variant="outline" onClick={() => transition.mutate({ targetStatus: "implementing" })}>
                      开始实施
                    </Button>
                    <Button variant="outline" onClick={() => transition.mutate({ targetStatus: "monitoring" })}>
                      开始监测
                    </Button>
                  </div>
                </div>
              </AdminPanel>
            </div>
          </TabsContent>

          <TabsContent value="boundary">
            <BoundaryBaselinePanel projectId={id} project={data} methodology={methodology.data} />
          </TabsContent>
          <TabsContent value="monitoring">
            <MonitoringPanel projectId={id} project={data} methodology={methodology.data} />
          </TabsContent>
          <TabsContent value="calculation">
            <CalculationPanel projectId={id} project={data} methodology={methodology.data} />
          </TabsContent>
          <TabsContent value="evidence">
            <AdminPanel title="证据文件">
              <MetricStrip>
                <MetricTile label="已关联证据" value={data.evidenceCount} unit="份" tone="domain" />
                <MetricTile label="方法学要求" value={methodology.data?.evidenceSchema.length ?? 0} unit="项" />
              </MetricStrip>
              <EvidenceChecklist required={methodology.data?.evidenceSchema ?? []} />
            </AdminPanel>
          </TabsContent>
          <TabsContent value="finance">
            <FinancialPanel projectId={id} project={data} />
          </TabsContent>
          <TabsContent value="review">
            <ReviewPanel projectId={id} project={data} />
          </TabsContent>
          {data.track === "ccer_project" && (
            <TabsContent value="ccer">
              <CcerPanel projectId={id} dossier={data.ccerDossier} />
            </TabsContent>
          )}
          <TabsContent value="audit">
            <RecordTable title="项目审计轨迹" rows={audit.data?.items ?? []} columns={["createdAt", "eventType", "actorName", "fromStatus", "toStatus", "reason"]} />
          </TabsContent>
        </Tabs>
      )}
    </AdminPageScaffold>
  )
}

function BoundaryBaselinePanel({
  projectId,
  project,
  methodology,
}: {
  projectId: number
  project: NonNullable<ReturnType<typeof useReductionProject>["data"]>
  methodology?: { id: number; applicabilitySchema: Array<Record<string, unknown>> }
}) {
  const create = useCreateReductionBaseline(projectId)
  const lock = useLockReductionBaseline(projectId)
  const assess = useAssessReductionApplicability(projectId)
  const saveBoundary = useSaveReductionProjectBoundary(projectId)
  const updateProject = useUpdateReductionProject(projectId)
  const methodologies = useReductionMethodologies({ executable: true })
  const [answers, setAnswers] = useState<Record<string, boolean>>({})
  const [boundary, setBoundary] = useState<ProjectBoundaryRequest>({
    physicalBoundary: { description: "" },
    ghgSourcesSinks: [],
    includedGases: ["CO2"],
    exclusions: [],
    resources: [],
  })
  const [resourceType, setResourceType] = useState("area")
  const [resourceKey, setResourceKey] = useState("")
  const [form, setForm] = useState<BaselineScenarioRequest>({
    name: "项目基准线",
    periodStart: `${new Date().getFullYear() - 1}-01-01`,
    periodEnd: `${new Date().getFullYear() - 1}-12-31`,
    modelKind: "adjusted_baseline",
    baselineTco2E: 0,
  })
  const physicalBoundary = boundary.physicalBoundary ?? {}
  const boundaryResources = boundary.resources ?? []
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <AdminPanel
        title="项目边界"
        actions={
          <Button size="sm" disabled={saveBoundary.isPending || !asText(physicalBoundary.description)} onClick={() => saveBoundary.mutate(boundary)}>
            <Save className="h-4 w-4" />
            保存边界
          </Button>
        }
      >
        <div className="grid gap-4">
          {project.track !== "internal_action" && (
            <div className="grid gap-2">
              <Label>核算方法学</Label>
              <Select
                value={project.methodologyId ? String(project.methodologyId) : "none"}
                onValueChange={(value) => value !== "none" && updateProject.mutate({ methodologyId: Number(value) })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">请选择</SelectItem>
                  {(methodologies.data?.items ?? []).map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.code} {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-2">
            <Label>物理边界说明</Label>
            <Textarea value={asText(physicalBoundary.description)} onChange={(event) => setBoundary({ ...boundary, physicalBoundary: { description: event.target.value } })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)_auto]">
            <Select value={resourceType} onValueChange={setResourceType}>
              <SelectTrigger aria-label="资源类型">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="area">区域</SelectItem>
                <SelectItem value="equipment">设备</SelectItem>
                <SelectItem value="measurement_boundary">计量边界</SelectItem>
                <SelectItem value="emission_source">排放源</SelectItem>
              </SelectContent>
            </Select>
            <Input aria-label="资源编码" placeholder="区域、设备或计量边界编码" value={resourceKey} onChange={(event) => setResourceKey(event.target.value)} />
            <Button
              type="button"
              variant="outline"
              disabled={!resourceKey}
              onClick={() => {
                setBoundary({ ...boundary, resources: [...boundaryResources, { resourceType, resourceKey, role: "affected" }] })
                setResourceKey("")
              }}
            >
              添加资源
            </Button>
          </div>
          <div className="divide-y rounded-md border text-sm">
            {boundaryResources.map((row) => (
              <div key={`${asText(row.resourceType)}-${asText(row.resourceKey)}`} className="flex items-center justify-between px-3 py-2">
                <span>{asText(row.resourceKey)}</span>
                <span className="text-muted-foreground">{asText(row.resourceType)}</span>
              </div>
            ))}
          </div>
          <dl className="grid grid-cols-3 gap-4 text-sm">
            <Detail label="已关联资源" value={`${project.resources.length} 项`} />
            <Detail label="边界版本" value={`${project.boundaries.length} 个`} />
            <Detail label="排放影响" value={project.inventoryImpactKind} />
          </dl>
        </div>
      </AdminPanel>
      <AdminPanel title="基准线版本">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label>名称</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <Label>模型</Label>
            <Select value={form.modelKind} onValueChange={(value) => setForm({ ...form, modelKind: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="adjusted_baseline">调整基准线</SelectItem>
                <SelectItem value="methodology_baseline">方法学基准线</SelectItem>
                <SelectItem value="historical_average">历史平均</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>基准期开始</Label>
            <Input type="date" value={form.periodStart} onChange={(e) => setForm({ ...form, periodStart: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <Label>基准期结束</Label>
            <Input type="date" value={form.periodEnd} onChange={(e) => setForm({ ...form, periodEnd: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <Label>基准排放（tCO₂e）</Label>
            <Input type="number" value={form.baselineTco2E ?? 0} onChange={(e) => setForm({ ...form, baselineTco2E: Number(e.target.value) })} />
          </div>
          <div className="flex items-end">
            <Button onClick={() => create.mutate(form)} disabled={create.isPending}>
              创建版本
            </Button>
          </div>
        </div>
        <div className="mt-4 divide-y rounded-md border">
          {project.baselines.map((row) => (
            <div key={asNumber(row.id)} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <div>
                <span className="font-medium">{asText(row.name)}</span>
                <span className="ml-2 text-muted-foreground">
                  V{asText(row.version)} · {asText(row.status)}
                </span>
              </div>
              {row.status !== "locked" && (
                <Button size="sm" variant="outline" onClick={() => lock.mutate(asNumber(row.id))}>
                  <LockKeyhole className="h-4 w-4" />
                  锁定
                </Button>
              )}
            </div>
          ))}
        </div>
      </AdminPanel>
      {methodology && project.track !== "internal_action" && (
        <AdminPanel
          className="xl:col-span-2"
          title="方法学适用性筛选"
          actions={
            <Button size="sm" disabled={assess.isPending} onClick={() => assess.mutate({ methodologyId: methodology.id, answers })}>
              保存评估
            </Button>
          }
        >
          <div className="grid gap-2 md:grid-cols-2">
            {methodology.applicabilitySchema.map((item) => {
              const code = asText(item.code)
              return (
                <label key={code} className="flex items-start gap-3 rounded-md border p-3 text-sm">
                  <input type="checkbox" className="mt-1" checked={answers[code] ?? false} onChange={(event) => setAnswers({ ...answers, [code]: event.target.checked })} />
                  <span>{asText(item.label) || code}</span>
                </label>
              )
            })}
          </div>
        </AdminPanel>
      )}
    </div>
  )
}

function MonitoringPanel({
  projectId,
  project,
  methodology,
}: {
  projectId: number
  project: NonNullable<ReturnType<typeof useReductionProject>["data"]>
  methodology?: { monitoringSchema: string[]; evidenceSchema: string[] }
}) {
  const save = useSaveReductionMonitoringPlan(projectId)
  const importer = useImportReductionMonitoringWorkbook(projectId)
  const [pendingWorkbook, setPendingWorkbook] = useState<{ fileName: string; workbookBase64: string } | null>(null)
  const [importPreview, setImportPreview] = useState<Record<string, unknown> | null>(null)
  const parameters = (methodology?.monitoringSchema ?? []).map((name) => ({
    name,
    source: "方法学监测要求",
    frequency: "monthly",
    unit: "按方法学",
    qualityControl: "校准与交叉核验",
  }))
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <AdminPanel
        title="监测计划"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void downloadReductionMonitoringTemplate(projectId, project.code)}>
              <Download className="h-4 w-4" />
              下载模板
            </Button>
            <Button asChild variant="outline" size="sm">
              <label>
                <Upload className="h-4 w-4" />
                导入监测数据
                <input
                  type="file"
                  accept=".xlsx"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (!file) return
                    const reader = new FileReader()
                    reader.onload = () => {
                      const encoded = String(reader.result ?? "").split(",")[1] ?? ""
                      const pending = { fileName: file.name, workbookBase64: encoded }
                      setPendingWorkbook(pending)
                      void importer.mutateAsync({ ...pending, commit: false }).then((result) => setImportPreview(result as Record<string, unknown>))
                    }
                    reader.readAsDataURL(file)
                  }}
                />
              </label>
            </Button>
            <Button
              size="sm"
              onClick={() =>
                save.mutate({
                  parameters,
                  evidenceRequirements: (methodology?.evidenceSchema ?? []).map((name) => ({ name, required: true })),
                  qualityControls: [{ code: "meter_calibration", status: "required" }],
                  publish: true,
                })
              }
            >
              <Save className="h-4 w-4" />
              发布计划
            </Button>
          </>
        }
      >
        <MonitoringRows rows={parameters} />
        {importPreview && (
          <div className="mt-4 rounded-md border p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium">导入校验结果</div>
                <div className="mt-1 text-muted-foreground">
                  有效 {asNumber((importPreview.metrics as Record<string, unknown> | undefined)?.validCount)} 条 · 错误{" "}
                  {asNumber((importPreview.metrics as Record<string, unknown> | undefined)?.errorCount)} 条
                </div>
              </div>
              <Button
                size="sm"
                disabled={!importPreview.canCommit || !pendingWorkbook || importer.isPending}
                onClick={() => pendingWorkbook && importer.mutate({ ...pendingWorkbook, commit: true })}
              >
                正式导入
              </Button>
            </div>
            {Array.isArray(importPreview.issues) && importPreview.issues.length > 0 && (
              <div className="mt-3 divide-y border-t">
                {(importPreview.issues as Array<Record<string, unknown>>).slice(0, 5).map((issue) => (
                  <div className="py-2 text-[hsl(var(--status-danger-foreground-admin))]" key={`${asText(issue.rowNumber)}-${asText(issue.issueCode)}`}>
                    {issue.rowNumber ? `第 ${asText(issue.rowNumber)} 行：` : ""}
                    {asText(issue.message)}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </AdminPanel>
      <RecordTable title="监测计划版本" rows={project.monitoringPlans} columns={["version", "status", "publishedAt", "dataRetentionYears"]} />
    </div>
  )
}

function CalculationPanel({
  projectId,
  project,
  methodology,
}: {
  projectId: number
  project: NonNullable<ReturnType<typeof useReductionProject>["data"]>
  methodology?: { id: number; code: string; parameterSchema: Array<Record<string, unknown>> }
}) {
  const calculate = useRunReductionCalculation(projectId)
  const lockedBaselines = project.baselines.filter((row) => row.status === "locked")
  const [baselineId, setBaselineId] = useState(asNumber(lockedBaselines[0]?.id))
  const [inputs, setInputs] = useState<Record<string, unknown>>({})
  const parameterRows = methodology?.parameterSchema ?? []
  const request = useMemo<CalculationRunRequest | null>(
    () =>
      methodology && baselineId > 0
        ? {
            methodologyId: methodology.id,
            baselineId,
            runKind: "ex_post",
            periodStart: `${new Date().getFullYear()}-01-01`,
            periodEnd: `${new Date().getFullYear()}-12-31`,
            inputs,
          }
        : null,
    [baselineId, inputs, methodology],
  )
  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <AdminPanel
        title={methodology ? `${methodology.code} 计算参数` : "计算参数"}
        actions={
          <Button size="sm" disabled={!request || calculate.isPending} onClick={() => request && calculate.mutate(request)}>
            <Play className="h-4 w-4" />
            运行计算
          </Button>
        }
      >
        <div className="grid gap-3">
          <div className="grid gap-2">
            <Label>锁定基准线</Label>
            <Select value={baselineId ? String(baselineId) : "none"} onValueChange={(value) => setBaselineId(Number(value))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">请选择</SelectItem>
                {lockedBaselines.map((row) => (
                  <SelectItem key={asNumber(row.id)} value={String(row.id)}>
                    V{asText(row.version)} {asText(row.name)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {parameterRows.map((row) => {
            const code = asText(row.code)
            return (
              <div className="grid gap-2" key={code}>
                <Label>
                  {asText(row.name) || asText(row.label) || code} {row.unit ? `(${asText(row.unit)})` : ""}
                </Label>
                <Input type="number" value={asNumber(inputs[code])} onChange={(e) => setInputs({ ...inputs, [code]: Number(e.target.value) })} />
              </div>
            )
          })}
        </div>
      </AdminPanel>
      <RecordTable
        title="减排量计算记录"
        rows={project.calculations}
        columns={["createdAt", "runKind", "status", "baselineTco2e", "projectTco2e", "leakageTco2e", "deductionTco2e", "reductionTco2e", "assuranceStatus"]}
      />
    </div>
  )
}

function FinancialPanel({ projectId, project }: { projectId: number; project: NonNullable<ReturnType<typeof useReductionProject>["data"]> }) {
  const create = useCreateReductionFinancialScenario(projectId)
  const [form, setForm] = useState<FinancialScenarioRequest>({
    name: "基准财务情景",
    capexCny: project.investmentCny,
    annualOpexCny: 0,
    annualEnergySavingsCny: 0,
    carbonPriceCnyPerT: 0,
    annualReductionTco2E: project.monitoredReductionTco2E || project.expectedReductionTco2E,
    projectLifeYears: 10,
    discountRate: 0.08,
  })
  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <AdminPanel
        title="财务评价参数"
        actions={
          <Button size="sm" onClick={() => create.mutate(form)} disabled={create.isPending || (form.projectLifeYears ?? 0) <= 0}>
            运行评价
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="情景名称" value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
          <NumberField label="初始投资（元）" value={form.capexCny} onChange={(value) => setForm({ ...form, capexCny: value })} />
          <NumberField label="年度运维成本（元）" value={form.annualOpexCny} onChange={(value) => setForm({ ...form, annualOpexCny: value })} />
          <NumberField label="年度节能收益（元）" value={form.annualEnergySavingsCny} onChange={(value) => setForm({ ...form, annualEnergySavingsCny: value })} />
          <NumberField label="碳价（元/tCO₂e）" value={form.carbonPriceCnyPerT} onChange={(value) => setForm({ ...form, carbonPriceCnyPerT: value })} />
          <NumberField label="年度减排量（tCO₂e）" value={form.annualReductionTco2E} onChange={(value) => setForm({ ...form, annualReductionTco2E: value })} />
          <NumberField label="项目寿命（年）" value={form.projectLifeYears ?? 0} onChange={(value) => setForm({ ...form, projectLifeYears: value })} />
          <NumberField label="折现率" value={form.discountRate ?? 0} step="0.01" onChange={(value) => setForm({ ...form, discountRate: value })} />
        </div>
      </AdminPanel>
      <RecordTable title="财务评价情景" rows={project.financialScenarios} columns={["name", "capexCny", "npvCny", "irr", "paybackYears", "maccCnyPerT"]} />
    </div>
  )
}

function ReviewPanel({ projectId, project }: { projectId: number; project: NonNullable<ReturnType<typeof useReductionProject>["data"]> }) {
  const create = useCreateReductionReview(projectId)
  const [form, setForm] = useState<ProjectReviewRequest>({
    reviewType: "internal",
    decision: "approved",
    reviewerName: "",
    organizationName: null,
    reviewedAt: new Date().toISOString(),
    conclusion: null,
  })
  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
      <AdminPanel
        title="新增审核记录"
        actions={
          <Button size="sm" onClick={() => create.mutate(form)} disabled={!form.reviewerName || create.isPending}>
            保存审核
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label>审核类型</Label>
            <Select value={form.reviewType} onValueChange={(value) => setForm({ ...form, reviewType: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="internal">内部复核</SelectItem>
                <SelectItem value="validation">第三方审定</SelectItem>
                <SelectItem value="verification">第三方核查</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>结论</Label>
            <Select value={form.decision} onValueChange={(value) => setForm({ ...form, decision: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="approved">通过</SelectItem>
                <SelectItem value="conditional">有条件通过</SelectItem>
                <SelectItem value="rejected">不通过</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Field label="审核人" value={form.reviewerName} onChange={(value) => setForm({ ...form, reviewerName: value })} />
          <Field label="机构" value={form.organizationName ?? ""} onChange={(value) => setForm({ ...form, organizationName: value || null })} />
          <div className="grid gap-2 sm:col-span-2">
            <Label>审核结论</Label>
            <Textarea value={form.conclusion ?? ""} onChange={(event) => setForm({ ...form, conclusion: event.target.value || null })} />
          </div>
        </div>
      </AdminPanel>
      <RecordTable title="审核与核查记录" rows={project.reviews} columns={["reviewType", "decision", "reviewerName", "organizationName", "reviewedAt"]} />
    </div>
  )
}

function CcerPanel({ projectId, dossier }: { projectId: number; dossier?: Record<string, unknown> | null }) {
  const save = useSaveCcerDossier(projectId)
  const [form, setForm] = useState<CcerDossierRequest>({
    status: asText(dossier?.status) || "preparation",
    projectDesignDocumentNo: asText(dossier?.projectDesignDocumentNo) || null,
    validationBody: asText(dossier?.validationBody) || null,
    verificationBody: asText(dossier?.verificationBody) || null,
    registrationNo: asText(dossier?.registrationNo) || null,
    registrationDate: asText(dossier?.registrationDate) || null,
    issuanceNo: asText(dossier?.issuanceNo) || null,
    issuanceDate: asText(dossier?.issuanceDate) || null,
    issuedQuantityTco2E: asNumber(dossier?.issuedQuantityTco2e) || null,
  })
  return (
    <AdminPanel
      title="CCER材料、登记与签发台账"
      actions={
        <Button size="sm" onClick={() => save.mutate(form)}>
          <Save className="h-4 w-4" />
          保存
        </Button>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label>台账状态</Label>
          <Select value={form.status} onValueChange={(value) => setForm({ ...form, status: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="preparation">材料准备</SelectItem>
              <SelectItem value="validated">已审定</SelectItem>
              <SelectItem value="verified">已核查</SelectItem>
              <SelectItem value="registered">已登记</SelectItem>
              <SelectItem value="issued">已签发</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="项目设计文件编号" value={form.projectDesignDocumentNo ?? ""} onChange={(value) => setForm({ ...form, projectDesignDocumentNo: value || null })} />
        <Field label="审定机构" value={form.validationBody ?? ""} onChange={(value) => setForm({ ...form, validationBody: value || null })} />
        <Field label="核查机构" value={form.verificationBody ?? ""} onChange={(value) => setForm({ ...form, verificationBody: value || null })} />
        <Field label="登记编号" value={form.registrationNo ?? ""} onChange={(value) => setForm({ ...form, registrationNo: value || null })} />
        <div className="grid gap-2">
          <Label>登记日期</Label>
          <Input type="date" value={form.registrationDate ?? ""} onChange={(event) => setForm({ ...form, registrationDate: event.target.value || null })} />
        </div>
        <Field label="签发编号" value={form.issuanceNo ?? ""} onChange={(value) => setForm({ ...form, issuanceNo: value || null })} />
        <div className="grid gap-2">
          <Label>签发日期</Label>
          <Input type="date" value={form.issuanceDate ?? ""} onChange={(event) => setForm({ ...form, issuanceDate: event.target.value || null })} />
        </div>
        <div className="grid gap-2">
          <Label>签发量（tCO₂e）</Label>
          <Input type="number" value={form.issuedQuantityTco2E ?? 0} onChange={(e) => setForm({ ...form, issuedQuantityTco2E: Number(e.target.value) })} />
        </div>
      </div>
    </AdminPanel>
  )
}

function MonitoringRows({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <div className="divide-y rounded-md border">
      {rows.map((row) => (
        <div key={asText(row.name)} className="grid grid-cols-[1fr_auto] gap-3 px-3 py-2 text-sm">
          <span>{asText(row.name)}</span>
          <span className="text-muted-foreground">{asText(row.frequency)}</span>
        </div>
      ))}
    </div>
  )
}
function EvidenceChecklist({ required }: { required: string[] }) {
  return (
    <div className="mt-4 divide-y rounded-md border">
      {required.map((name) => (
        <div key={name} className="flex items-center justify-between px-3 py-2 text-sm">
          <span>{name}</span>
          <StatusBadge status="pending" label="待关联" />
        </div>
      ))}
    </div>
  )
}
function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}
function NumberField({ label, value, onChange, step }: { label: string; value: number; onChange: (value: number) => void; step?: string }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  )
}
function Detail({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap">{value}</dd>
    </div>
  )
}
function RecordTable({ title, rows, columns }: { title: string; rows: Array<Record<string, unknown>>; columns: string[] }) {
  return (
    <AdminPanel title={title} contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column}>{columnLabel(column)}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={asText(row.id) || index}>
              {columns.map((column) => (
                <TableCell key={column} className="tabular-nums">
                  {formatCell(row[column])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}
const labels: Record<string, string> = {
  name: "情景",
  capexCny: "投资",
  npvCny: "NPV",
  irr: "IRR",
  paybackYears: "回收期",
  maccCnyPerT: "MACC",
  reviewType: "审核类型",
  decision: "结论",
  reviewerName: "审核人",
  organizationName: "机构",
  reviewedAt: "审核时间",
  createdAt: "时间",
  eventType: "事件",
  actorName: "操作人",
  fromStatus: "原状态",
  toStatus: "新状态",
  reason: "原因",
  version: "版本",
  status: "状态",
  publishedAt: "发布时间",
  dataRetentionYears: "留存年限",
  runKind: "计算类型",
  baselineTco2e: "基准排放",
  projectTco2e: "项目排放",
  leakageTco2e: "泄漏",
  deductionTco2e: "扣减",
  reductionTco2e: "减排量",
  assuranceStatus: "保证状态",
}
function columnLabel(key: string) {
  return labels[key] ?? key
}
function formatCell(value: unknown) {
  if (typeof value === "number") return formatReductionNumber(value)
  if (value == null || value === "") return "-"
  return String(value)
}
