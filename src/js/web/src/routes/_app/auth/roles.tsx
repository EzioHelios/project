import { createFileRoute } from "@tanstack/react-router"
import { RolesPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/auth/roles")({
  component: RolesPage,
})
