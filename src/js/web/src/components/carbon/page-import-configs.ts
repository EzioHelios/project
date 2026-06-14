import type { PageImportError, PageImportField, PageImportResult, PageImportRow } from "@/components/admin-ui"
import { request } from "@/components/platform/data-admin-pages"

type EnergyImportResponse = {
  dataset: string
  received_count: number
  imported_count: number
  skipped_count: number
  errors?: { row_number: number; message: string }[]
}

const sourceRecordAliases = ["源记录ID", "来源记录ID", "source_record_id"]

export const energyIntervalImportFields: PageImportField[] = [
  { name: "source_record_id", label: "来源记录ID", aliases: sourceRecordAliases, required: true, example: "energy-2026-03-line-01" },
  { name: "energy_type_code", label: "能源品种编码", aliases: ["能源类型", "energy_type_code"], example: "electricity" },
  { name: "period_start", label: "开始日期", aliases: ["期间开始", "period_start"], type: "date", required: true, example: "2026-03-01" },
  { name: "period_end", label: "结束日期", aliases: ["期间结束", "period_end"], type: "date", example: "2026-03-31" },
  { name: "amount", label: "用量", aliases: ["数量", "amount"], type: "number", required: true, example: "12500" },
  { name: "unit", label: "单位", aliases: ["计量单位", "unit"], required: true, example: "kWh" },
  { name: "equipment_code", label: "设备编码", aliases: ["equipment_code"], example: "METER-01" },
  { name: "equipment_name", label: "设备名称", aliases: ["equipment_name"], example: "总表" },
  { name: "area_id", label: "区域ID", aliases: ["area_id"] },
  { name: "area_name", label: "区域名称", aliases: ["area_name"], example: "一号厂房" },
  { name: "use_system_code", label: "用能系统编码", aliases: ["use_system_code"] },
  { name: "use_system_name", label: "用能系统名称", aliases: ["use_system_name"] },
  { name: "granularity", label: "粒度", aliases: ["granularity"], example: "month" },
  { name: "cost_cny", label: "费用(元)", aliases: ["金额", "cost_cny"], type: "number", example: "8600" },
  { name: "data_quality", label: "数据质量", aliases: ["质量等级", "data_quality"], example: "measured" },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const scope1StationaryImportFields: PageImportField[] = [
  { name: "source_record_id", label: "来源记录ID", aliases: sourceRecordAliases, required: true, example: "boiler-2026-03" },
  { name: "facility_name", label: "设施名称", aliases: ["设施", "facility_name"], required: true, example: "燃气锅炉" },
  { name: "period_start", label: "开始日期", aliases: ["period_start"], type: "date", required: true, example: "2026-03-01" },
  { name: "period_end", label: "结束日期", aliases: ["period_end"], type: "date", required: true, example: "2026-03-31" },
  { name: "fuel_type", label: "燃料类型", aliases: ["能源类型", "fuel_type"], required: true, example: "natural_gas" },
  { name: "amount", label: "用量", aliases: ["消耗量", "amount"], type: "number", required: true, example: "4200" },
  { name: "unit", label: "单位", aliases: ["计量单位", "unit"], required: true, example: "m3" },
  { name: "meter_reading_start", label: "起始读数", aliases: ["读数开始", "meter_reading_start"], type: "number" },
  { name: "meter_reading_end", label: "结束读数", aliases: ["读数结束", "meter_reading_end"], type: "number" },
  { name: "attachment", label: "附件", aliases: ["佐证", "attachment"] },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const scope2BillImportFields: PageImportField[] = [
  { name: "source_record_id", label: "来源记录ID", aliases: sourceRecordAliases, required: true, example: "bill-2026-03-001" },
  { name: "account_number", label: "户号", aliases: ["电力户号", "表号", "account_number"], required: true, example: "3200000001" },
  { name: "billing_month", label: "账期", aliases: ["账单月份", "billing_month"], type: "month", required: true, example: "2026-03" },
  { name: "total_kwh", label: "总电量(kWh)", aliases: ["总电量", "total_kwh"], type: "number", required: true, example: "12800" },
  { name: "peak_kwh", label: "峰(kWh)", aliases: ["峰电", "peak_kwh"], type: "number", example: "3800" },
  { name: "flat_kwh", label: "平(kWh)", aliases: ["平电", "flat_kwh"], type: "number", example: "5200" },
  { name: "valley_kwh", label: "谷(kWh)", aliases: ["谷电", "valley_kwh"], type: "number", example: "3800" },
  { name: "amount_cny", label: "金额(元)", aliases: ["电费", "amount_cny"], type: "number", example: "9800" },
  { name: "attachment", label: "附件", aliases: ["账单附件", "attachment"] },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const productionOutputImportFields: PageImportField[] = [
  { name: "source_record_id", label: "来源记录ID", aliases: sourceRecordAliases, required: true, example: "prod-2026-03-A001" },
  { name: "production_order_no", label: "工单号", aliases: ["生产工单", "production_order_no"], example: "WO-202603001" },
  { name: "batch_no", label: "批次号", aliases: ["批次", "batch_no"], example: "B20260301" },
  { name: "product_code", label: "产品编码", aliases: ["产品代码", "product_code"], required: true, example: "P-001" },
  { name: "product_name", label: "产品名称", aliases: ["product_name"], example: "样品产品" },
  { name: "product_spec", label: "产品规格", aliases: ["规格", "product_spec"] },
  { name: "output_kind", label: "业务类型", aliases: ["产量类型", "output_kind"], required: true, example: "product" },
  { name: "period_start", label: "开始日期", aliases: ["period_start"], type: "date", required: true, example: "2026-03-01" },
  { name: "period_end", label: "结束日期", aliases: ["period_end"], type: "date", example: "2026-03-31" },
  { name: "good_qty", label: "产量", aliases: ["合格数量", "good_qty"], type: "number", required: true, example: "25000" },
  { name: "scrap_qty", label: "报废量", aliases: ["scrap_qty"], type: "number", example: "120" },
  { name: "rework_qty", label: "返工量", aliases: ["rework_qty"], type: "number", example: "80" },
  { name: "unit", label: "业务单位", aliases: ["单位", "unit"], required: true, example: "件" },
  { name: "standard_qty", label: "标准产量", aliases: ["standard_qty"], type: "number" },
  { name: "standard_unit", label: "标准单位", aliases: ["standard_unit"] },
  { name: "quality_status", label: "质量状态", aliases: ["quality_status"], example: "qualified" },
  { name: "record_status", label: "记录状态", aliases: ["record_status"], example: "confirmed" },
  { name: "work_center_code", label: "工作中心", aliases: ["work_center_code"] },
  { name: "line_code", label: "产线编码", aliases: ["产线", "line_code"] },
  { name: "area_id", label: "区域ID", aliases: ["area_id"] },
  { name: "area_name", label: "区域名称", aliases: ["area_name"] },
  { name: "equipment_code", label: "设备编码", aliases: ["equipment_code"] },
  { name: "equipment_name", label: "设备名称", aliases: ["equipment_name"] },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const scope1MobileImportFields: PageImportField[] = [
  { name: "record_date", label: "记录日期", aliases: ["日期", "record_date"], type: "date", required: true, example: "2026-03-15" },
  { name: "asset_name", label: "资产/车辆名称", aliases: ["车辆", "资产名称", "asset_name"], example: "叉车01" },
  { name: "fuel_type", label: "燃料类型", aliases: ["能源类型", "fuel_type"], required: true, example: "diesel" },
  { name: "amount", label: "用量", aliases: ["消耗量", "amount"], type: "number", required: true, example: "260" },
  { name: "unit", label: "单位", aliases: ["计量单位", "unit"], required: true, example: "L" },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const scope3WasteImportFields: PageImportField[] = [
  { name: "date", label: "日期", aliases: ["产生日期", "date"], type: "date", required: true, example: "2026-03-20" },
  { name: "category", label: "类别", aliases: ["废弃物类别", "category"], required: true, example: "包装物" },
  { name: "weight_ton", label: "重量(吨)", aliases: ["重量", "weight_ton"], type: "number", required: true, example: "1.8" },
  { name: "treatment_method", label: "处理方式", aliases: ["处置方式", "treatment_method"], required: true, example: "recycle" },
  { name: "vendor_name", label: "处置方", aliases: ["供应商", "vendor_name"], example: "第三方处置公司" },
  { name: "remark", label: "备注", aliases: ["说明", "remark"] },
]

export const energyImportFieldMap: Record<string, PageImportField[]> = {
  energy_interval_facts: energyIntervalImportFields,
  production_output_facts: productionOutputImportFields,
  scope1_stationary_combustion: scope1StationaryImportFields,
  scope2_electricity_bills: scope2BillImportFields,
}

export async function submitEnergyDatasetImport(dataset: string, rows: PageImportRow[], sourceName: string): Promise<PageImportResult> {
  const response = await request<EnergyImportResponse>("/api/energy/imports/datasets", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ dataset, source_name: sourceName, rows }),
  })
  return normalizeEnergyImportResult(response.data)
}

export async function submitRowsIndividually(endpoint: string, rows: PageImportRow[], sourceName: string): Promise<PageImportResult> {
  const errors: PageImportError[] = []
  let importedCount = 0
  for (const [index, row] of rows.entries()) {
    try {
      await request(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(withSourceRemark(row, sourceName)),
      })
      importedCount += 1
    } catch (error) {
      errors.push({ rowNumber: index + 2, message: error instanceof Error ? error.message : "导入失败" })
    }
  }
  return {
    receivedCount: rows.length,
    importedCount,
    skippedCount: rows.length - importedCount,
    errors,
  }
}

function normalizeEnergyImportResult(value: EnergyImportResponse): PageImportResult {
  return {
    receivedCount: value.received_count,
    importedCount: value.imported_count,
    skippedCount: value.skipped_count,
    errors: (value.errors ?? []).map((error) => ({ rowNumber: error.row_number, message: error.message })),
  }
}

function withSourceRemark(row: PageImportRow, sourceName: string) {
  const remark = row.remark?.trim()
  const sourceRemark = sourceName.trim() ? `[页面导入:${sourceName.trim()}]` : "[页面导入]"
  return {
    ...row,
    remark: remark ? `${remark} ${sourceRemark}` : sourceRemark,
  }
}
