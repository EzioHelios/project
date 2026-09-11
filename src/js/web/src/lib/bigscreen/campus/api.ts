import type { CampusManifest } from "./types"

export class SceneNotConfiguredError extends Error {}

export function sceneEndpoint(teamId: string) {
  return `/api/teams/${encodeURIComponent(teamId)}/scene/`
}

export function assertTenantAssetUrl(url: string, teamId: string) {
  const resolved = new URL(url, window.location.origin)
  const prefix = `${sceneEndpoint(teamId)}assets/`
  if (resolved.origin !== window.location.origin || !resolved.pathname.startsWith(prefix)) {
    throw new Error("园区模型资源与当前租户不匹配")
  }
  return resolved.href
}

export async function fetchSceneManifest(teamId: string, signal: AbortSignal): Promise<CampusManifest> {
  const response = await fetch(new URL(sceneEndpoint(teamId), window.location.origin), {
    signal,
    credentials: "include",
    cache: "no-store",
    headers: { "X-Team-Id": teamId },
  })
  if (response.status === 404) throw new SceneNotConfiguredError("当前租户尚未配置园区模型")
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? "无权访问当前租户的园区模型" : "园区模型加载失败")
  const manifest = (await response.json()) as CampusManifest
  if (manifest.teamId !== teamId || !["three", "cesium", "cesium-campus"].includes(manifest.engine) || !Array.isArray(manifest.assets)) {
    throw new Error("园区模型配置无效")
  }
  for (const asset of manifest.assets) assertTenantAssetUrl(asset, teamId)
  if (manifest.engine !== "cesium") {
    if (!manifest.world?.entries?.length) throw new Error("园区模型配置无效")
    if (manifest.reference) assertTenantAssetUrl(manifest.reference, teamId)
    if (manifest.engine === "cesium-campus") {
      const g = manifest.georegistration
      if (
        !g ||
        g.version !== 1 ||
        g.crs !== "EPSG:4326" ||
        g.terrain !== "ellipsoid" ||
        g.upAxis !== "Y" ||
        g.forwardAxis !== "X" ||
        !Array.isArray(g.origin) ||
        g.origin.length !== 2 ||
        !g.origin.every(Number.isFinite) ||
        Math.abs(g.origin[0]) > 180 ||
        Math.abs(g.origin[1]) > 85 ||
        !Array.isArray(g.scale) ||
        g.scale.length !== 3 ||
        !g.scale.every((v) => Number.isFinite(v) && v > 0) ||
        !Number.isFinite(g.ellipsoidHeight) ||
        !g.imagery ||
        !g.imagery.url.startsWith("https://") ||
        !["{x}", "{y}", "{z}"].every((v) => g.imagery.url.includes(v)) ||
        !Number.isInteger(g.imagery.maximumLevel) ||
        g.imagery.maximumLevel < 0 ||
        g.imagery.maximumLevel > 24
      )
        throw new Error("园区地图定位配置无效")
    }
  } else assertTenantAssetUrl(manifest.legacyManifest, teamId)
  return manifest
}

export async function fetchSceneAsset(url: string, teamId: string, signal: AbortSignal) {
  const response = await fetch(assertTenantAssetUrl(url, teamId), {
    signal,
    credentials: "include",
    cache: "no-store",
    headers: { "X-Team-Id": teamId },
  })
  if (!response.ok) throw new Error("园区模型资源读取失败")
  return response
}
