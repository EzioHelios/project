import { createFileRoute } from "@tanstack/react-router"
import { EventWorkbenchPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/alarm-events")({
  component: AlarmEventsPage,
})

function AlarmEventsPage() {
  return <EventWorkbenchPage title="预警事件" endpoint="/api/data/alarm-events" queryKey={["data", "alarm-events"]} />
}
