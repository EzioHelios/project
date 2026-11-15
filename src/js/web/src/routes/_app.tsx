import { createFileRoute, redirect } from "@tanstack/react-router"
import { AppLayout } from "@/layouts/app-layout"
import { ensureAuthStoreHydrated, useAuthStore } from "@/lib/auth"
import { canAccessPath } from "@/lib/permissions"

export const Route = createFileRoute("/_app")({
  component: AppLayout,
  beforeLoad: async ({ location }) => {
    // Build redirect search params preserving current URL
    // Note: location.search is an object in TanStack Router, use href for full path
    const redirectSearch = { redirect: location.href }

    await ensureAuthStoreHydrated()

    // Server session cookies are authoritative after a hard refresh.
    try {
      await useAuthStore.getState().checkAuth()
    } catch {
      // If checkAuth fails, clear state and redirect
      useAuthStore.setState({
        isAuthenticated: false,
        access: null,
        user: null,
        currentTeam: null,
      })
      throw redirect({ to: "/login", search: redirectSearch })
    }

    const { isAuthenticated, access } = useAuthStore.getState()
    if (!isAuthenticated) {
      throw redirect({ to: "/login", search: redirectSearch })
    }
    if (!canAccessPath(access, location.pathname)) throw redirect({ to: "/forbidden" })
  },
})
