import { cleanup, render } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { CommuteEnergy, DeviceBoard, DeviceReadings, EnergyCalendar, WarehouseLedger } from "@/components/bigscreen/warehouse-subjects"
import type { BigscreenOperationsResponse } from "@/lib/bigscreen/types"

vi.mock("@/components/bigscreen/charts", () => ({
  BigscreenBarChart: ({ items }: { items: unknown }) => <output>{JSON.stringify(items)}</output>,
  BigscreenLedgerChart: ({ points }: { points: unknown }) => <output>{JSON.stringify(points)}</output>,
}))
afterEach(cleanup)
it("groups devices by area identity and keeps measured zero separate from missing readings", () => {
  const devices = [
    {id: "missing", name: "未采样设备", area_id: "a", area: "同名区域", category: 0, register_value: null, last_reading: null},
    {id: "measured", name: "采样设备", area_id: "b", area: "同名区域", category: 0, register_value: 0, register_unit: "kWh", last_reading: "2026-10-13T10:00:00"},
  ] as BigscreenOperationsResponse["devices"]
  const select = vi.fn()
  const view = render(<DeviceBoard devices={devices} onSelect={select} />)
  expect(view.getAllByRole("heading")).toHaveLength(2)
  expect(view.getAllByRole("button")[0].textContent).toContain("采样设备")
  expect(view.getByText("暂无采样")).toBeTruthy()
  expect(view.getByText("0", {selector: "strong"})).toBeTruthy()
  view.getAllByRole("button")[0].click()
  expect(select).toHaveBeenCalledWith("measured")
})
it("only includes actual sampling records in the recent readings list", () => {
  const devices = [
    {id: "missing", name: "未采样设备", last_reading: null},
    {id: "measured", name: "采样设备", register_value: 0, last_reading: "2026-10-13T10:00:00"},
  ] as BigscreenOperationsResponse["devices"]
  const view = render(<DeviceReadings devices={devices} onSelect={vi.fn()} />)
  expect(view.queryByText("未采样设备")).toBeNull()
  expect(view.getAllByRole("button")).toHaveLength(1)
})
it("distinguishes missing calendar readings from measured zero and displays coverage", () => {
  const view = render(<EnergyCalendar items={[
    { id: "day", label: "当日已记录", value: null, unit: "kWh", start: "2026-10-02", end: "2026-10-02", recorded_days: 0, calendar_days: 1 },
    { id: "month", label: "当月已记录", value: 0, unit: "kWh", start: "2026-10-01", end: "2026-10-02", recorded_days: 1, calendar_days: 2 },
  ]} />)
  expect(view.getByText("0 / 1 天有记录")).toBeTruthy()
  expect(view.getByText("1 / 2 天有记录")).toBeTruthy()
  expect(view.getByText("—")).toBeTruthy()
  expect(view.getByText("0", { exact: true })).toBeTruthy()
})
it("renders aggregate commute energy without converting archives into emissions or employee totals", () => {
  const data = { commute_power: [{ name: "汽油", value: 37 }, { name: "电力", value: 7 }] } as BigscreenOperationsResponse
  const view = render(<CommuteEnergy data={data} />)
  expect(view.getByText("44")).toBeTruthy()
  expect(view.container.textContent).not.toContain("kgCO2")
})
it("keeps missing dates and amounts visible next to ledger trends", () => {
  const data = { business: [], ledger: { trend: [], coverage: [{ kind: "inbound", records: 3716, dated_records: 3461, undated_records: 255, missing_amount: 373 }] } } as unknown as BigscreenOperationsResponse
  const view = render(<WarehouseLedger data={data} />)
  expect(view.getByText("入库 3,716 条")).toBeTruthy()
  expect(view.getByText("缺日期 255 · 缺金额 373")).toBeTruthy()
})
