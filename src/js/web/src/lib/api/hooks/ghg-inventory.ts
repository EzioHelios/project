import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  type BoundaryDiffResponse,
  type BoundarySelectionResponse,
  type GhgActivityResponse,
  type GhgActivityWriteRequest,
  type GhgAnalyticsFlowResponse,
  type GhgAnalyticsOverviewResponse,
  type GhgAnalyticsTrendResponse,
  type GhgCalculationRunListResponse,
  type GhgCatalogResponse,
  type GhgComparisonResponse,
  type GhgEmissionSourceResponse,
  type GhgEmissionSourceWriteRequest,
  type GhgImportBatchResponse,
  type GhgInventoryReadinessResponse,
  type GhgInventoryReportDeleteResponse,
  type GhgInventoryReportListResponse,
  type GhgInventoryReportResponse,
  type GhgInventoryReportUpdateRequest,
  type GhgResultDetailResponse,
  type GhgResultListResponse,
  type GhgResultSummaryResponse,
  ghgInventoryApproveReport,
  ghgInventoryArchiveReport,
  ghgInventoryCommitWorkbook,
  ghgInventoryCreateActivity,
  ghgInventoryCreateEmissionSource,
  ghgInventoryCreateReport,
  ghgInventoryDeleteActivity,
  ghgInventoryDeleteEmissionSource,
  ghgInventoryDeleteReport,
  ghgInventoryDownloadTemplate,
  ghgInventoryExportReport,
  ghgInventoryExportResults,
  ghgInventoryGenerateActivities,
  ghgInventoryGetActivity,
  ghgInventoryGetActivityAllocations,
  ghgInventoryGetAnalyticsComparison,
  ghgInventoryGetAnalyticsFlow,
  ghgInventoryGetAnalyticsOverview,
  ghgInventoryGetAnalyticsTrend,
  ghgInventoryGetCatalog,
  ghgInventoryGetEmissionSource,
  ghgInventoryGetReadiness,
  ghgInventoryGetReport,
  ghgInventoryGetResultDetail,
  ghgInventoryGetResultSummary,
  ghgInventoryListActivities,
  ghgInventoryListCalculationRuns,
  ghgInventoryListEmissionSources,
  ghgInventoryListImportBatches,
  ghgInventoryListReports,
  ghgInventoryListResults,
  ghgInventoryPreviewWorkbook,
  ghgInventoryPublishReport,
  ghgInventoryRejectReport,
  ghgInventoryReplaceActivityAllocations,
  ghgInventoryResubmitReport,
  ghgInventoryRunCalculation,
  ghgInventorySubmitReport,
  ghgInventoryUpdateActivity,
  ghgInventoryUpdateEmissionSource,
  ghgInventoryUpdateReport,
  organizationBoundaryCreateWorkingCopy,
  organizationBoundaryDiscardDraft,
  organizationBoundaryGetDiff,
  organizationBoundaryGetSelection,
  organizationBoundaryPublish,
  organizationBoundarySaveSelection,
  type SaveBoundarySelectionRequest,
} from "@/lib/generated/api"

export type GhgCatalog = GhgCatalogResponse
export type GhgImportBatch = GhgImportBatchResponse
export type GhgActivity = GhgActivityResponse
export type GhgActivityWrite = GhgActivityWriteRequest
export type GhgEmissionSource = GhgEmissionSourceResponse
export type GhgEmissionSourceWrite = GhgEmissionSourceWriteRequest
export type GhgAnalyticsOverview = GhgAnalyticsOverviewResponse
export type GhgAnalyticsTrend = GhgAnalyticsTrendResponse
export type GhgAnalyticsFlow = GhgAnalyticsFlowResponse
export type GhgCalculationRunList = GhgCalculationRunListResponse
export type GhgResultList = GhgResultListResponse
export type GhgResultDetail = GhgResultDetailResponse
export type GhgResultSummary = GhgResultSummaryResponse
export type GhgComparison = GhgComparisonResponse
export type OrganizationBoundarySelection = BoundarySelectionResponse
export type OrganizationBoundaryDiff = BoundaryDiffResponse
export type GhgInventoryReadiness = GhgInventoryReadinessResponse
export type GhgInventoryReportList = GhgInventoryReportListResponse
export type GhgInventoryReport = GhgInventoryReportResponse
export type GhgInventoryReportUpdate = GhgInventoryReportUpdateRequest
export type GhgInventoryReportDelete = GhgInventoryReportDeleteResponse

