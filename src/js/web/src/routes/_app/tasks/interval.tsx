import { createFileRoute } from "@tanstack/react-router"
import { TasksPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/tasks/interval")({
  component: IntervalPage,
})

function IntervalPage() {
  return <TasksPage mode="interval" />
}
