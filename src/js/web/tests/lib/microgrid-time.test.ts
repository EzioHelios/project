import { describe, expect, it } from "vitest"

import { formatMicrogridDateTime, formatMicrogridTime } from "@/lib/microgrid-time"

describe("microgrid site time formatting", () => {
  it("converts UTC timestamps to Asia/Shanghai", () => {
    expect(formatMicrogridDateTime("2026-08-12T21:45:00+00:00")).toBe("08-13 05:45")
    expect(formatMicrogridTime("2026-08-12T10:45:00+00:00")).toBe("18:45")
  })

  it("keeps invalid values inspectable", () => {
    expect(formatMicrogridDateTime("not-a-time")).toBe("not-a-time")
    expect(formatMicrogridDateTime(undefined)).toBe("-")
  })
})
