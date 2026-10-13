import { createFileRoute } from "@tanstack/react-router"
import { WarehouseOperations } from "@/components/bigscreen/operations"

export const Route = createFileRoute("/_app/bigscreen/monitor")({ component: () => <WarehouseOperations mode="monitor" /> })
