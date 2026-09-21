import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Plus, RefreshCw, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { AdminDataTable, AdminTableToolbar } from "@/components/admin-ui"
import { AdminFilterBar } from "@/components/admin-ui/filter-bar"
import { AdminPageScaffold } from "@/components/admin-ui/page-scaffold"
import { Button } from "@/components/ui/button"
import { DateTimeInput, isCompleteDateTime } from "@/components/ui/date-time-input"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuthStore } from "@/lib/auth"
import { equipmentKinds, type HandlingOptions, type HandlingRow, handlingRequest, handlingStates, localTime } from "@/lib/material-handling"
import { operationLabels } from "@/lib/vision"

export const Route = createFileRoute("/_app/data/material-handling")({ component: HandlingPage })
const selectClass = "h-9 w-full rounded-md border bg-background px-3 text-sm"
const initial = {
  operation_no: "",
  operation_type: "internal_transfer",
  equipment_id: "",
  equipment_type: "forklift",
  material_id: "",
  batch_no: "",
  quantity: "1",
  weight_kg: "",
  remark: "",
  active_intervals: [{ key: "initial", start: "", end: "" }],
}
type Form = typeof initial

function HandlingPage() {
  const team = useAuthStore((s) => s.currentTeam?.id)
  const cache = useQueryClient(),
    [tab, setTab] = useState("operations"),
    [keyword, setKeyword] = useState(""),
    [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<HandlingRow | null | undefined>(),
    [view, setView] = useState<HandlingRow | null>(null),
    [form, setForm] = useState<Form>(initial)
  const [action, setAction] = useState<{ row: HandlingRow; kind: string } | null>(null),
    [calculation, setCalculation] = useState(false)
  const [calc, setCalc] = useState({ equipment_id: "", energy_source_system: "", period_start: "", period_end: "", factor_id: "", applicability_note: "" })
  const options = useQuery({ queryKey: ["handling-options", team], queryFn: () => handlingRequest<HandlingOptions>("/api/material-allocation/options"), enabled: Boolean(team) })
  const admin = options.data?.can_manage === true
  const rows = useQuery({
    queryKey: ["handling", team, tab, keyword, offset],
    queryFn: () => handlingRequest<{ items: HandlingRow[]; total: number }>(`/api/material-allocation/${tab}?limit=25&offset=${offset}&keyword=${encodeURIComponent(keyword)}`),
    enabled: Boolean(team),
  })
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ["handling-options"] })
    void cache.invalidateQueries({ queryKey: ["handling"] })
    void cache.invalidateQueries({ queryKey: ["vision"] })
  }
  const mutation = useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: string; body?: unknown }) => handlingRequest(path, method, body),
    onSuccess: () => {
      toast.success("操作成功")
      setEditing(undefined)
      setAction(null)
      setCalculation(false)
      refresh()
    },
    onError: (e: Error) => toast.error(e.message),
  })
  const open = (row: HandlingRow | null) => {
    setEditing(row)
    setForm(
      row
        ? {
            operation_no: row.operation_no,
            operation_type: row.operation_type,
            equipment_id: String(row.equipment_id),
            equipment_type: row.equipment_type,
            material_id: String(row.material_id ?? ""),
            batch_no: row.batch_no ?? "",
            quantity: String(row.quantity),
            weight_kg: row.weight_kg === null ? "" : String(row.weight_kg),
            remark: row.remark ?? "",
            active_intervals: (row.active_intervals ?? []).map((i) => ({ key: crypto.randomUUID(), start: localTime(i.start), end: localTime(i.end) })),
          }
        : structuredClone(initial),
    )
  }
  const save = () => {
    if (!form.active_intervals.length || form.active_intervals.some((i) => !isCompleteDateTime(i.start) || !isCompleteDateTime(i.end))) {
      toast.error("请填写完整的作业日期和时间")
      return
    }
    const body = {
      ...form,
      equipment_id: Number(form.equipment_id),
      material_id: Number(form.material_id),
      quantity: form.quantity,
      weight_kg: form.weight_kg || null,
      active_intervals: form.active_intervals.map((i) => ({ start: new Date(i.start).toISOString(), end: new Date(i.end).toISOString() })),
    }
    if (editing) {
      const { operation_no: _, ...update } = body
      mutation.mutate({ path: `/api/material-allocation/operations/${editing.id}`, method: "PATCH", body: update })
    } else mutation.mutate({ path: "/api/material-allocation/operations", method: "POST", body })
  }
  const text = (key: Exclude<keyof Form, "active_intervals">, label: string, type = "text") => (
    <div>
      <Label htmlFor={`op-${key}`}>{label}</Label>
      <Input
        id={`op-${key}`}
        type={type}
        value={form[key]}
        step={type === "number" ? "any" : undefined}
        required={!["remark", "weight_kg"].includes(key)}
        disabled={key === "operation_no" && Boolean(editing)}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      />
    </div>
  )
  const select = (key: Exclude<keyof Form, "active_intervals">, label: string, choices: { value: string; label: string }[]) => (
    <div>
      <Label htmlFor={`op-${key}`}>{label}</Label>
      <select id={`op-${key}`} className={selectClass} required value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })}>
        <option value="">请选择</option>
        {choices.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
  return (
    <AdminPageScaffold
      title="物资作业"
      topActions={
        admin && (
          <Button onClick={() => open(null)}>
            <Plus />
            新增作业
          </Button>
        )
      }
      tabs={
        <Tabs
          value={tab}
          onValueChange={(v) => {
            setTab(v)
            setOffset(0)
          }}
        >
          <TabsList>
            <TabsTrigger value="operations">作业台账</TabsTrigger>
            <TabsTrigger value="runs">小时分配</TabsTrigger>
            <TabsTrigger value="results">物资结果</TabsTrigger>
          </TabsList>
        </Tabs>
      }
      filters={
        <AdminFilterBar
          fields={
            tab === "operations"
              ? [
                  {
                    key: "search",
                    node: (
                      <Input
                        aria-label="搜索作业"
                        placeholder="作业单 / 物资 / 设备"
                        value={keyword}
                        onChange={(e) => {
                          setKeyword(e.target.value)
                          setOffset(0)
                        }}
                      />
                    ),
                  },
                ]
              : []
          }
          actions={
            <>
              <Button variant="outline" onClick={refresh}>
                <RefreshCw />
                刷新
              </Button>
              {options.data?.can_calculate && tab !== "operations" && <Button onClick={() => setCalculation(true)}>计算分配</Button>}
              <Button variant="outline" asChild>
                <Link to="/carbon/product-footprint">产品碳足迹</Link>
              </Button>
            </>
          }
        />
      }
    >
      {options.isError && <p role="alert">{options.error.message}</p>}
      <AdminTableToolbar>
        <span>{rows.data?.total ?? 0} 条</span>
      </AdminTableToolbar>
      <AdminDataTable>
        <Table>
          <TableHeader>
            <TableRow>
              {(tab === "operations"
                ? ["作业单", "设备 / 区域", "物资 / 批次", "数量", "有效时长", "状态", "操作"]
                : tab === "runs"
                  ? ["设备", "计算时段", "已分配电量(kWh)", "未归属电量(kWh)", "状态", "操作"]
                  : ["物资 / 批次", "设备", "分配电量(kWh)", "碳排放(kgCO₂e)", "状态", "操作"]
              ).map((x) => (
                <TableHead key={x}>{x}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.isLoading ? (
              <TableRow>
                <TableCell colSpan={7}>加载中</TableCell>
              </TableRow>
            ) : rows.isError ? (
              <TableRow>
                <TableCell colSpan={7} role="alert">
                  {rows.error.message}
                  <Button variant="outline" onClick={() => void rows.refetch()}>
                    重试
                  </Button>
                </TableCell>
              </TableRow>
            ) : !rows.data?.items.length ? (
              <TableRow>
                <TableCell colSpan={7}>暂无记录</TableCell>
              </TableRow>
            ) : (
              rows.data.items.map((row) => (
                <TableRow key={row.id}>
                  {tab === "operations" ? (
                    <>
                      <TableCell>{row.operation_no}</TableCell>
                      <TableCell>
                        {row.equipment_name}
                        <small className="block text-muted-foreground">{row.area_name}</small>
                      </TableCell>
                      <TableCell>
                        {row.material_name}
                        <small className="block">{row.batch_no}</small>
                      </TableCell>
                      <TableCell>
                        {row.quantity} {row.unit}
                      </TableCell>
                      <TableCell>{Number(row.duration_minutes).toFixed(2)} 分钟</TableCell>
                      <TableCell>{handlingStates[row.operation_status]}</TableCell>
                    </>
                  ) : tab === "runs" ? (
                    <>
                      <TableCell>{row.equipment_name ?? "—"}</TableCell>
                      <TableCell>{localTime(row.period_start).replace("T", " ")}</TableCell>
                      <TableCell>{row.total_energy_kwh}</TableCell>
                      <TableCell>{row.unallocated_energy_kwh ?? "—"}</TableCell>
                      <TableCell>{handlingStates[row.status] ?? row.status}</TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell>
                        {row.material_name}
                        <small className="block">{row.batch_no}</small>
                      </TableCell>
                      <TableCell>{row.equipment_name}</TableCell>
                      <TableCell>{row.allocated_energy_kwh}</TableCell>
                      <TableCell>{row.allocated_co2e_kg}</TableCell>
                      <TableCell>{handlingStates[row.data_status]}</TableCell>
                    </>
                  )}
                  <TableCell>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setView(row)}>
                        详情
                      </Button>
                      {tab === "runs" && options.data?.can_calculate && row.input_snapshot?.command && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            const c = row.input_snapshot?.command
                            if (c) {
                              setCalc({
                                equipment_id: String(c.equipment_id),
                                energy_source_system: c.energy_source_system,
                                period_start: localTime(c.period_start),
                                period_end: localTime(c.period_end),
                                factor_id: String(c.factor_id),
                                applicability_note: c.applicability_note,
                              })
                              setCalculation(true)
                            }
                          }}
                        >
                          重新计算
                        </Button>
                      )}
                      {tab === "operations" && admin && (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => open(row)}>
                            编辑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setAction({ row, kind: row.operation_status === "confirmed" ? "withdraw" : "confirm" })}>
                            {row.operation_status === "confirmed" ? "撤回" : "确认"}
                          </Button>
                          <Button size="icon" variant="ghost" title="删除" onClick={() => setAction({ row, kind: "delete" })}>
                            <Trash2 size={16} />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </AdminDataTable>
      <div className="flex justify-end gap-3 py-3">
        <Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 25))}>
          上一页
        </Button>
        <Button variant="outline" disabled={offset + 25 >= (rows.data?.total ?? 0)} onClick={() => setOffset(offset + 25)}>
          下一页
        </Button>
      </div>
      <Sheet
        open={editing !== undefined}
        onOpenChange={(v) => {
          if (!v) setEditing(undefined)
        }}
      >
        <SheetContent className="overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{editing ? "编辑作业" : "新增作业"}</SheetTitle>
          </SheetHeader>
          <form
            className="space-y-4 p-4"
            onSubmit={(e) => {
              e.preventDefault()
              save()
            }}
          >
            <div className="grid grid-cols-2 gap-4">
              {text("operation_no", "作业单号")}
              {select(
                "operation_type",
                "作业类型",
                Object.entries(operationLabels).map(([value, label]) => ({ value, label })),
              )}
              {select(
                "equipment_id",
                "设备",
                (options.data?.devices ?? []).map((o) => ({ value: String(o.id), label: o.name ?? "" })),
              )}
              {select(
                "equipment_type",
                "设备类别",
                Object.entries(equipmentKinds).map(([value, label]) => ({ value, label })),
              )}
              {select(
                "material_id",
                "物资",
                (options.data?.materials ?? []).map((o) => ({ value: String(o.id), label: `${o.name} (${o.default_unit ?? "未设单位"})` })),
              )}
              {text("batch_no", "批次")}
              {text("quantity", "数量", "number")}
              {text("weight_kg", "重量(kg)", "number")}
            </div>
            <fieldset className="space-y-3">
              <legend>有效作业时段</legend>
              {form.active_intervals.map((v, i) => (
                <div className="flex items-end gap-2" key={v.key}>
                  <label className="flex-1" htmlFor={`start-${v.key}`}>
                    开始
                    <DateTimeInput
                      id={`start-${v.key}`}
                      label={`开始时间${i + 1}`}
                      required
                      value={v.start}
                      onChange={(value) => setForm({ ...form, active_intervals: form.active_intervals.map((item, n) => (n === i ? { ...item, start: value } : item)) })}
                    />
                  </label>
                  <label className="flex-1" htmlFor={`end-${v.key}`}>
                    结束
                    <DateTimeInput
                      id={`end-${v.key}`}
                      label={`结束时间${i + 1}`}
                      required
                      value={v.end}
                      onChange={(value) => setForm({ ...form, active_intervals: form.active_intervals.map((item, n) => (n === i ? { ...item, end: value } : item)) })}
                    />
                  </label>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="移除时段"
                    onClick={() => setForm({ ...form, active_intervals: form.active_intervals.filter((_, n) => i !== n) })}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                onClick={() => setForm({ ...form, active_intervals: [...form.active_intervals, { key: crypto.randomUUID(), start: "", end: "" }] })}
              >
                <Plus />
                添加时段
              </Button>
            </fieldset>
            {text("remark", "备注")}
            <Button type="submit" disabled={mutation.isPending || !form.active_intervals.length}>
              保存
            </Button>
          </form>
        </SheetContent>
      </Sheet>
      <Sheet
        open={Boolean(view)}
        onOpenChange={(v) => {
          if (!v) setView(null)
        }}
      >
        <SheetContent className="overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>记录详情</SheetTitle>
          </SheetHeader>
          {view && (
            <dl className="grid grid-cols-2 gap-4 p-4">
              {Object.entries({
                作业单: view.operation_no,
                设备: view.equipment_name,
                区域: view.area_name,
                物资: view.material_name,
                批次: view.batch_no,
                状态: handlingStates[view.operation_status ?? view.data_status ?? view.status],
                数据质量: handlingStates[view.data_quality],
                开始: localTime(view.period_start ?? ""),
                结束: localTime(view.period_end ?? ""),
                有效分钟: view.duration_minutes,
                分配电量: view.allocated_energy_kwh ?? view.total_energy_kwh,
                未归属电量: view.unallocated_energy_kwh,
                备注: view.remark,
              })
                .filter(([, value]) => value !== undefined)
                .map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-muted-foreground">{key}</dt>
                    <dd>{String(value ?? "—")}</dd>
                  </div>
                ))}
              {view.active_intervals?.map((i) => (
                <div key={i.start} className="col-span-2">
                  <dt>有效时段</dt>
                  <dd>
                    {localTime(i.start)} 至 {localTime(i.end)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </SheetContent>
      </Sheet>
      <Dialog
        open={Boolean(action)}
        onOpenChange={(v) => {
          if (!v) setAction(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{action?.kind === "delete" ? "删除作业" : action?.kind === "confirm" ? "确认作业" : "撤回确认"}</DialogTitle>
          </DialogHeader>
          <p>{action?.row.operation_no}</p>
          <Button
            disabled={mutation.isPending}
            onClick={() => {
              if (action)
                mutation.mutate({
                  path: `/api/material-allocation/operations/${action.row.id}${action.kind === "delete" ? "" : `/${action.kind}`}`,
                  method: action.kind === "delete" ? "DELETE" : "POST",
                })
            }}
          >
            确定
          </Button>
        </DialogContent>
      </Dialog>
      <Dialog open={calculation} onOpenChange={setCalculation}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>小时能耗分配</DialogTitle>
          </DialogHeader>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (!isCompleteDateTime(calc.period_start) || !isCompleteDateTime(calc.period_end)) {
                toast.error("请填写完整的计算日期和时间")
                return
              }
              mutation.mutate({
                path: "/api/material-allocation/runs/calculate",
                method: "POST",
                body: {
                  ...calc,
                  equipment_id: Number(calc.equipment_id),
                  factor_id: Number(calc.factor_id),
                  period_start: new Date(calc.period_start).toISOString(),
                  period_end: new Date(calc.period_end).toISOString(),
                  assumption: "hourly_uniform_intensity_v1",
                },
              })
            }}
          >
            <label className="block" htmlFor="calculate-device">
              设备
              <select
                id="calculate-device"
                aria-label="计算设备"
                className={selectClass}
                required
                value={calc.equipment_id}
                onChange={(e) => setCalc({ ...calc, equipment_id: e.target.value, energy_source_system: "" })}
              >
                <option value="">请选择</option>
                {options.data?.devices.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block" htmlFor="calculate-source">
              计量来源
              <select
                id="calculate-source"
                aria-label="计量来源"
                className={selectClass}
                required
                value={calc.energy_source_system}
                onChange={(e) => setCalc({ ...calc, energy_source_system: e.target.value })}
              >
                <option value="">请选择</option>
                {options.data?.sources
                  .filter((o) => o.equipment_id === Number(calc.equipment_id))
                  .map((o) => (
                    <option key={o.source_system} value={o.source_system}>
                      {o.source_system === "woheng-material-hour" ? "沃衡小时电量样例" : o.source_system}
                    </option>
                  ))}
              </select>
            </label>
            <label className="block" htmlFor="calculate-factor">
              排放因子
              <select
                id="calculate-factor"
                aria-label="排放因子"
                className={selectClass}
                required
                value={calc.factor_id}
                onChange={(e) => setCalc({ ...calc, factor_id: e.target.value })}
              >
                <option value="">请选择</option>
                {options.data?.factors.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.source} · {o.factor_value} kgCO₂e/kWh
                  </option>
                ))}
              </select>
            </label>
            <label className="block" htmlFor="calculate-start">
              开始时间
              <DateTimeInput id="calculate-start" label="计算开始时间" required value={calc.period_start} onChange={(value) => setCalc({ ...calc, period_start: value })} />
            </label>
            <label className="block" htmlFor="calculate-end">
              结束时间
              <DateTimeInput id="calculate-end" label="计算结束时间" required value={calc.period_end} onChange={(value) => setCalc({ ...calc, period_end: value })} />
            </label>
            <div className="text-sm">分配方法：小时平均强度估算</div>
            <label className="block" htmlFor="calculate-note">
              方法与因子适用依据
              <Input id="calculate-note" required minLength={4} value={calc.applicability_note} onChange={(e) => setCalc({ ...calc, applicability_note: e.target.value })} />
            </label>
            <Button type="submit" disabled={mutation.isPending}>
              计算
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </AdminPageScaffold>
  )
}
