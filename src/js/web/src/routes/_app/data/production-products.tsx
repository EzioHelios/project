import { createFileRoute } from "@tanstack/react-router"
import { ProductionProductsPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/production-products")({
  component: ProductionProductsPage,
})
