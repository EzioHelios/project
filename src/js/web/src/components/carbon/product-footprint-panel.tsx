import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Calculator, Download, Layers3, Link, Package, Plus, RefreshCw, ShieldCheck } from "lucide-react"
import type { ReactNode } from "react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageScaffold, AdminPanel, AdminTableStateRow, AdminTabsList, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, fetchCarbonApi } from "@/components/carbon/analytics-panels"
import { MaterialResultImport } from "@/components/carbon/material-result-import"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { type PageResult, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { createDistributionChartOption, createRankingChartOption, createSankeyChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"

type ProductFootprintSummary = {
  study_count: number
  calculated_count: number
  incomplete_count: number
  inventory_item_count: number
  latest_study?: ProductFootprintStudy | null
}

type ProductFootprintStudy = {
  id: number
  study_code: string
  study_name: string
  product_code: string
  product_name?: string | null
  product_spec?: string | null
  standard_code: string
  pcr_code?: string | null
  functional_unit?: string | null
  declared_unit?: string | null
  period_start: string
  period_end: string
  boundary_type: string
  status: string
  result_status: string
  inventory_count?: number
  result_count?: number
  latest_result?: ProductFootprintResult | null
}

type ProductSystemBoundary = {
  id?: number
  study_id?: number
  boundary_type?: string | null
  included_stages?: string[] | null
  excluded_stages?: string[] | null
  cutoff_rule?: string | null
  geography?: string | null
  technology_scope?: string | null
  temporal_scope?: string | null
  assumption?: string | null
  standard_code?: string | null
  source_name?: string | null
}

type ProductLifeCycleStage = {
  id: number
  study_id: number
  stage_code: string
  stage_name: string
  sequence: number
  included: boolean
}

type ProductInventoryItem = {
  id: number
  study_id: number
  stage_id?: number | null
  stage_code?: string | null
  stage_name?: string | null
  item_no: string
  activity_type: string
  item_name: string
  activity_amount?: number | null
  activity_unit?: string | null
  factor_id?: number | null
  factor_value?: number | null
  factor_unit?: string | null
  factor_source?: string | null
  supplier_pcf_value?: number | null
  supplier_pcf_unit?: string | null
  supplier_name?: string | null
  allocation_ratio?: number | null
  computed_co2e?: number | null
  calc_status: string
  data_quality?: string | null
  source_type?: string | null
  source_ref?: string | null
  included: boolean
}

type SupplierDataCandidate = {
  id: number
  data_no: string
  data_type: string
  product_code?: string | null
  product_name?: string | null
  material_code?: string | null
  material_name?: string | null
  activity_amount?: number | null
  activity_unit?: string | null
  pcf_value?: number | null
  pcf_unit?: string | null
  data_quality?: string | null
  supplier_name?: string | null
  supplier_code?: string | null
  task_no?: string | null
  task_name?: string | null
  period_start?: string | null
  period_end?: string | null
  match_type?: string | null
  published_to_pcf?: boolean
}

type ProductAllocationRule = {
  id: number
  study_id: number
  process_code?: string | null
  process_name: string
  allocation_method: string
  basis?: string | null
  ratio: number
  source_name?: string | null
}

type ProductFootprintResult = {
  id: number
  study_id: number
  result_version: number
  total_co2e: number
  unit: string
  footprint_per_declared_unit?: number | null
  result_status: string
  inventory_count: number
  missing_factor_count: number
  calculated_at: string
  stage_payload?: StageSummary[]
}

type StageSummary = {
  stage_code: string
  stage_name: string
  kg_co2e: number
  item_count: number
}

type ProductFootprintReport = {
  study: ProductFootprintStudy
  boundary?: ProductSystemBoundary | null
  stages: ProductLifeCycleStage[]
  inventory_items: ProductInventoryItem[]
  allocation_rules: ProductAllocationRule[]
  latest_result?: ProductFootprintResult | null
  stage_summary: StageSummary[]
  quality_summary: Record<string, number>
}

type StudyForm = {
  study_code: string
  study_name: string
  product_code: string
  product_name: string
  product_spec: string
  standard_code: string
  pcr_code: string
  functional_unit: string
  declared_unit: string
  period_start: string
  period_end: string
  boundary_type: string
}

type BoundaryForm = {
  boundary_type: string
  included_stages: string
  excluded_stages: string
  cutoff_rule: string
  geography: string
  technology_scope: string
  temporal_scope: string
  assumption: string
}

type StageForm = {
  stage_code: string
  stage_name: string
  sequence: string
  included: string
}

type InventoryForm = {
  stage_id: string
  item_no: string
  activity_type: string
  item_name: string
  activity_amount: string
  activity_unit: string
  factor_id: string
  factor_value: string
  factor_unit: string
  factor_source: string
  supplier_pcf_value: string
  supplier_pcf_unit: string
  supplier_name: string
  allocation_ratio: string
  data_quality: string
  included: string
}

type SupplierImportForm = {
  supplier_data_id: string
  stage_id: string
  allocation_ratio: string
}

type AllocationForm = {
  process_code: string
  process_name: string
  allocation_method: string
  basis: string
  ratio: string
  source_name: string
}

const QUERY_KEY = ["product-footprint"]

const defaultStudyForm: StudyForm = {
  study_code: "",
  study_name: "",
  product_code: "",
  product_name: "",
  product_spec: "",
  standard_code: "ISO 14067",
  pcr_code: "",
  functional_unit: "",
  declared_unit: "1 件产品",
  period_start: "",
  period_end: "",
  boundary_type: "cradle_to_gate",
}

const defaultBoundaryForm: BoundaryForm = {
  boundary_type: "cradle_to_gate",
  included_stages: "raw_material,manufacturing,transport",
  excluded_stages: "",
  cutoff_rule: "",
  geography: "",
  technology_scope: "",
  temporal_scope: "",
  assumption: "",
}

const defaultStageForm: StageForm = {
  stage_code: "",
  stage_name: "",
  sequence: "1",
  included: "true",
}

const defaultInventoryForm: InventoryForm = {
  stage_id: "",
  item_no: "",
  activity_type: "material",
  item_name: "",
  activity_amount: "",
  activity_unit: "",
  factor_id: "",
  factor_value: "",
  factor_unit: "kgCO2e/unit",
  factor_source: "",
  supplier_pcf_value: "",
  supplier_pcf_unit: "",
  supplier_name: "",
  allocation_ratio: "1",
  data_quality: "measured",
  included: "true",
}

const defaultSupplierImportForm: SupplierImportForm = {
  supplier_data_id: "",
  stage_id: "",
  allocation_ratio: "1",
}

const defaultAllocationForm: AllocationForm = {
  process_code: "",
  process_name: "",
  allocation_method: "physical",
  basis: "",
  ratio: "1",
  source_name: "",
}

const boundaryLabels: Record<string, string> = {
  cradle_to_gate: "摇篮到大门",
  cradle_to_grave: "摇篮到坟墓",
  gate_to_gate: "大门到大门",
}

const resultLabels: Record<string, string> = {
  pending: "待核算",
  stale_source: "待更新",
  not_calculated: "未核算",
  no_inventory: "无清单",
  incomplete_inventory: "清单不完整",
  calculated: "已核算",
}

const activityLabels: Record<string, string> = {
  material: "物料",
  energy: "能源",
  transport: "运输",
  process: "过程",
  waste: "废弃物",
  supplier_pcf: "供应商PCF",
  other: "其他",
}

const supplierMatchLabels: Record<string, string> = {
  data_product: "产品匹配",
  task_product: "任务匹配",
  material: "物料数据",
  approved_pcf: "已审核PCF",
}

export function ProductFootprintPanel({ header }: { header?: ReactNode }) {
  const chartTheme = useAdminChartTheme("carbon")
  const qc = useQueryClient()
  const [selectedStudyId, setSelectedStudyId] = useState<number | null>(null)
  const [studyOpen, setStudyOpen] = useState(false)
  const [stageOpen, setStageOpen] = useState(false)
  const [inventoryOpen, setInventoryOpen] = useState(false)
  const [supplierImportOpen, setSupplierImportOpen] = useState(false)
  const [allocationOpen, setAllocationOpen] = useState(false)
  const [studyForm, setStudyForm] = useState<StudyForm>(defaultStudyForm)
  const [boundaryForm, setBoundaryForm] = useState<BoundaryForm>(defaultBoundaryForm)
  const [stageForm, setStageForm] = useState<StageForm>(defaultStageForm)
  const [inventoryForm, setInventoryForm] = useState<InventoryForm>(defaultInventoryForm)
  const [supplierImportForm, setSupplierImportForm] = useState<SupplierImportForm>(defaultSupplierImportForm)
  const [allocationForm, setAllocationForm] = useState<AllocationForm>(defaultAllocationForm)

  const summaryQuery = useQuery<ApiEnvelope<ProductFootprintSummary>>({
    queryKey: [...QUERY_KEY, "summary"],
    queryFn: () => fetchCarbonApi<ProductFootprintSummary>("/api/carbon/product-footprint/summary"),
  })
  const studiesQuery = useQuery<PageResult<ProductFootprintStudy>>({
    queryKey: [...QUERY_KEY, "studies"],
    queryFn: () => requestPage<ProductFootprintStudy>("/api/carbon/product-footprint/studies", { limit: 100 }),
  })

  const studies = studiesQuery.data?.items ?? []
  const activeStudyId = selectedStudyId ?? studies[0]?.id ?? null
  const activeStudy = useMemo(() => studies.find((item) => item.id === activeStudyId) ?? null, [activeStudyId, studies])

  const boundaryQuery = useQuery<ApiEnvelope<ProductSystemBoundary>>({
    queryKey: [...QUERY_KEY, "boundary", activeStudyId],
    queryFn: () => fetchCarbonApi<ProductSystemBoundary>(`/api/carbon/product-footprint/studies/${activeStudyId}/boundary`),
    enabled: Boolean(activeStudyId),
  })
  const stagesQuery = useQuery<PageResult<ProductLifeCycleStage>>({
    queryKey: [...QUERY_KEY, "stages", activeStudyId],
    queryFn: () => requestPage<ProductLifeCycleStage>("/api/carbon/product-footprint/stages", { study_id: activeStudyId, limit: 200 }),
    enabled: Boolean(activeStudyId),
  })
  const inventoryQuery = useQuery<PageResult<ProductInventoryItem>>({
    queryKey: [...QUERY_KEY, "inventory", activeStudyId],
    queryFn: () => requestPage<ProductInventoryItem>("/api/carbon/product-footprint/inventory-items", { study_id: activeStudyId, limit: 200 }),
    enabled: Boolean(activeStudyId),
  })
  const supplierCandidatesQuery = useQuery<PageResult<SupplierDataCandidate>>({
    queryKey: [...QUERY_KEY, "supplier-data-candidates", activeStudyId],
    queryFn: () => requestPage<SupplierDataCandidate>(`/api/carbon/product-footprint/studies/${activeStudyId}/supplier-data-candidates`, { limit: 100 }),
    enabled: Boolean(activeStudyId),
  })
  const allocationQuery = useQuery<PageResult<ProductAllocationRule>>({
    queryKey: [...QUERY_KEY, "allocations", activeStudyId],
    queryFn: () => requestPage<ProductAllocationRule>("/api/carbon/product-footprint/allocation-rules", { study_id: activeStudyId, limit: 200 }),
    enabled: Boolean(activeStudyId),
  })
  const resultsQuery = useQuery<PageResult<ProductFootprintResult>>({
    queryKey: [...QUERY_KEY, "results", activeStudyId],
    queryFn: () => requestPage<ProductFootprintResult>("/api/carbon/product-footprint/results", { study_id: activeStudyId, limit: 20 }),
    enabled: Boolean(activeStudyId),
  })
  const reportQuery = useQuery<ApiEnvelope<ProductFootprintReport>>({
    queryKey: [...QUERY_KEY, "report", activeStudyId],
    queryFn: () => fetchCarbonApi<ProductFootprintReport>(`/api/carbon/product-footprint/studies/${activeStudyId}/report`),
    enabled: Boolean(activeStudyId),
  })

  const summary = summaryQuery.data?.data
  const stages = stagesQuery.data?.items ?? []
  const inventoryItems = inventoryQuery.data?.items ?? []
  const supplierCandidates = supplierCandidatesQuery.data?.items ?? []
  const allocationRules = allocationQuery.data?.items ?? []
  const results = resultsQuery.data?.items ?? []
  const boundary = boundaryQuery.data?.data
  const latestResult = reportQuery.data?.data.latest_result ?? results[0] ?? activeStudy?.latest_result ?? null
  const stageSummary = reportQuery.data?.data.stage_summary ?? latestResult?.stage_payload ?? []
  const qualitySummary = reportQuery.data?.data.quality_summary ?? {}
  const productFootprintRanking = useMemo(() => buildProductFootprintRanking(studies), [studies])
  const stageDistribution = useMemo(
    () => stageSummary.map((item) => ({ name: item.stage_name || item.stage_code, value: item.kg_co2e })).filter((item) => item.value > 0),
    [stageSummary],
  )
  const stageDistributionOption = useMemo(() => createDistributionChartOption(chartTheme, stageDistribution, { unit: "kgCO2e" }), [chartTheme, stageDistribution])
  const productRankingOption = useMemo(
    () => createRankingChartOption(chartTheme, productFootprintRanking, { unit: "kgCO2e", colorKey: "carbon", limit: 8 }),
    [chartTheme, productFootprintRanking],
  )
  const footprintFlow = useMemo(() => buildProductFootprintFlow(stageSummary, inventoryItems, latestResult?.total_co2e), [stageSummary, inventoryItems, latestResult?.total_co2e])
  const footprintFlowOption = useMemo(
    () =>
      createSankeyChartOption(chartTheme, footprintFlow.nodes, footprintFlow.links, {
        categoryColorMap: {
          product_total: "carbon",
          stage: "energy",
          activity: "scope2",
        },
      }),
    [chartTheme, footprintFlow],
  )

  useEffect(() => {
    if (!activeStudyId) {
      setBoundaryForm(defaultBoundaryForm)
      return
    }
    setBoundaryForm(boundaryToForm(boundary))
  }, [activeStudyId, boundary])

  useEffect(() => {
    if (!supplierImportOpen || supplierImportForm.supplier_data_id || !supplierCandidates.length) return
    setSupplierImportForm((current) => ({ ...current, supplier_data_id: String(supplierCandidates[0].id) }))
  }, [supplierCandidates, supplierImportForm.supplier_data_id, supplierImportOpen])

  const createStudy = useMutation({
    mutationFn: () =>
      request<ProductFootprintStudy>("/api/carbon/product-footprint/studies", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(studyPayload(studyForm)),
      }),
    onSuccess: async (response) => {
      toast.success("产品碳足迹研究已创建")
      setStudyOpen(false)
      setStudyForm(defaultStudyForm)
      setSelectedStudyId(response.data.id)
      await invalidateFootprint(qc)
    },
    onError: toastError("创建研究失败"),
  })

  const saveBoundary = useMutation({
    mutationFn: () =>
      request<ProductSystemBoundary>(`/api/carbon/product-footprint/studies/${activeStudyId}/boundary`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(boundaryPayload(boundaryForm)),
      }),
    onSuccess: async () => {
      toast.success("生命周期边界已保存")
      await invalidateFootprint(qc)
    },
    onError: toastError("保存边界失败"),
  })

  const createStage = useMutation({
    mutationFn: () =>
      request<ProductLifeCycleStage>("/api/carbon/product-footprint/stages", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...stagePayload(stageForm), study_id: activeStudyId }),
      }),
    onSuccess: async () => {
      toast.success("生命周期阶段已创建")
      setStageOpen(false)
      setStageForm(defaultStageForm)
      await invalidateFootprint(qc)
    },
    onError: toastError("创建阶段失败"),
  })

  const createInventory = useMutation({
    mutationFn: () =>
      request<ProductInventoryItem>("/api/carbon/product-footprint/inventory-items", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...inventoryPayload(inventoryForm), study_id: activeStudyId }),
      }),
    onSuccess: async () => {
      toast.success("活动数据已创建")
      setInventoryOpen(false)
      setInventoryForm(defaultInventoryForm)
      await invalidateFootprint(qc)
    },
    onError: toastError("创建活动数据失败"),
  })

  const importSupplierData = useMutation({
    mutationFn: () =>
      request<ProductInventoryItem>(`/api/carbon/product-footprint/studies/${activeStudyId}/import-supplier-data`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(supplierImportPayload(supplierImportForm)),
      }),
    onSuccess: async () => {
      toast.success("供应商数据已引用")
      setSupplierImportOpen(false)
      setSupplierImportForm(defaultSupplierImportForm)
      await invalidateFootprint(qc)
    },
    onError: toastError("引用供应商数据失败"),
  })

  const createAllocation = useMutation({
    mutationFn: () =>
      request<ProductAllocationRule>("/api/carbon/product-footprint/allocation-rules", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...allocationPayload(allocationForm), study_id: activeStudyId }),
      }),
    onSuccess: async () => {
      toast.success("分配规则已创建")
      setAllocationOpen(false)
      setAllocationForm(defaultAllocationForm)
      await invalidateFootprint(qc)
    },
    onError: toastError("创建分配规则失败"),
  })

  const calculateStudy = useMutation({
    mutationFn: () =>
      request<ProductFootprintResult>(`/api/carbon/product-footprint/studies/${activeStudyId}/calculate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      }),
    onSuccess: async () => {
      toast.success("产品碳足迹已核算")
      await invalidateFootprint(qc)
    },
    onError: toastError("核算失败"),
  })

  const exportReport = useMutation({
    mutationFn: async () => {
      if (!activeStudyId) throw new Error("请选择产品碳足迹研究")
      await downloadProductFootprintReport(activeStudyId)
    },
    onSuccess: () => toast.success("产品碳足迹报告已导出"),
    onError: toastError("导出报告失败"),
  })

  return (
    <Tabs defaultValue="studies" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="studies">产品与研究</TabsTrigger>
            <TabsTrigger value="boundary">生命周期边界</TabsTrigger>
            <TabsTrigger value="inventory">活动数据清单</TabsTrigger>
            <TabsTrigger value="allocation">分配与因子</TabsTrigger>
            <TabsTrigger value="results">核算结果</TabsTrigger>
            <TabsTrigger value="report">报告生成</TabsTrigger>
          </AdminTabsList>
        }
      >
        <TabsContent value="studies" className="space-y-4">
          <MetricGrid
            items={[
              { label: "研究数", value: String(summary?.study_count ?? 0), icon: Package },
              { label: "已核算", value: String(summary?.calculated_count ?? 0), icon: ShieldCheck },
              { label: "清单不完整", value: String(summary?.incomplete_count ?? 0), icon: RefreshCw },
              { label: "活动数据", value: String(summary?.inventory_item_count ?? 0), icon: Layers3 },
            ]}
          />
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartPanel title="多产品碳足迹排行" unit="kgCO2e" option={productRankingOption} height={360} emptyLabel="暂无已核算产品排行" />
            <AdminPanel
              title="产品与研究"
              actions={
                <Dialog open={studyOpen} onOpenChange={setStudyOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">
                      <Plus className="size-4" />
                      新建研究
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>新建产品碳足迹研究</DialogTitle>
                      <DialogDescription className="sr-only">维护产品碳足迹研究的基础信息和核算边界。</DialogDescription>
                    </DialogHeader>
                    <StudyFormView value={studyForm} onChange={setStudyForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setStudyOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createStudy.isPending} onClick={() => createStudy.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>研究编号</TableHead>
                      <TableHead>产品</TableHead>
                      <TableHead>边界</TableHead>
                      <TableHead>报告期</TableHead>
                      <TableHead>清单</TableHead>
                      <TableHead>结果</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {studies.map((item) => (
                      <TableRow key={item.id} data-state={item.id === activeStudyId ? "selected" : undefined}>
                        <TableCell>
                          <div className="font-medium">{item.study_code}</div>
                          <div className="text-muted-foreground text-xs">{item.study_name}</div>
                        </TableCell>
                        <TableCell>
                          <div>{item.product_name || item.product_code}</div>
                          <div className="text-muted-foreground text-xs">{item.product_spec || item.product_code}</div>
                        </TableCell>
                        <TableCell>{boundaryLabel(item.boundary_type)}</TableCell>
                        <TableCell>{dateRange(item.period_start, item.period_end)}</TableCell>
                        <TableCell>{item.inventory_count ?? 0}</TableCell>
                        <TableCell>
                          <ResultBadge status={item.result_status} />
                        </TableCell>
                        <TableCell className="text-right">
                          <Button size="sm" variant="outline" onClick={() => setSelectedStudyId(item.id)}>
                            查看
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {!studies.length ? <EmptyRow colSpan={7} label="暂无产品碳足迹研究" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="boundary">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <AdminPanel
              title="生命周期边界"
              actions={
                <Button size="sm" disabled={!activeStudyId || saveBoundary.isPending} onClick={() => saveBoundary.mutate()}>
                  保存边界
                </Button>
              }
            >
              <BoundaryFormView
                value={boundaryForm}
                onChange={(value) => {
                  setBoundaryForm(value)
                }}
              />
            </AdminPanel>
            <AdminPanel
              title="生命周期阶段"
              actions={
                <Dialog open={stageOpen} onOpenChange={setStageOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!activeStudyId}>
                      <Plus className="size-4" />
                      新增阶段
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增生命周期阶段</DialogTitle>
                      <DialogDescription className="sr-only">维护当前产品碳足迹研究的生命周期阶段。</DialogDescription>
                    </DialogHeader>
                    <StageFormView value={stageForm} onChange={setStageForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setStageOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createStage.isPending} onClick={() => createStage.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>阶段编码</TableHead>
                      <TableHead>阶段</TableHead>
                      <TableHead>排序</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stages.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.stage_code}</TableCell>
                        <TableCell>{item.stage_name}</TableCell>
                        <TableCell>{item.sequence}</TableCell>
                        <TableCell>{item.included ? <Badge>纳入</Badge> : <Badge variant="secondary">排除</Badge>}</TableCell>
                      </TableRow>
                    ))}
                    {!stages.length ? <EmptyRow colSpan={4} label="暂无生命周期阶段" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="inventory">
          <AdminPanel
            title="活动数据清单"
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <MaterialResultImport studyId={activeStudyId} stages={stages} />
                <Dialog open={supplierImportOpen} onOpenChange={setSupplierImportOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="outline" disabled={!activeStudyId}>
                      <Link className="size-4" />
                      引用供应商
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-5xl">
                    <DialogHeader>
                      <DialogTitle>引用供应商数据</DialogTitle>
                      <DialogDescription className="sr-only">选择供应链填报数据并引用到产品碳足迹活动清单。</DialogDescription>
                    </DialogHeader>
                    <SupplierImportView candidates={supplierCandidates} stages={stages} value={supplierImportForm} onChange={setSupplierImportForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setSupplierImportOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={importSupplierData.isPending || !supplierImportForm.supplier_data_id} onClick={() => importSupplierData.mutate()}>
                        引用
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
                <Dialog open={inventoryOpen} onOpenChange={setInventoryOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!activeStudyId}>
                      <Plus className="size-4" />
                      新增活动
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-4xl">
                    <DialogHeader>
                      <DialogTitle>新增活动数据</DialogTitle>
                      <DialogDescription className="sr-only">维护产品碳足迹研究的活动数据和排放因子。</DialogDescription>
                    </DialogHeader>
                    <InventoryFormView stages={stages} value={inventoryForm} onChange={setInventoryForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setInventoryOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createInventory.isPending} onClick={() => createInventory.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            }
            contentClassName="p-0"
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>编号</TableHead>
                    <TableHead>阶段</TableHead>
                    <TableHead>活动</TableHead>
                    <TableHead>活动量</TableHead>
                    <TableHead>因子</TableHead>
                    <TableHead>分配</TableHead>
                    <TableHead>结果(kgCO2e)</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {inventoryItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.item_no}</TableCell>
                      <TableCell>{item.stage_name || "-"}</TableCell>
                      <TableCell>
                        <div>{item.item_name}</div>
                        <div className="text-muted-foreground text-xs">{activityLabels[item.activity_type] ?? item.activity_type}</div>
                      </TableCell>
                      <TableCell>{amountWithUnit(item.activity_amount, item.activity_unit)}</TableCell>
                      <TableCell>{factorDisplay(item)}</TableCell>
                      <TableCell>{percent(item.allocation_ratio ?? 1)}</TableCell>
                      <TableCell>{formatNumber(item.computed_co2e)}</TableCell>
                      <TableCell>
                        <CalcStatusBadge status={item.calc_status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {!inventoryItems.length ? <EmptyRow colSpan={8} label="暂无活动数据" /> : null}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>
        </TabsContent>

        <TabsContent value="allocation">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <AdminPanel
              title="分配规则"
              actions={
                <Dialog open={allocationOpen} onOpenChange={setAllocationOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" disabled={!activeStudyId}>
                      <Plus className="size-4" />
                      新增规则
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增分配规则</DialogTitle>
                      <DialogDescription className="sr-only">维护产品碳足迹研究的分配规则。</DialogDescription>
                    </DialogHeader>
                    <AllocationFormView value={allocationForm} onChange={setAllocationForm} />
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setAllocationOpen(false)}>
                        取消
                      </Button>
                      <Button disabled={createAllocation.isPending} onClick={() => createAllocation.mutate()}>
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              }
              contentClassName="p-0"
            >
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>过程</TableHead>
                      <TableHead>方法</TableHead>
                      <TableHead>依据</TableHead>
                      <TableHead>比例</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allocationRules.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div>{item.process_name}</div>
                          <div className="text-muted-foreground text-xs">{item.process_code || "-"}</div>
                        </TableCell>
                        <TableCell>{allocationMethodLabel(item.allocation_method)}</TableCell>
                        <TableCell>{item.basis || "-"}</TableCell>
                        <TableCell>{percent(item.ratio)}</TableCell>
                      </TableRow>
                    ))}
                    {!allocationRules.length ? <EmptyRow colSpan={4} label="暂无分配规则" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
            <AdminPanel title="因子使用" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>活动</TableHead>
                      <TableHead>因子值</TableHead>
                      <TableHead>来源</TableHead>
                      <TableHead>质量</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {inventoryItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.item_name}</TableCell>
                        <TableCell>{factorDisplay(item)}</TableCell>
                        <TableCell>{item.factor_source || item.supplier_name || "-"}</TableCell>
                        <TableCell>{item.data_quality || "-"}</TableCell>
                      </TableRow>
                    ))}
                    {!inventoryItems.length ? <EmptyRow colSpan={4} label="暂无因子使用记录" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>

        <TabsContent value="results" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
            <AdminPanel
              title="核算结果"
              actions={
                <Button size="sm" disabled={!activeStudyId || calculateStudy.isPending} onClick={() => calculateStudy.mutate()}>
                  <Calculator className="size-4" />
                  执行核算
                </Button>
              }
              contentClassName="space-y-4"
            >
              <MetricStrip className="sm:grid-cols-2 xl:grid-cols-2">
                <Kpi label="总量(kgCO2e)" value={formatNumber(latestResult?.total_co2e)} />
                <Kpi label="单位足迹" value={formatNumber(latestResult?.footprint_per_declared_unit)} />
                <Kpi label="纳入清单" value={String(latestResult?.inventory_count ?? 0)} />
                <Kpi label="缺失项" value={String(latestResult?.missing_factor_count ?? 0)} />
              </MetricStrip>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-sm">结果状态</span>
                <ResultBadge status={latestResult?.result_status ?? activeStudy?.result_status} />
              </div>
            </AdminPanel>
            <AdminPanel title="阶段贡献" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>阶段</TableHead>
                      <TableHead>活动数</TableHead>
                      <TableHead>排放量(kgCO2e)</TableHead>
                      <TableHead>占比</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stageSummary.map((item) => (
                      <TableRow key={item.stage_code}>
                        <TableCell>{item.stage_name}</TableCell>
                        <TableCell>{item.item_count}</TableCell>
                        <TableCell>{formatNumber(item.kg_co2e)}</TableCell>
                        <TableCell>{percentOf(item.kg_co2e, latestResult?.total_co2e ?? 0)}</TableCell>
                      </TableRow>
                    ))}
                    {!stageSummary.length ? <EmptyRow colSpan={4} label="暂无阶段结果" /> : null}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
            <ChartPanel title="产品碳足迹总分结构" unit="kgCO2e" option={footprintFlowOption} height={420} emptyLabel="暂无总分结构数据" />
            <ChartPanel title="生命周期阶段构成" unit="kgCO2e" option={stageDistributionOption} height={420} emptyLabel="暂无阶段构成数据" />
          </div>
        </TabsContent>

        <TabsContent value="report">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <AdminPanel
              title="报告上下文"
              actions={
                <Button size="sm" disabled={!activeStudyId || exportReport.isPending} onClick={() => exportReport.mutate()}>
                  <Download className="size-4" />
                  导出报告
                </Button>
              }
              contentClassName="space-y-3 text-sm"
            >
              <KeyValue label="研究编号" value={activeStudy?.study_code} />
              <KeyValue label="产品" value={activeStudy?.product_name || activeStudy?.product_code} />
              <KeyValue label="标准" value={activeStudy?.standard_code} />
              <KeyValue label="PCR" value={activeStudy?.pcr_code} />
              <KeyValue label="功能单位" value={activeStudy?.functional_unit} />
              <KeyValue label="声明单位" value={activeStudy?.declared_unit} />
              <KeyValue label="周期" value={activeStudy ? dateRange(activeStudy.period_start, activeStudy.period_end) : "-"} />
              <KeyValue label="边界" value={boundaryLabel(activeStudy?.boundary_type)} />
            </AdminPanel>
            <AdminPanel title="材料状态" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>项目</TableHead>
                      <TableHead>数量</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>生命周期阶段</TableCell>
                      <TableCell>{stages.length}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>活动数据</TableCell>
                      <TableCell>{inventoryItems.length}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>分配规则</TableCell>
                      <TableCell>{allocationRules.length}</TableCell>
                    </TableRow>
                    {Object.entries(qualitySummary).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell>{calcStatusLabel(key)}</TableCell>
                        <TableCell>{value}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </div>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

function StudyFormView({ value, onChange }: { value: StudyForm; onChange: (value: StudyForm) => void }) {
  const set = (key: keyof StudyForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="研究编号" value={value.study_code} onChange={(next) => set("study_code", next)} />
      <Field label="研究名称" value={value.study_name} onChange={(next) => set("study_name", next)} />
      <Field label="产品编码" value={value.product_code} onChange={(next) => set("product_code", next)} />
      <Field label="产品名称" value={value.product_name} onChange={(next) => set("product_name", next)} />
      <Field label="产品规格" value={value.product_spec} onChange={(next) => set("product_spec", next)} />
      <Field label="标准编号" value={value.standard_code} onChange={(next) => set("standard_code", next)} />
      <Field label="PCR 编号" value={value.pcr_code} onChange={(next) => set("pcr_code", next)} />
      <SelectField
        label="边界类型"
        value={value.boundary_type}
        options={Object.entries(boundaryLabels).map(([optionValue, label]) => ({ label, value: optionValue }))}
        onChange={(next) => set("boundary_type", next)}
      />
      <Field label="功能单位" value={value.functional_unit} onChange={(next) => set("functional_unit", next)} />
      <Field label="声明单位" value={value.declared_unit} onChange={(next) => set("declared_unit", next)} />
      <Field label="开始日期" type="date" value={value.period_start} onChange={(next) => set("period_start", next)} />
      <Field label="结束日期" type="date" value={value.period_end} onChange={(next) => set("period_end", next)} />
    </div>
  )
}

function BoundaryFormView({ value, onChange }: { value: BoundaryForm; onChange: (value: BoundaryForm) => void }) {
  const set = (key: keyof BoundaryForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <SelectField
        label="边界类型"
        value={value.boundary_type}
        options={Object.entries(boundaryLabels).map(([optionValue, label]) => ({ label, value: optionValue }))}
        onChange={(next) => set("boundary_type", next)}
      />
      <Field label="纳入阶段" value={value.included_stages} onChange={(next) => set("included_stages", next)} />
      <Field label="排除阶段" value={value.excluded_stages} onChange={(next) => set("excluded_stages", next)} />
      <Field label="地理范围" value={value.geography} onChange={(next) => set("geography", next)} />
      <Field label="技术范围" value={value.technology_scope} onChange={(next) => set("technology_scope", next)} />
      <Field label="时间范围" value={value.temporal_scope} onChange={(next) => set("temporal_scope", next)} />
      <TextareaField label="截断规则" value={value.cutoff_rule} onChange={(next) => set("cutoff_rule", next)} />
      <TextareaField label="假设" value={value.assumption} onChange={(next) => set("assumption", next)} />
    </div>
  )
}

function StageFormView({ value, onChange }: { value: StageForm; onChange: (value: StageForm) => void }) {
  const set = (key: keyof StageForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <Field label="阶段编码" value={value.stage_code} onChange={(next) => set("stage_code", next)} />
      <Field label="阶段名称" value={value.stage_name} onChange={(next) => set("stage_name", next)} />
      <Field label="排序" type="number" value={value.sequence} onChange={(next) => set("sequence", next)} />
      <SelectField
        label="状态"
        value={value.included}
        options={[
          { label: "纳入", value: "true" },
          { label: "排除", value: "false" },
        ]}
        onChange={(next) => set("included", next)}
      />
    </div>
  )
}

function SupplierImportView({
  candidates,
  stages,
  value,
  onChange,
}: {
  candidates: SupplierDataCandidate[]
  stages: ProductLifeCycleStage[]
  value: SupplierImportForm
  onChange: (value: SupplierImportForm) => void
}) {
  const set = (key: keyof SupplierImportForm, next: string) => onChange({ ...value, [key]: next })
  const selected = candidates.find((item) => String(item.id) === value.supplier_data_id)
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <SelectField
          label="供应商数据"
          value={value.supplier_data_id || "none"}
          options={[
            { label: "未选择", value: "none" },
            ...candidates.map((item) => ({
              label: `${item.supplier_name || "供应商"} · ${item.product_name || item.material_name || item.data_no}`,
              value: String(item.id),
            })),
          ]}
          onChange={(next) => set("supplier_data_id", next === "none" ? "" : next)}
        />
        <SelectField
          label="生命周期阶段"
          value={value.stage_id || "none"}
          options={[{ label: "未分配", value: "none" }, ...stages.map((item) => ({ label: item.stage_name, value: String(item.id) }))]}
          onChange={(next) => set("stage_id", next === "none" ? "" : next)}
        />
        <Field label="分配比例" type="number" value={value.allocation_ratio} onChange={(next) => set("allocation_ratio", next)} />
      </div>
      <AdminDataTable>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>供应商</TableHead>
              <TableHead>对象</TableHead>
              <TableHead>PCF</TableHead>
              <TableHead>周期</TableHead>
              <TableHead>匹配</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.slice(0, 8).map((item) => (
              <TableRow key={item.id} className={selected?.id === item.id ? "bg-muted/50" : undefined}>
                <TableCell>{item.supplier_name || "-"}</TableCell>
                <TableCell>
                  <div>{item.product_name || item.material_name || item.data_no}</div>
                  <div className="text-muted-foreground text-xs">{item.product_code || item.material_code || item.task_no || "-"}</div>
                </TableCell>
                <TableCell>{amountWithUnit(item.pcf_value, item.pcf_unit || "kgCO2e")}</TableCell>
                <TableCell>{dateRange(item.period_start, item.period_end)}</TableCell>
                <TableCell>
                  <Badge variant="outline">{supplierMatchLabels[item.match_type || "approved_pcf"] ?? item.match_type}</Badge>
                </TableCell>
                <TableCell>{item.published_to_pcf ? "已引用" : "可引用"}</TableCell>
              </TableRow>
            ))}
            {!candidates.length ? <EmptyRow colSpan={6} label="暂无可引用供应商数据" /> : null}
          </TableBody>
        </Table>
      </AdminDataTable>
    </div>
  )
}

function InventoryFormView({ stages, value, onChange }: { stages: ProductLifeCycleStage[]; value: InventoryForm; onChange: (value: InventoryForm) => void }) {
  const set = (key: keyof InventoryForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <SelectField
        label="生命周期阶段"
        value={value.stage_id || "none"}
        options={[{ label: "未分配", value: "none" }, ...stages.map((item) => ({ label: item.stage_name, value: String(item.id) }))]}
        onChange={(next) => set("stage_id", next === "none" ? "" : next)}
      />
      <Field label="活动编号" value={value.item_no} onChange={(next) => set("item_no", next)} />
      <SelectField
        label="活动类型"
        value={value.activity_type}
        options={Object.entries(activityLabels).map(([optionValue, label]) => ({ label, value: optionValue }))}
        onChange={(next) => set("activity_type", next)}
      />
      <Field label="活动名称" value={value.item_name} onChange={(next) => set("item_name", next)} />
      <Field label="活动量" type="number" value={value.activity_amount} onChange={(next) => set("activity_amount", next)} />
      <Field label="活动单位" value={value.activity_unit} onChange={(next) => set("activity_unit", next)} />
      <Field label="因子 ID" type="number" value={value.factor_id} onChange={(next) => set("factor_id", next)} />
      <Field label="因子值" type="number" value={value.factor_value} onChange={(next) => set("factor_value", next)} />
      <Field label="因子单位" value={value.factor_unit} onChange={(next) => set("factor_unit", next)} />
      <Field label="因子来源" value={value.factor_source} onChange={(next) => set("factor_source", next)} />
      <Field label="供应商 PCF" type="number" value={value.supplier_pcf_value} onChange={(next) => set("supplier_pcf_value", next)} />
      <Field label="供应商" value={value.supplier_name} onChange={(next) => set("supplier_name", next)} />
      <Field label="分配比例" type="number" value={value.allocation_ratio} onChange={(next) => set("allocation_ratio", next)} />
      <Field label="数据质量" value={value.data_quality} onChange={(next) => set("data_quality", next)} />
      <SelectField
        label="状态"
        value={value.included}
        options={[
          { label: "纳入", value: "true" },
          { label: "排除", value: "false" },
        ]}
        onChange={(next) => set("included", next)}
      />
    </div>
  )
}

function AllocationFormView({ value, onChange }: { value: AllocationForm; onChange: (value: AllocationForm) => void }) {
  const set = (key: keyof AllocationForm, next: string) => onChange({ ...value, [key]: next })
  return (
    <div className="grid gap-4">
      <Field label="过程编码" value={value.process_code} onChange={(next) => set("process_code", next)} />
      <Field label="过程名称" value={value.process_name} onChange={(next) => set("process_name", next)} />
      <SelectField
        label="分配方法"
        value={value.allocation_method}
        options={[
          { label: "物理分配", value: "physical" },
          { label: "经济分配", value: "economic" },
          { label: "质量分配", value: "mass" },
          { label: "能量分配", value: "energy" },
          { label: "不分配", value: "none" },
        ]}
        onChange={(next) => set("allocation_method", next)}
      />
      <Field label="分配依据" value={value.basis} onChange={(next) => set("basis", next)} />
      <Field label="比例" type="number" value={value.ratio} onChange={(next) => set("ratio", next)} />
      <Field label="来源" value={value.source_name} onChange={(next) => set("source_name", next)} />
    </div>
  )
}

function MetricGrid({ items }: { items: { label: string; value: string; icon: typeof Package }[] }) {
  return (
    <MetricStrip className="sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} />
      ))}
    </MetricStrip>
  )
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <MetricTile label={label} value={value} />
}

function KeyValue({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b py-2 last:border-b-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{value || "-"}</span>
    </div>
  )
}

function buildProductFootprintRanking(studies: ProductFootprintStudy[]) {
  return studies
    .map((study) => ({
      name: study.product_name || study.study_name || study.product_code,
      value: Number(study.latest_result?.total_co2e ?? 0),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
}

function buildProductFootprintFlow(stageSummary: StageSummary[], inventoryItems: ProductInventoryItem[], total?: number | null) {
  const stages = stageSummary.filter((item) => item.kg_co2e > 0)
  const totalValue = Number(total ?? stages.reduce((sum, item) => sum + item.kg_co2e, 0))
  if (!stages.length || totalValue <= 0) return { nodes: [], links: [] }

  const nodes = [{ id: "product-total", name: "产品总足迹", value: totalValue, category: "product_total" }]
  const links: { source: string; target: string; value: number }[] = []

  for (const stage of stages) {
    const stageId = `stage-${stage.stage_code}`
    nodes.push({ id: stageId, name: stage.stage_name || stage.stage_code, value: stage.kg_co2e, category: "stage" })
    links.push({ source: "product-total", target: stageId, value: stage.kg_co2e })

    const stageItems = inventoryItems
      .filter((item) => item.included && item.stage_code === stage.stage_code && Number(item.computed_co2e ?? 0) > 0)
      .map((item) => ({ id: `item-${item.id}`, name: item.item_name, value: Number(item.computed_co2e ?? 0) }))
      .sort((a, b) => b.value - a.value)

    const visibleItems = stageItems.slice(0, 4)
    for (const item of visibleItems) {
      nodes.push({ ...item, category: "activity" })
      links.push({ source: stageId, target: item.id, value: item.value })
    }

    const otherValue = stageItems.slice(4).reduce((sum, item) => sum + item.value, 0)
    if (otherValue > 0) {
      const otherId = `${stageId}-other`
      nodes.push({ id: otherId, name: "其他活动", value: otherValue, category: "activity" })
      links.push({ source: stageId, target: otherId, value: otherValue })
    }
  }

  return { nodes, links }
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function TextareaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: { label: string; value: string }[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function ResultBadge({ status }: { status?: string | null }) {
  const value = status || "not_calculated"
  if (value === "calculated") return <CarbonStatusBadge status="approved" />
  if (value === "incomplete_inventory") return <Badge variant="outline">{resultLabels[value]}</Badge>
  return <Badge variant="secondary">{resultLabels[value] ?? value}</Badge>
}

function CalcStatusBadge({ status }: { status: string }) {
  if (status === "ready") return <Badge>可核算</Badge>
  if (status === "excluded") return <Badge variant="secondary">排除</Badge>
  return <Badge variant="outline">{calcStatusLabel(status)}</Badge>
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return <AdminTableStateRow colSpan={colSpan}>{label}</AdminTableStateRow>
}

function studyPayload(form: StudyForm) {
  return {
    ...form,
    product_name: optional(form.product_name),
    product_spec: optional(form.product_spec),
    pcr_code: optional(form.pcr_code),
    functional_unit: optional(form.functional_unit),
    source_name: "product_footprint",
    confidence_level: "medium",
  }
}

function boundaryPayload(form: BoundaryForm) {
  return {
    ...form,
    included_stages: splitList(form.included_stages),
    excluded_stages: splitList(form.excluded_stages),
    cutoff_rule: optional(form.cutoff_rule),
    geography: optional(form.geography),
    technology_scope: optional(form.technology_scope),
    temporal_scope: optional(form.temporal_scope),
    assumption: optional(form.assumption),
    standard_code: "ISO 14067",
    source_name: "product_footprint",
  }
}

function stagePayload(form: StageForm) {
  return {
    stage_code: form.stage_code.trim(),
    stage_name: form.stage_name.trim(),
    sequence: toNumber(form.sequence) ?? 1,
    included: form.included === "true",
  }
}

function inventoryPayload(form: InventoryForm) {
  return {
    stage_id: toNumber(form.stage_id),
    item_no: form.item_no.trim(),
    activity_type: form.activity_type,
    item_name: form.item_name.trim(),
    activity_amount: toNumber(form.activity_amount),
    activity_unit: optional(form.activity_unit),
    factor_id: toNumber(form.factor_id),
    factor_value: toNumber(form.factor_value),
    factor_unit: optional(form.factor_unit),
    factor_source: optional(form.factor_source),
    supplier_pcf_value: toNumber(form.supplier_pcf_value),
    supplier_pcf_unit: optional(form.supplier_pcf_unit),
    supplier_name: optional(form.supplier_name),
    allocation_ratio: toNumber(form.allocation_ratio) ?? 1,
    data_quality: optional(form.data_quality),
    source_type: "manual",
    included: form.included === "true",
  }
}

function supplierImportPayload(form: SupplierImportForm) {
  return {
    supplier_data_id: toNumber(form.supplier_data_id),
    stage_id: toNumber(form.stage_id),
    allocation_ratio: toNumber(form.allocation_ratio) ?? 1,
  }
}

function allocationPayload(form: AllocationForm) {
  return {
    process_code: optional(form.process_code),
    process_name: form.process_name.trim(),
    allocation_method: form.allocation_method,
    basis: optional(form.basis),
    ratio: toNumber(form.ratio) ?? 1,
    source_name: optional(form.source_name),
  }
}

function boundaryToForm(boundary?: ProductSystemBoundary | null): BoundaryForm {
  if (!boundary?.id) return defaultBoundaryForm
  return {
    boundary_type: boundary.boundary_type || defaultBoundaryForm.boundary_type,
    included_stages: (boundary.included_stages || []).join(","),
    excluded_stages: (boundary.excluded_stages || []).join(","),
    cutoff_rule: boundary.cutoff_rule || "",
    geography: boundary.geography || "",
    technology_scope: boundary.technology_scope || "",
    temporal_scope: boundary.temporal_scope || "",
    assumption: boundary.assumption || "",
  }
}

function optional(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function toNumber(value: string) {
  if (!value) return undefined
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function boundaryLabel(value?: string | null) {
  return value ? (boundaryLabels[value] ?? value) : "-"
}

function allocationMethodLabel(value: string) {
  return (
    {
      physical: "物理分配",
      economic: "经济分配",
      mass: "质量分配",
      energy: "能量分配",
      none: "不分配",
    }[value] ?? value
  )
}

function calcStatusLabel(value: string) {
  return (
    {
      ready: "可核算",
      pending_factor: "缺因子",
      incomplete_activity: "缺活动量",
      excluded: "排除",
    }[value] ?? value
  )
}

function amountWithUnit(value?: number | null, unit?: string | null) {
  if (value === null || value === undefined) return "-"
  return `${formatNumber(value)} ${unit || ""}`.trim()
}

function factorDisplay(item: ProductInventoryItem) {
  if (item.supplier_pcf_value !== null && item.supplier_pcf_value !== undefined) {
    return amountWithUnit(item.supplier_pcf_value, item.supplier_pcf_unit || "kgCO2e")
  }
  return item.factor_value !== null && item.factor_value !== undefined ? amountWithUnit(item.factor_value, item.factor_unit) : "-"
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "-"
  return `${start || "-"} 至 ${end || "-"}`
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value)
}

function percent(value: number) {
  return `${formatNumber(value * 100)}%`
}

function percentOf(value: number, total: number) {
  if (!total) return "-"
  return percent(value / total)
}

function toastError(prefix: string) {
  return (error: Error) => toast.error(prefix, { description: error.message })
}

async function downloadProductFootprintReport(studyId: number) {
  const response = await fetch(`/api/carbon/product-footprint/studies/${studyId}/export-report`, { method: "POST" })
  if (!response.ok) {
    const text = await response.text()
    let message = `HTTP ${response.status}`
    try {
      const payload = JSON.parse(text) as { msg?: string; detail?: string }
      message = payload.msg || payload.detail || message
    } catch {
      message = text || message
    }
    throw new Error(message)
  }
  const blob = await response.blob()
  const filename = filenameFromDisposition(response.headers.get("content-disposition")) ?? `product-footprint-report-${studyId}.zip`
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function filenameFromDisposition(disposition: string | null) {
  if (!disposition) return null
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) return decodeURIComponent(encoded)
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return plain || null
}

async function invalidateFootprint(qc: ReturnType<typeof useQueryClient>) {
  await qc.invalidateQueries({ queryKey: QUERY_KEY })
}
