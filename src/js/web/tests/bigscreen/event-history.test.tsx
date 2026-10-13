import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, fireEvent, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { EventList } from "@/components/bigscreen/operations"
import { useAuthStore } from "@/lib/auth"
import type { BigscreenEventSummary } from "@/lib/bigscreen/types"
import type { Team } from "@/lib/generated/api"

vi.mock("@/components/bigscreen/charts", () => ({ BigscreenBarChart: () => <div>统计图</div>, BigscreenLineChart: () => null }))
const events: BigscreenEventSummary = { total: 11, page: 1, page_size: 10, start: null, end: null, distribution: [], region_distribution: [{ name: "堆场", value: 11 }], status_distribution: [], recent: [] }
beforeEach(() => {
  useAuthStore.persist.setOptions({ storage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } })
  useAuthStore.setState({ currentTeam: { id: "a" } as Team })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it("paginates, resets page on filters, scopes requests and closes history when tenant changes", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ data: { ...events, page: Number(new URL(url, "http://localhost").searchParams.get("page")) } })))
  vi.stubGlobal("fetch", fetcher)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  const view = render(<QueryClientProvider client={client}><EventList events={events} category="video" /></QueryClientProvider>)
  fireEvent.click(view.getByText("全部记录 · 11 条"))
  await waitFor(() => expect(view.getByText("共 11 条 · 第 1 / 2 页")).toBeTruthy())
  fireEvent.click(view.getByRole("button", { name: "下一页" }))
  await waitFor(() => expect(view.getByText("共 11 条 · 第 2 / 2 页")).toBeTruthy())
  fireEvent.change(view.getByLabelText("预警区域"), { target: { value: "堆场" } })
  await waitFor(() => expect(view.getByText("共 11 条 · 第 1 / 2 页")).toBeTruthy())
  const url = new URL(fetcher.mock.calls.at(-1)![0], "http://localhost")
  expect(url.searchParams.get("area")).toBe("堆场")
  expect(url.searchParams.get("category")).toBe("video")
  fireEvent.change(view.getByLabelText("预警开始日期"), { target: { value: "2025-12-01" } })
  await waitFor(() => expect(fetcher.mock.calls.at(-1)![0]).toContain("start=2025-12-01"))
  fireEvent.click(view.getByText("重置"))
  await waitFor(() => expect(view.getByLabelText("预警开始日期").getAttribute("value")).toBe(""))
  await act(async () => useAuthStore.setState({ currentTeam: { id: "b" } as Team }))
  expect(view.queryByRole("dialog")).toBeNull()
})
