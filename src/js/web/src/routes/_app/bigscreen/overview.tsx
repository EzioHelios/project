import { createFileRoute } from "@tanstack/react-router"
import { WarehouseOperations } from "@/components/bigscreen/operations"

export const Route = createFileRoute("/_app/bigscreen/overview")({ component: () => <WarehouseOperations mode="overview" /> })
