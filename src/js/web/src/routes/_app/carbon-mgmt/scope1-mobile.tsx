/**
 * [Scope1] 移动源燃烧 - 列表/新增/送审/通过/驳回/删除
 * API: /api/carbon/scope1-mobile-combustion
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { toast } from "sonner"
import { CarbonRecordActions } from "@/components/carbon/record-actions"
import { CarbonStatusBadge } from "@/components/carbon/status-badge"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"

type Scope1Mobile = {
  id: number
  record_date: string
  asset_id?: string | null
  asset_name?: string | null
  fuel_type: string
  amount: string | number
  unit: string
  mileage_km?: string | number | null
  work_hours?: string | number | null
  attachment?: string | null
  remark?: string | null
  status?: string
  approved_at?: string | null
  reject_reason?: string | null
}

type ApiResponse<T> = { code: number; msg: string; data: T }

export const Route = createFileRoute("/_app/carbon-mgmt/scope1-mobile")({
  component: Scope1MobilePage,
})

function Scope1MobilePage() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [status, setStatus] = useState<string>("all")
  const [createOpen, setCreateOpen] = useState(false)
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const [form, setForm] = useState({
    record_date: "",
    asset_name: "",
    fuel_type: "diesel",
    amount: "",
    unit: "L",
    remark: "",
  })

  const listQuery = useQuery({
    queryKey: ["carbon-mgmt", "scope1-mobile", "list", keyword, status, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<Scope1Mobile>("/api/carbon/scope1-mobile-combustion", {
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        status: status === "all" ? undefined : status,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const items = listQuery.data?.items ?? []

  const createMut = useMutation({
    mutationFn: async () => {
      const payload = {
        record_date: form.record_date,
        asset_name: form.asset_name || null,
        fuel_type: form.fuel_type,
        amount: form.amount,
        unit: form.unit,
        remark: form.remark || null,
      }
      const res = await fetch("/api/carbon/scope1-mobile-combustion", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
      const json = (await res.json()) as ApiResponse<Scope1Mobile>
      // 只根据 HTTP 状态码判断是否成功，后端固定返回 2xx + JSON
      if (!res.ok) throw new Error(json.msg || `HTTP ${res.status}`)
      return json.data
    },
    onSuccess: async () => {
      toast.success("新增成功")
      setCreateOpen(false)
      setForm({ record_date: "", asset_name: "", fuel_type: "diesel", amount: "", unit: "L", remark: "" })
      await qc.invalidateQueries({ queryKey: ["carbon-mgmt", "scope1-mobile", "list"] })
    },
    onError: (e) => toast.error("新增失败", { description: e instanceof Error ? e.message : "请稍后重试" }),
  })

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="碳排放管理" title="[范围1] 移动源燃烧" description="移动源燃烧数据填报、审核流转与记录管理。" />

      <PageSection>
        <Card>
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>数据列表</CardTitle>
              <div className="flex flex-wrap gap-2">
                <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                  <DialogTrigger asChild>
                    <Button>新增</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>新增 - 移动源燃烧</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4">
                      <div className="grid gap-2">
                        <Label>记录日期</Label>
                        <Input type="date" value={form.record_date} onChange={(e) => setForm((s) => ({ ...s, record_date: e.target.value }))} />
                      </div>
                      <div className="grid gap-2">
                        <Label>资产/车辆名称</Label>
                        <Input value={form.asset_name} onChange={(e) => setForm((s) => ({ ...s, asset_name: e.target.value }))} placeholder="例如：叉车/货车" />
                      </div>
                      <div className="grid gap-2">
                        <Label>燃料类型</Label>
                        <Select value={form.fuel_type} onValueChange={(v) => setForm((s) => ({ ...s, fuel_type: v }))}>
                          <SelectTrigger>
                            <SelectValue placeholder="选择燃料类型" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="diesel">柴油</SelectItem>
                            <SelectItem value="gasoline">汽油</SelectItem>
                            <SelectItem value="lng">LNG</SelectItem>
                            <SelectItem value="cng">CNG</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="grid gap-2">
                          <Label>用量</Label>
                          <Input value={form.amount} onChange={(e) => setForm((s) => ({ ...s, amount: e.target.value }))} placeholder="例如：12.5" />
                        </div>
                        <div className="grid gap-2">
                          <Label>单位</Label>
                          <Input value={form.unit} onChange={(e) => setForm((s) => ({ ...s, unit: e.target.value }))} placeholder="L/kg/m³" />
                        </div>
                      </div>
                      <div className="grid gap-2">
                        <Label>备注</Label>
                        <Textarea value={form.remark} onChange={(e) => setForm((s) => ({ ...s, remark: e.target.value }))} placeholder="可选" />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setCreateOpen(false)}>
                        取消
                      </Button>
                      <Button
                        onClick={() => createMut.mutate()}
                        disabled={!form.record_date || !form.fuel_type || !String(form.amount).trim() || !form.unit || createMut.isPending}
                      >
                        保存
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

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
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-[260px] flex-1">
                <Input
                  value={keyword}
                  onChange={(e) => {
                    setKeyword(e.target.value)
                    setPageIndex(0)
                  }}
                  placeholder="搜索：资产名称/燃料类型/单位…"
                />
              </div>
              <div className="w-[160px]">
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
              </div>
              <Button variant="secondary" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
                查询
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-3">
            {listQuery.isLoading && <div className="text-sm text-muted-foreground">正在加载…</div>}
            {listQuery.isError && <div className="text-sm text-destructive">加载失败，请检查后端接口。</div>}

            {!listQuery.isLoading && !listQuery.isError && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead>资产名称</TableHead>
                    <TableHead>燃料类型</TableHead>
                    <TableHead className="text-right">用量</TableHead>
                    <TableHead>单位</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                        暂无数据
                      </TableCell>
                    </TableRow>
                  )}
                  {items.map((r) => {
                    const st = r.status ?? "draft"
                    return (
                      <TableRow key={r.id}>
                        <TableCell>{r.record_date}</TableCell>
                        <TableCell>{r.asset_name ?? "-"}</TableCell>
                        <TableCell>{r.fuel_type}</TableCell>
                        <TableCell className="text-right">{String(r.amount)}</TableCell>
                        <TableCell>{r.unit}</TableCell>
                        <TableCell>
                          <CarbonStatusBadge status={st} />
                        </TableCell>
                        <TableCell className="text-right">
                          <CarbonRecordActions id={r.id} status={st} basePath="/api/carbon/scope1-mobile-combustion" invalidateKey={["carbon-mgmt", "scope1-mobile", "list"]} />
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
            <PaginationBar
              page={listQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
              pageIndex={pageIndex}
              pageSize={pageSize}
              onPageChange={setPageIndex}
              onPageSizeChange={(size) => {
                setPageSize(size)
                setPageIndex(0)
              }}
            />
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
