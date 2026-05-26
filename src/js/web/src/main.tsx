import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import React from "react"
import ReactDOM from "react-dom/client"
import { ErrorBoundary } from "@/components/error-boundary"
import { usePublicConfig } from "@/hooks/use-public-config"
import { setAccessToken, useAuthStore } from "@/lib/auth"
import { client } from "@/lib/generated/api/client.gen"
import { ThemeProvider } from "@/lib/theme-context"

// Import the generated route tree
import { routeTree } from "./routeTree.gen"

import "./styles.css"
import reportWebVitals from "./reportWebVitals.ts"

// Extend Window type for CSRF token injected by litestar-vite
declare global {
  interface Window {
    __LITESTAR_CSRF__?: string
  }
}

const queryClient = new QueryClient()

const apiUrl = import.meta.env.VITE_API_URL ?? ""
const rawFetch: typeof fetch = (...args) => globalThis.fetch(...args)
const publicAuthPaths = ["/login", "/signup", "/forgot-password", "/reset-password"]

const isPublicAuthPath = (pathname: string) => publicAuthPaths.some((path) => pathname.startsWith(path))

const shouldSkipRefresh = (requestUrl: string) => requestUrl.includes("/api/access/refresh") || requestUrl.includes("/api/access/login")

client.setConfig({
  baseUrl: apiUrl,
  credentials: "include",
  fetch: async (input, init) => {
    const request = input instanceof Request ? input : new Request(input, init)
    const retryRequest = request.clone()
    let response = await rawFetch(request)

    if (response.status !== 401 || typeof window === "undefined" || shouldSkipRefresh(request.url) || isPublicAuthPath(window.location.pathname)) {
      return response
    }

    try {
      const accessToken = await refreshAccessToken()
      const retryHeaders = new Headers(retryRequest.headers)
      retryHeaders.set("Authorization", `Bearer ${accessToken}`)
      response = await rawFetch(new Request(retryRequest, { headers: retryHeaders }))
      return response
    } catch {
      clearClientAuthState()
      queryClient.clear()
      if (window.location.pathname !== "/login") {
        window.location.href = "/login"
      }
      return response
    }
  },
  auth: () => {
    if (typeof window === "undefined") {
      return undefined
    }
    return window.localStorage.getItem("access_token") ?? undefined
  },
})

// Add CSRF token to all non-GET requests
// litestar-vite injects the token into window.__LITESTAR_CSRF__
client.interceptors.request.use((request, _options) => {
  const method = request.method?.toUpperCase()
  // Only add CSRF header for unsafe methods (non-GET/HEAD/OPTIONS)
  if (method && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = window.__LITESTAR_CSRF__
    if (csrfToken) {
      request.headers.set("X-XSRF-TOKEN", csrfToken)
    }
  }
  return request
})

// Silent token refresh state
let refreshPromise: Promise<string> | null = null

const clearClientAuthState = () => {
  setAccessToken(null)
  useAuthStore.setState({
    user: null,
    currentTeam: null,
    teams: [],
    isLoading: false,
    isAuthenticated: false,
  })
}

const refreshAccessToken = async (): Promise<string> => {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const headers = new Headers()
      const csrfToken = window.__LITESTAR_CSRF__
      if (csrfToken) {
        headers.set("X-XSRF-TOKEN", csrfToken)
      }

      const refreshResponse = await rawFetch(new URL("/api/access/refresh", window.location.origin), {
        method: "POST",
        credentials: "include",
        headers,
      })

      if (!refreshResponse.ok) {
        throw new Error(`Token refresh failed with status ${refreshResponse.status}`)
      }

      const payload = (await refreshResponse.json()) as { access_token?: string }
      if (!payload.access_token) {
        throw new Error("Refresh response did not include an access token")
      }

      setAccessToken(payload.access_token)
      return payload.access_token
    })().finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

// Create the router using the generated route tree
const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
  defaultPreload: "intent",
  scrollRestoration: true,
  defaultStructuralSharing: true,
  defaultPreloadStaleTime: 0,
  defaultErrorComponent: ErrorBoundary,
})

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

function DocumentTitle() {
  const { config } = usePublicConfig()

  React.useEffect(() => {
    document.title = config.displayName
  }, [config.displayName])

  return null
}

// Render the app
const rootElement = document.getElementById("root")
if (rootElement && !rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  root.render(
    <React.StrictMode>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <DocumentTitle />
          <RouterProvider router={router} />
          <ReactQueryDevtools />
        </QueryClientProvider>
      </ThemeProvider>
    </React.StrictMode>,
  )
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals()
