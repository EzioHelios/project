import { resolveBigscreenPublicUrl } from "@/lib/bigscreen/map/scene"

export type BigscreenTenantSceneIdentity = {
  id?: string | null
  slug?: string | null
}

const SAFE_SCENE_KEY = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/u

function normalizeSceneKey(value: string | null | undefined) {
  const normalized = value?.trim().toLowerCase()
  return normalized && SAFE_SCENE_KEY.test(normalized) ? normalized : null
}

function unique(values: string[]) {
  return [...new Set(values)]
}

/**
 * Resolve a tenant-specific scene without coupling React routes to a concrete park.
 *
 * Asset lookup order:
 * 1. stable tenant slug namespace;
 * 2. immutable tenant id namespace;
 * 3. configured platform fallback scene.
 *
 * Missing tenant manifests may fall back, while malformed manifests fail loudly so
 * a tenant can never silently render another tenant's partially configured assets.
 */
export function resolveTenantBigscreenSceneManifestCandidates(
  tenant: BigscreenTenantSceneIdentity | null | undefined,
  fallbackManifest = import.meta.env.VITE_BIGSCREEN_DEFAULT_SCENE_MANIFEST || "maps/taizhou-warehouse/scene.json",
) {
  const slug = normalizeSceneKey(tenant?.slug)
  const id = normalizeSceneKey(tenant?.id)
  return unique(
    [
      slug ? resolveBigscreenPublicUrl(`maps/tenants/${slug}/scene.json`) : null,
      id ? resolveBigscreenPublicUrl(`maps/tenants/${id}/scene.json`) : null,
      resolveBigscreenPublicUrl(fallbackManifest),
    ].filter((value): value is string => Boolean(value)),
  )
}
