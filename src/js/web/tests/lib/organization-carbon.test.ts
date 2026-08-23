import { describe, expect, it } from "vitest"

import {
  equipmentOptionsForArea,
  organizationCarbonSearchSchema,
  toAnalyticsFilters,
} from "@/components/carbon/organization-inventory-common"

describe("organization carbon query state", () => {
  it("restores validated URL defaults and maps analytics filters", () => {
    const search = organizationCarbonSearchSchema.parse({ run: "RUN-1", scope2: "market", pageSize: "50", areaId: "12" })

    expect(search).toMatchObject({ run: "RUN-1", scope2: "market", page: 1, pageSize: 50, areaId: 12 })
    expect(toAnalyticsFilters(search)).toMatchObject({ runCode: "RUN-1", scope2Method: "market", areaId: 12 })
  })

  it("keeps equipment in the selected area and all descendants", () => {
    const areas = [
      { id: 1, code: "ROOT", name: "园区", level: 0 },
      { id: 2, code: "CHILD", name: "车间", level: 1, parentId: 1 },
      { id: 3, code: "OTHER", name: "其他区域", level: 0 },
    ]
    const equipment = [
      { id: 10, code: "M-ROOT", name: "园区总表", areaId: 1 },
      { id: 11, code: "M-CHILD", name: "车间电表", areaId: 2 },
      { id: 12, code: "M-OTHER", name: "其他电表", areaId: 3 },
    ]

    expect(equipmentOptionsForArea(areas, equipment, 1).map((item) => item.id)).toEqual([10, 11])
  })
})
