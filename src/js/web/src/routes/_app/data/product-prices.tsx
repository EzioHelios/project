import { createFileRoute } from "@tanstack/react-router"
import { ProductPricesPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/product-prices")({
  component: ProductPricesPage,
})
