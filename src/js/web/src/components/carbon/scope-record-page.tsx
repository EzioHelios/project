import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type ReactNode, useMemo, useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar } from "@/components/admin-ui"
import { CarbonRecordActions } from "@/components/carbon/record-actions"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"

type Option = { label: string; value: string }
type Field = {
  name: string
  label: string
  type?: "text" | "number" | "date" | "select" | "textarea"
  required?: boolean
  placeholder?: string
  options?: Option[]
}

type Column<T> = {
  key: string
  label: string
  align?: "right"
  render?: (row: T) => string
}

type ScopeRow = Record<string, unknown> & {
  id: number
  status?: string
  computed_co2e?: number | null
  factor_source?: string | null
  factor_year?: number | null
}

type ApiResponse<T> = { code: number; msg?: string; data: T }

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

async function requestJson<T>(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiResponse<T>
}

function initialForm(fields: Field[]) {
  return Object.fromEntries(fields.map((field) => [field.name, ""])) as Record<string, string>
}

function toPayload(fields: Field[], form: Record<string, string>) {
  const payload: Record<string, unknown> = {}
  for (const field of fields) {
    const raw = form[field.name] ?? ""
    if (field.type === "number") {
      payload[field.name] = raw.trim() ? raw : null
    } else {
      payload[field.name] = raw.trim() ? raw : null
    }
  }
  return payload
}

function FieldControl({ field, value, onChange }: { field: Field; value: string; onChange: (value: string) => void }) {
  if (field.type === "select") {
    return (
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder={field.placeholder || field.label} />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }
  if (field.type === "textarea") {
    return <Textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder={field.placeholder} />
  }
  return (
    <Input
      type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.placeholder}
    />
  )
}

export function ScopeRecordPage<T extends ScopeRow>({
  title,
  endpoint,
  queryKey,
  searchPlaceholder,
  columns,
  fields,
  embedded = false,
  importPanel,
}: {
  title: string
  endpoint: string
  queryKey: string[]
  searchPlaceholder: string
  columns: Column<T>[]
  fields: Field[]
  embedded?: boolean
  importPanel?: ReactNode
}) {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [status, setStatus] = useState<string>("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<T | null>(null)
  const [form, setForm] = useState<Record<string, string>>(() => initialForm(fields))

  const listQuery = useQuery({
    queryKey: [...queryKey, keyword, status, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<T>(endpoint, {
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        status: status === "all" ? undefined : status,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const createMut = useMutation({
    mutationFn: async () => requestJson<T>(endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(toPayload(fields, form)) }),
    onSuccess: async () => {
      toast.success("新增成功")
      setCreateOpen(false)
      setForm(initialForm(fields))
      await qc.invalidateQueries({ queryKey })
    },
    onError: (error) => toast.error("新增失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })

  const items = listQuery.data?.items ?? []
  const formReady = useMemo(() => fields.every((field) => !field.required || Boolean((form[field.name] ?? "").trim())), [fields, form])
  const detailLabels = useMemo(
    () => Object.fromEntries([...columns.map((column) => [column.key, column.label] as const), ...fields.map((field) => [field.name, field.label] as const)]),
    [columns, fields],
  )

  const content = (
    <>
      <PageSection>
        <AdminPanel title="数据列表">
          <div className="space-y-3">
            <AdminTableToolbar
              fields={[
                {
                  key: "keyword",
                  node: (
                    <Input
                      value={keyword}
                      onChange={(event) => {
                        setKeyword(event.target.value)
                        setPageIndex(0)
                      }}
                      placeholder={searchPlaceholder}
                    />
                  ),
                },
                {
                  key: "status",
                  node: (
                    <Select
                      value={status}
                      onValueChange={(value) => {
                        setStatus(value)
                        setPageIndex(0)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="状态" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">全部状态</SelectItem>
                        <SelectItem value="draft">草稿</SelectItem>
                        <SelectItem value="pending">待审核</SelectItem>
                        <SelectItem value="approved">已通过</SelectItem>
                        <SelectItem value="rejected">已驳回</SelectItem>
                      </SelectContent>
                    </Select>
                  ),
                },
              ]}
              actions={
                <>
                  <Button variant="secondary" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
                    查询
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setKeyword("")
                      setStatus("all")
                      setPageIndex(0)
                    }}
                  >
                    重置
                  </Button>
                  <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                    <DialogTrigger asChild>
                      <Button>新增</Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新增记录</DialogTitle>
                      </DialogHeader>
                      <div className="grid gap-4">
                        {fields.map((field) => (
                          <div key={field.name} className="grid gap-2">
                            <Label>{field.label}</Label>
                            <FieldControl field={field} value={form[field.name] ?? ""} onChange={(value) => setForm((state) => ({ ...state, [field.name]: value }))} />
                          </div>
                        ))}
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>
                          取消
                        </Button>
                        <Button onClick={() => createMut.mutate()} disabled={!formReady || createMut.isPending}>
                          保存
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </>
              }
            />

            <AdminDataTable>
              {listQuery.isLoading || listQuery.isError ? (
                <Table>
                  <TableBody>
                    {listQuery.isLoading && <AdminTableStateRow colSpan={columns.length + 3}>正在加载数据…</AdminTableStateRow>}
                    {listQuery.isError && (
                      <AdminTableStateRow colSpan={columns.length + 3} tone="danger">
                        加载失败，请检查后端接口。
                      </AdminTableStateRow>
                    )}
                  </TableBody>
                </Table>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      {columns.map((column) => (
                        <TableHead key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                          {column.label}
                        </TableHead>
                      ))}
                      <TableHead className="text-right">核算结果</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.length === 0 && <AdminTableStateRow colSpan={columns.length + 3}>暂无数据</AdminTableStateRow>}
                    {items.map((row) => (
                      <TableRow key={row.id}>
                        {columns.map((column) => (
                          <TableCell key={`${row.id}-${column.key}`} className={column.align === "right" ? "text-right" : undefined}>
                            {column.render ? column.render(row) : display(row[column.key])}
                          </TableCell>
                        ))}
                        <TableCell className="text-right">{row.computed_co2e === null || row.computed_co2e === undefined ? "-" : `${row.computed_co2e} kgCO2e`}</TableCell>
                        <TableCell>
                          <CarbonStatusBadge status={row.status} />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex flex-wrap justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => setDetail(row)}>
                              详情
                            </Button>
                            <CarbonRecordActions id={row.id} status={row.status} basePath={endpoint} invalidateKey={queryKey} />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </AdminDataTable>

            {!listQuery.isLoading && !listQuery.isError && (
              <PaginationBar
                page={listQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
                pageIndex={pageIndex}
                pageSize={pageSize}
                onPageChange={setPageIndex}
                onPageSizeChange={(value) => {
                  setPageSize(value)
                  setPageIndex(0)
                }}
              />
            )}
          </div>
        </AdminPanel>
      </PageSection>

      <Sheet open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>记录详情</SheetTitle>
          </SheetHeader>
          <div className="space-y-2 px-4 pb-6">
            {detail &&
              Object.entries(detail).map(([key, value]) => (
                <div key={key} className="grid grid-cols-[132px_1fr] gap-3 rounded-md border px-3 py-2 text-sm">
                  <div className="text-muted-foreground">{detailLabels[key] ?? key}</div>
                  <div className="min-w-0 break-all">{display(value)}</div>
                </div>
              ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  )

  if (embedded) {
    return content
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title={title} actions={importPanel} />
      {content}
    </PageContainer>
  )
}
