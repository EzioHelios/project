import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppSidebar } from "@/components/app-sidebar"
import { SidebarProvider } from "@/components/ui/sidebar"

const routeState = vi.hoisted(() => ({
  pathname: "/carbon/organization/overview",
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
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
    routeState.pathname = "/carbon/organization/overview"
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

  it("shows the primary organization carbon entries", () => {
    renderSidebar()

    const overviewLink = screen.getByRole("link", { name: "组织碳总览" })
    const activityLedgerLink = screen.getByRole("link", { name: "活动数据总账" })
    const recordsLink = screen.getByRole("link", { name: "碳排放查询" })
    const flowLink = screen.getByRole("link", { name: "碳流分析" })
    const boundaryLink = screen.getByRole("link", { name: "核算边界" })

    expect(overviewLink).toHaveAttribute("href", "/carbon/organization/overview")
    expect(activityLedgerLink).toHaveAttribute("href", "/carbon-mgmt/activities")
    expect(recordsLink).toHaveAttribute("href", "/carbon/organization/records")
    expect(flowLink).toHaveAttribute("href", "/carbon/organization/flow")
    expect(boundaryLink).toHaveAttribute("href", "/carbon/organization/boundary")
  })

  it("shows carbon data entry links by ISO 14064-1 category", () => {
    routeState.pathname = "/carbon-mgmt/category/2.1"

    renderSidebar()

    const parentButton = screen.getByRole("button", { name: "碳数据填报" })
    const currentLeafLink = screen.getByRole("link", { name: "2.1 购入电力" })

    expect(parentButton).toHaveAttribute("data-active", "false")
    expect(parentButton).not.toHaveAttribute("aria-current")
    expect(currentLeafLink).toHaveAttribute("href", "/carbon-mgmt/category/2.1")
    expect(currentLeafLink).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "1.1 固定燃烧" })).toHaveAttribute("href", "/carbon-mgmt/category/1.1")
    expect(screen.getByRole("link", { name: "1.2 移动燃烧" })).toHaveAttribute("href", "/carbon-mgmt/category/1.2")
    expect(screen.getByRole("link", { name: "4.4 运营废物处置" })).toHaveAttribute("href", "/carbon-mgmt/category/4.4")
  })

  it("places carbon accounting after carbon data entry", () => {
    renderSidebar()

    const carbonDataEntryButton = screen.getByRole("button", { name: "碳数据填报" })
    const carbonAccountingButton = screen.getByRole("button", { name: "碳核算" })

    expect(carbonDataEntryButton.compareDocumentPosition(carbonAccountingButton)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it("separates carbon assets from carbon accounting", () => {
    routeState.pathname = "/carbon/assets/overview"
    renderSidebar()

    expect(screen.getByRole("button", { name: "碳资产" })).toHaveAttribute("data-context-active", "true")
    expect(screen.getByRole("link", { name: "资产台账" })).toHaveAttribute("href", "/carbon/assets/ledger")
    expect(screen.queryByRole("link", { name: "组织碳总览" })).not.toBeInTheDocument()
  })

  it("groups climate governance, budgets, and reduction work", () => {
    routeState.pathname = "/carbon/climate"
    renderSidebar()

    expect(screen.getByRole("button", { name: "气候与减碳" })).toHaveAttribute("data-context-active", "true")
    expect(screen.getByRole("link", { name: "气候目标与披露" })).toHaveAttribute("href", "/carbon/climate")
    expect(screen.getByRole("link", { name: "能碳预算" })).toHaveAttribute("href", "/energy/budget")
    expect(screen.getByRole("link", { name: "减排项目库" })).toHaveAttribute("href", "/carbon/reduction/projects")
  })
})
