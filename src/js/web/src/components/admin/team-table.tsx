import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { AdminDataTable, AdminPanel, AdminTableStateRow, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { SkeletonTable } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAdminTeams } from "@/lib/api/hooks/admin"

const PAGE_SIZE = 25

export function TeamTable() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useAdminTeams(page, PAGE_SIZE)

  if (isLoading) {
    return <SkeletonTable rows={6} />
  }

  if (isError || !data) {
    return (
      <AdminPanel title="团队列表">
        <div className="text-muted-foreground text-sm">团队数据加载失败，请稍后重试。</div>
      </AdminPanel>
    )
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <AdminPanel title="团队列表" contentClassName="space-y-4">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>标识</TableHead>
              <TableHead>成员数</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && <AdminTableStateRow colSpan={5}>暂无团队</AdminTableStateRow>}
            {data.items.map((team) => (
              <TableRow key={team.id}>
                <TableCell>{team.name}</TableCell>
                <TableCell className="text-muted-foreground">{team.slug}</TableCell>
                <TableCell>{team.memberCount ?? 0}</TableCell>
                <TableCell>
                  <StatusBadge status={team.isActive ? "approved" : "inactive"} label={team.isActive ? "启用" : "停用"} />
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="outline" size="sm">
                    <Link to="/admin/teams/$teamId" params={{ teamId: team.id }}>
                      查看
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </AdminDataTable>
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          第 {page} 页 / 共 {totalPages} 页
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            上一页
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
            下一页
          </Button>
        </div>
      </div>
    </AdminPanel>
  )
}
