import backdropImage from "@/components/bigscreen/skins/taizhou/assets/backdrop-bg.png"
import collapseLeft from "@/components/bigscreen/skins/taizhou/assets/collapse-left.svg"
import collapseRight from "@/components/bigscreen/skins/taizhou/assets/collapse-right.svg"
import panelFrameNarrow from "@/components/bigscreen/skins/taizhou/assets/panel-frame-narrow.svg"
import panelFrameTall from "@/components/bigscreen/skins/taizhou/assets/panel-frame-tall.svg"
import panelFrameWide from "@/components/bigscreen/skins/taizhou/assets/panel-frame-wide.svg"
import panelTitleStrip from "@/components/bigscreen/skins/taizhou/assets/panel-title-strip.svg"
import headerBase from "@/components/bigscreen/skins/taizhou/assets/screen-header-base.svg"
import headerTitlePlate from "@/components/bigscreen/skins/taizhou/assets/screen-title-center-plate.svg"
import type { BigscreenSkinDefinition } from "@/components/bigscreen/skins/types"

import "./tokens.css"

export const taizhouBigscreenSkin: BigscreenSkinDefinition = {
  id: "taizhou",
  displayName: "Taizhou Warehouse",
  tokenClassName: "bigscreen-skin-taizhou",
  assets: {
    backdropImage,
    headerBase,
    headerTitlePlate,
    panelTitleStrip,
    panelFrameWide,
    panelFrameTall,
    panelFrameNarrow,
    collapseLeft,
    collapseRight,
  },
  panelFrames: {
    wide: {
      headerHeight: 56,
      renderMode: "svg-frame",
      titleWidth: 360,
      bodyPadding: { top: 10, right: 22, bottom: 20, left: 22 },
    },
    tall: {
      headerHeight: 58,
      renderMode: "svg-frame",
      titleWidth: 304,
      bodyPadding: { top: 10, right: 18, bottom: 20, left: 18 },
    },
    narrow: {
      headerHeight: 58,
      renderMode: "svg-frame",
      titleWidth: 252,
      bodyPadding: { top: 8, right: 18, bottom: 22, left: 40 },
    },
  },
}
