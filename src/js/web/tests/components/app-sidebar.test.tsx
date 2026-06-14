import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppSidebar } from "@/components/app-sidebar"
import { SidebarProvider } from "@/components/ui/sidebar"

const routeState = vi.hoisted(() => ({
  pathname: "/carbon/ledger",
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => <a href={to}>{children}</a>,
  useNavigate: () => vi.fn(),
  useRouterState: ({ select }: { select: (state: { location: { pathname: string } }) => string }) => select({ location: { pathname: routeState.pathname } }),
}))

vi.mock("@/components/nav-user", () => ({
  NavUser: () => null,
}))

vi.mock("@/components/theme-toggle", () => ({
  ThemeToggle: () => null,
}))

vi.mock("@/hooks/use-public-config", () => ({
  usePublicConfig: () => ({
    config: {
      displayName: "碳数据收集与管理系统",
      shortName: "CD",
    },
  }),
}))

function renderSidebar() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </QueryClientProvider>,
  )
}

describe("AppSidebar", () => {
  beforeEach(() => {
    routeState.pathname = "/carbon/ledger"
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  })

  it("shows a direct carbon emission ledger entry", () => {
    renderSidebar()

    const ledgerLink = screen.getByRole("link", { name: "碳排放台账" })

    expect(ledgerLink).toBeInTheDocument()
    expect(ledgerLink).toHaveAttribute("href", "/carbon/ledger")
  })

  it("shows carbon data entry links for Scope records", () => {
    routeState.pathname = "/carbon-mgmt/scope2-bill"

    renderSidebar()

    expect(screen.getByRole("link", { name: "碳数据填报" })).toHaveAttribute("href", "/carbon-mgmt/scope2-bill")
    expect(screen.getByRole("link", { name: "电力账单" })).toHaveAttribute("href", "/carbon-mgmt/scope2-bill")
    expect(screen.getByRole("link", { name: "固定源燃烧" })).toHaveAttribute("href", "/carbon-mgmt/scope1-stationary")
    expect(screen.getByRole("link", { name: "移动源燃烧" })).toHaveAttribute("href", "/carbon-mgmt/scope1-mobile")
    expect(screen.getByRole("link", { name: "废弃物处理" })).toHaveAttribute("href", "/carbon-mgmt/scope3-waste")
  })

  it("places carbon data entry after activity ledger", () => {
    renderSidebar()

    const activityLedgerLink = screen.getByRole("link", { name: "活动台账" })
    const carbonDataEntryLink = screen.getByRole("link", { name: "碳数据填报" })

    expect(activityLedgerLink.compareDocumentPosition(carbonDataEntryLink)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })
})
