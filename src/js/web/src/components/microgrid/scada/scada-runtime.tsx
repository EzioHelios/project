import { Background, BackgroundVariant, Controls, ReactFlow } from "@xyflow/react"
import { useEffect, useMemo, useRef, useState } from "react"
import "@xyflow/react/dist/style.css"
import type { MicrogridTopology } from "@/lib/api/hooks/microgrid"
import { ScadaFeederEdge } from "./scada-edges"
import { ScadaAssetNode, ScadaBusbarNode, ScadaStructuralNode } from "./scada-nodes"
import { createScadaRuntimeModel } from "./scada-scene-adapter"
import type { ScadaSelection } from "./types"
import "./scada.css"

const nodeTypes = {
  scadaAsset: ScadaAssetNode,
  scadaStructural: ScadaStructuralNode,
  scadaBusbar: ScadaBusbarNode,
}

const edgeTypes = { scadaFeeder: ScadaFeederEdge }

export function ScadaRuntime({ topology, onSelect }: { topology: MicrogridTopology; onSelect: (selection: ScadaSelection) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setContainerWidth(entry?.contentRect.width ?? element.clientWidth))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  const direction = containerWidth >= 960 ? "LR" : "TB"
  const model = useMemo(() => createScadaRuntimeModel(topology, { direction }), [direction, topology])
  return (
    <div className="overflow-hidden" data-testid="microgrid-scada-runtime">
      <div className="scada-runtime-toolbar">
        <ul className="scada-runtime-legend" aria-label="运行状态图例">
          <li>
            <i />
            带电
          </li>
          <li className="flow">
            <i />
            功率流
          </li>
          <li className="offline">
            <i />
            失电或离线
          </li>
        </ul>
        <div className="text-muted-foreground text-[10px] tabular-nums">拓扑 V{topology.topologyVersion ?? 1} · 实时监视</div>
      </div>
      <div className="scada-runtime" ref={containerRef}>
        <ReactFlow
          aria-label="祥泰仓库微电网一次系统图"
          colorMode="light"
          deleteKeyCode={null}
          edges={model.edges}
          edgesFocusable={false}
          edgesReconnectable={false}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.06, minZoom: 0.25, maxZoom: 1.2 }}
          key={direction}
          maxZoom={1.6}
          minZoom={0.25}
          nodes={model.nodes}
          nodesConnectable={false}
          nodesDraggable={false}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => onSelect({ nodeId: node.id, ...node.data })}
          onlyRenderVisibleElements
          panOnScroll
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--scada-grid)" gap={22} lineWidth={0.7} variant={BackgroundVariant.Lines} />
          <Controls position="bottom-left" showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  )
}
