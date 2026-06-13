import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { AdminPageHeader } from "@/components/admin-ui"
import { type ApiEnvelope, DistributionChart, fetchCarbonApi, MiniStatList, TrendChart } from "@/components/carbon/analytics-panels"
import { DetailPanel, EmptyStateCard, FacetNavigation, statusBadge } from "@/components/carbon/energy-carbon-center"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type MonitorArea = {
  id: number
  name: string
  status: string
  health_ratio: number
  equipment_total: number
  equipment_online: number
  equipment_fault: number
  video_total: number
  video_online: number
  alert_unhandled: number
}

type MonitorDevice = {
  id: number
  name: string
  code?: string | null
  category?: number | null
  sector_id?: number | null
  sector_name?: string | null
  status?: number | null
  trip_state?: number | null
  location?: string | null
  protocol?: string | null
  alert_unhandled?: number
}

type DeviceDetail = {
  device: {
    id: number
    name: string
    code?: string | null
    category?: number | null
    status?: number | null
    trip_state?: number | null
    sector_name?: string | null
    location?: string | null
    protocol?: string | null
    install_time?: string | null
  }
  meter_samples: Record<string, unknown>[]
  alerts: Record<string, unknown>[]
}

type DeviceTimeseries = {
  series: {
    period: string
    energy_kwh: number
    carbon_co2e: number
  }[]
}

export const Route = createFileRoute("/_app/energy-carbon/monitor")({
  component: MonitorCenterPage,
})

