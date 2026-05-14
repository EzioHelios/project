import { createFileRoute } from "@tanstack/react-router"
import { TasksPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/tasks/schedules")({
  component: SchedulesPage,
})

function SchedulesPage() {
  return <TasksPage mode="schedules" />
}
