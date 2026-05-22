import type { PropsWithChildren } from "react"
import { createContext, useContext } from "react"

import { defaultBigscreenSkin } from "@/components/bigscreen/skins/registry"
import type { BigscreenSkinDefinition } from "@/components/bigscreen/skins/types"

const BigscreenSkinContext = createContext<BigscreenSkinDefinition>(defaultBigscreenSkin)

export function BigscreenSkinProvider({
  children,
  skin,
}: PropsWithChildren<{
  skin?: BigscreenSkinDefinition
}>) {
  return <BigscreenSkinContext.Provider value={skin ?? defaultBigscreenSkin}>{children}</BigscreenSkinContext.Provider>
}

export function useBigscreenSkin() {
  return useContext(BigscreenSkinContext)
}
