import { createFileRoute } from "@tanstack/react-router"
import { WarningRulesPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/alarm-rules")({
  component: WarningRulesPage,
})