export type GhgImportContext = {
  inventoryCode: string
  reportingPeriodId?: number
  organizationCode: string
  facilityCode: string
  isoCategoryCode: string
  reportingProfileCode: string
  methodCode: string
}

export function useGhgCatalog() {
  return useQuery({
    queryKey: ["ghg-inventory", "catalog"],
    queryFn: async () => (await ghgInventoryGetCatalog({ throwOnError: true })).data,
  })
}

export function useGhgActivities(filters: { inventoryCode?: string; categoryCode?: string; qualityStatus?: string }) {
  return useQuery({
    queryKey: ["ghg-inventory", "activities", filters],
    queryFn: async () =>
      (
        await ghgInventoryListActivities({
          query: {
            inventory_code: filters.inventoryCode || undefined,
            category_code: filters.categoryCode || undefined,
            quality_status: filters.qualityStatus || undefined,
            limit: 200,
          },
          throwOnError: true,
        })
      ).data,
  })
}

export function useGhgActivity(filters: { inventoryCode?: string; recordCode?: string }) {
  return useQuery({
    queryKey: ["ghg-inventory", "activities", "detail", filters],
    queryFn: async () => {
      if (!filters.inventoryCode || !filters.recordCode) throw new Error("缺少活动记录上下文")
      return (
        await ghgInventoryGetActivity({
          path: { record_code: filters.recordCode },
          query: { inventory_code: filters.inventoryCode },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.inventoryCode && filters.recordCode),
  })
}

export function useGhgEmissionSources(filters: { inventoryCode?: string; categoryCode?: string; status?: string; keyword?: string }) {
  return useQuery({
    queryKey: ["ghg-inventory", "emission-sources", filters],
    queryFn: async () =>
      (
        await ghgInventoryListEmissionSources({
          query: {
            inventory_code: filters.inventoryCode,
            category_code: filters.categoryCode,
            status: filters.status,
            keyword: filters.keyword,
            limit: 300,
          },
          throwOnError: true,
        })
      ).data,
  })
}

export function useGhgEmissionSource(filters: { inventoryCode?: string; sourceCode?: string }) {
  return useQuery({
    queryKey: ["ghg-inventory", "emission-sources", "detail", filters],
    queryFn: async () => {
      if (!filters.inventoryCode || !filters.sourceCode) throw new Error("缺少排放源上下文")
      return (
        await ghgInventoryGetEmissionSource({
          path: { source_code: filters.sourceCode },
          query: { inventory_code: filters.inventoryCode },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.inventoryCode && filters.sourceCode),
  })
}

export function useGhgActivityAllocations(filters: { inventoryCode?: string; recordCode?: string }) {
  return useQuery({
    queryKey: ["ghg-inventory", "activities", "allocations", filters],
    queryFn: async () => {
      if (!filters.inventoryCode || !filters.recordCode) throw new Error("缺少归集上下文")
      return (
        await ghgInventoryGetActivityAllocations({
          path: { record_code: filters.recordCode },
          query: { inventory_code: filters.inventoryCode },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.inventoryCode && filters.recordCode),
  })
}

export function useGhgImportBatches() {
  return useQuery({
    queryKey: ["ghg-inventory", "import-batches"],
    queryFn: async () => (await ghgInventoryListImportBatches({ query: { limit: 50 }, throwOnError: true })).data,
  })
}

export function useGhgCalculationRuns(
  filters: { inventoryCode?: string; reportingOrgId?: number; reportingPeriodId?: number; organizationBoundaryId?: number; status?: string } = {},
) {
  return useQuery({
    queryKey: ["ghg-inventory", "calculation-runs", filters],
    queryFn: async () =>
      (
        await ghgInventoryListCalculationRuns({
          query: {
            inventory_code: filters.inventoryCode,
            reporting_org_id: filters.reportingOrgId,
            reporting_period_id: filters.reportingPeriodId,
            organization_boundary_id: filters.organizationBoundaryId,
            status: filters.status,
            limit: 100,
          },
          throwOnError: true,
        })
      ).data,
  })
}

export type GhgAnalyticsFilters = {
  runCode?: string
  scope2Method: "location" | "market"
  dateFrom?: string
  dateTo?: string
  ghgScope?: string
  isoCategoryCode?: string
  sourceCode?: string
  sourceMechanism?: string
  areaId?: number
  includeDescendants?: boolean
  equipmentId?: number
  qualityStatus?: string
  keyword?: string
}

function analyticsQuery(filters: GhgAnalyticsFilters) {
  return {
    run_code: filters.runCode,
    scope2_method: filters.scope2Method,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    ghg_scope: filters.ghgScope,
    iso_category_code: filters.isoCategoryCode,
    source_code: filters.sourceCode,
    source_mechanism: filters.sourceMechanism,
    area_id: filters.areaId,
    include_descendants: filters.includeDescendants ?? true,
    equipment_id: filters.equipmentId,
    quality_status: filters.qualityStatus,
  }
}

export function useGhgAnalyticsOverview(filters: GhgAnalyticsFilters) {
  return useQuery({
    queryKey: ["ghg-inventory", "analytics", "overview", filters],
    queryFn: async () => {
      if (!filters.runCode) throw new Error("请选择核算运行")
      return (
        await ghgInventoryGetAnalyticsOverview({
          query: analyticsQuery(filters),
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.runCode),
  })
}

export function useGhgAnalyticsTrend(filters: GhgAnalyticsFilters & { reportingOrgId?: number; grain?: "month" | "quarter" | "year" }) {
  return useQuery({
    queryKey: ["ghg-inventory", "analytics", "trend", filters],
    queryFn: async () => {
      if (!filters.runCode) throw new Error("请选择核算运行")
      return (
        await ghgInventoryGetAnalyticsTrend({
          query: { ...analyticsQuery(filters), reporting_org_id: filters.reportingOrgId, grain: filters.grain ?? "month", limit: 60 },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.runCode),
  })
}

export function useGhgAnalyticsFlow(filters: GhgAnalyticsFilters & { classification: "scope" | "iso_category" }) {
  return useQuery({
    queryKey: ["ghg-inventory", "analytics", "flow", filters],
    queryFn: async () => {
      if (!filters.runCode) throw new Error("请选择核算运行")
      return (
        await ghgInventoryGetAnalyticsFlow({
          query: { ...analyticsQuery(filters), run_code: filters.runCode, classification: filters.classification },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.runCode),
  })
}

export type GhgResultFilters = GhgAnalyticsFilters & { page?: number; pageSize?: 25 | 50 | 100; sortBy?: string; sortOrder?: "asc" | "desc" }

export function useGhgResults(filters: GhgResultFilters) {
  return useQuery({
    queryKey: ["ghg-inventory", "results", filters],
    queryFn: async () => {
      if (!filters.runCode) throw new Error("请选择核算运行")
      return (
        await ghgInventoryListResults({
          query: {
            ...analyticsQuery(filters),
            run_code: filters.runCode,
            keyword: filters.keyword,
            page: filters.page ?? 1,
            page_size: filters.pageSize ?? 25,
            sort_by: filters.sortBy ?? "period_start",
            sort_order: filters.sortOrder ?? "desc",
          },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.runCode),
  })
}

export function useGhgResultSummary(filters: GhgAnalyticsFilters) {
  return useQuery({
    queryKey: ["ghg-inventory", "results", "summary", filters],
    queryFn: async () => {
      if (!filters.runCode) throw new Error("请选择核算运行")
      return (await ghgInventoryGetResultSummary({ query: { ...analyticsQuery(filters), run_code: filters.runCode, keyword: filters.keyword }, throwOnError: true })).data
    },
    enabled: Boolean(filters.runCode),
  })
}

export function useGhgComparison(filters: GhgAnalyticsFilters & { runCodes: string[] }) {
  return useQuery({
    queryKey: ["ghg-inventory", "analytics", "comparison", filters],
    queryFn: async () =>
      (
        await ghgInventoryGetAnalyticsComparison({
          query: { ...analyticsQuery(filters), run_codes: filters.runCodes.join(",") },
          throwOnError: true,
        })
      ).data,
    enabled: filters.runCodes.length >= 2 && filters.runCodes.length <= 3,
  })
}

export async function exportGhgResults(filters: GhgAnalyticsFilters) {
  if (!filters.runCode) throw new Error("请选择核算运行")
  const response = await ghgInventoryExportResults({
    query: { ...analyticsQuery(filters), run_code: filters.runCode, keyword: filters.keyword },
    parseAs: "blob",
    throwOnError: true,
  })
  const blob = response.data as unknown as Blob
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `组织碳排放查询_${filters.runCode}.xlsx`
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function exportGhgInventoryReport(reportCode: string, version: number, fileFormat: "docx" | "pdf") {
  const response = await ghgInventoryExportReport({
    path: { report_code: reportCode, version },
    query: { file_format: fileFormat },
    parseAs: "blob",
    throwOnError: true,
  })
  const blob = response.data as unknown as Blob
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `组织温室气体盘查报告_${reportCode}_v${version}.${fileFormat}`
  anchor.click()
  URL.revokeObjectURL(url)
}

export function useGhgResultDetail(filters: { runCode?: string; recordCode?: string; scope2Method: "location" | "market" }) {
  return useQuery({
    queryKey: ["ghg-inventory", "results", "detail", filters],
    queryFn: async () => {
      if (!filters.runCode || !filters.recordCode) throw new Error("缺少核算结果上下文")
      return (
        await ghgInventoryGetResultDetail({
          path: { record_code: filters.recordCode },
          query: { run_code: filters.runCode, scope2_method: filters.scope2Method },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.runCode && filters.recordCode),
  })
}

export function useGhgInventoryReadiness(filters: { inventoryCode?: string; reportingPeriodId?: number; organizationBoundaryId?: number }) {
  return useQuery({
    queryKey: ["ghg-inventory", "readiness", filters],
    queryFn: async () => {
      if (!filters.inventoryCode) throw new Error("请选择盘查任务")
      return (
        await ghgInventoryGetReadiness({
          query: {
            inventory_code: filters.inventoryCode,
            reporting_period_id: filters.reportingPeriodId,
            organization_boundary_id: filters.organizationBoundaryId,
          },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(filters.inventoryCode),
  })
}

export function useGhgInventoryReports() {
  return useQuery({
    queryKey: ["ghg-inventory", "reports"],
    queryFn: async () => (await ghgInventoryListReports({ query: { limit: 100 }, throwOnError: true })).data,
  })
}

export function useGhgInventoryReport(reportCode?: string, version?: number) {
  return useQuery({
    queryKey: ["ghg-inventory", "reports", reportCode, version],
    queryFn: async () => {
      if (!reportCode || !version) throw new Error("请选择盘查报告")
      return (await ghgInventoryGetReport({ path: { report_code: reportCode, version }, throwOnError: true })).data
    },
    enabled: Boolean(reportCode && version),
  })
}

export function useGhgInventoryActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => queryClient.invalidateQueries({ queryKey: ["ghg-inventory"] })

  const createSource = useMutation({
    mutationFn: async (body: GhgEmissionSourceWrite) => (await ghgInventoryCreateEmissionSource({ body, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("排放源已保存")
    },
    onError: (error: Error) => toast.error("排放源保存失败", { description: error.message }),
  })

  const updateSource = useMutation({
    mutationFn: async ({ sourceCode, body }: { sourceCode: string; body: GhgEmissionSourceWrite }) =>
      (await ghgInventoryUpdateEmissionSource({ path: { source_code: sourceCode }, body, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("排放源已更新")
    },
    onError: (error: Error) => toast.error("排放源更新失败", { description: error.message }),
  })

  const deleteSource = useMutation({
    mutationFn: async ({ inventoryCode, sourceCode }: { inventoryCode: string; sourceCode: string }) =>
      (await ghgInventoryDeleteEmissionSource({ path: { source_code: sourceCode }, query: { inventory_code: inventoryCode }, throwOnError: true })).data,
    onSuccess: async (data) => {
      await invalidate()
      toast.success(data.deleted ? "排放源已删除" : "排放源已停用")
    },
    onError: (error: Error) => toast.error("排放源删除失败", { description: error.message }),
  })

  const createActivity = useMutation({
    mutationFn: async (body: GhgActivityWrite) => (await ghgInventoryCreateActivity({ body, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("活动数据已保存")
    },
    onError: (error: Error) => toast.error("活动数据保存失败", { description: error.message }),
  })

  const updateActivity = useMutation({
    mutationFn: async ({ recordCode, body }: { recordCode: string; body: GhgActivityWrite }) =>
      (await ghgInventoryUpdateActivity({ path: { record_code: recordCode }, body, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("活动数据已更新")
    },
    onError: (error: Error) => toast.error("活动数据更新失败", { description: error.message }),
  })

  const deleteActivity = useMutation({
    mutationFn: async ({ inventoryCode, recordCode }: { inventoryCode: string; recordCode: string }) =>
      (await ghgInventoryDeleteActivity({ path: { record_code: recordCode }, query: { inventory_code: inventoryCode }, throwOnError: true })).data,
    onSuccess: async (data) => {
      await invalidate()
      toast.success(data.deleted ? "活动数据已删除" : "活动数据已归档")
    },
    onError: (error: Error) => toast.error("活动数据删除失败", { description: error.message }),
  })

  const generateActivities = useMutation({
    mutationFn: async (body: { inventoryCode: string; reportingPeriodId: number; organizationBoundaryId?: number; sourceTypes: string[] }) =>
      (await ghgInventoryGenerateActivities({ body, throwOnError: true })).data,
    onSuccess: async (data) => {
      await invalidate()
      toast.success("活动数据生成完成", { description: `新增 ${data.createdCount} 条，更新 ${data.updatedCount} 条，跳过 ${data.skippedCount} 条` })
    },
    onError: (error: Error) => toast.error("活动数据生成失败", { description: error.message }),
  })

  const replaceAllocations = useMutation({
    mutationFn: async ({
      inventoryCode,
      recordCode,
      allocations,
    }: {
      inventoryCode: string
      recordCode: string
      allocations: Array<{
        allocationCode?: string
        areaId: number
        equipmentId?: number
        measurementBoundaryId?: number
        allocationRole: string
        allocationRatio: string
        externalFacilityCode?: string
        externalFacilityName?: string
        sourceKind?: string
      }>
    }) =>
      (
        await ghgInventoryReplaceActivityAllocations({
          path: { record_code: recordCode },
          body: { inventoryCode, allocations },
          throwOnError: true,
        })
      ).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("区域设备归集已保存")
    },
    onError: (error: Error) => toast.error("归集保存失败", { description: error.message }),
  })

  const downloadTemplate = useMutation({
    mutationFn: async (context: GhgImportContext) => {
      const response = await ghgInventoryDownloadTemplate({
        query: {
          inventory_code: context.inventoryCode,
          organization_code: context.organizationCode,
          facility_code: context.facilityCode,
          iso_category_code: context.isoCategoryCode,
          reporting_profile_code: context.reportingProfileCode,
          method_code: context.methodCode,
        },
        parseAs: "blob",
        throwOnError: true,
      })
      const blob = response.data as unknown as Blob
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `温室气体活动数据_${context.isoCategoryCode.replace(".", "-")}.xlsx`
      anchor.click()
      URL.revokeObjectURL(url)
    },
    onError: (error: Error) => toast.error("模板下载失败", { description: error.message }),
  })

  const preview = useMutation({
    mutationFn: async ({ context, file }: { context: GhgImportContext; file: File }) => {
      const workbookBase64 = await readFileBase64(file)
      return (
        await ghgInventoryPreviewWorkbook({
          body: {
            inventoryCode: context.inventoryCode,
            reportingPeriodId: context.reportingPeriodId,
            organizationCode: context.organizationCode,
            facilityCode: context.facilityCode,
            isoCategoryCode: context.isoCategoryCode,
            reportingProfileCode: context.reportingProfileCode,
            methodCode: context.methodCode,
            fileName: file.name,
            workbookBase64,
          },
          throwOnError: true,
        })
      ).data
    },
    onSuccess: async () => {
      await invalidate()
      toast.success("预检完成")
    },
    onError: (error: Error) => toast.error("预检失败", { description: error.message }),
  })

  const commit = useMutation({
    mutationFn: async ({ batchCode, acknowledgeWarnings, warningAcknowledgement }: { batchCode: string; acknowledgeWarnings: boolean; warningAcknowledgement?: string }) =>
      (
        await ghgInventoryCommitWorkbook({
          body: { batchCode, acknowledgeWarnings, warningAcknowledgement },
          throwOnError: true,
        })
      ).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("活动数据已导入")
    },
    onError: (error: Error) => toast.error("导入失败", { description: error.message }),
  })

  const calculate = useMutation({
    mutationFn: async ({
      inventoryCode,
      reportingProfileCode,
      reportingPeriodId,
      reportingOrgId,
      organizationBoundaryId,
      defaultScope2Method = "location",
    }: Pick<GhgImportContext, "inventoryCode" | "reportingProfileCode" | "reportingPeriodId"> & {
      reportingOrgId?: number
      organizationBoundaryId?: number
      defaultScope2Method?: "location" | "market"
    }) =>
      (
        await ghgInventoryRunCalculation({
          body: { inventoryCode, reportingProfileCode, reportingPeriodId, reportingOrgId, organizationBoundaryId, defaultScope2Method },
          throwOnError: true,
        })
      ).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("核算已完成")
    },
    onError: (error: Error) => toast.error("核算失败", { description: error.message }),
  })

  return {
    createSource,
    updateSource,
    deleteSource,
    createActivity,
    updateActivity,
    deleteActivity,
    generateActivities,
    replaceAllocations,
    downloadTemplate,
    preview,
    commit,
    calculate,
  }
}

export function useGhgInventoryReportActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => queryClient.invalidateQueries({ queryKey: ["ghg-inventory"] })
  const mutationOptions = {
    onSuccess: async () => {
      await invalidate()
      toast.success("盘查报告状态已更新")
    },
    onError: (error: Error) => toast.error("盘查报告操作失败", { description: error.message }),
  }
  const create = useMutation({
    mutationFn: async ({ runCode, title, changeSummary }: { runCode: string; title: string; changeSummary?: string }) =>
      (await ghgInventoryCreateReport({ body: { runCode, title, changeSummary }, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("盘查报告已生成")
    },
    onError: mutationOptions.onError,
  })
  const update = useMutation({
    mutationFn: async ({ reportCode, version, body }: { reportCode: string; version: number; body: GhgInventoryReportUpdateRequest }) =>
      (await ghgInventoryUpdateReport({ path: { report_code: reportCode, version }, body, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("盘查报告已更新")
    },
    onError: mutationOptions.onError,
  })
  const remove = useMutation({
    mutationFn: async ({ reportCode, version }: { reportCode: string; version: number }) =>
      (await ghgInventoryDeleteReport({ path: { report_code: reportCode, version }, throwOnError: true })).data,
    onSuccess: async (data) => {
      await invalidate()
      toast.success(data.deleted ? "盘查报告已删除" : "盘查报告已归档")
    },
    onError: mutationOptions.onError,
  })
  const submit = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment?: string }) =>
      (await ghgInventorySubmitReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const approve = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment?: string }) =>
      (await ghgInventoryApproveReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const reject = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment: string }) =>
      (await ghgInventoryRejectReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const publish = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment?: string }) =>
      (await ghgInventoryPublishReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const resubmit = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment?: string }) =>
      (await ghgInventoryResubmitReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const archive = useMutation({
    mutationFn: async ({ reportCode, version, comment }: { reportCode: string; version: number; comment?: string }) =>
      (await ghgInventoryArchiveReport({ path: { report_code: reportCode, version }, body: { comment }, throwOnError: true })).data,
    ...mutationOptions,
  })
  const exportReport = useMutation({
    mutationFn: async ({ reportCode, version, fileFormat }: { reportCode: string; version: number; fileFormat: "docx" | "pdf" }) =>
      exportGhgInventoryReport(reportCode, version, fileFormat),
    onSuccess: (_data, variables) => {
      toast.success(variables.fileFormat === "pdf" ? "PDF报告已导出" : "Word报告已导出")
    },
    onError: (error: Error) => toast.error("盘查报告导出失败", { description: error.message }),
  })
  return { create, update, remove, submit, resubmit, approve, reject, publish, archive, exportReport }
}

export function useOrganizationBoundarySelection(boundaryId?: number) {
  return useQuery({
    queryKey: ["organization-boundary", "selection", boundaryId],
    queryFn: async () => {
      if (!boundaryId) throw new Error("请选择核算边界")
      return (await organizationBoundaryGetSelection({ path: { boundary_id: boundaryId }, throwOnError: true })).data
    },
    enabled: Boolean(boundaryId),
  })
}

export function useOrganizationBoundaryDiff(boundaryId?: number, againstBoundaryId?: number) {
  return useQuery({
    queryKey: ["organization-boundary", "diff", boundaryId, againstBoundaryId],
    queryFn: async () => {
      if (!boundaryId) throw new Error("请选择核算边界")
      return (
        await organizationBoundaryGetDiff({
          path: { boundary_id: boundaryId },
          query: { against_boundary_id: againstBoundaryId },
          throwOnError: true,
        })
      ).data
    },
    enabled: Boolean(boundaryId),
  })
}

export function useOrganizationBoundaryActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["organization-boundary"] })
    await queryClient.invalidateQueries({ queryKey: ["ghg-inventory"] })
  }
  const workingCopy = useMutation({
    mutationFn: async (boundaryId: number) => (await organizationBoundaryCreateWorkingCopy({ path: { boundary_id: boundaryId }, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("工作草稿已就绪")
    },
    onError: (error: Error) => toast.error("创建草稿失败", { description: error.message }),
  })
  const save = useMutation({
    mutationFn: async ({ boundaryId, selection }: { boundaryId: number; selection: SaveBoundarySelectionRequest }) =>
      (
        await organizationBoundarySaveSelection({
          path: { boundary_id: boundaryId },
          body: selection,
          throwOnError: true,
        })
      ).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("核算边界已保存")
    },
    onError: (error: Error) => toast.error("保存失败", { description: error.message }),
  })
  const publish = useMutation({
    mutationFn: async (boundaryId: number) => (await organizationBoundaryPublish({ path: { boundary_id: boundaryId }, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("核算边界已发布")
    },
    onError: (error: Error) => toast.error("发布失败", { description: error.message }),
  })
  const discard = useMutation({
    mutationFn: async (boundaryId: number) => (await organizationBoundaryDiscardDraft({ path: { boundary_id: boundaryId }, throwOnError: true })).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("工作草稿已放弃")
    },
    onError: (error: Error) => toast.error("放弃草稿失败", { description: error.message }),
  })
  return { workingCopy, save, publish, discard }
}

function readFileBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "")
    reader.onerror = () => reject(reader.error ?? new Error("文件读取失败"))
    reader.readAsDataURL(file)
  })
}
