import { describe, expect, it } from "vitest"
import { blocksWalkAt } from "@/lib/bigscreen/campus/collision"
import type { PixelPoint } from "@/lib/bigscreen/campus/types"

describe("warehouse walking clearance", () => {
  const polygon: PixelPoint[] = [[518, 681], [911, 630], [925, 720], [529, 759]]
  const clearance = 0.7 / 0.5041559328825945
  it("keeps the real diagonal aisle open inside the footprint's bounding box", () => {
    expect(blocksWalkAt([798, 637], polygon, clearance)).toBe(false)
    expect(blocksWalkAt([798, 657], polygon, clearance)).toBe(true)
  })
  it("rejects walls, corners, and interiors regardless of footprint winding", () => {
    for (const points of [polygon, [...polygon].reverse()]) {
      expect(blocksWalkAt([518, 681], points, clearance)).toBe(true)
      expect(blocksWalkAt([517, 681], points, clearance)).toBe(true)
      expect(blocksWalkAt([700, 710], points, clearance)).toBe(true)
      expect(blocksWalkAt([500, 680], points, clearance)).toBe(false)
    }
  })
})
