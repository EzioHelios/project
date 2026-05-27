import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { SkeletonTable } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAdminAuditLogs } from "@/lib/api/hooks/admin"

const PAGE_SIZE = 50

export function AuditLogTable() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [action, setAction] = useState("")
  const [actorId, setActorId] = useState("")
  const [targetType, setTargetType] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")

  const { data, isLoading, isError } = useAdminAuditLogs({
    page,
    pageSize: PAGE_SIZE,
    search: search || undefined,
    action: action || undefined,
    actorId: actorId || undefined,
    targetType: targetType || undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
  })

  if (isLoading) {
    return <SkeletonTable rows={6} />
  }

  if (isError || !data) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>审计日志</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">审计日志加载失败，请稍后重试。</CardContent>
        </Card>
      )
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <Card>
      <CardHeader>
        <CardTitle>审计日志</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-6">
          <Input placeholder="搜索关键字" value={search} onChange={(event) => setSearch(event.target.value)} />
          <Input placeholder="动作" value={action} onChange={(event) => setAction(event.target.value)} />
          <Input placeholder="操作者 ID" value={actorId} onChange={(event) => setActorId(event.target.value)} />
          <Input placeholder="目标类型" value={targetType} onChange={(event) => setTargetType(event.target.value)} />
          <Input placeholder="创建于之后（ISO）" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <Input placeholder="创建于之前（ISO）" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>动作</TableHead>
              <TableHead>操作者</TableHead>
              <TableHead>目标</TableHead>
              <TableHead>创建时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  暂无审计记录。
                </TableCell>
              </TableRow>
            )}
            {data.items.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell>{entry.action}</TableCell>
                <TableCell className="text-muted-foreground">{entry.actorEmail ?? entry.actorId ?? "System"}</TableCell>
                <TableCell className="text-muted-foreground">{entry.targetLabel ?? entry.targetId ?? "-"}</TableCell>
                <TableCell className="text-muted-foreground">{new Date(entry.createdAt).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
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
      </CardContent>
    </Card>
  )
}
