import { createFileRoute, Link } from "@tanstack/react-router"
import { AdminPageHeader } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_app/forbidden")({ component: ForbiddenPage })

function ForbiddenPage() {
  return (
    <section className="p-6 space-y-4">
      <AdminPageHeader title="无权访问" />
      <p className="text-sm text-muted-foreground">当前账号没有此功能的访问权限。</p>
      <Button asChild variant="outline">
        <Link to="/home">返回工作台</Link>
      </Button>
    </section>
  )
}
