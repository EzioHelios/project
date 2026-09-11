import { fireEvent, render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { BigscreenDataState } from "@/components/bigscreen/data-state"
import { BigscreenMetricCard } from "@/components/bigscreen/panel"

vi.mock("@/components/bigscreen/motion", () => ({ BigscreenCountUp: ({ value }: { value: number }) => <span>{value}</span> }))

describe("bigscreen data availability", () => {
  it("distinguishes a missing result from a measured zero", () => {
    const view = render(<BigscreenMetricCard metric={{ label: "用电", value: null, emphasis: "暂无电量汇总" }} />)
    expect(view.getByText("—")).toBeTruthy()
    expect(view.getByText("暂无电量汇总")).toBeTruthy()
    view.rerender(<BigscreenMetricCard metric={{ label: "用电", value: 0, emphasis: "账期 2026-06" }} />)
    expect(view.getByText("0")).toBeTruthy()
    expect(view.getByText("账期 2026-06")).toBeTruthy()
    expect(view.queryByText("—")).toBeNull()
  })

  it("shows a retryable error instead of zero KPIs", () => {
    const retry = vi.fn()
    const view = render(<BigscreenDataState failed retry={retry} />)
    expect(view.getByRole("alert").textContent).toContain("数据加载失败")
    fireEvent.click(view.getByRole("button", { name: "重新加载" }))
    expect(retry).toHaveBeenCalledOnce()
  })
})
