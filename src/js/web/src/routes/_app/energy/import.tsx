import { createFileRoute } from "@tanstack/react-router"
import { Download, FileCheck2, FileSpreadsheet, UploadCloud } from "lucide-react"
import type { ChangeEvent } from "react"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, MetricStrip, MetricTile } from "@/components/admin-ui"
import { request } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/energy/import")({
  component: DataCollectionWorkbookImportPage,
})

type WorkbookPreview = {
  total_rows: number
  sheets: WorkbookSheetPreview[]
}

type WorkbookSheetPreview = {
  sheet_name: string
  dataset_name: string
  row_count: number
  fields: WorkbookField[]
  missing_required: Array<{ row: number; field: string; label: string }>
  preview_rows: Record<string, string>[]
}

type WorkbookField = {
  key: string
  label: string
  type: string
  required: boolean
  example?: string
  help_text?: string
  choices?: Record<string, string>
}

type ImportResult = {
  enterprise_code: string
  tenant_slug: string
  team_id: string
  dry_run: boolean
  imported: Record<string, number>
  skipped: Record<string, number>
  source_missing_pages: string[]
}

const emptyPreview: WorkbookPreview = { total_rows: 0, sheets: [] }

function DataCollectionWorkbookImportPage() {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [fileName, setFileName] = useState("")
  const [workbookBase64, setWorkbookBase64] = useState("")
  const [preview, setPreview] = useState<WorkbookPreview>(emptyPreview)
  const [selectedSheetName, setSelectedSheetName] = useState("")
  const [result, setResult] = useState<ImportResult | null>(null)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isImporting, setIsImporting] = useState(false)

  const nonEmptySheets = useMemo(() => preview.sheets.filter((sheet) => sheet.row_count > 0), [preview.sheets])
  const sheetWithErrors = useMemo(() => preview.sheets.filter((sheet) => sheet.missing_required.length > 0).length, [preview.sheets])
  const selectedSheet = useMemo(() => {
    if (!preview.sheets.length) return null
    return preview.sheets.find((sheet) => sheet.sheet_name === selectedSheetName) ?? nonEmptySheets[0] ?? preview.sheets[0]
  }, [nonEmptySheets, preview.sheets, selectedSheetName])
  const importedTotal = useMemo(() => Object.values(result?.imported ?? {}).reduce((sum, value) => sum + Number(value || 0), 0), [result])

  async function handleDownloadTemplate() {
    const response = await fetch("/api/carbon/data-collection-workbooks/template")
    if (!response.ok) {
      toast.error("模板下载失败")
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "energy-carbon-data-collection-template.xlsx"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    setResult(null)
    setIsPreviewing(true)
    try {
      const base64 = await fileToBase64(file)
      setWorkbookBase64(base64)
      const response = await request<WorkbookPreview>("/api/carbon/data-collection-workbooks/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workbook_base64: base64 }),
      })
      setPreview(response.data)
      setSelectedSheetName(response.data.sheets.find((sheet) => sheet.row_count > 0)?.sheet_name ?? response.data.sheets[0]?.sheet_name ?? "")
      toast.success("预览已生成")
    } catch (error) {
      setPreview(emptyPreview)
      setWorkbookBase64("")
      toast.error(error instanceof Error ? error.message : "文件解析失败")
    } finally {
      setIsPreviewing(false)
    }
  }

  async function handleImport() {
    if (!workbookBase64 || sheetWithErrors > 0) return
    setIsImporting(true)
    try {
      const response = await request<ImportResult>("/api/carbon/data-collection-workbooks/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workbook_base64: workbookBase64 }),
      })
      setResult(response.data)
      toast.success("导入完成")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败")
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <PageContainer>
      <PageSection className="space-y-4">
        <AdminPageHeader
          title="采集包导入"
          actions={
            <>
              <Button variant="outline" size="sm" type="button" onClick={handleDownloadTemplate}>
                <Download />
                下载模板
              </Button>
              <Input ref={inputRef} className="hidden" type="file" accept=".xlsx" onChange={handleFileChange} />
              <Button variant="outline" size="sm" type="button" onClick={() => inputRef.current?.click()} disabled={isPreviewing || isImporting}>
                <UploadCloud />
                选择文件
              </Button>
              <Button size="sm" type="button" onClick={handleImport} disabled={!workbookBase64 || sheetWithErrors > 0 || isPreviewing || isImporting}>
                <FileCheck2 />
                {isImporting ? "导入中" : "确认导入"}
              </Button>
            </>
          }
        />

        <MetricStrip>
          <MetricTile label="文件" value={fileName || "-"} />
          <MetricTile label="有效行数" value={preview.total_rows} />
          <MetricTile label="有数据 Sheet" value={nonEmptySheets.length} />
          <MetricTile label="待修正 Sheet" value={sheetWithErrors} tone={sheetWithErrors > 0 ? "warning" : "default"} />
        </MetricStrip>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <AdminPanel title="Sheet 覆盖" contentClassName="p-0">
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sheet</TableHead>
                    <TableHead className="text-right">行数</TableHead>
                    <TableHead className="text-right">缺项</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.sheets.length === 0 ? (
                    <AdminTableStateRow colSpan={3}>{isPreviewing ? "解析中" : "请选择 .xlsx 文件"}</AdminTableStateRow>
                  ) : (
                    preview.sheets.map((sheet) => (
                      <TableRow
                        key={sheet.sheet_name}
                        className={cn("cursor-pointer", selectedSheet?.sheet_name === sheet.sheet_name && "bg-accent/45")}
                        onClick={() => setSelectedSheetName(sheet.sheet_name)}
                      >
                        <TableCell className="max-w-[260px] truncate font-medium">{sheet.sheet_name}</TableCell>
                        <TableCell className="text-right">{sheet.row_count}</TableCell>
                        <TableCell className={cn("text-right", sheet.missing_required.length > 0 && "text-[hsl(var(--status-warning-foreground-admin))]")}>
                          {sheet.missing_required.length}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>

          <AdminPanel title={selectedSheet?.sheet_name ?? "数据预览"} contentClassName="space-y-4">
            {selectedSheet ? (
              <>
                <div className="grid gap-3 sm:grid-cols-3">
                  <SmallStat label="字段数" value={selectedSheet.fields.length} />
                  <SmallStat label="必填字段" value={selectedSheet.fields.filter((field) => field.required).length} />
                  <SmallStat label="缺失项" value={selectedSheet.missing_required.length} />
                </div>
                <PreviewRowsTable sheet={selectedSheet} />
                {selectedSheet.missing_required.length > 0 && <MissingRequiredTable sheet={selectedSheet} />}
              </>
            ) : (
              <div className="flex min-h-72 items-center justify-center text-muted-foreground text-sm">
                <FileSpreadsheet className="mr-2 size-4" />
                待上传
              </div>
            )}
          </AdminPanel>
        </div>

        {result && (
          <AdminPanel title="导入结果">
            <MetricStrip>
              <MetricTile label="入库行数" value={importedTotal} tone="success" />
              <MetricTile label="租户" value={result.tenant_slug || "-"} />
              <MetricTile label="企业编码" value={result.enterprise_code || "-"} />
              <MetricTile label="未匹配资料页" value={result.source_missing_pages.length} />
            </MetricStrip>
          </AdminPanel>
        )}
      </PageSection>
    </PageContainer>
  )
}

function PreviewRowsTable({ sheet }: { sheet: WorkbookSheetPreview }) {
  const columns = sheet.fields.slice(0, 8).map((field) => field.label)
  if (sheet.preview_rows.length === 0) {
    return <div className="rounded-md border border-border/70 py-12 text-center text-muted-foreground text-sm">当前 Sheet 无数据</div>
  }
  return (
    <AdminDataTable>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column}>{column}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sheet.preview_rows.map((row, index) => (
            <TableRow key={`${sheet.sheet_name}-${index}`}>
              {columns.map((column) => (
                <TableCell key={column} className="max-w-[180px] truncate">
                  {row[column] || "-"}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

function MissingRequiredTable({ sheet }: { sheet: WorkbookSheetPreview }) {
  return (
    <AdminDataTable>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>行号</TableHead>
            <TableHead>字段</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sheet.missing_required.slice(0, 8).map((item) => (
            <TableRow key={`${item.row}-${item.field}`}>
              <TableCell>{item.row}</TableCell>
              <TableCell>{item.label}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AdminDataTable>
  )
}

function SmallStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-semibold tabular-nums">{value}</div>
    </div>
  )
}

async function fileToBase64(file: File) {
  const buffer = await file.arrayBuffer()
  let binary = ""
  const bytes = new Uint8Array(buffer)
  const chunkSize = 0x8000
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize))
  }
  return btoa(binary)
}
