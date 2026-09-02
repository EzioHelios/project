import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { normalizePageResponse, requestPage } from "@/components/platform/data-admin-pages"

export type CalculationFactor = {
  id: number
  ownerType: "shared" | "enterprise"
  editable: boolean
  scope: string
  category: string
  subCategory: string
  unit: string
  factorValue: string
  factorUnit: string
  year: number
  source: string
  sourceSystem?: string | null
  sourceSnapshotId?: string | null
  rawRecordId?: number | null
  projectionStatus?: string | null
  reviewStatus?: string | null
  isActive: boolean
  note?: string | null
}

export type CalculationFactorWrite = {
  scope: string
  category: string
  subCategory: string
  unit: string
  factorValue: string
  factorUnit: string
  year: number
  source: string
  sourceSystem?: string | null
  sourceSnapshotId?: string | null
  rawRecordId?: number | null
  projectionStatus: string
  reviewStatus: string
  isActive: boolean
  note?: string | null
}

export type CalculationFactorImportIssue = {
  severity: string
  rowNumber?: number | null
  field?: string | null
  code: string
  message: string
  value?: string | null
}

export type CalculationFactorImportRow = {
  rowNumber: number
  action: "create" | "update" | "invalid"
  factor?: CalculationFactorWrite | null
  issues: CalculationFactorImportIssue[]
}

export type CalculationFactorImportPreview = {
  fileName: string
  rowCount: number
  validCount: number
  errorCount: number
  createCount: number
  updateCount: number
  rows: CalculationFactorImportRow[]
}

export type ActivityFactorCandidate = Omit<CalculationFactor, "editable" | "note" | "sourceSnapshotId" | "rawRecordId"> & {
  matchReason: string
}

export type ActivityFactorCandidates = {
  items: ActivityFactorCandidate[]
  currentParameters: Array<{
    parameterCode: string
    parameterName: string
    value: string
    unit: string
    sourceMode: string
    sourceName: string
    sourceVersion?: string | null
    qualityGrade?: string | null
  }>
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  })
  const text = await response.text()
  const raw = text ? JSON.parse(text) : {}
  if (!response.ok || (raw.code && raw.code >= 400)) throw new Error(raw.msg || raw.detail || `HTTP ${response.status}`)
  return ("data" in raw ? raw.data : raw) as T
}

function queryString(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value))
  }
  return search.toString()
}

export function useCalculationFactors(filters: { keyword?: string; scope?: string; category?: string; active?: string; owner?: string; pageIndex: number; pageSize: number }) {
  return useQuery({
    queryKey: ["factor-library", "calculation-factors", filters],
    queryFn: async () =>
      requestPage<CalculationFactor>("/api/carbon/emission-factors", {
        search: filters.keyword,
        scope: filters.scope === "all" ? undefined : filters.scope,
        category: filters.category === "all" ? undefined : filters.category,
        is_active: filters.active === "all" ? undefined : filters.active === "active",
        owner: filters.owner === "all" ? undefined : filters.owner,
        limit: filters.pageSize,
        offset: filters.pageIndex * filters.pageSize,
      }),
  })
}

export function useActivityFactorCandidates(filters: { inventoryCode?: string; recordCode?: string }) {
  return useQuery({
    queryKey: ["factor-library", "activity-candidates", filters],
    queryFn: async () => {
      if (!filters.inventoryCode || !filters.recordCode) throw new Error("缺少活动记录")
      const qs = queryString({ inventory_code: filters.inventoryCode })
      return requestJson<ActivityFactorCandidates>(`/api/ghg-inventory/activities/${encodeURIComponent(filters.recordCode)}/factor-candidates?${qs}`)
    },
    enabled: Boolean(filters.inventoryCode && filters.recordCode),
  })
}

