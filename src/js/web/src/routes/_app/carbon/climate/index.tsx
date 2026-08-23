import { createFileRoute } from "@tanstack/react-router"
import { CheckCircle2, Play, Plus, RefreshCw, Settings2, TriangleAlert } from "lucide-react"
import type * as React from "react"
import { useEffect, useMemo, useState } from "react"

import { AdminEmptyState, AdminFilterBar, AdminPageScaffold, AdminPanel, AdminTabsList, ChartPanel, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"
import { createBulletProgressChartOption, createReadinessMatrixOption, createTargetPathChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import {
  useClimateOverview,
  useClimatePrograms,
  useCreateRenewableElectricityClaim,
  usePublishClimateTarget,
  useRunClimateAssessment,
  useSaveClimateDisclosureCycle,
  useSaveClimateProgram,
} from "@/lib/api/hooks/climate-governance"
import type { ClimateProgramResponse, RenewableElectricityClaimRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/climate/")({ component: ClimateGovernancePage })

type Framework = "sbti" | "cdp" | "re100"
type View = "overview" | Framework
type AnyRecord = Record<string, unknown>

const frameworkLabels: Record<Framework, string> = { sbti: "SBTi目标", cdp: "CDP披露", re100: "RE100进展" }
const claimSourceLabels: Record<string, string> = {
  onsite_generation: "自发自用",
  self_generation: "自发自用",
  ppa: "购电协议",
  green_power: "绿电交易",
  certificate: "绿色电力证书",
  supplier_product: "供应商绿色电力产品",
  grid: "其他电网电力",
}

const cycleStatusLabels: Record<string, string> = {
  preparing: "准备中",
  internal_review: "内部复核",
  submitted: "已提交",
  completed: "已完成",
  not_configured: "未配置",
}

function record(value: unknown): AnyRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as AnyRecord) : {}
}

function records(value: unknown): AnyRecord[] {
  return Array.isArray(value) ? value.map(record) : []
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function textValue(value: unknown, fallback = "") {
  return value == null ? fallback : String(value)
}

function formatNumber(value: unknown, digits = 1) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: digits }) : "-"
}

