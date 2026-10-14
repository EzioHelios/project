import { cleanup, fireEvent, render } from "@testing-library/react"
import type { ComponentType, ReactNode } from "react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { BigscreenCarbonResponse, BigscreenOperationsResponse } from "@/lib/bigscreen/types"
import { Route } from "@/routes/_app/bigscreen/carbon"

const state = vi.hoisted(() => ({
  carbon: { data: undefined as { data: BigscreenCarbonResponse } | undefined, isError: false, isFetching: false, refetch: vi.fn() },
  operations: { data: undefined as { data: BigscreenOperationsResponse } | undefined, isError: false, isFetching: true, refetch: vi.fn() },
}))
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options: unknown) => ({ options }),
  Link: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}))
vi.mock("@/lib/bigscreen/hooks", () => ({ useBigscreenCarbon: () => state.carbon, useBigscreenOverview: () => state.operations }))
vi.mock("@/components/bigscreen/charts", () => ({ BigscreenBarChart: () => <div>chart</div>, BigscreenSankeyChart: () => <div>carbon flow</div> }))
vi.mock("@/components/bigscreen/panel", () => ({ BigscreenPanel: ({ title, children }: { title: string; children: ReactNode }) => <section aria-label={title}>{children}</section> }))
vi.mock("@/components/bigscreen/operations", () => ({ EventList: () => <div>carbon alerts</div>, ScreenMetrics: () => <div>carbon totals</div>, ScreenFacts: () => <div>carbon facts</div> }))
vi.mock("@/components/bigscreen/warehouse-subjects", () => ({ CommuteEnergy: () => <div>commute energy</div> }))
const CarbonPage = Route.options.component as ComponentType

beforeEach(() => {
  state.carbon.data = { data: { hero_metrics: [], period_facts: [], activity_distribution: [], scope_distribution: [], source_ranking: [], area_ranking: [], factors: [], flow: { title: "碳流", unit: "kgCO2e", nodes: [], links: [] } } }
  state.carbon.isError = false
  state.carbon.isFetching = false
  state.operations.data = undefined
  state.operations.isError = false
  state.operations.isFetching = true
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

it("renders carbon results and flow while only the operations panels wait", () => {
  const view = render(<CarbonPage />)
  expect(view.getByText("carbon totals")).toBeTruthy()
  expect(view.getByText("carbon flow")).toBeTruthy()
  expect(view.getAllByRole("status")).toHaveLength(2)
  expect(view.container.querySelector('[data-screen-ready="false"]')).toBeTruthy()
  state.operations.data = { data: { presentation: { carbon_focus: "commute" } } as BigscreenOperationsResponse }
  state.operations.isFetching = false
  view.rerender(<CarbonPage />)
  expect(view.queryByRole("status")).toBeNull()
  expect(view.getByText("commute energy")).toBeTruthy()
  expect(view.getByText("carbon alerts")).toBeTruthy()
  expect(view.container.querySelector('[data-screen-ready="true"]')).toBeTruthy()
})

it("isolates an operations failure and retries only that request", () => {
  state.operations.isError = true
  state.operations.isFetching = false
  const view = render(<CarbonPage />)
  expect(view.getByText("carbon flow")).toBeTruthy()
  expect(view.getAllByRole("alert")).toHaveLength(2)
  fireEvent.click(view.getAllByRole("button", { name: "重新加载" })[0])
  expect(state.operations.refetch).toHaveBeenCalledOnce()
  expect(state.carbon.refetch).not.toHaveBeenCalled()
})

it("keeps the original non-commute panels after operations loads", () => {
  state.operations.data = { data: { presentation: {} } as BigscreenOperationsResponse }
  state.operations.isFetching = false
  const view = render(<CarbonPage />)
  expect(view.getByRole("region", { name: "排放分类构成" })).toBeTruthy()
  expect(view.getByRole("region", { name: "排放源清单" })).toBeTruthy()
  expect(view.queryByText("commute energy")).toBeNull()
})

it("does not show old carbon panels when the carbon query has no data", () => {
  state.carbon.data = undefined
  state.carbon.isError = true
  const view = render(<CarbonPage />)
  expect(view.queryByText("carbon totals")).toBeNull()
  fireEvent.click(view.getByRole("button", { name: "重新加载" }))
  expect(state.carbon.refetch).toHaveBeenCalledOnce()
  expect(state.operations.refetch).not.toHaveBeenCalled()
})
