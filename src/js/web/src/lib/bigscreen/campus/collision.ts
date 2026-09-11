import type { PixelPoint } from "./types"

/** Keep walkers outside the actual footprint and its wall clearance. */
export function blocksWalkAt(point: PixelPoint, polygon: PixelPoint[], clearance = 0.7) {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[j]
    const b = polygon[i]
    if (a[1] > y !== b[1] > y && x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside
    const dx = b[0] - a[0]
    const dy = b[1] - a[1]
    const lengthSquared = dx * dx + dy * dy
    const t = lengthSquared ? Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / lengthSquared)) : 0
    if ((x - a[0] - t * dx) ** 2 + (y - a[1] - t * dy) ** 2 <= clearance ** 2) return true
  }
  return inside
}
