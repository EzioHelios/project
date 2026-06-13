import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { toast } from "sonner"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar } from "@/components/admin-ui"
import { PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type EmployeeCommute = {
  id: number
  name: string
  category?: string | null
  car_power_type?: number | null
  mileage?: number | null
  unit_consumption?: number | null
}

type ApiResponse<T> = {
  code: number
  msg: string
  data: T
}

export const Route = createFileRoute("/_app/data/commute")({
  component: CommutePage,
})

const carPowerTypeLabels: Record<number, string> = {
  0: "柴油",
  1: "汽油",
  2: "电力",
}

function CommutePage() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [category, setCategory] = useState<string>("all")
  const [createOpen, setCreateOpen] = useState(false)
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const [form, setForm] = useState({
    name: "",
    category: "",
    car_power_type: "1",
    mileage: "",
    unit_consumption: "",
  })

  const listQuery = useQuery({
    queryKey: ["data", "commute", "list", keyword, category, pageIndex, pageSize],
    queryFn: async () =>
      requestPage<EmployeeCommute>("/api/data/employee-commute", {
        search: keyword.trim() || undefined,
        keyword: keyword.trim() || undefined,
        category: category === "all" ? undefined : category,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const items = listQuery.data?.items ?? []

  const createMut = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        category: form.category || null,
        car_power_type: Number.parseInt(form.car_power_type || "1", 10),
        mileage: form.mileage ? Number(form.mileage) : null,
        unit_consumption: form.unit_consumption ? Number(form.unit_consumption) : null,
      }
      const res = await fetch("/api/data/employee-commute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      })
      const json = (await res.json()) as ApiResponse<EmployeeCommute>
      if (!res.ok || json.code !== 200) {
        throw new Error(json.msg || "新增失败")
      }
      return json.data
    },
    onSuccess: async () => {
      toast.success("新增成功")
      setCreateOpen(false)
      setForm({ name: "", category: "", car_power_type: "1", mileage: "", unit_consumption: "" })
      await qc.invalidateQueries({ queryKey: ["data", "commute", "list"] })
    },
    onError: (e) => toast.error("新增失败", { description: e instanceof Error ? e.message : "请稍后重试" }),
  })

  const deleteMut = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/data/employee-commute/${id}`, { method: "DELETE" })
      if (!res.ok) {
        let msg = "删除失败"
        try {
          const json = (await res.json()) as ApiResponse<unknown>
          msg = json.msg || msg
        } catch {
          // 忽略解析错误
        }
        throw new Error(msg)
      }
    },
    onSuccess: async () => {
      toast.success("删除成功")
      await qc.invalidateQueries({ queryKey: ["data", "commute", "list"] })
    },
    onError: (e) => toast.error("删除失败", { description: e instanceof Error ? e.message : "请稍后重试" }),
  })

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="员工通勤" />

      <PageSection>
        <AdminPanel title="员工通勤列表">
          <div className="space-y-3">
            <AdminTableToolbar
              search={<Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索：姓名 / 通勤类别…" />}
              filters={
                <div className="w-[160px]">
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="通勤类别" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部类别</SelectItem>
                      <SelectItem value="自驾">自驾</SelectItem>
                      <SelectItem value="公交">公交</SelectItem>
                      <SelectItem value="班车">班车</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              }
              actions={
                <>
                  <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                    <DialogTrigger asChild>
                      <Button>新增</Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新增员工通勤记录</DialogTitle>
                      </DialogHeader>
                      <div className="grid gap-4">
                        <div className="grid gap-2">
                          <Label>员工姓名 / 标识</Label>
                          <Input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} placeholder="例如：张三 / 员工编号" />
                        </div>
                        <div className="grid gap-2">
                          <Label>通勤类别</Label>
                          <Input value={form.category} onChange={(e) => setForm((s) => ({ ...s, category: e.target.value }))} placeholder="例如：自驾 / 公交 / 班车" />
                        </div>
                        <div className="grid gap-2">
                          <Label>车辆动力类型</Label>
                          <Select value={form.car_power_type} onValueChange={(v) => setForm((s) => ({ ...s, car_power_type: v }))}>
                            <SelectTrigger>
                              <SelectValue placeholder="选择车辆动力类型" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="0">柴油</SelectItem>
                              <SelectItem value="1">汽油</SelectItem>
                              <SelectItem value="2">电力</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="grid gap-2">
                            <Label>平均单次里程（km）</Label>
                            <Input value={form.mileage} onChange={(e) => setForm((s) => ({ ...s, mileage: e.target.value }))} placeholder="可选，例如：15" />
                          </div>
                          <div className="grid gap-2">
                            <Label>单位油耗（L/100km）</Label>
                            <Input value={form.unit_consumption} onChange={(e) => setForm((s) => ({ ...s, unit_consumption: e.target.value }))} placeholder="可选，例如：8.5" />
                          </div>
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>
                          取消
                        </Button>
                        <Button onClick={() => createMut.mutate()} disabled={!form.name.trim() || createMut.isPending}>
                          保存
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>

                  <Button
                    variant="outline"
                    onClick={() => {
                      setKeyword("")
                      setCategory("all")
                    }}
                  >
                    重置
                  </Button>
                </>
              }
            >
              <Button variant="secondary" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
                查询
              </Button>
            </AdminTableToolbar>
            <AdminDataTable>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>姓名 / 标识</TableHead>
                    <TableHead>通勤类别</TableHead>
                    <TableHead>车辆动力类型</TableHead>
                    <TableHead className="text-right">平均单次里程 (km)</TableHead>
                    <TableHead className="text-right">单位油耗 (L/100km)</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {listQuery.isLoading && <AdminTableStateRow colSpan={6}>正在加载数据...</AdminTableStateRow>}
                  {listQuery.isError && (
                    <AdminTableStateRow colSpan={6} tone="danger">
                      加载失败，请检查后端接口。
                    </AdminTableStateRow>
                  )}
                  {!listQuery.isLoading && !listQuery.isError && items.length === 0 && <AdminTableStateRow colSpan={6}>暂无数据</AdminTableStateRow>}
                  {!listQuery.isLoading &&
                    !listQuery.isError &&
                    items.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>{r.name}</TableCell>
                        <TableCell>{r.category ?? "-"}</TableCell>
                        <TableCell>{r.car_power_type != null ? (carPowerTypeLabels[r.car_power_type] ?? r.car_power_type) : "-"}</TableCell>
                        <TableCell className="text-right">{r.mileage ?? "-"}</TableCell>
                        <TableCell className="text-right">{r.unit_consumption ?? "-"}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" onClick={() => deleteMut.mutate(r.id)} disabled={deleteMut.isPending}>
                            删除
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </AdminDataTable>
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
          </div>
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
