import { afterEach, describe, expect, it, vi } from "vitest"
import { fetchSceneManifest } from "@/lib/bigscreen/campus/api"

const config = () => ({
  engine: "cesium-campus", teamId: "team-a", assets: ["/api/teams/team-a/scene/assets/model.glb"], world: { entries: [{ id: "gate" }] },
  georegistration: {
    version: 1, crs: "EPSG:4326", origin: [120, 32], scale: [1, 1, 1], ellipsoidHeight: 0.2,
    terrain: "ellipsoid", upAxis: "Y", forwardAxis: "X",
    imagery: { url: "https://example.com/{z}/{x}/{y}", maximumLevel: 18 },
  },
})
afterEach(() => vi.unstubAllGlobals())
function respond(value: unknown) { vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => value })) }
describe("geographic scene manifest boundary", () => {
  it("accepts the supported coordinate frame", async () => {
    respond(config())
    expect((await fetchSceneManifest("team-a", new AbortController().signal)).engine).toBe("cesium-campus")
  })
  it("rejects a copied asset URL from a different tenant", async () => {
    respond({ ...config(), assets: ["/api/teams/team-b/scene/assets/model.glb"] })
    await expect(fetchSceneManifest("team-a", new AbortController().signal)).rejects.toThrow("当前租户不匹配")
  })
  it("rejects an unsupported map datum instead of placing it as WGS84", async () => {
    const value = config(); value.georegistration.crs = "GCJ-02"; respond(value)
    await expect(fetchSceneManifest("team-a", new AbortController().signal)).rejects.toThrow("定位配置无效")
  })
})
