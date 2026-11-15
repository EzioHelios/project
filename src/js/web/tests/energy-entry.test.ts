import { describe, expect, it } from "vitest"
import { moneyLabel, numberLabel, parseEnergyCsv, periodLabel, sourceLabel, summarizeEnergy } from "@/components/energy/entry-utils"

describe("energy entry", () => {
  it("reads Chinese names, quoted separators, multiline remarks and real zero values", () => {
    const rows = parseEnergyCsv('\uFEFF区域,设备,能源种类,月份,能源用量,单位,备注\r\n涂装车间,烘干炉,天然气,2026-08,0,m3,"停机,检修\n无消耗"\r\n')
    expect(rows).toEqual([{ area_name: "涂装车间", equipment_name: "烘干炉", energy_type_name: "天然气", month: "2026-08", amount: "0", unit: "m3", remark: "停机,检修\n无消耗" }])
  })
  it("rejects malformed rows and files without consumption", () => {
    expect(() => parseEnergyCsv("月份,单位\n2026-08,kWh")).toThrow("能源用量")
    expect(() => parseEnergyCsv("能源用量,单位\n1,kWh,extra")).toThrow("第 2 行")
    expect(() => parseEnergyCsv('能源用量,单位\n1,"kWh')).toThrow("引号")
  })
  it("groups energy totals by both energy and unit without summing incompatible units", () => {
    const base = { period_start: "2026-08-01", period_end: "2026-08-31" }
    const totals = summarizeEnergy([
      { ...base, energy_type_code: "purchased_electricity", amount: 1200, unit: "kWh", cost_cny: 800 },
      { ...base, energy_type_code: "natural_gas", amount: 10, unit: "m3" },
      { ...base, energy_type_code: "natural_gas", amount: 0, unit: "m3", cost_cny: 0 },
      { ...base, energy_type_code: "purchased_electricity", amount: 1, unit: "MWh" },
    ])
    expect(totals).toHaveLength(3)
    expect(totals[1]).toMatchObject({ amount: 10, count: 2, cost_cny: 0 })
  })
  it("never exposes the projection source enum", () => {
    expect(sourceLabel("meter_projection")).toBe("自动采集")
    expect(sourceLabel("supplier_ledger")).toBe("供应商台账")
    expect(sourceLabel("woheng_enterprise_entry_v1")).toBe("企业月结台账")
    expect(sourceLabel("demo_ghg_activity_monthly")).toBe("历史非电月度台账")
    expect(sourceLabel("demo_ghg_activity_daily")).toBe("历史非电日度台账")
    expect(sourceLabel("unknown_system")).toBe("其他来源")
  })
})

it("formats useful display precision and distinguishes hourly intervals", () => {
  expect(numberLabel(1060974.477981)).toBe("1,060,974.478")
  expect(moneyLabel(3395118.329561)).toBe("3,395,118.33")
  const row = { energy_type_code: "natural_gas", amount: 0, unit: "m3", period_start: "2026-08-01T08:00:00", period_end: "2026-08-01T09:00:00", granularity: "hour" }
  expect(periodLabel(row)).toBe("2026-08-01 08:00—09:00")
  expect(periodLabel({ ...row, granularity: "month" })).toBe("2026-08")
})