function MonitorCenterPage() {
  const [selectedArea, setSelectedArea] = useState("all")
  const [status, setStatus] = useState("all")
  const [deviceKeyword, setDeviceKeyword] = useState("")
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null)

  const areasQuery = useQuery<ApiEnvelope<{ items: MonitorArea[] }>>({
    queryKey: ["energy-carbon", "monitor", "areas"],
    queryFn: () => fetchCarbonApi<{ items: MonitorArea[] }>("/api/energy-carbon/monitor/areas"),
  })
  const devicesQuery = useQuery<ApiEnvelope<{ items: MonitorDevice[] }>>({
    queryKey: ["energy-carbon", "monitor", "devices", selectedArea, status],
    queryFn: () => {
      const params = new URLSearchParams()
      if (selectedArea !== "all") params.set("sector_id", selectedArea)
      if (status !== "all") params.set("status", status)
      params.set("limit", "100")
      params.set("offset", "0")
      return fetchCarbonApi<{ items: MonitorDevice[] }>(`/api/energy-carbon/monitor/devices?${params.toString()}`)
    },
  })
  const detailQuery = useQuery<ApiEnvelope<DeviceDetail>>({
    queryKey: ["energy-carbon", "monitor", "device", selectedDeviceId],
    queryFn: () => fetchCarbonApi<DeviceDetail>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}`),
    enabled: selectedDeviceId !== null,
  })
  const timeseriesQuery = useQuery<ApiEnvelope<DeviceTimeseries>>({
    queryKey: ["energy-carbon", "monitor", "timeseries", selectedDeviceId],
    queryFn: () => fetchCarbonApi<DeviceTimeseries>(`/api/energy-carbon/monitor/devices/${selectedDeviceId}/timeseries`),
    enabled: selectedDeviceId !== null,
  })

  const areas = areasQuery.data?.data.items ?? []
  const devices = devicesQuery.data?.data.items ?? []
  const filteredDevices = useMemo(() => {
    const keyword = deviceKeyword.trim()
    if (!keyword) return devices
    return devices.filter((item) => (item.name || "").includes(keyword) || (item.code || "").includes(keyword))
  }, [deviceKeyword, devices])

  useEffect(() => {
    if (filteredDevices.length > 0 && !filteredDevices.some((item) => item.id === selectedDeviceId)) {
      setSelectedDeviceId(filteredDevices[0]?.id ?? null)
    }
    if (filteredDevices.length === 0) {
      setSelectedDeviceId(null)
    }
  }, [filteredDevices, selectedDeviceId])

  const detail = detailQuery.data?.data
  const onlineCount = devices.filter((item) => item.status === 0).length
  const faultCount = devices.filter((item) => item.status !== 0).length
  const areaDistribution = areas.slice(0, 8).map((item) => ({ name: item.name, value: item.alert_unhandled }))

  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="数据采集与监测" />

      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Select value={selectedArea} onValueChange={setSelectedArea}>
            <SelectTrigger>
              <SelectValue placeholder="区域筛选" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部区域</SelectItem>
              {areas.map((area) => (
                <SelectItem key={area.id} value={String(area.id)}>
                  {area.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger>
              <SelectValue placeholder="状态筛选" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="0">在线</SelectItem>
              <SelectItem value="1">故障 / 离线</SelectItem>
            </SelectContent>
          </Select>
          <div className="xl:col-span-2">
            <Input value={deviceKeyword} onChange={(event) => setDeviceKeyword(event.target.value)} placeholder="搜索设备名称或编码" />
          </div>
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[320px_340px_minmax(0,1fr)]">
        <MiniStatList
          title="运行概况"
          items={[
            { label: "区域总数", value: areas.length },
            { label: "在线设备", value: onlineCount },
            { label: "故障 / 离线", value: faultCount },
            { label: "高风险区域", value: areas.filter((item) => item.status !== "稳定").length },
            { label: "未处理异常", value: areas.reduce((sum, item) => sum + (item.alert_unhandled ?? 0), 0) },
          ]}
        />
        <DistributionChart title="区域风险分布" items={areaDistribution} unit="条" height={280} />
        <TrendChart
          title="设备近时段测点趋势"
          points={timeseriesQuery.data?.data.series ?? []}
          lines={[{ key: "energy_kwh", label: "设备测点", colorKey: "energy" }]}
          height={280}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[260px_minmax(0,0.95fr)_420px]">
        <FacetNavigation
          title="区域列表"
          items={[{ key: "all", label: "全部区域", count: areas.length }, ...areas.map((item) => ({ key: String(item.id), label: item.name, count: item.alert_unhandled }))]}
          selectedKey={selectedArea}
          onSelect={setSelectedArea}
        />

        <div className="rounded-lg border border-border/60 bg-card shadow-sm">
          <div className="border-b px-4 py-3 text-sm font-medium">设备工作列表</div>
          <div className="h-[560px] overflow-y-auto">
            <div className="space-y-2 p-3">
              {filteredDevices.length === 0 && <div className="text-sm text-muted-foreground">当前筛选条件下没有设备。</div>}
              {filteredDevices.map((device) => (
                <button
                  key={device.id}
                  type="button"
                  onClick={() => setSelectedDeviceId(device.id)}
                  className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                    selectedDeviceId === device.id ? "border-primary bg-primary/5" : "border-border/60 bg-card/60 hover:bg-accent/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{device.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {device.code || "未配置编码"} · {device.sector_name || "未分区"}
                      </div>
                    </div>
                    {statusBadge(device.status === 0 ? "稳定" : "高风险")}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span>{device.location || "未标注位置"}</span>
                    <span>{device.alert_unhandled ?? 0} 条未处理异常</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {detail ? (
          <div className="space-y-4">
            <DetailPanel
              title={detail.device.name}
              description="设备检查面板"
              items={[
                { label: "设备编码", value: detail.device.code },
                { label: "所属区域", value: detail.device.sector_name },
                { label: "位置", value: detail.device.location },
                { label: "协议", value: detail.device.protocol },
                { label: "安装时间", value: detail.device.install_time },
              ]}
            />
            <div className="rounded-lg border border-border/60 bg-card shadow-sm">
              <Tabs defaultValue="alerts">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="alerts">最近异常</TabsTrigger>
                  <TabsTrigger value="samples">最近测点</TabsTrigger>
                </TabsList>
                <TabsContent value="alerts" className="space-y-2 p-3">
                  {detail.alerts.slice(0, 6).map((item, index) => (
                    <div key={`${item.id ?? index}`} className="rounded-md border border-border/60 bg-card/60 px-3 py-2">
                      <div className="font-medium">{String(item.event_desc ?? "设备异常")}</div>
                      <div className="text-xs text-muted-foreground">{String(item.event_time ?? "-")}</div>
                    </div>
                  ))}
                </TabsContent>
                <TabsContent value="samples" className="space-y-2 p-3">
                  {detail.meter_samples.slice(0, 6).map((item, index) => (
                    <div key={`${item.id ?? index}`} className="rounded-md border border-border/60 bg-card/60 px-3 py-2">
                      <div className="font-medium">{String(item.ammeter_name ?? detail.device.name)}</div>
                      <div className="text-xs text-muted-foreground">{String(item.reading_time ?? "-")}</div>
                    </div>
                  ))}
                </TabsContent>
              </Tabs>
            </div>
          </div>
        ) : (
          <EmptyStateCard title="选择一台设备" description="左侧选中设备后，这里会展示基础信息、最近测点和异常记录，方便值班人员快速判断是否需要切换到专业台账页继续处理。" />
        )}
      </PageSection>
    </PageContainer>
  )
}
