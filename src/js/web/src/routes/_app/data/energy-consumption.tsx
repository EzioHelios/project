import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { type PageImportField, PageImportPanel } from "@/components/admin-ui"
import { CrudDataPage, type Row, request, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_app/data/energy-consumption")({
  component: EnergyConsumptionFactsPage,
})

const energyImportFields: PageImportField[] = [
  { key: "source_record_id", label: "记录编码", required: true, aliases: ["source_record_id"] },
  { key: "energy_type_code", label: "能源种类编码", required: true, aliases: ["energy_type_code"] },
  { key: "period_start", label: "开始时间", required: true, aliases: ["period_start"] },
  { key: "period_end", label: "结束时间", aliases: ["period_end"] },
  { key: "amount", label: "能源用量", required: true, type: "number", aliases: ["amount"] },
  { key: "unit", label: "单位", required: true, aliases: ["unit"] },
  { key: "source_system", label: "数据来源", aliases: ["source_system"] },
  { key: "equipment_code", label: "设备编码", aliases: ["equipment_code"] },
  { key: "equipment_name", label: "设备名称", aliases: ["equipment_name"] },
  { key: "area_id", label: "区域ID", aliases: ["area_id"] },
  { key: "area_name", label: "区域名称", aliases: ["area_name"] },
  { key: "use_system_code", label: "用能系统编码", aliases: ["use_system_code"] },
  { key: "use_system_name", label: "用能系统名称", aliases: ["use_system_name"] },
  { key: "granularity", label: "时间粒度", aliases: ["granularity"] },
  { key: "cost_cny", label: "费用", type: "number", aliases: ["cost_cny"] },
  { key: "data_quality", label: "数据质量", aliases: ["data_quality"] },
  { key: "remark", label: "备注", aliases: ["remark"] },
]

