import { Cartesian3, Matrix4, Transforms } from "cesium"
import type { CampusGeoregistration } from "./types"

export function campusModelMatrix(registration: CampusGeoregistration) {
  const anchor = Cartesian3.fromDegrees(...registration.origin, registration.ellipsoidHeight)
  return Matrix4.multiplyByScale(Transforms.eastNorthUpToFixedFrame(anchor), Cartesian3.fromArray(registration.scale), new Matrix4())
}

/** Existing controls use glTF/Three coordinates: east, up, south. */
export function campusPointToFixed(matrix: Matrix4, east: number, up: number, south: number) {
  return Matrix4.multiplyByPoint(matrix, new Cartesian3(east, -south, up), new Cartesian3())
}
