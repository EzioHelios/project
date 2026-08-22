import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  type GhgActivityResponse,
  type GhgCatalogResponse,
  type GhgImportBatchResponse,
  ghgInventoryCommitWorkbook,
  ghgInventoryDownloadTemplate,
  ghgInventoryGetCatalog,
  ghgInventoryListActivities,
  ghgInventoryListImportBatches,
  ghgInventoryPreviewWorkbook,
  ghgInventoryRunCalculation,
} from "@/lib/generated/api"

export type GhgCatalog = GhgCatalogResponse
export type GhgImportBatch = GhgImportBatchResponse
export type GhgActivity = GhgActivityResponse

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

export function useGhgImportBatches() {
  return useQuery({
    queryKey: ["ghg-inventory", "import-batches"],
    queryFn: async () => (await ghgInventoryListImportBatches({ query: { limit: 50 }, throwOnError: true })).data,
  })
}

export function useGhgInventoryActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => queryClient.invalidateQueries({ queryKey: ["ghg-inventory"] })

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
    mutationFn: async ({ inventoryCode, reportingProfileCode, reportingPeriodId }: Pick<GhgImportContext, "inventoryCode" | "reportingProfileCode" | "reportingPeriodId">) =>
      (
        await ghgInventoryRunCalculation({
          body: { inventoryCode, reportingProfileCode, reportingPeriodId },
          throwOnError: true,
        })
      ).data,
    onSuccess: async () => {
      await invalidate()
      toast.success("核算已完成")
    },
    onError: (error: Error) => toast.error("核算失败", { description: error.message }),
  })

  return { downloadTemplate, preview, commit, calculate }
}

function readFileBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "")
    reader.onerror = () => reject(reader.error ?? new Error("文件读取失败"))
    reader.readAsDataURL(file)
  })
}
