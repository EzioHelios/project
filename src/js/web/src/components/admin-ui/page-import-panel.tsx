import { Download, FileUp } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export type PageImportField = {
  key: string
  label: string
  required?: boolean
  type?: "text" | "number"
  aliases?: string[]
}

type ImportResult = {
  receivedCount: number
  importedCount: number
  skippedCount: number
  errors: string[]
}

type PageImportPanelProps = {
  title: string
  fields: PageImportField[]
  testId?: string
  onConfirm: (rows: Record<string, string>[], meta: { sourceName: string }) => Promise<ImportResult> | ImportResult
}

type ParsedImport = {
  rows: Record<string, string>[]
  errors: string[]
  sourceText: string
}

function splitCsvLine(line: string) {
  const cells: string[] = []
  let value = ""
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (character === '"' && line[index + 1] === '"' && quoted) {
      value += '"'
      index += 1
    } else if (character === '"') {
      quoted = !quoted
    } else if (character === "," && !quoted) {
      cells.push(value.trim())
      value = ""
    } else {
      value += character
    }
  }
  cells.push(value.trim())
  return cells
}

function parseCsv(sourceText: string, fields: PageImportField[]): ParsedImport {
  const lines = sourceText
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .filter((line) => line.trim())
  if (lines.length < 2) return { rows: [], errors: ["文件中没有可导入的数据行"], sourceText }

  const headers = splitCsvLine(lines[0])
  const headerMap = new Map<string, PageImportField>()
  for (const field of fields) {
    for (const name of [field.label, field.key, ...(field.aliases ?? [])]) headerMap.set(name.trim(), field)
  }
  const mappedFields = headers.map((header) => headerMap.get(header))
  const errors: string[] = []
  const rows = lines.slice(1).map((line, rowIndex) => {
    const values = splitCsvLine(line)
    const row: Record<string, string> = {}
    mappedFields.forEach((field, columnIndex) => {
      if (field) row[field.key] = values[columnIndex]?.trim() ?? ""
    })
    for (const field of fields) {
      const value = row[field.key] ?? ""
      if (field.required && !value) errors.push(`第 ${rowIndex + 2} 行：${field.label}不能为空`)
      if (field.type === "number" && value && !Number.isFinite(Number(value))) errors.push(`第 ${rowIndex + 2} 行：${field.label}必须是数字`)
    }
    return row
  })

  return { rows, errors, sourceText }
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

function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }))
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function PageImportPanel({ title, fields, testId = "page-import", onConfirm }: PageImportPanelProps) {
  const [parsed, setParsed] = useState<ParsedImport>({ rows: [], errors: [], sourceText: "" })
  const [result, setResult] = useState<ImportResult | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const downloadTemplate = () => {
    downloadText(`${title}模板.csv`, `\uFEFF${fields.map((field) => field.label).join(",")}\n`)
  }

  const handleFile = async (file?: File) => {
    setResult(null)
    if (!file) {
      setParsed({ rows: [], errors: [], sourceText: "" })
      return
    }
    try {
      setParsed(parseCsv(await readFileText(file), fields))
    } catch (error) {
      setParsed({ rows: [], errors: [error instanceof Error ? error.message : "文件读取失败"], sourceText: "" })
    }
  }

  const submit = async () => {
    if (parsed.errors.length || parsed.rows.length === 0) return
    setIsSubmitting(true)
    try {
      const nextResult = await onConfirm(parsed.rows, { sourceName: "页面级导入" })
      setResult(nextResult)
      toast.success("导入完成")
    } catch (error) {
      toast.error("导入失败", { description: error instanceof Error ? error.message : "请稍后重试" })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" data-testid={`${testId}-trigger`}>
          <FileUp />
          {title}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>上传 CSV 文件，系统将按中文表头校验并映射字段。</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input type="file" accept=".csv,text/csv" data-testid={`${testId}-file`} onChange={(event) => void handleFile(event.target.files?.[0])} />
            <Button type="button" variant="outline" onClick={downloadTemplate} data-testid={`${testId}-template-download`}>
              <Download />
              下载模板
            </Button>
          </div>

          {parsed.errors.length > 0 ? (
            <div className="rounded-md border border-[hsl(var(--status-danger))]/30 bg-[hsl(var(--status-danger))]/5 p-3 text-sm">
              <div className="font-medium text-[hsl(var(--status-danger-foreground-admin))]">发现 {parsed.errors.length} 个校验问题</div>
              <ul className="mt-2 space-y-1 text-muted-foreground">
                {parsed.errors.map((error) => (
                  <li key={error}>{error.replace(/^第 \d+ 行：/, "")}</li>
                ))}
              </ul>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                data-testid={`${testId}-errors-download`}
                onClick={() => downloadText(`${title}错误.csv`, `${parsed.sourceText}\n\n${parsed.errors.join("\n")}`)}
              >
                下载错误
              </Button>
            </div>
          ) : parsed.rows.length > 0 ? (
            <div className="rounded-md border border-border/70 bg-muted/30 p-3 text-sm">已读取 {parsed.rows.length} 条记录，等待确认入库。</div>
          ) : null}

          {result ? (
            <div className="rounded-md border border-[hsl(var(--status-success))]/30 bg-[hsl(var(--status-success))]/5 p-3 text-sm">
              <div className="font-medium">服务端入库</div>
              <div className="mt-2 grid grid-cols-3 gap-3 text-muted-foreground">
                <span>
                  接收 <strong className="font-semibold text-foreground">{result.receivedCount}</strong>
                </span>
                <span>
                  导入 <strong className="font-semibold text-foreground">{result.importedCount}</strong>
                </span>
                <span>
                  跳过 <strong className="font-semibold text-foreground">{result.skippedCount}</strong>
                </span>
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" onClick={() => void submit()} disabled={parsed.rows.length === 0 || parsed.errors.length > 0 || isSubmitting} data-testid={`${testId}-submit`}>
            {isSubmitting ? "正在导入" : "确认导入"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
