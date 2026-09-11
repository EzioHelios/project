import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Cartesian3, Cartographic, Math as CesiumMath } from "cesium"
import { describe, expect, it } from "vitest"
import { campusModelMatrix, campusPointToFixed } from "@/lib/bigscreen/campus/georegistration"
import type { CampusGeoregistration } from "@/lib/bigscreen/campus/types"

describe("geographic campus placement", () => {
  it("maps glTF east/up/south into the Earth's east/north/up frame", () => {
    const matrix = campusModelMatrix({ origin: [0, 0], scale: [1, 1, 1], ellipsoidHeight: 0 } as CampusGeoregistration)
    expect(campusPointToFixed(matrix, 0, 0, 0)).toEqual(new Cartesian3(6378137, 0, 0))
    expect(campusPointToFixed(matrix, 10, 2, 3)).toEqual(new Cartesian3(6378139, 10, -3))
  })

  for (const pack of ["anfang-central-geo-v1", "xiangtai-warehouse-geo-v1"]) {
    it(`${pack} retains the generated source footprint coordinates and metre scale`, () => {
      const base = resolve("../../py/app/assets/scenes/packs", pack)
      const scene = JSON.parse(readFileSync(resolve(base, "scene.json"), "utf8"))
      const report = JSON.parse(readFileSync(resolve(base, "registration-report.json"), "utf8"))
      const matrix = campusModelMatrix(scene.georegistration)
      expect(report.controlPoints.length).toBeGreaterThanOrEqual(8)
      for (const point of report.controlPoints) {
        const [u, v] = point.pixel
        const fixed = campusPointToFixed(matrix, (u - scene.world.originPixel[0]) * scene.world.metresPerPixel, 0, (v - scene.world.originPixel[1]) * scene.world.metresPerPixel)
        const expected = Cartesian3.fromDegrees(...point.longitudeLatitude, scene.georegistration.ellipsoidHeight)
        expect(Cartesian3.distance(fixed, expected)).toBeLessThan(0.02)
      }
      const origin = Cartographic.fromCartesian(campusPointToFixed(matrix, 0, 0, 0))
      expect(CesiumMath.toDegrees(origin.longitude)).toBeCloseTo(scene.world.origin[0], 7)
      expect(CesiumMath.toDegrees(origin.latitude)).toBeCloseTo(scene.world.origin[1], 7)
    })
  }
})
