import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  type ApplicabilityAssessmentRequest,
  type BaselineScenarioRequest,
  type CalculationRunRequest,
  type CcerDossierRequest,
  carbonReductionAssessApplicability,
  carbonReductionCreateBaseline,
  carbonReductionCreateFinancialScenario,
  carbonReductionCreateProject,
  carbonReductionCreateReview,
  carbonReductionCreateTarget,
  carbonReductionDownloadMonitoringTemplate,
  carbonReductionGetMethodology,
  carbonReductionGetOverview,
  carbonReductionGetProject,
  carbonReductionImportMonitoringWorkbook,
  carbonReductionListAuditEvents,
  carbonReductionListMethodologies,
  carbonReductionListProjects,
  carbonReductionListTargets,
  carbonReductionLockBaseline,
  carbonReductionPublishTarget,
  carbonReductionRunCalculation,
  carbonReductionSaveCcerDossier,
  carbonReductionSaveMonitoringPlan,
  carbonReductionSaveProjectBoundary,
  carbonReductionTransitionProject,
  carbonReductionUpdateProject,
  type FinancialScenarioRequest,
  type MonitoringPlanRequest,
  type ProjectBoundaryRequest,
  type ProjectReviewRequest,
  type ReductionProjectRequest,
  type ReductionProjectUpdateRequest,
  type ReductionTargetRequest,
} from "@/lib/generated/api"

const rootKey = ["carbon", "reduction"] as const
const keys = {
  root: rootKey,
  overview: (filters?: Record<string, unknown>) => [...rootKey, "overview", filters] as const,
  projects: (filters?: Record<string, unknown>) => [...rootKey, "projects", filters] as const,
  project: (id: number) => [...rootKey, "project", id] as const,
  methodologies: (filters?: Record<string, unknown>) => [...rootKey, "methodologies", filters] as const,
  methodology: (id: number) => [...rootKey, "methodology", id] as const,
  targets: [...rootKey, "targets"] as const,
  audit: (id: number) => [...rootKey, "audit", id] as const,
}

async function apiData<T>(promise: Promise<{ data?: T; error?: unknown }>) {
  const result = await promise
  if (result.error) throw result.error
  if (result.data === undefined) throw new Error("接口未返回数据")
  return result.data
}

export function useReductionOverview(query?: { target_year?: number; category?: string; area_id?: number; status?: string }) {
  return useQuery({ queryKey: keys.overview(query), queryFn: () => apiData(carbonReductionGetOverview({ query })) })
}

export function useReductionProjects(query?: {
  keyword?: string
  category?: string
  track?: string
  status?: string
  risk_level?: string
  methodology_id?: number
  limit?: number
  offset?: number
}) {
  return useQuery({ queryKey: keys.projects(query), queryFn: () => apiData(carbonReductionListProjects({ query })) })
}

export function useReductionProject(projectId: number) {
  return useQuery({ queryKey: keys.project(projectId), queryFn: () => apiData(carbonReductionGetProject({ path: { project_id: projectId } })), enabled: projectId > 0 })
}

export function useReductionMethodologies(query?: { keyword?: string; sector?: string; executable?: boolean }) {
  return useQuery({ queryKey: keys.methodologies(query), queryFn: () => apiData(carbonReductionListMethodologies({ query })) })
}

export function useReductionMethodology(methodologyId: number) {
  return useQuery({
    queryKey: keys.methodology(methodologyId),
    queryFn: () => apiData(carbonReductionGetMethodology({ path: { methodology_id: methodologyId } })),
    enabled: methodologyId > 0,
  })
}

export function useReductionTargets() {
  return useQuery({ queryKey: keys.targets, queryFn: () => apiData(carbonReductionListTargets()) })
}

export function useReductionAuditEvents(projectId: number) {
  return useQuery({ queryKey: keys.audit(projectId), queryFn: () => apiData(carbonReductionListAuditEvents({ path: { project_id: projectId } })), enabled: projectId > 0 })
}

function useReductionMutation<TVariables, TData = unknown>(mutationFn: (variables: TVariables) => Promise<TData>, message: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.root })
      toast.success(message)
    },
    onError: () => toast.error("操作未完成，请检查输入后重试"),
  })
}

