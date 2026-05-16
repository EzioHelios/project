import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { type ApiEnvelope, fetchCarbonApi, LedgerTable, MiniStatList, SectionHeader } from "@/components/carbon/analytics-panels"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type SectorRow = {
  id: number
  name?: string
  location?: string
  address?: string
}

type VideoRow = {
  id: number
  location?: string
  f_area?: string
  status?: number
  ip_address?: string
}

export const Route = createFileRoute("/_app/carbon/map")({
  component: MapPage,
})

function MapPage() {
  const sectorsQuery = useQuery<ApiEnvelope<SectorRow[]>>({
    queryKey: ["carbon", "map", "sectors"],
    queryFn: () => fetchCarbonApi<SectorRow[]>("/api/map/monitorSector/list"),
  })
  const videosQuery = useQuery<ApiEnvelope<VideoRow[]>>({
    queryKey: ["carbon", "map", "videos"],
    queryFn: () => fetchCarbonApi<VideoRow[]>("/api/map/videos"),
  })

  const sectors = sectorsQuery.data?.data ?? []
  const videos = videosQuery.data?.data ?? []
  const onlineVideos = videos.filter((item) => item.status === 0).length

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="监测地图" title="区域与视频点位" description="这页先做监测对象台账和弹窗入口校验，后续再接真实底图与热区渲染。" />

      <PageSection className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <MiniStatList
          title="点位概况"
          items={[
            { label: "监测区域", value: sectors.length },
            { label: "视频点位", value: videos.length },
            { label: "视频在线", value: `${onlineVideos}/${videos.length}` },
          ]}
        />
        <SectionHeader
          badge="弹窗接口"
          title="地图联动准备"
          description="区域弹窗使用 /api/map/popup/{area_id}，视频弹窗使用 /api/map/vedio/popup/{vid}。当前先确认对象台账和接口都在位。"
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-2">
        <LedgerTable
          title="监测区域"
          rows={sectors as unknown as Record<string, unknown>[]}
          columns={[
            { key: "id", label: "ID" },
            { key: "name", label: "名称" },
            { key: "location", label: "位置" },
            { key: "address", label: "地址" },
          ]}
        />
        <LedgerTable
          title="视频点位"
          rows={videos as unknown as Record<string, unknown>[]}
          columns={[
            { key: "id", label: "ID" },
            { key: "location", label: "位置" },
            { key: "f_area", label: "区域" },
            { key: "status", label: "状态" },
            { key: "ip_address", label: "IP" },
          ]}
        />
      </PageSection>
    </PageContainer>
  )
}
