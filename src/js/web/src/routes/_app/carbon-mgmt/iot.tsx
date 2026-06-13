/**
 * IoT 时序数据 - 简单列表/筛选
 * API: /api/carbon/iot-telemetry
 */
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminPageHeader, AdminPanel, AdminTableStateRow, AdminTableToolbar } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type IotRow = {
  id: number
  site_id: string
  device_id: string
  reading_time: string
  active_power?: number | null
  reactive_power?: number | null
  voltage_a?: number | null
  current_a?: number | null
  total_energy?: number | null
  interval: string
}

type ApiResponse<T> = { code: number; msg: string; data: T }

export const Route = createFileRoute("/_app/carbon-mgmt/iot")({
  component: IotPage,
})

function IotPage() {
  const [siteId, setSiteId] = useState("")
  const [deviceId, setDeviceId] = useState("")
  const [limit, setLimit] = useState("200")

  const { data, isLoading, isError, refetch } = useQuery<ApiResponse<IotRow[]>>({
    queryKey: ["carbon-mgmt", "iot", siteId, deviceId, limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (siteId.trim()) params.set("site_id", siteId.trim())
      if (deviceId.trim()) params.set("device_id", deviceId.trim())
      if (limit.trim()) params.set("limit", limit.trim())
      const res = await fetch(`/api/carbon/iot-telemetry?${params.toString()}`)
      return res.json()
    },
  })

  const rows = useMemo(() => data?.data ?? [], [data?.data])

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="IoT时序数据" />
      <PageSection>
        <AdminPanel title="数据列表" contentClassName="space-y-3">
          <AdminTableToolbar
            search={
              <>
                <div className="w-[160px]">
                  <Input value={siteId} onChange={(e) => setSiteId(e.target.value)} placeholder="站点ID(site_id)" />
                </div>
                <div className="w-[180px]">
                  <Input value={deviceId} onChange={(e) => setDeviceId(e.target.value)} placeholder="设备ID(device_id)" />
                </div>
              </>
            }
            filters={
              <div className="w-[140px]">
                <Select value={limit} onValueChange={setLimit}>
                  <SelectTrigger>
                    <SelectValue placeholder="条数" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="100">最近 100 条</SelectItem>
                    <SelectItem value="200">最近 200 条</SelectItem>
                    <SelectItem value="500">最近 500 条</SelectItem>
                    <SelectItem value="1000">最近 1000 条</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            }
            actions={
              <Button type="button" variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
                查询
              </Button>
            }
          />
          {isLoading && <div className="text-sm text-muted-foreground">正在加载…</div>}
          {isError && <div className="text-sm text-destructive">加载失败，请检查后端接口。</div>}
          {!isLoading && !isError && (
            <AdminDataTable>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>站点ID</TableHead>
                    <TableHead>设备ID</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead className="text-right">有功功率</TableHead>
                    <TableHead className="text-right">总电量</TableHead>
                    <TableHead>周期</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.length === 0 && <AdminTableStateRow colSpan={6}>暂无数据</AdminTableStateRow>}
                  {rows.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.site_id}</TableCell>
                      <TableCell>{r.device_id}</TableCell>
                      <TableCell>{r.reading_time}</TableCell>
                      <TableCell className="text-right">{r.active_power ?? "-"}</TableCell>
                      <TableCell className="text-right">{r.total_energy ?? "-"}</TableCell>
                      <TableCell>{r.interval}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AdminDataTable>
          )}
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
