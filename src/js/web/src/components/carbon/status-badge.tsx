import { Badge } from "@/components/ui/badge"

export type CarbonStatus = "draft" | "pending" | "approved" | "rejected" | "rebuilt" | "pending_revision" | "locked" | "archived" | string | undefined

export function CarbonStatusBadge({ status }: { status: CarbonStatus }) {
  if (status === "locked") return <Badge>已锁定</Badge>
  if (status === "approved") return <Badge>已通过</Badge>
  if (status === "pending") return <Badge variant="secondary">待审核</Badge>
  if (status === "pending_revision") return <Badge variant="secondary">修订待审批</Badge>
  if (status === "rebuilt") return <Badge variant="secondary">已重建</Badge>
  if (status === "rejected") return <Badge variant="destructive">已驳回</Badge>
  if (status === "archived") return <Badge variant="outline">已归档</Badge>
  return <Badge variant="outline">草稿</Badge>
}
