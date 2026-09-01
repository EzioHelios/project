import { createFileRoute, Link } from "@tanstack/react-router"
import { Download, Plus, RefreshCw } from "lucide-react"
import { useState } from "react"

import { AdminFilterBar, AdminPageScaffold, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { formatReductionNumber, ReductionStatusBadge, reductionCategoryLabels, reductionTrackLabels } from "@/components/carbon/reduction-common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCreateReductionProject, useReductionProjects } from "@/lib/api/hooks/decarbonization"
import type { ReductionProjectRequest } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/carbon/reduction/projects")({ component: ReductionProjectsPage })

const initialProject: ReductionProjectRequest = {
  code: "",
  name: "",
  track: "internal_action",
  category: "energy_efficiency",
  ownerName: "",
  investmentCny: 0,
  expectedReductionTco2E: 0,
  inventoryImpactKind: "none",
}

type ReductionProjectEvidenceRow = NonNullable<ReturnType<typeof useReductionProjects>["data"]>["items"][number] & {
  latestLockedBaselineTco2E?: number | null
  latestCalculationBaselineTco2E?: number | null
  latestCalculationProjectTco2E?: number | null
  latestCalculationReductionTco2E?: number | null
  latestCalculationStatus?: string | null
}

function ReductionProjectsPage() {
  const [keyword, setKeyword] = useState("")
  const [track, setTrack] = useState("all")
  const [category, setCategory] = useState("all")
  const [status, setStatus] = useState("all")
  const [risk, setRisk] = useState("all")
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<ReductionProjectRequest>(initialProject)
  const projects = useReductionProjects({
    keyword: keyword || undefined,
    track: track === "all" ? undefined : track,
    category: category === "all" ? undefined : category,
    status: status === "all" ? undefined : status,
    risk_level: risk === "all" ? undefined : risk,
    limit: 200,
  })
  const createProject = useCreateReductionProject()
  const items = (projects.data?.items ?? []) as ReductionProjectEvidenceRow[]
  const baselineCount = items.filter((item) => item.latestLockedBaselineTco2E != null).length
  const calculatedReduction = items.reduce((sum, item) => sum + (item.latestCalculationReductionTco2E ?? 0), 0)

  const exportProjects = () => {
    const header = ["项目编号", "项目名称", "轨道", "分类", "责任人", "投资（元）", "预计减排量（tCO₂e）", "监测减排量（tCO₂e）", "核查减排量（tCO₂e）", "进度（%）", "阶段"]
    const rows = items.map((item) => [
      item.code,
      item.name,
      reductionTrackLabels[item.track] ?? item.track,
      reductionCategoryLabels[item.category] ?? item.category,
      item.ownerName,
      item.investmentCny,
      item.expectedReductionTco2E,
      item.monitoredReductionTco2E,
      item.verifiedReductionTco2E,
      item.progressPct,
      item.status,
    ])
    const csv = [header, ...rows].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n")
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }))
    const link = document.createElement("a")
    link.href = url
    link.download = `减排项目库-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const submit = async () => {
    await createProject.mutateAsync(form)
    setOpen(false)
    setForm(initialProject)
  }

  return (
    <AdminPageScaffold
      title="减排项目库"
      topActions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4" />
              新建项目
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>新建减排项目</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="project-code">项目编号</Label>
                <Input id="project-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-name">项目名称</Label>
                <Input id="project-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label>项目轨道</Label>
                <Select value={form.track} onValueChange={(value) => setForm({ ...form, track: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(reductionTrackLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>项目分类</Label>
                <Select value={form.category} onValueChange={(value) => setForm({ ...form, category: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(reductionCategoryLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-owner">责任人</Label>
                <Input id="project-owner" value={form.ownerName} onChange={(e) => setForm({ ...form, ownerName: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-department">责任部门</Label>
                <Input id="project-department" value={form.departmentName ?? ""} onChange={(e) => setForm({ ...form, departmentName: e.target.value || null })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-investment">计划投资（元）</Label>
                <Input id="project-investment" type="number" value={form.investmentCny} onChange={(e) => setForm({ ...form, investmentCny: Number(e.target.value) })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-reduction">预计减排量（tCO₂e）</Label>
                <Input
                  id="project-reduction"
                  type="number"
                  value={form.expectedReductionTco2E}
                  onChange={(e) => setForm({ ...form, expectedReductionTco2E: Number(e.target.value) })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button onClick={() => void submit()} disabled={!form.code || !form.name || !form.ownerName || createProject.isPending}>
                保存项目
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      }
      filters={
        <AdminFilterBar
          fields={[
            { key: "search", node: <Input aria-label="搜索项目" placeholder="项目名称或编号" value={keyword} onChange={(e) => setKeyword(e.target.value)} /> },
            {
              key: "track",
              node: (
                <Select value={track} onValueChange={setTrack}>
                  <SelectTrigger aria-label="项目轨道">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部轨道</SelectItem>
                    {Object.entries(reductionTrackLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "category",
              node: (
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger aria-label="项目分类">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部分类</SelectItem>
                    {Object.entries(reductionCategoryLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "status",
              node: (
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger aria-label="项目状态">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部阶段</SelectItem>
                    <SelectItem value="draft">草稿</SelectItem>
                    <SelectItem value="implementing">实施中</SelectItem>
                    <SelectItem value="monitoring">监测中</SelectItem>
                    <SelectItem value="verified">已核查</SelectItem>
                    <SelectItem value="issued">已签发</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "risk",
              node: (
                <Select value={risk} onValueChange={setRisk}>
                  <SelectTrigger aria-label="风险等级">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部风险</SelectItem>
                    <SelectItem value="low">低风险</SelectItem>
                    <SelectItem value="medium">中风险</SelectItem>
                    <SelectItem value="high">高风险</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
          ]}
          actions={
            <>
              <Button variant="outline" size="sm" onClick={exportProjects} disabled={items.length === 0}>
                <Download className="h-4 w-4" />
                导出
              </Button>
              <Button variant="outline" size="sm" onClick={() => void projects.refetch()}>
                <RefreshCw className="h-4 w-4" />
                刷新
              </Button>
            </>
          }
        />
      }
      metrics={
        <MetricStrip>
          <MetricTile label="项目总数" value={projects.data?.total ?? 0} unit="项" tone="domain" />
          <MetricTile label="执行中" value={items.filter((item) => ["implementing", "monitoring"].includes(item.status)).length} unit="项" />
          <MetricTile label="锁定基准线" value={baselineCount} unit="个" />
          <MetricTile label="实际减排计算" value={formatReductionNumber(calculatedReduction)} unit="tCO₂e" tone="success" />
        </MetricStrip>
      }
    >
      <AdminPanel contentClassName="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>项目</TableHead>
              <TableHead>轨道 / 分类</TableHead>
              <TableHead>责任人</TableHead>
              <TableHead>投资</TableHead>
              <TableHead>基准排放</TableHead>
              <TableHead>项目排放</TableHead>
              <TableHead>实际减排</TableHead>
              <TableHead>进度</TableHead>
              <TableHead>阶段</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <div className="font-medium">{item.name}</div>
                  <div className="text-muted-foreground text-xs">{item.code}</div>
                </TableCell>
                <TableCell>
                  <div>{reductionTrackLabels[item.track] ?? item.track}</div>
                  <div className="text-muted-foreground text-xs">{reductionCategoryLabels[item.category] ?? item.category}</div>
                </TableCell>
                <TableCell>
                  <div>{item.ownerName}</div>
                  <div className="text-muted-foreground text-xs">{item.departmentName ?? "-"}</div>
                </TableCell>
                <TableCell className="tabular-nums">{formatReductionNumber(item.investmentCny / 10000)} 万元</TableCell>
                <TableCell className="tabular-nums">
                  <div>{formatReductionNumber(item.latestCalculationBaselineTco2E ?? item.latestLockedBaselineTco2E)} tCO₂e</div>
                  <div className="text-muted-foreground text-xs">锁定基准线</div>
                </TableCell>
                <TableCell className="tabular-nums">
                  <div>{formatReductionNumber(item.latestCalculationProjectTco2E)} tCO₂e</div>
                  <div className="text-muted-foreground text-xs">核算运行</div>
                </TableCell>
                <TableCell className="tabular-nums">
                  <div>{formatReductionNumber(item.latestCalculationReductionTco2E ?? item.verifiedReductionTco2E ?? item.monitoredReductionTco2E)} tCO₂e</div>
                  <div className="text-muted-foreground text-xs">预计 {formatReductionNumber(item.expectedReductionTco2E)} tCO₂e</div>
                </TableCell>
                <TableCell className="tabular-nums">{formatReductionNumber(item.progressPct, 0)}%</TableCell>
                <TableCell>
                  <ReductionStatusBadge status={item.status} />
                </TableCell>
                <TableCell>
                  <Button asChild variant="ghost" size="sm">
                    <Link to="/carbon/reduction/projects/$projectId" params={{ projectId: String(item.id) }}>
                      详情
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminPanel>
    </AdminPageScaffold>
  )
}
