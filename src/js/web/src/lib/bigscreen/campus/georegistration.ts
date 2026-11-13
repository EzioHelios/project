import { Cartesian3, Math as CesiumMath, Matrix3, Matrix4, Transforms } from "cesium"
import type { CampusGeoregistration } from "./types"

export function campusModelMatrix(registration: CampusGeoregistration) {
  const anchor = Cartesian3.fromDegrees(...registration.origin, registration.ellipsoidHeight)
  const frame = Transforms.eastNorthUpToFixedFrame(anchor)
  const heading = Matrix4.fromRotationTranslation(Matrix3.fromRotationZ(CesiumMath.toRadians(registration.headingDegrees)))
  const rotatedFrame = Matrix4.multiply(frame, heading, new Matrix4())
  return Matrix4.multiplyByScale(rotatedFrame, Cartesian3.fromArray(registration.scale), rotatedFrame)
}

export function campusOffsetToEnu(registration: CampusGeoregistration, east: number, north: number, up: number) {
  const heading = CesiumMath.toRadians(registration.headingDegrees)
  const scaledEast = east * registration.scale[0]
  const scaledNorth = north * registration.scale[1]
  return new Cartesian3(
    scaledEast * Math.cos(heading) - scaledNorth * Math.sin(heading),
    scaledEast * Math.sin(heading) + scaledNorth * Math.cos(heading),
    up * registration.scale[2],
  )
}

export function campusCameraHeading(registration: CampusGeoregistration, localYaw: number) {
  return -localYaw - CesiumMath.toRadians(registration.headingDegrees)
}

/** Existing controls use glTF/Three coordinates: east, up, south. */
export function campusPointToFixed(matrix: Matrix4, east: number, up: number, south: number) {
  return Matrix4.multiplyByPoint(matrix, new Cartesian3(east, -south, up), new Cartesian3())
}
