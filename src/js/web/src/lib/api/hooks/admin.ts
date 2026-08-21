import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getApiBaseUrl } from "@/lib/api-base-url"
import {
  type AdminListAuditLogsData,
  type AdminListTeamsData,
  type AdminListUsersData,
  type AdminTeamDetail,
  type AdminTeamSummary,
  type AdminUserDetail,
  type AdminUserSummary,
  type AuditLogEntry,
  adminDeleteTeam,
  adminDeleteUser,
  adminGetTeam,
  adminGetUser,
  adminListAuditLogs,
  adminListTeams,
  adminListUsers,
  adminUpdateTeam,
  adminUpdateUser,
  type DashboardStats,
  getDashboardStats,
  getRecentActivity,
  type ListRolesData,
  listRoles,
  type RecentActivity,
} from "@/lib/generated/api"

export interface AdminPermission {
  id: string
  code: string
  name: string
  description: string | null
  module: string
  createdAt: string
  updatedAt: string
}

export interface AdminRolePermissionsResponse {
  id: string
  slug: string
  name: string
  permissions: AdminPermission[]
  createdAt: string
  updatedAt: string
}

async function requestAdminJson<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getApiBaseUrl()
  const headers = new Headers(init?.headers)
  const csrfToken = window.__LITESTAR_CSRF__
  if (csrfToken) {
    headers.set("X-XSRF-TOKEN", csrfToken)
  }
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(`${apiUrl}${path}`, {
    credentials: "include",
    ...init,
    headers,
  })
  const text = await response.text()
  const raw = text ? JSON.parse(text) : {}
  if (!response.ok) {
    throw new Error(raw.detail || raw.message || raw.msg || `HTTP ${response.status}`)
  }
  return raw as T
}

export function useAdminDashboardStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () => {
      const response = await getDashboardStats()
      return response.data as DashboardStats
    },
  })
}

export function useAdminRecentActivity() {
  return useQuery({
    queryKey: ["admin", "activity"],
    queryFn: async () => {
      const response = await getRecentActivity()
      return response.data as RecentActivity
    },
  })
}

export function useAdminUsers(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: ["admin", "users", page, pageSize],
    queryFn: async () => {
      const query = {
        currentPage: page,
        pageSize,
      } as unknown as AdminListUsersData["query"]
      const response = await adminListUsers({ query })
      return response.data as { items: AdminUserSummary[]; total: number }
    },
  })
}

export function useAdminTeams(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: ["admin", "teams", page, pageSize],
    queryFn: async () => {
      const query = {
        currentPage: page,
        pageSize,
      } as unknown as AdminListTeamsData["query"]
      const response = await adminListTeams({ query })
      return response.data as { items: AdminTeamSummary[]; total: number }
    },
  })
}

export function useAdminRoles(page = 1, pageSize = 50) {
  return useQuery({
    queryKey: ["admin", "roles", page, pageSize],
    queryFn: async () => {
      const query = {
        currentPage: page,
        pageSize,
      } as unknown as ListRolesData["query"]
      const response = await listRoles({ query })
      return response.data as { items: Array<{ id: string; slug: string; name: string; createdAt: string; updatedAt: string }>; total: number }
    },
  })
}

export function useAdminPermissions() {
  return useQuery({
    queryKey: ["admin", "permissions"],
    queryFn: async () => requestAdminJson<AdminPermission[]>("/api/admin/permissions"),
  })
}

export function useAdminRolePermissions(roleId: string) {
  return useQuery({
    queryKey: ["admin", "role-permissions", roleId],
    queryFn: async () => requestAdminJson<AdminRolePermissionsResponse>(`/api/admin/roles/${roleId}/permissions`),
    enabled: !!roleId,
  })
}

export function useAdminUpdateRolePermissions(roleId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (permissionCodes: string[]) => {
      return requestAdminJson<AdminRolePermissionsResponse>(`/api/admin/roles/${roleId}/permissions`, {
        method: "PUT",
        body: JSON.stringify({ permissionCodes }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "role-permissions", roleId] })
      queryClient.invalidateQueries({ queryKey: ["admin", "roles"] })
      toast.success("Role permissions updated")
    },
    onError: (error) => {
      toast.error("Unable to update role permissions", {
        description: error instanceof Error ? error.message : "Try again later",
      })
    },
  })
}

export function useAdminAuditLogs(params: {
  page?: number
  pageSize?: number
  search?: string
  action?: string
  actorId?: string
  targetType?: string
  startDate?: string
  endDate?: string
}) {
  const { page = 1, pageSize = 50, search, action, actorId, targetType, startDate, endDate } = params
  return useQuery({
    queryKey: ["admin", "audit", page, pageSize, search, action, actorId, targetType, startDate, endDate],
    queryFn: async () => {
      const query = {
        currentPage: page,
        pageSize,
        searchString: search,
        searchIgnoreCase: search ? true : undefined,
        actionIn: action ? [action] : undefined,
        actorIdIn: actorId ? [actorId] : undefined,
        targetTypeIn: targetType ? [targetType] : undefined,
        createdAfter: startDate,
        createdBefore: endDate,
      } as unknown as AdminListAuditLogsData["query"]
      const response = await adminListAuditLogs({
        query,
      })
      return response.data as { items: AuditLogEntry[]; total: number }
    },
  })
}

export function useAdminUser(userId: string) {
  return useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: async () => {
      const response = await adminGetUser({ path: { user_id: userId } })
      return response.data as AdminUserDetail
    },
    enabled: !!userId,
  })
}

export function useAdminTeam(teamId: string) {
  return useQuery({
    queryKey: ["admin", "team", teamId],
    queryFn: async () => {
      const response = await adminGetTeam({ path: { team_id: teamId } })
      return response.data as AdminTeamDetail
    },
    enabled: !!teamId,
  })
}

export function useAdminUpdateUser(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const response = await adminUpdateUser({
        path: { user_id: userId },
        body: payload,
      })
      return response.data as AdminUserDetail
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] })
      queryClient.invalidateQueries({ queryKey: ["admin", "user", userId] })
      toast.success("User updated")
    },
    onError: (error) => {
      toast.error("Unable to update user", {
        description: error instanceof Error ? error.message : "Try again later",
      })
    },
  })
}

export function useAdminUpdateTeam(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const response = await adminUpdateTeam({
        path: { team_id: teamId },
        body: payload,
      })
      return response.data as AdminTeamDetail
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "teams"] })
      queryClient.invalidateQueries({ queryKey: ["admin", "team", teamId] })
      toast.success("Team updated")
    },
    onError: (error) => {
      toast.error("Unable to update team", {
        description: error instanceof Error ? error.message : "Try again later",
      })
    },
  })
}

export function useAdminDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      const response = await adminDeleteUser({ path: { user_id: userId } })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] })
      toast.success("User deleted")
    },
    onError: (error) => {
      toast.error("Unable to delete user", {
        description: error instanceof Error ? error.message : "Try again later",
      })
    },
  })
}

export function useAdminDeleteTeam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (teamId: string) => {
      const response = await adminDeleteTeam({ path: { team_id: teamId } })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "teams"] })
      toast.success("Team deleted")
    },
    onError: (error) => {
      toast.error("Unable to delete team", {
        description: error instanceof Error ? error.message : "Try again later",
      })
    },
  })
}
