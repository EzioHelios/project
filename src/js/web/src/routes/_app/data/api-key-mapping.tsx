import { createFileRoute } from "@tanstack/react-router"
import { ApiKeyMappingPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/api-key-mapping")({
  component: ApiKeyMappingPage,
})