function ClimateGovernancePage() {
  const currentYear = new Date().getFullYear()
  const [reportingYear, setReportingYear] = useState(currentYear)
  const [view, setView] = useState<View>("overview")
  const [programOpen, setProgramOpen] = useState(false)
  const [targetOpen, setTargetOpen] = useState(false)
  const [disclosureOpen, setDisclosureOpen] = useState(false)
  const [claimOpen, setClaimOpen] = useState(false)
  const chartTheme = useAdminChartTheme("carbon")
  const overview = useClimateOverview(reportingYear)
  const programsQuery = useClimatePrograms(reportingYear)
  const data = overview.data
  const metrics = record(data?.metrics)
  const sbti = record(data?.sbti)
  const cdp = record(data?.cdp)
  const re100 = record(data?.re100)
  const sbtiTarget = record(sbti.target)
  const programs = programsQuery.data?.items ?? []
  const selectedFramework = view === "overview" ? null : view
  const selectedProgram = selectedFramework ? programs.find((item) => item.framework === selectedFramework) : undefined
  const runAssessment = useRunClimateAssessment(selectedProgram?.id ?? 0)

  const trendOption = useMemo(
    () =>
      createTargetPathChartOption(
        chartTheme,
        records(data?.inventoryTrend).map((item) => ({
          period: textValue(item.period),
          actual: item.actual == null ? null : numberValue(item.actual),
          reference: item.reference == null && item.target == null ? null : numberValue(item.reference ?? item.target),
          forecast: item.forecast == null ? null : numberValue(item.forecast),
        })),
        {
          unit: "tCO₂e",
          baselineYear: numberValue(sbtiTarget.baselineYear) || undefined,
          reportingYear,
          targetYear: numberValue(sbtiTarget.targetYear) || undefined,
        },
      ),
    [chartTheme, data?.inventoryTrend, reportingYear, sbtiTarget.baselineYear, sbtiTarget.targetYear],
  )
  const scopeOption = useMemo(
    () =>
      createBulletProgressChartOption(
        chartTheme,
        records(data?.scopeBreakdown).map((item, index) => ({
          name: textValue(item.name),
          value: numberValue(item.value),
          colorKey: (["scope1", "scope2", "scope3"] as const)[index] ?? "neutral",
        })),
        { unit: "tCO₂e", label: `${reportingYear}年度` },
      ),
    [chartTheme, data?.scopeBreakdown, reportingYear],
  )
  const cdpOption = useMemo(
    () =>
      createReadinessMatrixOption(
        chartTheme,
        records(cdp.readinessMatrix).map((item) => ({
          domain: textValue(item.domain),
          dimension: textValue(item.dimension),
          status: textValue(item.status, "missing") as "complete" | "partial" | "missing" | "blocked" | "not_applicable",
          detail: textValue(item.detail),
        })),
      ),
    [cdp.readinessMatrix, chartTheme],
  )
  const re100MixOption = useMemo(
    () =>
      createBulletProgressChartOption(
        chartTheme,
        records(re100.sourceMix).map((item, index) => ({
          name: claimSourceLabels[textValue(item.name)] ?? textValue(item.name),
          value: numberValue(item.value),
          colorKey: (["carbon", "scope2", "scope3", "energy", "neutral"] as const)[index] ?? "muted",
        })),
        { unit: "MWh", label: "来源构成", max: numberValue(re100.totalElectricityMwh) },
      ),
    [chartTheme, re100.sourceMix, re100.totalElectricityMwh],
  )
  const re100CoverageOption = useMemo(
    () =>
      createBulletProgressChartOption(
        chartTheme,
        records(re100.coverageSegments).map((item) => ({
          name: textValue(item.name),
          value: numberValue(item.value),
          colorKey: item.status === "eligible" ? "success" : item.status === "pending" ? "warning" : "muted",
        })),
        {
          unit: "MWh",
          label: "年度用电",
          max: numberValue(re100.totalElectricityMwh),
          target: (numberValue(re100.totalElectricityMwh) * numberValue(re100.targetPct)) / 100,
          targetLabel: `目标 ${formatNumber(re100.targetPct, 0)}%`,
        },
      ),
    [chartTheme, re100.coverageSegments, re100.targetPct, re100.totalElectricityMwh],
  )

  const runCurrentAssessment = async () => {
    if (!selectedProgram) return
    await runAssessment.mutateAsync({})
  }

  return (
    <Tabs value={view} onValueChange={(value) => setView(value as View)}>
      <AdminPageScaffold
        title="气候目标与披露"
        meta={<span>{reportingYear}年度</span>}
        topActions={
          selectedFramework ? (
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setProgramOpen(true)}>
                <Settings2 className="h-4 w-4" />
                计划设置
              </Button>
              <Button size="sm" onClick={() => void runCurrentAssessment()} disabled={!selectedProgram || runAssessment.isPending}>
                <Play className="h-4 w-4" />
                运行评估
              </Button>
            </div>
          ) : undefined
        }
        tabs={
          <AdminTabsList>
            <TabsTrigger value="overview">综合概览</TabsTrigger>
            <TabsTrigger value="sbti">SBTi目标</TabsTrigger>
            <TabsTrigger value="cdp">CDP披露</TabsTrigger>
            <TabsTrigger value="re100">RE100进展</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <AdminFilterBar
            fields={[
              {
                key: "year",
                node: <Input aria-label="报告年度" type="number" value={reportingYear} onChange={(event) => setReportingYear(Number(event.target.value))} />,
              },
            ]}
            actions={
              <Button variant="outline" size="sm" onClick={() => void overview.refetch()} disabled={overview.isFetching}>
                <RefreshCw className="h-4 w-4" />
                刷新
              </Button>
            }
          />
        }
        metrics={
          <MetricStrip className="xl:grid-cols-6">
            <MetricTile label="组织排放" value={formatNumber(metrics.actualTco2e)} unit="tCO₂e" tone="domain" />
            <MetricTile label="SBTi就绪度" value={formatNumber(metrics.sbtiReadinessPct, 0)} unit="%" tone={numberValue(metrics.sbtiReadinessPct) >= 80 ? "success" : "warning"} />
            <MetricTile label="目标路径差距" value={formatNumber(metrics.sbtiGapTco2e)} unit="tCO₂e" tone={numberValue(metrics.sbtiGapTco2e) > 0 ? "warning" : "success"} />
            <MetricTile label="CDP披露就绪度" value={formatNumber(metrics.cdpReadinessPct, 0)} unit="%" />
            <MetricTile label="可再生电力占比" value={formatNumber(metrics.re100ProgressPct, 1)} unit="%" tone="success" />
            <MetricTile label="待处理事项" value={formatNumber(metrics.actionCount, 0)} unit="项" tone={numberValue(metrics.actionCount) > 0 ? "warning" : "success"} />
          </MetricStrip>
        }
      >
        <TabsContent value="overview" className="m-0 grid gap-3">
          <div className="grid gap-3 xl:grid-cols-2">
            <ChartPanel title="SBTi减排路径与年度跟踪" unit="tCO₂e" source="组织碳盘查与已发布目标版本" option={trendOption} height={310} />
            <ChartPanel title="组织排放结构" unit="tCO₂e" source="最新组织碳盘查" option={scopeOption} height={310} />
          </div>
          <FrameworkProgress
            sbti={sbti}
            cdp={cdp}
            re100={re100}
            programs={programs}
            onOpen={(framework) => {
              setView(framework)
              setProgramOpen(true)
            }}
          />
          <ChecksTable title="优先处理事项" checks={records(data?.tasks)} showFramework />
        </TabsContent>

        <TabsContent value="sbti" className="m-0 grid gap-3">
          {!selectedProgram ? <ConfigureState framework="sbti" onClick={() => setProgramOpen(true)} /> : null}
          <div className="grid gap-3 xl:grid-cols-2">
            <ChartPanel title="SBTi减排路径与年度跟踪" unit="tCO₂e" source="组织碳盘查与已发布目标版本" option={trendOption} height={320} />
            <AdminPanel
              title="目标状态"
              actions={
                <Button size="sm" onClick={() => setTargetOpen(true)} disabled={!selectedProgram}>
                  <Settings2 className="h-4 w-4" />
                  维护目标
                </Button>
              }
            >
              <KeyFacts
                items={[
                  [sbti.actualKind === "partial_year" ? "报告期排放" : "当前排放", `${formatNumber(sbti.actualTco2e)} tCO₂e`],
                  ...(sbti.actualKind === "partial_year" ? [["年度预测", `${formatNumber(sbti.trackingTco2e)} tCO₂e`] as [string, string]] : []),
                  ["目标路径", sbti.targetPathTco2e == null ? "未配置" : `${formatNumber(sbti.targetPathTco2e)} tCO₂e`],
                  ["路径差距", sbti.gapTco2e == null ? "-" : `${formatNumber(sbti.gapTco2e)} tCO₂e`],
                  ["目标完成度", sbti.targetCompletionPct == null ? "-" : `${formatNumber(sbti.targetCompletionPct, 1)}%`],
                  ["Scope 3占比", `${formatNumber(sbti.scope3SharePct, 1)}%`],
                ]}
              />
            </AdminPanel>
          </div>
          <ChecksTable title="SBTi目标就绪检查" checks={records(sbti.checks)} />
        </TabsContent>

        <TabsContent value="cdp" className="m-0 grid gap-3">
          {!selectedProgram ? <ConfigureState framework="cdp" onClick={() => setProgramOpen(true)} /> : null}
          <div className="grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
            <ChartPanel title="披露主题准备矩阵" source="当前披露周期内部检查" option={cdpOption} height={330} />
            <AdminPanel
              title="披露周期"
              actions={
                <Button size="sm" onClick={() => setDisclosureOpen(true)} disabled={!selectedProgram}>
                  <Settings2 className="h-4 w-4" />
                  维护披露信息
                </Button>
              }
            >
              <KeyFacts
                items={[
                  ["内部就绪度", `${formatNumber(cdp.readinessPct, 0)}%`],
                  ["完成主题", `${formatNumber(cdp.completedDomains, 0)} / ${formatNumber(cdp.totalDomains, 0)}`],
                  ["问卷版本", textValue(cdp.questionnaireVersion, "2026")],
                  ["周期状态", cycleStatusLabels[textValue(cdp.cycleStatus)] ?? textValue(cdp.cycleStatus, "未配置")],
                ]}
              />
            </AdminPanel>
          </div>
          <ChecksTable title="CDP披露数据检查" checks={records(cdp.checks)} />
        </TabsContent>

        <TabsContent value="re100" className="m-0 grid gap-3">
          {!selectedProgram ? <ConfigureState framework="re100" onClick={() => setProgramOpen(true)} /> : null}
          <div className="grid gap-3 xl:grid-cols-3">
            <ChartPanel title="可再生电力目标覆盖" unit="MWh" source="用电边界与电力属性资格结果" option={re100CoverageOption} height={290} />
            <ChartPanel title="企业用电来源结构" unit="MWh" source="能源计量与可再生电力台账" option={re100MixOption} height={290} className="xl:col-span-2" />
          </div>
          <AdminPanel
            title="可再生电力属性台账"
            actions={
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setTargetOpen(true)} disabled={!selectedProgram}>
                  维护目标
                </Button>
                <Button size="sm" onClick={() => setClaimOpen(true)} disabled={!selectedProgram}>
                  <Plus className="h-4 w-4" />
                  登记电力属性
                </Button>
              </div>
            }
            contentClassName="p-0"
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>属性编号</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead>电量（MWh）</TableHead>
                  <TableHead>年度</TableHead>
                  <TableHead>市场</TableHead>
                  <TableHead>归属状态</TableHead>
                  <TableHead>资格</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records(re100.claims).map((claim) => (
                  <TableRow key={numberValue(claim.id)}>
                    <TableCell className="font-medium">{textValue(claim.claimNo)}</TableCell>
                    <TableCell>{claimSourceLabels[textValue(claim.sourceType)] ?? textValue(claim.sourceType)}</TableCell>
                    <TableCell className="tabular-nums">{formatNumber(claim.quantityMwh, 2)}</TableCell>
                    <TableCell>{textValue(claim.reportingYear)}</TableCell>
                    <TableCell>{textValue(claim.consumptionCountry, "-")}</TableCell>
                    <TableCell>{textValue(claim.ownershipStatus)}</TableCell>
                    <TableCell>
                      <StatusBadge status={claim.eligibilityStatus === "eligible" ? "approved" : "pending"} label={claim.eligibilityStatus === "eligible" ? "合格" : "待核验"} />
                    </TableCell>
                  </TableRow>
                ))}
                {records(re100.claims).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                      尚未登记可再生电力属性
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </AdminPanel>
          <ChecksTable title="RE100资格与目标检查" checks={records(re100.checks)} />
        </TabsContent>
      </AdminPageScaffold>

      {selectedFramework ? (
        <ProgramDialog open={programOpen} onOpenChange={setProgramOpen} framework={selectedFramework} reportingYear={reportingYear} current={selectedProgram} />
      ) : null}
      {selectedFramework && selectedProgram ? (
        <TargetDialog
          open={targetOpen}
          onOpenChange={setTargetOpen}
          framework={selectedFramework}
          program={selectedProgram}
          overview={selectedFramework === "sbti" ? sbti : re100}
        />
      ) : null}
      {selectedProgram?.framework === "cdp" ? (
        <DisclosureDialog open={disclosureOpen} onOpenChange={setDisclosureOpen} program={selectedProgram} reportingYear={reportingYear} current={cdp} />
      ) : null}
      {selectedProgram?.framework === "re100" ? <ClaimDialog open={claimOpen} onOpenChange={setClaimOpen} program={selectedProgram} reportingYear={reportingYear} /> : null}
    </Tabs>
  )
}

