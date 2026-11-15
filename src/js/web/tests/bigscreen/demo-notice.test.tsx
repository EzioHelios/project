import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, expect, it } from "vitest"
import { BigscreenDemoNotice } from "@/components/bigscreen/demo-notice"

beforeEach(() => sessionStorage.clear())

it("explains the demo once per browser session and account, and can be reopened", () => {
  const view = render(<BigscreenDemoNotice userId="customer-a" />)
  expect(screen.getByRole("dialog").textContent).toContain("虚拟基地和演示数据")
  fireEvent.click(screen.getByRole("button", { name: "了解，进入大屏" }))
  expect(screen.queryByRole("dialog")).toBeNull()
  view.unmount()
  const reopened = render(<BigscreenDemoNotice userId="customer-a" />)
  expect(screen.queryByRole("dialog")).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "定制演示", exact: true }))
  expect(screen.getByRole("dialog")).toBeTruthy()
  reopened.unmount()
  render(<BigscreenDemoNotice userId="customer-b" />)
  expect(screen.getByRole("dialog")).toBeTruthy()
})
