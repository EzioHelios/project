import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { DevicePointsWorkbenchPage, MonitorAreaWorkbenchPage } from "@/components/platform/master-data-workbench"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe("master data workbench", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("renders area tree and summary details", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes("/api/master-data/areas/tree")) {
        return new Response(
          JSON.stringify({
            code: 200,
            data: {
              items: [
                {
                  id: 1,
                  code: "ROOT",
                  name: "区域主数据",
                  is_enabled: false,
                  equipment_count: 0,
                  children: [{ id: 2, code: "WH-A", name: "A仓", area_type: "warehouse", equipment_count: 1, children: [] }],
                },
              ],
            },
          }),
        )
      }
      if (url.includes("/api/master-data/areas/2/summary")) {
        return new Response(
          JSON.stringify({
            code: 200,
            data: {
              area: { id: 2, code: "WH-A", name: "A仓", area_type: "warehouse", remark: "重点仓区", child_count: 0, equipment_count: 1 },
              children: [],
              devices: [{ id: 11, code: "DEV-11", name: "总表", status: 0, device_type: { id: 1, code: "meter", name: "电表" }, asset_code: "ASSET-11" }],
              stats: { device_total: 1, device_online: 1, device_fault: 0, child_area_total: 0 },
            },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    render(<MonitorAreaWorkbenchPage />, { wrapper: createWrapper() })

    expect(await screen.findByText("A仓")).toBeInTheDocument()
    expect(await screen.findByText("重点仓区")).toBeInTheDocument()
    expect(screen.getByText("总表")).toBeInTheDocument()
  })

  it("creates device and point through selectors instead of raw ids", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes("/api/master-data/areas/tree")) {
        return new Response(
          JSON.stringify({
            code: 200,
            data: {
              items: [
                {
                  id: 1,
                  code: "ROOT",
                  name: "区域主数据",
                  is_enabled: false,
                  children: [{ id: 2, code: "WH-A", name: "A仓", area_type: "warehouse", equipment_count: 1, children: [] }],
                },
              ],
            },
          }),
        )
      }
      if (url.includes("/api/master-data/device-types/tree")) {
        return new Response(
          JSON.stringify({
            code: 200,
            data: { items: [{ id: 1, code: "meter", name: "电表", children: [] }] },
          }),
        )
      }
      if (url.includes("/api/master-data/devices?")) {
        return new Response(
          JSON.stringify({
            items: [{ id: 11, code: "DEV-11", name: "总表", area_name: "A仓", device_type: { id: 1, code: "meter", name: "电表" }, point_count: 1, status: 0 }],
            total: 1,
            limit: 100,
            offset: 0,
          }),
        )
      }
      if (url.includes("/api/master-data/devices/11")) {
        return new Response(
          JSON.stringify({
            code: 200,
            data: {
              device: { id: 11, code: "DEV-11", name: "总表", area_name: "A仓", device_type: { id: 1, code: "meter", name: "电表" }, point_count: 1 },
              children: [],
              points: [{ id: 21, device_id: 11, point_code: "active_power", point_name: "有功功率", value_type: "float" }],
            },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    render(<DevicePointsWorkbenchPage />, { wrapper: createWrapper() })

    await screen.findByText("总表")
    expect(await screen.findByText("有功功率")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /新增设备/i }))
    expect(screen.getByText("所属区域")).toBeInTheDocument()
    expect(screen.getAllByText("设备类型").length).toBeGreaterThan(0)
    expect(screen.queryByText("区域ID")).not.toBeInTheDocument()
    expect(screen.queryByText("设备ID")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /取消/i }))
    await user.click(screen.getByRole("button", { name: /新增测点/i }))
    await waitFor(() => {
      expect(screen.getByText("测点编码")).toBeInTheDocument()
    })
    expect(screen.queryByText("设备ID")).not.toBeInTheDocument()
  })
})
