import { AlertTriangle, CheckCircle2, Download, FileText, Upload } from "lucide-react"
import { type ReactNode, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminTableStateRow } from "@/components/admin-ui/data-table"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

export type PageImportField = {
  name: string
  label: string
  aliases?: string[]
  required?: boolean
  type?: "text" | "number" | "date" | "month"
  example?: string
}

export type PageImportRow = Record<string, string>

export type PageImportError = {
  rowNumber: number
  message: string
}

export type PageImportResult = {
  receivedCount: number
  importedCount: number
  skippedCount: number
  errors?: PageImportError[]
}

type ParsedImport = {
  rows: PageImportRow[]
  errors: PageImportError[]
  sourceLines: string[]
}

type PageImportPanelProps = {
  title?: string
  fields: PageImportField[]
  sourceNameDefault?: string
  sourceNameLabel?: string
  submitLabel?: string
  triggerLabel?: string
  testId?: string
  controls?: ReactNode
  onConfirm: (rows: PageImportRow[], context: { sourceName: string }) => Promise<PageImportResult>
  onCompleted?: (result: PageImportResult) => void | Promise<void>
}

export function PageImportPanel({
  title = "数据导入",
  fields,
  sourceNameDefault = "页面级导入",
  sourceNameLabel = "来源名称",
  submitLabel = "确认入库",
  triggerLabel = "导入",
  testId,
  controls,
  onConfirm,
  onCompleted,
}: PageImportPanelProps) {
  const [sourceName, setSourceName] = useState(sourceNameDefault)
  const [csvText, setCsvText] = useState("")
  const [result, setResult] = useState<PageImportResult | null>(null)
  const [pending, setPending] = useState(false)
  const [open, setOpen] = useState(false)
  const parsed = useMemo(() => parsePageImportCsv(csvText, fields), [csvText, fields])
  const allErrors = [...parsed.errors, ...(result?.errors ?? [])]
  const canConfirm = parsed.rows.length > 0 && parsed.errors.length === 0 && !pending
  const hasFileContent = csvText.trim().length > 0
  const activeStep = result ? 3 : hasFileContent ? 2 : 1

  useEffect(() => {
    setSourceName(sourceNameDefault)
  }, [sourceNameDefault])

  async function loadFile(file: File | undefined) {
    if (!file) return
    setCsvText(await readFileText(file))
    setResult(null)
  }

  async function confirmImport() {
    if (!canConfirm) return
    setPending(true)
    try {
      const next = await onConfirm(parsed.rows, { sourceName: sourceName.trim() || sourceNameDefault })
      setResult(next)
      await onCompleted?.(next)
      toast.success(`已入库 ${next.importedCount} 行`, {
        description: next.skippedCount ? `跳过 ${next.skippedCount} 行` : undefined,
      })
    } catch (error) {
      toast.error("导入失败", { description: error instanceof Error ? error.message : "请检查导入文件" })
    } finally {
      setPending(false)
    }
  }

  function downloadTemplate() {
    downloadCsv(`${slugify(title)}-template.csv`, buildTemplateCsv(fields))
  }

  function downloadErrors() {
    if (!allErrors.length) return
    downloadCsv(`${slugify(title)}-errors.csv`, buildErrorCsv(allErrors, parsed.sourceLines))
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" data-testid={testId ? `${testId}-trigger` : undefined}>
          <Upload className="mr-2 size-4" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">下载模板、上传 CSV、校验字段并确认入库。</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="grid gap-2 md:grid-cols-3">
            <ImportStep index={1} title="下载模板" active={activeStep === 1} done={hasFileContent || Boolean(result)} />
            <ImportStep index={2} title="上传校验" active={activeStep === 2} done={Boolean(result)} muted={!hasFileContent} />
            <ImportStep index={3} title="确认入库" active={activeStep === 3} done={Boolean(result)} muted={!canConfirm && !result} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/20 p-3">
                <div className="flex items-center gap-2 font-medium text-sm">
                  <FileText className="size-4 text-muted-foreground" />
                  模板
                </div>
                <div className="mt-3 space-y-3">
                  {controls}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full justify-center"
                    onClick={downloadTemplate}
                    data-testid={testId ? `${testId}-template-download` : undefined}
                  >
                    <Download className="mr-2 size-4" />
                    下载模板
                  </Button>
                </div>
              </div>

              <div className="rounded-md border bg-muted/20 p-3" data-testid={testId ? `${testId}-template-fields` : undefined}>
                <div className="mb-2 font-medium text-sm">模板字段</div>
                <div className="break-all text-muted-foreground text-xs leading-5">{fields.map((field) => field.label).join("，")}</div>
              </div>

              <div className="rounded-md border bg-muted/20 p-3" data-testid={testId ? `${testId}-alias-fields` : undefined}>
                <div className="mb-2 font-medium text-sm">字段映射</div>
                <div className="break-all text-muted-foreground text-xs leading-5">{fields.map((field) => `${field.label}=${field.name}`).join("，")}</div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
                <div className="space-y-2">
                  <Label>{sourceNameLabel}</Label>
                  <Input value={sourceName} onChange={(event) => setSourceName(event.target.value)} data-testid={testId ? `${testId}-source-name` : undefined} />
                </div>
                <div className="space-y-2">
                  <Label>CSV 文件</Label>
                  <Input
                    type="file"
                    accept=".csv,text/csv,text/plain"
                    onChange={(event) => loadFile(event.target.files?.[0])}
                    data-testid={testId ? `${testId}-file` : undefined}
                  />
                </div>
              </div>

              <Textarea
                value={csvText}
                onChange={(event) => {
                  setCsvText(event.target.value)
                  setResult(null)
                }}
                className="min-h-44 font-mono text-xs"
                placeholder={fields.map((field) => field.label).join(",")}
                data-testid={testId ? `${testId}-csv-text` : undefined}
              />

              <div className="grid gap-3 text-sm md:grid-cols-4">
                <SummaryCell label="接收行" value={parsed.rows.length + parsed.errors.length} />
                <SummaryCell label="可入库" value={parsed.rows.length} />
                <SummaryCell label="校验错误" value={parsed.errors.length} tone={parsed.errors.length ? "danger" : undefined} />
                <SummaryCell label="已入库" value={result?.importedCount ?? "-"} />
              </div>

              {result ? (
                <div className="grid gap-3 text-sm md:grid-cols-3">
                  <SummaryCell label="服务端接收" value={result.receivedCount} />
                  <SummaryCell label="服务端入库" value={result.importedCount} />
                  <SummaryCell label="服务端跳过" value={result.skippedCount} tone={result.skippedCount ? "warning" : undefined} />
                </div>
              ) : null}

              {allErrors.length ? (
                <div className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 font-medium text-sm">
                      <AlertTriangle className="size-4 text-destructive" />
                      错误行
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={downloadErrors} data-testid={testId ? `${testId}-errors-download` : undefined}>
                      <Download className="mr-2 size-4" />
                      下载错误行
                    </Button>
                  </div>
                  <AdminDataTable className="rounded-md">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>行号</TableHead>
                          <TableHead>错误</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {allErrors.slice(0, 8).map((error, index) => (
                          <TableRow key={`${error.rowNumber}-${error.message}-${index}`}>
                            <TableCell>{error.rowNumber}</TableCell>
                            <TableCell>{error.message}</TableCell>
                          </TableRow>
                        ))}
                        {allErrors.length > 8 ? <AdminTableStateRow colSpan={2}>其余错误请下载错误行查看</AdminTableStateRow> : null}
                      </TableBody>
                    </Table>
                  </AdminDataTable>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            关闭
          </Button>
          <Button type="button" onClick={confirmImport} disabled={!canConfirm} data-testid={testId ? `${testId}-submit` : undefined}>
            <CheckCircle2 className="mr-2 size-4" />
            {pending ? "入库中" : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ImportStep({ index, title, active, done, muted }: { index: number; title: string; active?: boolean; done?: boolean; muted?: boolean }) {
  return (
    <div className={cn("flex items-center gap-3 rounded-md border px-3 py-2 text-sm", active && "border-primary bg-primary/5", muted && "opacity-60")}>
      <span
        className={cn("flex size-6 shrink-0 items-center justify-center rounded-full border text-xs tabular-nums", done && "border-primary bg-primary text-primary-foreground")}
      >
        {done ? <CheckCircle2 className="size-4" /> : index}
      </span>
      <span className="font-medium">{title}</span>
    </div>
  )
}

function SummaryCell({ label, value, tone }: { label: string; value: number | string; tone?: "danger" | "warning" }) {
  const toneClass = tone === "danger" ? "text-destructive" : tone === "warning" ? "text-amber-700" : "text-foreground"
  return (
    <div className="rounded-md border bg-muted/20 px-3 py-2">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={`font-medium tabular-nums ${toneClass}`}>{value}</div>
    </div>
  )
}

function parsePageImportCsv(value: string, fields: PageImportField[]): ParsedImport {
  const sourceLines = value.replace(/^\uFEFF/, "").split(/\r?\n/)
  const lines = sourceLines.filter((line) => line.trim())
  if (!value.trim()) return { rows: [], errors: [], sourceLines: [] }
  if (lines.length < 2) return { rows: [], errors: [{ rowNumber: 0, message: "CSV 至少需要表头和一行数据" }], sourceLines }
  const headerCells = parseCsvLine(lines[0])
  const fieldByHeader = buildHeaderMap(fields)
  const mappedHeaders = headerCells.map((header) => fieldByHeader.get(normalizeHeader(header)) ?? "")
  const rows: PageImportRow[] = []
  const errors: PageImportError[] = []

  for (let index = 1; index < lines.length; index += 1) {
    const values = parseCsvLine(lines[index])
    const row: PageImportRow = {}
    for (let cellIndex = 0; cellIndex < mappedHeaders.length; cellIndex += 1) {
      const fieldName = mappedHeaders[cellIndex]
      if (fieldName) row[fieldName] = values[cellIndex]?.trim() ?? ""
    }
    const rowNumber = index + 1
    const rowErrors = validateRow(row, fields)
    if (rowErrors.length) {
      errors.push(...rowErrors.map((message) => ({ rowNumber, message })))
    } else {
      rows.push(row)
    }
  }

  return { rows, errors, sourceLines }
}

function buildHeaderMap(fields: PageImportField[]) {
  const map = new Map<string, string>()
  for (const field of fields) {
    for (const header of [field.name, field.label, ...(field.aliases ?? [])]) {
      map.set(normalizeHeader(header), field.name)
    }
  }
  return map
}

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "")
}

function validateRow(row: PageImportRow, fields: PageImportField[]) {
  const errors: string[] = []
  for (const field of fields) {
    const value = row[field.name]?.trim() ?? ""
    if (field.required && !value) {
      errors.push(`${field.label}不能为空`)
      continue
    }
    if (!value) continue
    if (field.type === "number" && Number.isNaN(Number(value))) errors.push(`${field.label}必须是数字`)
    if (field.type === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(value)) errors.push(`${field.label}格式应为 YYYY-MM-DD`)
    if (field.type === "month" && !/^\d{4}-\d{2}$/.test(value)) errors.push(`${field.label}格式应为 YYYY-MM`)
  }
  return errors
}

function parseCsvLine(line: string) {
  const cells: string[] = []
  let current = ""
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const next = line[index + 1]
    if (char === '"' && quoted && next === '"') {
      current += '"'
      index += 1
    } else if (char === '"') {
      quoted = !quoted
    } else if (char === "," && !quoted) {
      cells.push(current)
      current = ""
    } else {
      current += char
    }
  }
  cells.push(current)
  return cells
}

function buildTemplateCsv(fields: PageImportField[]) {
  const headers = fields.map((field) => field.label)
  const examples = fields.map((field) => field.example ?? "")
  return `\uFEFF${headers.map(csvCell).join(",")}\n${examples.map(csvCell).join(",")}\n`
}

function buildErrorCsv(errors: PageImportError[], sourceLines: string[]) {
  const rows = [["row_number", "message", "raw_csv_line"]]
  for (const error of errors) {
    rows.push([String(error.rowNumber), error.message, sourceLines[error.rowNumber - 1] ?? ""])
  }
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\n")}\n`
}

function csvCell(value: unknown) {
  const text = value === null || value === undefined ? "" : String(value)
  return `"${text.replace(/"/g, '""')}"`
}

function readFileText(file: File) {
  if (typeof file.text === "function") return file.text()
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ""))
    reader.onerror = () => reject(reader.error ?? new Error("文件读取失败"))
    reader.readAsText(file)
  })
}

function downloadCsv(filename: string, text: string) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function slugify(value: string) {
  return value
    .trim()
    .replace(/[^\u4e00-\u9fa5\w-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
}
