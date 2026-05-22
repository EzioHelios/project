import { taizhouBigscreenSkin } from "@/components/bigscreen/skins/taizhou"
import type { BigscreenSkinDefinition } from "@/components/bigscreen/skins/types"

export const BIGSCREEN_SKINS: Record<string, BigscreenSkinDefinition> = {
  taizhou: taizhouBigscreenSkin,
}

export const DEFAULT_BIGSCREEN_SKIN_ID = "taizhou"

export const defaultBigscreenSkin = BIGSCREEN_SKINS[DEFAULT_BIGSCREEN_SKIN_ID]

export function getBigscreenSkinDefinition(skinId = DEFAULT_BIGSCREEN_SKIN_ID) {
  return BIGSCREEN_SKINS[skinId] ?? defaultBigscreenSkin
}
