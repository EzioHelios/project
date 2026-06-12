import { createFileRoute } from "@tanstack/react-router"
import { ProductResourceBindingsPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/product-resource-bindings")({
  component: ProductResourceBindingsPage,
})
