import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { z } from "zod"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import {
  useAdminPermissions,
  useAdminRolePermissions,
  useAdminRoles,
  useAdminUpdateRolePermissions,
} from "@/lib/api/hooks/admin"

const permissionLabels: Record<string, { name: string; description: string }> = {
  "admin.audit.view": { name: "查看审计日志", description: "查看系统审计与权限变更记录" },
  "admin.team.manage": { name: "团队管理", description: "创建和维护团队信息" },
  "auth.role.manage": { name: "角色管理", description: "创建、编辑角色并配置权限" },
  "auth.user.manage": { name: "用户管理", description: "创建和维护系统用户" },
  "carbon.alarm.handle": { name: "处理告警", description: "处置碳业务告警事件" },
  "carbon.audit.view": { name: "查看碳审计", description: "查看碳业务审计轨迹" },
  "carbon.config.manage": { name: "管理碳配置", description: "维护碳业务数据和配置" },
  "carbon.record.create": { name: "新增碳记录", description: "创建碳排放记录" },
  "carbon.record.delete": { name: "删除碳记录", description: "删除碳排放记录" },
  "carbon.record.submit": { name: "提交碳记录", description: "提交碳排放记录进入审核" },
  "carbon.record.update": { name: "更新碳记录", description: "更新碳排放记录" },
  "carbon.review.approve": { name: "审核通过", description: "批准已提交的碳记录" },
  "carbon.review.reject": { name: "审核驳回", description: "驳回已提交的碳记录" },
}

const moduleLabels: Record<string, string> = {
  admin: "系统管理",
  auth: "账号权限",
  carbon: "碳业务",
}

export const Route = createFileRoute("/_app/admin/roles")({
  validateSearch: (search) =>
    z
      .object({
        roleId: z.string().optional(),
      })
      .parse(search),
  component: AdminRolesPage,
})

function AdminRolesPage() {
  const search = Route.useSearch()
  const navigate = useNavigate()
  const { data: rolesData, isLoading: rolesLoading } = useAdminRoles()
  const { data: permissions = [], isLoading: permissionsLoading } = useAdminPermissions()
  const roles = rolesData?.items ?? []
  const [selectedRoleId, setSelectedRoleId] = useState<string>("")
  const rolePermissionsQuery = useAdminRolePermissions(selectedRoleId)
  const updateRolePermissions = useAdminUpdateRolePermissions(selectedRoleId)
  const [draftPermissionCodes, setDraftPermissionCodes] = useState<string[]>([])

  useEffect(() => {
    if (search.roleId && roles.some((role) => role.id === search.roleId)) {
      setSelectedRoleId(search.roleId)
      return
    }
    if (!selectedRoleId && roles.length > 0) {
      setSelectedRoleId(roles[0].id)
    }
  }, [roles, search.roleId, selectedRoleId])

  useEffect(() => {
    setDraftPermissionCodes(rolePermissionsQuery.data?.permissions.map((permission) => permission.code) ?? [])
  }, [rolePermissionsQuery.data?.permissions])

  const permissionsByModule = useMemo(() => {
    return permissions.reduce<Record<string, typeof permissions>>((acc, permission) => {
      const bucket = acc[permission.module] ?? []
      bucket.push(permission)
      acc[permission.module] = bucket
      return acc
    }, {})
  }, [permissions])

  const selectedRole = roles.find((role) => role.id === selectedRoleId)
  const hasSelection = Boolean(selectedRoleId)

  const togglePermission = (code: string) => {
    setDraftPermissionCodes((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    )
  }

  const handleSave = () => {
    if (!selectedRoleId) return
    updateRolePermissions.mutate(draftPermissionCodes)
  }

  return (
    <PageContainer className="flex-1 space-y-8">
      <PageHeader
        eyebrow="权限中心"
        title="权限配置"
        description="按角色配置权限码，并与角色管理页联动。"
      />
      <PermissionCenterNav />

      <PageSection className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">角色列表</CardTitle>
            <CardDescription>选择一个角色，编辑它的权限集合。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {rolesLoading ? (
              <p className="text-sm text-muted-foreground">正在加载角色...</p>
            ) : roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无角色。</p>
            ) : (
              roles.map((role) => {
                const active = role.id === selectedRoleId
                return (
                  <Button
                    key={role.id}
                    type="button"
                    variant={active ? "default" : "outline"}
                    className="w-full justify-between"
                    onClick={() => {
                      setSelectedRoleId(role.id)
                      void navigate({ to: "/admin/roles", search: { roleId: role.id }, replace: true })
                    }}
                  >
                    <span>{role.name}</span>
                    <Badge variant={active ? "secondary" : "outline"}>{role.slug}</Badge>
                  </Button>
                )
              })
            )}
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle className="text-base">{selectedRole?.name ?? "请选择角色"}</CardTitle>
              {selectedRole ? <Badge variant="secondary">{selectedRole.slug}</Badge> : null}
            </div>
            <CardDescription>
              {permissionsLoading
                ? "正在加载权限..."
                : "勾选权限后保存即可更新该角色。"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!hasSelection ? (
              <p className="text-sm text-muted-foreground">请先从左侧选择一个角色。</p>
            ) : rolePermissionsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">正在加载角色权限...</p>
            ) : (
              <>
                {Object.entries(permissionsByModule).map(([module, modulePermissions]) => (
                  <div key={module} className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium tracking-wide text-muted-foreground">{moduleLabels[module] ?? module}</h3>
                      <Badge variant="outline">{modulePermissions.length}</Badge>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {modulePermissions.map((permission) => {
                        const checked = draftPermissionCodes.includes(permission.code)
                        const permissionLabel = permissionLabels[permission.code] ?? {
                          name: permission.name,
                          description: permission.description ?? permission.code,
                        }
                        return (
                          <label
                            key={permission.id}
                            className="flex cursor-pointer items-start gap-3 rounded-lg border border-border/60 p-3 transition-colors hover:bg-muted/40"
                            >
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                              checked={checked}
                              onChange={() => togglePermission(permission.code)}
                            />
                            <span className="space-y-1">
                              <span className="block text-sm font-medium">{permissionLabel.name}</span>
                              <span className="block text-xs text-muted-foreground">{permission.code}</span>
                              <span className="block text-xs text-muted-foreground">{permissionLabel.description}</span>
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                ))}

                <div className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-4">
                  <Button type="button" onClick={handleSave} disabled={updateRolePermissions.isPending}>
                    {updateRolePermissions.isPending ? "保存中..." : "保存权限"}
                  </Button>
                  <p className="text-sm text-muted-foreground">
                    已选择 {draftPermissionCodes.length} 项权限
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
