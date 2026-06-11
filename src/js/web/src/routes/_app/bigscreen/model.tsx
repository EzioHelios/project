import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/bigscreen/model")({
  component: BigscreenModelPage,
})

function BigscreenModelPage() {
  return (
    <div className="bigscreen-model-page">
      <div className="bigscreen-model-status">
        <span>泰州中心库三维模型</span>
        <strong>siteLayer / buildingLayer / zoneLayer</strong>
      </div>
      <div className="bigscreen-model-legend" aria-label="园区模型图例">
        <span data-tone="site">底盘道路绿化</span>
        <span data-tone="building">建筑体块</span>
        <span data-tone="solar">光伏屋顶</span>
        <span data-tone="zone">功能分区</span>
      </div>
    </div>
  )
}