function FrameworkProgress({
  sbti,
  cdp,
  re100,
  programs,
  onOpen,
}: {
  sbti: AnyRecord
  cdp: AnyRecord
  re100: AnyRecord
  programs: ClimateProgramResponse[]
  onOpen: (framework: Framework) => void
}) {
  const rows = [
    { framework: "sbti" as const, value: numberValue(sbti.readinessPct), label: "目标就绪度" },
    { framework: "cdp" as const, value: numberValue(cdp.readinessPct), label: "披露就绪度" },
    { framework: "re100" as const, value: numberValue(re100.progressPct), label: "可再生电力占比" },
  ]
  return (
    <AdminPanel title="气候承诺进展">
      <div className="grid gap-5 lg:grid-cols-3">
        {rows.map((row) => {
          const configured = programs.some((program) => program.framework === row.framework)
          return (
            <button type="button" className="grid gap-2 text-left" key={row.framework} onClick={() => onOpen(row.framework)}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{frameworkLabels[row.framework]}</span>
                <StatusBadge status={configured ? (row.value >= 80 ? "approved" : "pending") : "inactive"} label={configured ? `${formatNumber(row.value, 0)}%` : "待配置"} />
              </div>
              <div className="h-2 overflow-hidden rounded-sm bg-muted">
                <div className="h-full bg-[hsl(var(--admin-accent))]" style={{ width: `${Math.min(Math.max(row.value, 0), 100)}%` }} />
              </div>
              <span className="text-muted-foreground text-xs">{row.label}</span>
            </button>
          )
        })}
      </div>
    </AdminPanel>
  )
}