function EnergyConsumptionFactsPage() {
  const queryClient = useQueryClient()
  const [isExporting, setIsExporting] = useState(false)
  const energyTypesQuery = useQuery({
    queryKey: ["energy", "types", "energy-consumption-options"],
    queryFn: async () => (await request<{ items: Row[] }>("/api/energy/types?limit=500")).data,
  })
  const areasQuery = useQuery({
    queryKey: ["master-data", "areas", "tree", "energy-consumption-options"],
    queryFn: async () => (await request<{ items: Row[] }>("/api/master-data/areas/tree")).data,
  })
  const devicesQuery = useQuery({
    queryKey: ["master-data", "devices", "energy-consumption-options"],
    queryFn: async () => requestPage<Row>("/api/master-data/devices", { limit: 500, offset: 0 }),
  })
  const energyTypeOptions = useMemo(
    () =>
      (energyTypesQuery.data?.items ?? []).map((item) => ({
        label: `${display(item.name)} · ${display(item.code)}`,
        value: String(item.code ?? ""),
        data: item,
      })),
    [energyTypesQuery.data?.items],
  )
  const areaOptions = useMemo(
    () =>
      flattenRows(areasQuery.data?.items ?? []).map((item) => ({
        label: `${display(item.name)} · ${display(item.code)}`,
        value: String(item.id ?? ""),
        data: item,
      })),
    [areasQuery.data?.items],
  )
  const deviceOptions = useMemo(
    () => [
      { label: "不挂载设备", value: "__none" },
      ...(devicesQuery.data?.items ?? []).map((item) => ({
        label: `${display(item.name)} · ${display(item.code)} · ${display(item.area_name)}`,
        value: String(item.id ?? ""),
        data: item,
      })),
    ],
    [devicesQuery.data?.items],
  )
  const energyTypeNameByCode = useMemo(
    () => new Map((energyTypesQuery.data?.items ?? []).map((item) => [String(item.code ?? ""), String(item.name ?? item.code ?? "")])),
    [energyTypesQuery.data?.items],
  )
  async function exportEnergyIntervalFacts() {
    setIsExporting(true)
    try {
      const response = await fetch("/api/energy/interval-facts/export", { credentials: "include" })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "energy_interval_facts.csv"
      document.body.append(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast.success("导出成功")
    } catch (error) {
      toast.error("导出失败", { description: error instanceof Error ? error.message : "请稍后重试" })
    } finally {
      setIsExporting(false)
    }
  }
  return (
    <CrudDataPage
      title="能源数据维护"
      endpoint="/api/energy/interval-facts"
      queryKey={["data", "energy-interval-facts"]}
      searchPlaceholder="搜索记录编码、能源种类、区域、设备"
      topActions={
        <>
          <PageImportPanel
            title="导入能源数据"
            testId="energy-interval-import"
            fields={energyImportFields}
            onConfirm={async (rows, meta) => {
              const response = await request<{
                received_count: number
                imported_count: number
                skipped_count: number
                errors: { row_number?: number; message?: string }[]
              }>("/api/energy/imports/datasets", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ dataset: "energy_interval_facts", rows, source_name: meta.sourceName }),
              })
              await queryClient.invalidateQueries({ queryKey: ["data", "energy-interval-facts"] })
              return {
                receivedCount: response.data.received_count,
                importedCount: response.data.imported_count,
                skippedCount: response.data.skipped_count,
                errors: response.data.errors.map((item) => `${item.row_number ?? "-"}: ${item.message ?? "导入失败"}`),
              }
            }}
          />
          <Button type="button" variant="outline" onClick={() => void exportEnergyIntervalFacts()} disabled={isExporting}>
            <Download className="h-4 w-4" />
            导出
          </Button>
        </>
      }
      columns={[
        { key: "source_record_id", label: "记录编码" },
        { key: "energy_type_code", label: "能源种类", render: (row) => energyTypeNameByCode.get(String(row.energy_type_code ?? "")) ?? String(row.energy_type_code ?? "-") },
        { key: "amount", label: "能源用量", align: "right" },
        { key: "unit", label: "单位" },
        { key: "period_start", label: "开始日期", render: (row) => dateLabel(row.period_start) },
        { key: "period_end", label: "结束日期", render: (row) => dateLabel(row.period_end) },
        { key: "area_name", label: "区域" },
        { key: "equipment_name", label: "设备" },
        { key: "data_quality", label: "数据质量", render: (row) => dataQualityLabel(row.data_quality) },
        { key: "source_system", label: "来源" },
      ]}
      fields={[
        { name: "source_record_id", label: "记录编码", required: true },
        {
          name: "energy_type_code",
          label: "能源种类",
          type: "select",
          required: true,
          options: energyTypeOptions,
          derive: (option) => ({ unit: String(option.data?.original_unit ?? "") }),
        },
        { name: "amount", label: "能源用量", type: "number", required: true },
        { name: "unit", label: "单位", required: true },
        { name: "period_start", label: "开始日期", type: "date", required: true },
        { name: "period_end", label: "结束日期", type: "date", required: true },
        {
          name: "granularity",
          label: "时间粒度",
          type: "select",
          options: [
            { label: "小时", value: "hour" },
            { label: "日", value: "day" },
            { label: "月", value: "month" },
            { label: "年", value: "year" },
          ],
        },
        {
          name: "data_quality",
          label: "数据质量",
          type: "select",
          options: [
            { label: "实测", value: "measured" },
            { label: "手工", value: "manual" },
            { label: "导入", value: "imported" },
            { label: "估算", value: "estimated" },
          ],
        },
        { name: "source_system", label: "数据来源" },
        {
          name: "area_id",
          label: "区域",
          type: "select",
          valueKind: "string",
          options: areaOptions,
          derive: (option) => ({ area_name: String(option.data?.name ?? "") }),
        },
        {
          name: "equipment_id",
          label: "设备",
          type: "select",
          valueKind: "number",
          options: deviceOptions,
          derive: (option, form) =>
            option.value === "__none"
              ? {
                  equipment_code: "",
                  equipment_name: "",
                  area_id: String(form.area_id ?? ""),
                  area_name: String(form.area_name ?? ""),
                }
              : {
                  equipment_code: String(option.data?.code ?? ""),
                  equipment_name: String(option.data?.name ?? ""),
                  area_id: option.data?.area_id === null || option.data?.area_id === undefined ? "" : String(option.data.area_id),
                  area_name: String(option.data?.area_name ?? ""),
                },
        },
        { name: "use_system_code", label: "用能系统编码" },
        { name: "use_system_name", label: "用能系统名称" },
        { name: "cost_cny", label: "费用", type: "number" },
        { name: "tariff_segment_type", label: "电价时段" },
        { name: "reading_count", label: "采样数", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function dataQualityLabel(value: unknown) {
  return (
    (
      {
        measured: "实测",
        manual: "手工",
        imported: "导入",
        estimated: "估算",
      } as Record<string, string>
    )[String(value ?? "")] ?? String(value ?? "-")
  )
}

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  return String(value)
}

function flattenRows(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenRows(Array.isArray(row.children) ? (row.children as Row[]) : [])])
}

function dateLabel(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  const text = String(value)
  return text.includes("T") ? text.split("T")[0] : text
}
