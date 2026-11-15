import { describe, expect, it } from "vitest"
import { energyQuantityMetric } from "@/lib/energy-quantity-metric"

describe("original energy quantity KPI", () => {
  it("uses the whole summary even when the first page contains only electricity", () => {
    const firstPage = Array.from({ length: 20 }, () => ({ energy_type_code: "purchased_electricity", original_unit: "kWh" }))
    const summary = [
      { original_unit: "t", groups: [{ dimension: "energy_type", key: "purchased_steam" }] },
      { original_unit: "kWh", groups: [{ dimension: "energy_type", key: "purchased_electricity" }] },
    ]
    expect(energyQuantityMetric(259745.755022, 1040, firstPage, summary).value).toBe("按能源品种查看")
    expect(energyQuantityMetric(100, 1040, firstPage, summary.map((item) => ({ ...item, original_unit: "kWh" }))).value).toBe("按能源品种查看")
  })
  it("does not present the backend's mixed energy total as a quantity", () => {
    expect(energyQuantityMetric(1328256.987, 126, [
      { energy_type_code: "natural_gas", original_unit: "m3" },
      { energy_type_code: "purchased_electricity", original_unit: "kWh" },
      { energy_type_code: "purchased_steam", original_unit: "t" },
      { energy_type_code: "diesel", original_unit: "L" },
    ])).toEqual({ value: "按能源品种查看", unit: undefined })
  })
  it("also rejects different units for one energy, and different energies sharing a unit", () => {
    expect(energyQuantityMetric(1001, 2, [
      { energy_type_code: "purchased_electricity", original_unit: "kWh" },
      { energy_type_code: "purchased_electricity", original_unit: "MWh" },
    ]).unit).toBeUndefined()
    expect(energyQuantityMetric(100, 2, [
      { energy_type_code: "diesel", original_unit: "L" },
      { energy_type_code: "gasoline", original_unit: "L" },
    ]).value).toBe("按能源品种查看")
  })
  it("keeps a verified single energy quantity and unit, including zero", () => {
    const records = [{ energy_type_code: "natural_gas", original_unit: "m3" }]
    expect(energyQuantityMetric(18600, 1, records)).toEqual({ value: "18,600", unit: "m3" })
    expect(energyQuantityMetric(0, 1, records)).toEqual({ value: "0", unit: "m3" })
  })
  it("does not infer unit consistency from an incomplete page or missing unit", () => {
    expect(energyQuantityMetric(100, 21, [{ energy_type_code: "natural_gas", original_unit: "m3" }]).value).toBe("—")
    expect(energyQuantityMetric(100, 1, [{ energy_type_code: "natural_gas" }]).value).toBe("—")
    expect(energyQuantityMetric(null, 0, []).value).toBe("—")
  })
})
