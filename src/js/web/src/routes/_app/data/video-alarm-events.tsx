import { createFileRoute } from "@tanstack/react-router"
import { EventWorkbenchPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/video-alarm-events")({
  component: VideoAlarmEventsPage,
})

function VideoAlarmEventsPage() {
  return <EventWorkbenchPage title="视频监控预警事件" endpoint="/api/data/video-alarm-events" queryKey={["data", "video-alarm-events"]} video />
}