export function useCreateReductionProject() {
  return useReductionMutation((body: ReductionProjectRequest) => apiData(carbonReductionCreateProject({ body })), "项目已创建")
}

export function useUpdateReductionProject(projectId: number) {
  return useReductionMutation((body: ReductionProjectUpdateRequest) => apiData(carbonReductionUpdateProject({ path: { project_id: projectId }, body })), "项目已更新")
}

export function useCreateReductionTarget() {
  return useReductionMutation((body: ReductionTargetRequest) => apiData(carbonReductionCreateTarget({ body })), "目标已创建")
}

export function usePublishReductionTarget() {
  return useReductionMutation((targetId: number) => apiData(carbonReductionPublishTarget({ path: { target_id: targetId } })), "目标已发布")
}

export function useTransitionReductionProject(projectId: number) {
  return useReductionMutation(
    (body: { targetStatus: string; reason?: string | null; actorName?: string | null }) => apiData(carbonReductionTransitionProject({ path: { project_id: projectId }, body })),
    "项目状态已更新",
  )
}

export function useAssessReductionApplicability(projectId: number) {
  return useReductionMutation((body: ApplicabilityAssessmentRequest) => apiData(carbonReductionAssessApplicability({ path: { project_id: projectId }, body })), "适用性评估已保存")
}

export function useCreateReductionBaseline(projectId: number) {
  return useReductionMutation((body: BaselineScenarioRequest) => apiData(carbonReductionCreateBaseline({ path: { project_id: projectId }, body })), "基准线已创建")
}

export function useLockReductionBaseline(projectId: number) {
  return useReductionMutation((baselineId: number) => apiData(carbonReductionLockBaseline({ path: { project_id: projectId, baseline_id: baselineId } })), "基准线已锁定")
}

export function useSaveReductionMonitoringPlan(projectId: number) {
  return useReductionMutation((body: MonitoringPlanRequest) => apiData(carbonReductionSaveMonitoringPlan({ path: { project_id: projectId }, body })), "监测计划已保存")
}

export function useSaveReductionProjectBoundary(projectId: number) {
  return useReductionMutation((body: ProjectBoundaryRequest) => apiData(carbonReductionSaveProjectBoundary({ path: { project_id: projectId }, body })), "项目边界已保存")
}

export async function downloadReductionMonitoringTemplate(projectId: number, projectCode: string) {
  const response = await carbonReductionDownloadMonitoringTemplate({ path: { project_id: projectId }, parseAs: "blob" })
  if (response.error || !response.data) throw response.error ?? new Error("模板下载失败")
  const blob = response.data as unknown as Blob
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `${projectCode}-监测数据模板.xlsx`
  link.click()
  URL.revokeObjectURL(url)
}

export function useImportReductionMonitoringWorkbook(projectId: number) {
  return useReductionMutation(
    (body: { fileName: string; workbookBase64: string; commit?: boolean }) => apiData(carbonReductionImportMonitoringWorkbook({ path: { project_id: projectId }, body })),
    "监测工作簿已处理",
  )
}

export function useRunReductionCalculation(projectId: number) {
  return useReductionMutation((body: CalculationRunRequest) => apiData(carbonReductionRunCalculation({ path: { project_id: projectId }, body })), "减排量计算已完成")
}

export function useCreateReductionFinancialScenario(projectId: number) {
  return useReductionMutation((body: FinancialScenarioRequest) => apiData(carbonReductionCreateFinancialScenario({ path: { project_id: projectId }, body })), "财务评价已完成")
}

export function useCreateReductionReview(projectId: number) {
  return useReductionMutation((body: ProjectReviewRequest) => apiData(carbonReductionCreateReview({ path: { project_id: projectId }, body })), "审核记录已保存")
}

export function useSaveCcerDossier(projectId: number) {
  return useReductionMutation((body: CcerDossierRequest) => apiData(carbonReductionSaveCcerDossier({ path: { project_id: projectId }, body })), "CCER材料台账已保存")
}
