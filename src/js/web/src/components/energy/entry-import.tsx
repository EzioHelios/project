import { useRef, useState } from "react"
import { toast } from "sonner"
import type { Row } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { type EnergyImportResult, importEnergy, monthRange } from "@/hooks/use-energy-entry"
import { EnergyTable, EnergyTotals } from "./entry-table"
import { downloadCsv, parseEnergyCsv, summarizeEnergy } from "./entry-utils"

export function EnergyEntryImport({
  types,
  defaults,
  onClose,
  onImported,
}: {
  types: Row[]
  defaults: { month: string; area_id: string; energy_type_code: string }
  onClose: () => void
  onImported: (result: EnergyImportResult) => Promise<void>
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [rows, setRows] = useState<Record<string, string>[]>([])
  const [name, setName] = useState("")
  const [preview, setPreview] = useState<EnergyImportResult | null>(null)
  const [result, setResult] = useState<EnergyImportResult | null>(null)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  const loadFile = async (file?: File) => {
    setRows([])
    setPreview(null)
    setResult(null)
    setError("")
    if (!file) return
    setPending(true)
    setName(file.name)
    try {
      const data = parseEnergyCsv(await file.text()).map((row) => {
        const month = row.month || defaults.month
        if (month && !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error("月份必须使用 YYYY-MM 格式")
        return {
          ...(!row.energy_type_name && !row.energy_type_code && defaults.energy_type_code ? { energy_type_code: defaults.energy_type_code } : {}),
          ...(!row.area_name && !row.area_id && defaults.area_id ? { area_id: defaults.area_id } : {}),
          ...(month && !row.period_start ? monthRange(month) : {}),
          ...Object.fromEntries(Object.entries(row).filter(([, value]) => value !== "")),
        }
      })
      setRows(data)
      setPreview(await importEnergy(data, file.name, true))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文件预检失败")
    } finally {
      setPending(false)
    }
  }
  const submit = async () => {
    setPending(true)
    setError("")
    try {
      const saved = await importEnergy(rows, name, false)
      setResult(saved)
      await onImported(saved)
      if (saved.imported_count)
        toast.success(`已导入 ${saved.imported_count} 条能源数据`, {
          description: saved.skipped_count ? `${saved.skipped_count} 条未导入，请查看结果` : "列表已定位到本次导入记录",
        })
      else toast.error("本次没有新增记录", { description: "请查看逐行结果" })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "导入失败")
    } finally {
      setPending(false)
    }
  }
  const ready = preview?.records.filter((row) => row.status === "ready") ?? []
  const shown = result ?? preview
  return (
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle>{result ? "能源导入结果" : "导入能源数据"}</DialogTitle>
          <DialogDescription>仅新增记录；重复记录不覆盖，已有数据请在列表中编辑。同一区域、设备、能源和期间的无编号记录视为重复。</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileInput}
            className="sr-only"
            aria-label="能源导入文件"
            type="file"
            accept=".csv,text/csv"
            data-testid="energy-interval-import-file"
            disabled={pending}
            onChange={(event) => void loadFile(event.target.files?.[0])}
          />
          <Button type="button" variant="outline" disabled={pending} onClick={() => fileInput.current?.click()}>
            选择文件
          </Button>
          <span className="self-center text-sm text-muted-foreground">{name || "未选择文件"}</span>
          <Button
            variant="outline"
            data-testid="energy-interval-import-template-download"
            onClick={() => downloadCsv("能源数据填报模板.csv", "区域,设备,能源种类,月份,能源用量,单位,费用,备注\n")}
          >
            下载模板
          </Button>
        </div>
        {pending && <output className="text-sm">正在处理能源数据…</output>}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {shown && (
          <>
            <output className="text-sm tabular-nums">
              读取 {shown.received_count} 条 · {result ? `实际导入 ${result.imported_count}` : `将新增 ${ready.length}`} 条 · {shown.skipped_count} 条
              {result ? "未导入" : "存在问题"}
            </output>
            <EnergyTotals
              totals={summarizeEnergy(result ? result.records.filter((row) => row.status === "imported") : ready)}
              types={types}
              label={result ? "实际导入合计" : "待导入合计"}
            />
            <EnergyTable rows={shown.records} types={types} preview={!result} />
            {shown.errors.length > 0 && (
              <div role="alert" className="space-y-1 text-sm text-destructive">
                {shown.errors.map((item) => (
                  <p key={item.row_number}>
                    第 {item.row_number} 行：{item.message}
                  </p>
                ))}
              </div>
            )}
          </>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={pending}>
            {result ? "查看本次导入记录" : "取消"}
          </Button>
          {!result && (
            <Button data-testid="energy-interval-import-submit" disabled={pending || !preview || ready.length === 0} onClick={() => void submit()}>
              {pending ? "正在导入" : `确认导入 ${ready.length} 条`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
