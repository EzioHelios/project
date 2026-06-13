import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { AdminDataTable, AdminPanel, AdminTableStateRow, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { SkeletonTable } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAdminUsers } from "@/lib/api/hooks/admin"

const PAGE_SIZE = 25

export function UserTable() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useAdminUsers(page, PAGE_SIZE)

  if (isLoading) {
    return <SkeletonTable rows={6} />
  }

  if (isError || !data) {
    return (
      <AdminPanel title="用户列表">
        <div className="text-muted-foreground text-sm">用户数据加载失败，请稍后重试。</div>
      </AdminPanel>
    )
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <AdminPanel title="用户列表" contentClassName="space-y-4">
      <AdminDataTable className="rounded-none border-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>姓名</TableHead>
              <TableHead>邮箱</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>角色</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && <AdminTableStateRow colSpan={5}>暂无用户</AdminTableStateRow>}
            {data.items.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.name ?? user.email}</TableCell>
                <TableCell className="text-muted-foreground">{user.email}</TableCell>
                <TableCell>
                  <StatusBadge status={user.isActive ? "approved" : "inactive"} label={user.isActive ? "启用" : "停用"} />
                </TableCell>
                <TableCell>{user.isSuperuser ? "超级管理员" : "普通用户"}</TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="outline" size="sm">
                    <Link to="/admin/users/$userId" params={{ userId: user.id }}>
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
