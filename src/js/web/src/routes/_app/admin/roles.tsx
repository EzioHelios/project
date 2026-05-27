import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { AdminNav } from "@/components/admin/admin-nav"
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

export const Route = createFileRoute("/_app/admin/roles")({
  component: AdminRolesPage,
})

function AdminRolesPage() {
  const { data: rolesData, isLoading: rolesLoading } = useAdminRoles()
  const { data: permissions = [], isLoading: permissionsLoading } = useAdminPermissions()
  const roles = rolesData?.items ?? []
  const [selectedRoleId, setSelectedRoleId] = useState<string>("")
  const rolePermissionsQuery = useAdminRolePermissions(selectedRoleId)
  const updateRolePermissions = useAdminUpdateRolePermissions(selectedRoleId)
  const [draftPermissionCodes, setDraftPermissionCodes] = useState<string[]>([])

  useEffect(() => {
    if (!selectedRoleId && roles.length > 0) {
      setSelectedRoleId(roles[0].id)
    }
  }, [roles, selectedRoleId])

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
        eyebrow="Administration"
        title="Roles and Permissions"
        description="Manage role-based permissions with explicit permission codes."
      />
      <AdminNav />

      <PageSection className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Roles</CardTitle>
            <CardDescription>Select a role to edit its permission set.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {rolesLoading ? (
              <p className="text-sm text-muted-foreground">Loading roles...</p>
            ) : roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No roles found.</p>
            ) : (
              roles.map((role) => {
                const active = role.id === selectedRoleId
                return (
                  <Button
                    key={role.id}
                    type="button"
                    variant={active ? "default" : "outline"}
                    className="w-full justify-between"
                    onClick={() => setSelectedRoleId(role.id)}
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
              <CardTitle className="text-base">{selectedRole?.name ?? "Select a role"}</CardTitle>
              {selectedRole ? <Badge variant="secondary">{selectedRole.slug}</Badge> : null}
            </div>
            <CardDescription>
              {permissionsLoading
                ? "Loading permissions..."
                : "Toggle permissions and save to update the role."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!hasSelection ? (
              <p className="text-sm text-muted-foreground">Choose a role from the list on the left.</p>
            ) : rolePermissionsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading role permissions...</p>
            ) : (
              <>
                {Object.entries(permissionsByModule).map(([module, modulePermissions]) => (
                  <div key={module} className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">{module}</h3>
                      <Badge variant="outline">{modulePermissions.length}</Badge>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {modulePermissions.map((permission) => {
                        const checked = draftPermissionCodes.includes(permission.code)
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
                              <span className="block text-sm font-medium">{permission.name}</span>
                              <span className="block text-xs text-muted-foreground">{permission.code}</span>
                              {permission.description ? (
                                <span className="block text-xs text-muted-foreground">{permission.description}</span>
                              ) : null}
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                ))}

                <div className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-4">
                  <Button type="button" onClick={handleSave} disabled={updateRolePermissions.isPending}>
                    {updateRolePermissions.isPending ? "Saving..." : "Save permissions"}
                  </Button>
                  <p className="text-sm text-muted-foreground">
                    {draftPermissionCodes.length} permission{draftPermissionCodes.length === 1 ? "" : "s"} selected
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
