import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  type ClimateAssessmentRequest,
  type ClimateDisclosureCycleRequest,
  type ClimateProgramRequest,
  type ClimateTargetRequest,
  carbonClimateCreateRenewableClaim,
  carbonClimateGetOverview,
  carbonClimateListAssessments,
  carbonClimateListPrograms,
  carbonClimateListRenewableClaims,
  carbonClimatePublishTarget,
  carbonClimateRunAssessment,
  carbonClimateSaveDisclosureCycle,
  carbonClimateSaveProgram,
  type RenewableElectricityClaimRequest,
} from "@/lib/generated/api"

const rootKey = ["carbon", "climate"] as const
const keys = {
  root: rootKey,
  overview: (year: number) => [...rootKey, "overview", year] as const,
  programs: (year?: number) => [...rootKey, "programs", year] as const,
  claims: (year?: number, programId?: number) => [...rootKey, "claims", year, programId] as const,
  assessments: (programId: number) => [...rootKey, "assessments", programId] as const,
}

async function apiData<T>(promise: Promise<{ data?: T; error?: unknown }>) {
  const result = await promise
  if (result.error) throw result.error
  if (result.data === undefined) throw new Error("接口未返回数据")
  return result.data
}

export function useClimateOverview(reportingYear: number) {
  return useQuery({
    queryKey: keys.overview(reportingYear),
    queryFn: () => apiData(carbonClimateGetOverview({ query: { reporting_year: reportingYear } })),
  })
}

export function useClimatePrograms(reportingYear?: number) {
  return useQuery({
    queryKey: keys.programs(reportingYear),
    queryFn: () => apiData(carbonClimateListPrograms({ query: { reporting_year: reportingYear } })),
  })
}

export function useRenewableElectricityClaims(reportingYear?: number, programId?: number) {
  return useQuery({
    queryKey: keys.claims(reportingYear, programId),
    queryFn: () => apiData(carbonClimateListRenewableClaims({ query: { reporting_year: reportingYear, program_id: programId } })),
  })
}

export function useClimateAssessments(programId: number) {
  return useQuery({
    queryKey: keys.assessments(programId),
    queryFn: () => apiData(carbonClimateListAssessments({ path: { program_id: programId } })),
    enabled: programId > 0,
  })
}

function useClimateMutation<TVariables, TData>(mutationFn: (variables: TVariables) => Promise<TData>, message: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.root })
      toast.success(message)
    },
    onError: () => toast.error("操作未完成，请检查输入和权限后重试"),
  })
}

export function useSaveClimateProgram() {
  return useClimateMutation((body: ClimateProgramRequest) => apiData(carbonClimateSaveProgram({ body })), "气候计划已保存")
}

export function usePublishClimateTarget(programId: number) {
  return useClimateMutation((body: ClimateTargetRequest) => apiData(carbonClimatePublishTarget({ path: { program_id: programId }, body })), "目标版本已发布")
}

export function useSaveClimateDisclosureCycle(programId: number) {
  return useClimateMutation((body: ClimateDisclosureCycleRequest) => apiData(carbonClimateSaveDisclosureCycle({ path: { program_id: programId }, body })), "披露周期已保存")
}

export function useCreateRenewableElectricityClaim(programId: number) {
  return useClimateMutation(
    (body: RenewableElectricityClaimRequest) => apiData(carbonClimateCreateRenewableClaim({ path: { program_id: programId }, body })),
    "可再生电力属性已登记",
  )
}

export function useRunClimateAssessment(programId: number) {
  return useClimateMutation((body: ClimateAssessmentRequest = {}) => apiData(carbonClimateRunAssessment({ path: { program_id: programId }, body })), "评估结果已更新")
}
