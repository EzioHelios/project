import { Cartesian3, Matrix4, Transforms } from "cesium"
import { describe, expect, it } from "vitest"
import { campusModelMatrix, campusOffsetToEnu, campusPointToFixed } from "./georegistration"
import type { CampusGeoregistration } from "./types"

const registration = (headingDegrees: number): CampusGeoregistration => ({
  version: 2,
  crs: "EPSG:4326",
  origin: [120, 32],
  headingDegrees,
  scale: [1, 1, 1],
  ellipsoidHeight: 0,
  heightStatus: "estimated",
  upAxis: "Y",
  forwardAxis: "X",
  terrain: "ellipsoid",
  imagery: {
    url: "https://example.test/{z}/{y}/{x}",
    credit: "test",
    maximumLevel: 18,
  },
})

describe("campusModelMatrix", () => {
  it("rotates the model and interactive points around the local up axis", () => {
    const config = registration(90)
    const fixed = campusPointToFixed(campusModelMatrix(config), 10, 0, 0)
    const anchor = Cartesian3.fromDegrees(...config.origin, config.ellipsoidHeight)
    const inverseFrame = Matrix4.inverseTransformation(Transforms.eastNorthUpToFixedFrame(anchor), new Matrix4())
    const local = Matrix4.multiplyByPoint(inverseFrame, fixed, new Cartesian3())

    expect(local.x).toBeCloseTo(0, 6)
    expect(local.y).toBeCloseTo(10, 6)
    expect(local.z).toBeCloseTo(0, 6)
  })

  it("rotates camera offsets with the registered site heading", () => {
    const offset = campusOffsetToEnu(registration(90), 10, 0, 5)

    expect(offset.x).toBeCloseTo(0, 6)
    expect(offset.y).toBeCloseTo(10, 6)
    expect(offset.z).toBeCloseTo(5, 6)
  })
})