export function useCalculationFactorActions() {
  const queryClient = useQueryClient()
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["factor-library"] })
    await queryClient.invalidateQueries({ queryKey: ["ghg-inventory"] })
  }
  const create = useMutation({
    mutationFn: async (body: CalculationFactorWrite) => requestJson<CalculationFactor>("/api/carbon/emission-factors", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async () => {
      await invalidate()
      toast.success("计算因子已保存")
    },
    onError: (error: Error) => toast.error("计算因子保存失败", { description: error.message }),
  })
  const update = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: CalculationFactorWrite }) =>
      requestJson<CalculationFactor>(`/api/carbon/emission-factors/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: async () => {
      await invalidate()
      toast.success("计算因子已更新")
    },
    onError: (error: Error) => toast.error("计算因子更新失败", { description: error.message }),
  })
  const remove = useMutation({
    mutationFn: async (id: number) => requestJson<{ deleted: boolean }>(`/api/carbon/emission-factors/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate()
      toast.success("计算因子已删除")
    },
    onError: (error: Error) => toast.error("计算因子删除失败", { description: error.message }),
  })
  const previewImport = useMutation({
    mutationFn: async (file: File) =>
      requestJson<CalculationFactorImportPreview>("/api/carbon/emission-factors/import/preview", {
        method: "POST",
        body: JSON.stringify({ fileName: file.name, csvBase64: await readFileBase64(file) }),
      }),
    onSuccess: () => toast.success("计算因子导入预检完成"),
    onError: (error: Error) => toast.error("导入预检失败", { description: error.message }),
  })
  const commitImport = useMutation({
    mutationFn: async (file: File) =>
      requestJson<CalculationFactorImportPreview>("/api/carbon/emission-factors/import/commit", {
        method: "POST",
        body: JSON.stringify({ fileName: file.name, csvBase64: await readFileBase64(file) }),
      }),
    onSuccess: async (data) => {
      await invalidate()
      toast.success("计算因子已导入", { description: `新增 ${data.createCount} 条，更新 ${data.updateCount} 条` })
    },
    onError: (error: Error) => toast.error("计算因子导入失败", { description: error.message }),
  })
  const applyToActivity = useMutation({
    mutationFn: async ({ inventoryCode, recordCode, factorId }: { inventoryCode: string; recordCode: string; factorId: number }) =>
      requestJson(`/api/ghg-inventory/activities/${encodeURIComponent(recordCode)}/factor-selection`, {
        method: "PUT",
        body: JSON.stringify({ inventoryCode, factorId }),
      }),
    onSuccess: async () => {
      await invalidate()
      toast.success("活动数据采用因子已更新")
    },
    onError: (error: Error) => toast.error("采用因子失败", { description: error.message }),
  })
  const downloadTemplate = () => {
    const anchor = document.createElement("a")
    anchor.href = "/api/carbon/emission-factors/template"
    anchor.download = "calculation-factor-template.csv"
    anchor.click()
  }
  return { create, update, remove, previewImport, commitImport, applyToActivity, downloadTemplate }
}

export function factorWriteDefaults(source?: CalculationFactor): CalculationFactorWrite {
  return {
    scope: source?.scope ?? "scope2",
    category: source?.category ?? "electricity",
    subCategory: source?.subCategory ?? "grid_electricity_jiangsu",
    unit: source?.unit ?? "kWh",
    factorValue: source?.factorValue ?? "0.5827",
    factorUnit: source?.factorUnit ?? "kgCO2e/kWh",
    year: source?.year ?? new Date().getFullYear(),
    source: source?.source ?? "企业批准计算因子",
    sourceSystem: source?.sourceSystem ?? "enterprise",
    sourceSnapshotId: source?.sourceSnapshotId ?? undefined,
    rawRecordId: source?.rawRecordId ?? undefined,
    projectionStatus: source?.projectionStatus ?? "manual",
    reviewStatus: source?.reviewStatus ?? "approved",
    isActive: source?.isActive ?? true,
    note: source?.note ?? "",
  }
}

function readFileBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "")
    reader.onerror = () => reject(reader.error ?? new Error("文件读取失败"))
    reader.readAsDataURL(file)
  })
}

export function normalizeFactorPage(raw: unknown) {
  return normalizePageResponse<CalculationFactor>(raw)
}
