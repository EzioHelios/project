import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { ensureAuthStoreHydrated, useAuthStore } from "@/lib/auth"

export const Route = createFileRoute("/mobile")({
  component: MobileRoot,
  beforeLoad: async ({ location }) => {
    const redirectSearch = { redirect: location.href }
    await ensureAuthStoreHydrated()
    try {
      await useAuthStore.getState().checkAuth()
    } catch {
      useAuthStore.setState({
        isAuthenticated: false,
        user: null,
        currentTeam: null,
      })
      throw redirect({ to: "/login", search: redirectSearch })
    }
    if (!useAuthStore.getState().isAuthenticated) {
      throw redirect({ to: "/login", search: redirectSearch })
    }
    if (location.pathname === "/mobile") {
      throw redirect({ to: "/mobile/energy" })
    }
  },
})

function MobileRoot() {
  return <Outlet />
}
