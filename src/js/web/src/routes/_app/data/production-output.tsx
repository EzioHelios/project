import { createFileRoute } from "@tanstack/react-router"
import { ProductionOutputPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/production-output")({
  component: ProductionOutputPage,
})
