import { createFileRoute } from "@tanstack/react-router"
import { TasksPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/tasks/crontab")({
  component: CrontabPage,
})

function CrontabPage() {
  return <TasksPage mode="crontab" />
}