function ConfigureState({ framework, onClick }: { framework: Framework; onClick: () => void }) {
  return (
    <AdminEmptyState
      title={`尚未建立${frameworkLabels[framework]}计划`}
      actions={
        <Button size="sm" onClick={onClick}>
          <Plus className="h-4 w-4" />
          建立计划
        </Button>
      }
    />
  )
}

function ChecksTable({ title, checks, showFramework = false }: { title: string; checks: AnyRecord[]; showFramework?: boolean }) {
  return (
    <AdminPanel title={title} contentClassName="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            {showFramework ? <TableHead>框架</TableHead> : null}
            <TableHead>检查项</TableHead>
            <TableHead>当前值</TableHead>
            <TableHead>要求</TableHead>
            <TableHead>状态</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {checks.map((check, index) => (
            <TableRow key={`${textValue(check.framework)}-${textValue(check.code)}-${index}`}>
              {showFramework ? <TableCell>{frameworkLabels[textValue(check.framework) as Framework] ?? textValue(check.framework)}</TableCell> : null}
              <TableCell className="font-medium">{textValue(check.label)}</TableCell>
              <TableCell className="tabular-nums">{check.value == null ? "-" : formatNumber(check.value, 1)}</TableCell>
              <TableCell className="tabular-nums">{check.threshold == null ? "-" : formatNumber(check.threshold, 1)}</TableCell>
              <TableCell>
                {check.passed ? (
                  <span className="inline-flex items-center gap-1 text-[hsl(var(--status-success))] text-xs">
                    <CheckCircle2 className="h-4 w-4" /> 已满足
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[hsl(var(--status-warning))] text-xs">
                    <TriangleAlert className="h-4 w-4" /> 待完善
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))}
          {checks.length === 0 ? (
            <TableRow>
              <TableCell colSpan={showFramework ? 5 : 4} className="h-24 text-center text-muted-foreground">
                当前没有待处理事项
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </AdminPanel>
  )
}

function KeyFacts({ items }: { items: Array<[string, string]> }) {
  return (
    <dl className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div className="grid gap-1 border-b pb-3" key={label}>
          <dt className="text-muted-foreground text-xs">{label}</dt>
          <dd className="font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function ProgramDialog({
  open,
  onOpenChange,
  framework,
  reportingYear,
  current,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  framework: Framework
  reportingYear: number
  current?: ClimateProgramResponse
}) {
  const save = useSaveClimateProgram()
  const [ownerName, setOwnerName] = useState(current?.ownerName ?? "")
  useEffect(() => {
    if (open) setOwnerName(current?.ownerName ?? "")
  }, [current?.ownerName, open])
  const saveProgram = async () => {
    await save.mutateAsync({
      code: current?.code ?? `${framework.toUpperCase()}-${reportingYear}`,
      name: `${reportingYear}年度${frameworkLabels[framework]}计划`,
      framework,
      reportingYear,
      ownerName: ownerName || null,
      sourceName: "企业气候目标与披露计划",
      configuration: current?.configuration ?? {},
    })
    onOpenChange(false)
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{frameworkLabels[framework]}计划设置</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <FormField label="报告年度">
            <Input value={reportingYear} disabled />
          </FormField>
          <FormField label="标准版本">
            <Input value={current?.standardVersion ?? "保存后由当前有效规则确定"} disabled />
          </FormField>
          <FormField label="责任人">
            <Input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} />
          </FormField>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={() => void saveProgram()} disabled={save.isPending}>
            保存计划
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TargetDialog({
  open,
  onOpenChange,
  framework,
  program,
  overview,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  framework: Framework
  program: ClimateProgramResponse
  overview: AnyRecord
}) {
  const current = record(overview.target)
  const currentCoverage = record(current.scopeCoverage)
  const publish = usePublishClimateTarget(program.id)
  const [baselineYear, setBaselineYear] = useState(numberValue(current.baselineYear, program.reportingYear - 1))
  const [baselineValue, setBaselineValue] = useState(numberValue(current.baselineValue, framework === "re100" ? 0 : numberValue(overview.actualTco2e)))
  const [targetYear, setTargetYear] = useState(numberValue(current.targetYear, framework === "re100" ? 2030 : program.reportingYear + 5))
  const [targetValue, setTargetValue] = useState(numberValue(current.targetValue, framework === "re100" ? 100 : 0))
  const [reductionPct, setReductionPct] = useState(numberValue(current.reductionPct, framework === "re100" ? 0 : 42))
  const [scope12Pct, setScope12Pct] = useState(numberValue(currentCoverage.scope12Pct, 95))
  const [scope3Pct, setScope3Pct] = useState(numberValue(currentCoverage.scope3Pct, 67))
  const [scope2Method, setScope2Method] = useState(textValue(current.scope2Method, "location"))
  useEffect(() => {
    if (!open) return
    setBaselineYear(numberValue(current.baselineYear, program.reportingYear - 1))
    setBaselineValue(numberValue(current.baselineValue, framework === "re100" ? 0 : numberValue(overview.actualTco2e)))
    setTargetYear(numberValue(current.targetYear, framework === "re100" ? 2030 : program.reportingYear + 5))
    setTargetValue(numberValue(current.targetValue, framework === "re100" ? 100 : 0))
    setReductionPct(numberValue(current.reductionPct, framework === "re100" ? 0 : 42))
    setScope12Pct(numberValue(currentCoverage.scope12Pct, 95))
    setScope3Pct(numberValue(currentCoverage.scope3Pct, 67))
    setScope2Method(textValue(current.scope2Method, "location"))
  }, [
    current.baselineValue,
    current.baselineYear,
    current.reductionPct,
    current.scope2Method,
    current.targetValue,
    current.targetYear,
    currentCoverage.scope12Pct,
    currentCoverage.scope3Pct,
    framework,
    open,
    overview.actualTco2e,
    program.reportingYear,
  ])
  const submit = async () => {
    await publish.mutateAsync({
      targetKind: framework === "re100" ? "renewable_electricity_pct" : "absolute_reduction",
      baselineYear,
      baselineValue,
      targetYear,
      targetValue: framework === "re100" ? targetValue : null,
      reductionPct: framework === "sbti" ? reductionPct : null,
      scope2Method,
      scopeCoverage: framework === "sbti" ? { scope12Pct, scope3Pct } : {},
      sourceName: "企业气候目标",
    })
    onOpenChange(false)
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{framework === "re100" ? "可再生电力目标" : "SBTi目标版本"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2 sm:grid-cols-2">
          <NumberField label="基准年度" value={baselineYear} onChange={setBaselineYear} />
          <NumberField label="目标年度" value={targetYear} onChange={setTargetYear} />
          <NumberField label={framework === "re100" ? "基准可再生电力占比（%）" : "基准排放（tCO₂e）"} value={baselineValue} onChange={setBaselineValue} />
          {framework === "re100" ? (
            <NumberField label="目标可再生电力占比（%）" value={targetValue} onChange={setTargetValue} />
          ) : (
            <NumberField label="目标减排比例（%）" value={reductionPct} onChange={setReductionPct} />
          )}
          {framework === "sbti" ? (
            <>
              <FormField label="Scope 2核算方法">
                <Select value={scope2Method} onValueChange={setScope2Method}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="location">位置法</SelectItem>
                    <SelectItem value="market">市场法</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <NumberField label="Scope 1+2覆盖率（%）" value={scope12Pct} onChange={setScope12Pct} />
              <NumberField label="Scope 3覆盖率（%）" value={scope3Pct} onChange={setScope3Pct} />
            </>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={publish.isPending}>
            发布目标版本
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DisclosureDialog({
  open,
  onOpenChange,
  program,
  reportingYear,
  current,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  program: ClimateProgramResponse
  reportingYear: number
  current: AnyRecord
}) {
  const save = useSaveClimateDisclosureCycle(program.id)
  const currentChecks = Object.fromEntries(records(current.checks).map((item) => [textValue(item.code).replace("cdp_", ""), Boolean(item.passed)]))
  const [ownerName, setOwnerName] = useState(program.ownerName ?? "")
  const [manual, setManual] = useState<Record<string, boolean>>({
    governance: Boolean(currentChecks.governance),
    risks: Boolean(currentChecks.risks),
    strategy: Boolean(currentChecks.strategy),
  })
  useEffect(() => {
    if (!open) return
    setOwnerName(program.ownerName ?? "")
    setManual({
      governance: Boolean(currentChecks.governance),
      risks: Boolean(currentChecks.risks),
      strategy: Boolean(currentChecks.strategy),
    })
  }, [currentChecks.governance, currentChecks.risks, currentChecks.strategy, open, program.ownerName])
  const submit = async () => {
    await save.mutateAsync({ reportingYear, status: "preparing", ownerName: ownerName || null, domainStatuses: manual, responseSnapshot: {}, evidenceSnapshot: [] })
    onOpenChange(false)
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>CDP披露周期</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <FormField label="责任人">
            <Input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} />
          </FormField>
          {[
            ["governance", "治理责任已确认"],
            ["risks", "气候风险与机遇已确认"],
            ["strategy", "战略与转型计划已确认"],
          ].map(([code, label]) => (
            <label className="flex items-center gap-3 border-b pb-3" htmlFor={`cdp-${code}`} key={code}>
              <input
                id={`cdp-${code}`}
                type="checkbox"
                className="h-4 w-4 accent-[hsl(var(--admin-accent))]"
                checked={manual[code]}
                onChange={(event) => setManual({ ...manual, [code]: event.target.checked })}
              />
              <span className="text-sm">{label}</span>
            </label>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={save.isPending}>
            保存披露周期
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ClaimDialog({
  open,
  onOpenChange,
  program,
  reportingYear,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  program: ClimateProgramResponse
  reportingYear: number
}) {
  const createClaim = useCreateRenewableElectricityClaim(program.id)
  const [form, setForm] = useState<RenewableElectricityClaimRequest>({
    claimNo: `RE-${reportingYear}-${Date.now().toString().slice(-6)}`,
    sourceType: "green_power",
    reportingYear,
    periodStart: `${reportingYear}-01-01`,
    periodEnd: `${reportingYear}-12-31`,
    quantityMwh: 0,
    generationCountry: "CN",
    consumptionCountry: "CN",
    vintageYear: reportingYear,
    ownershipStatus: "retired",
    sourceName: "企业可再生电力台账",
  })
  const submit = async () => {
    await createClaim.mutateAsync(form)
    onOpenChange(false)
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>登记可再生电力属性</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2 sm:grid-cols-2">
          <FormField label="属性编号">
            <Input value={form.claimNo} onChange={(event) => setForm({ ...form, claimNo: event.target.value })} />
          </FormField>
          <FormField label="来源类型">
            <Select value={form.sourceType} onValueChange={(value) => setForm({ ...form, sourceType: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(claimSourceLabels)
                  .filter(([code]) => code !== "grid")
                  .map(([code, label]) => (
                    <SelectItem key={code} value={code}>
                      {label}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </FormField>
          <NumberField label="电量（MWh）" value={form.quantityMwh} onChange={(value) => setForm({ ...form, quantityMwh: value })} />
          <FormField label="证书或合同编号">
            <Input value={form.certificateNo ?? ""} onChange={(event) => setForm({ ...form, certificateNo: event.target.value || null })} />
          </FormField>
          <FormField label="登记机构">
            <Input value={form.registry ?? ""} onChange={(event) => setForm({ ...form, registry: event.target.value || null })} />
          </FormField>
          <FormField label="凭证索引">
            <Input value={form.evidenceReference ?? ""} onChange={(event) => setForm({ ...form, evidenceReference: event.target.value || null })} />
          </FormField>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={createClaim.isPending || form.quantityMwh <= 0 || !form.evidenceReference}>
            登记并校验
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <FormField label={label}>
      <Input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </FormField>
  )
}
