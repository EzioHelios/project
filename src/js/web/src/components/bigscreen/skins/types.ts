export type BigscreenPanelFrame = "wide" | "tall" | "narrow"

export type BigscreenPanelInsets = {
  top: number
  right: number
  bottom: number
  left: number
}

export type BigscreenPanelFrameConfig = {
  bodyPadding: BigscreenPanelInsets
  headerHeight: number
  renderMode?: "background-image" | "svg-frame"
  titleWidth: number
}

export type BigscreenSkinAssetMap = {
  backdropImage?: string
  headerBase?: string
  headerTitlePlate?: string
  panelTitleStrip?: string
  panelFrameWide?: string
  panelFrameTall?: string
  panelFrameNarrow?: string
  collapseLeft?: string
  collapseRight?: string
}

export type BigscreenSkinDefinition = {
  id: string
  displayName: string
  tokenClassName: string
  assets: BigscreenSkinAssetMap
  panelFrames: Record<BigscreenPanelFrame, BigscreenPanelFrameConfig>
}
