import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, fireEvent, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { BigscreenTenantSwitcher } from "@/components/bigscreen/tenant-switcher"
import { useAuthStore } from "@/lib/auth"
import { useBigscreenOverview } from "@/lib/bigscreen/hooks"
import type { Team } from "@/lib/generated/api"

const mocks = vi.hoisted(() => ({ listTeams: vi.fn() }))
vi.mock("@/lib/generated/api", () => ({ listTeams: mocks.listTeams }))
const teams = [{ id: "team-a", name: "安方中心库" }, { id: "team-b", name: "祥泰仓库" }] as Team[]
function Overview() {
  const query = useBigscreenOverview()
  return <output data-testid="overview">{JSON.stringify(query.data?.data) ?? "加载中"}</output>
}
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><BigscreenTenantSwitcher /><Overview /></QueryClientProvider>)
}
beforeEach(() => {
  useAuthStore.persist.setOptions({ storage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } })
  useAuthStore.setState({ isAuthenticated: true, currentTeam: teams[0], teams: [] })
  mocks.listTeams.mockResolvedValue({ data: { items: teams } })
})
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })

describe("bigscreen tenant switching", () => {
  it("lists authorized teams and scopes both selection and requests to the selected team", async () => {
    const fetchMock = vi.fn(async (_url, init) => new Response(JSON.stringify({ data: { tenant: init.headers["X-Team-Id"] } })))
    vi.stubGlobal("fetch", fetchMock)
    const view = setup()
    await waitFor(() => expect(view.getAllByRole("option")).toHaveLength(2))
    await waitFor(() => expect(view.getByTestId("overview").textContent).toContain("team-a"))
    fireEvent.change(view.getByRole("combobox", { name: "切换租户" }), { target: { value: "team-b" } })
    expect(useAuthStore.getState().currentTeam?.id).toBe("team-b")
    await waitFor(() => expect(view.getByTestId("overview").textContent).toContain("team-b"))
    expect(fetchMock.mock.calls.at(-1)?.[1].headers["X-Team-Id"]).toBe("team-b")
  })

  it("cancels the previous request and ignores its late response after switching", async () => {
    let resolveA: (response: Response) => void = () => {}
    let oldSignal: AbortSignal | undefined
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      if (init.headers["X-Team-Id"] === "team-a") {
        oldSignal = init.signal
        return new Promise<Response>((resolve) => { resolveA = resolve })
      }
      return Promise.resolve(new Response(JSON.stringify({ data: { tenant: "team-b" } })))
    }))
    const view = setup()
    await waitFor(() => expect(view.getAllByRole("option")).toHaveLength(2))
    fireEvent.change(view.getByRole("combobox", { name: "切换租户" }), { target: { value: "team-b" } })
    await waitFor(() => expect(view.getByTestId("overview").textContent).toContain("team-b"))
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => resolveA(new Response(JSON.stringify({ data: { tenant: "team-a" } }))))
    expect(view.getByTestId("overview").textContent).toContain("team-b")
  })
})
