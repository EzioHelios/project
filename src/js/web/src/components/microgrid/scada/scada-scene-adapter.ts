import type { MicrogridAsset, MicrogridTopology } from "@/lib/api/hooks/microgrid"
import { autoLayoutScadaScene } from "./scada-layout"
import type { ScadaLayoutDirection, ScadaNodeData, ScadaNodeKind, ScadaRuntimeModel, ScadaStateTone } from "./types"

const NODE_KINDS = new Set<ScadaNodeKind>([
  "utility",
  "isolator",
  "breaker",
  "meter",
  "transformer",
  "inverter",
  "pcs",
  "busbar",
  "pv",
  "storage",
  "charger",
  "lighting",
  "load",
  "asset",
])

function normalizeKind(kind: string | undefined): ScadaNodeKind {
  return kind && NODE_KINDS.has(kind as ScadaNodeKind) ? (kind as ScadaNodeKind) : "asset"
}

export function getAssetTone(asset: MicrogridAsset | undefined): ScadaStateTone {
  if (!asset) return "simulated"
  if (!asset.online) return "offline"
  if (["critical", "alarm", "error"].includes(asset.alarmLevel)) return "alarm"
  if (["warning", "minor"].includes(asset.alarmLevel)) return "warning"
  return "normal"
}

function assetStatus(asset: MicrogridAsset | undefined, kind: ScadaNodeKind) {
  if (!asset) return kind === "isolator" || kind === "breaker" ? "合闸" : "结构节点"
  if (!asset.online) return "通信中断"
  if (asset.alarmLevel !== "normal") return asset.alarmLevel === "warning" ? "预警" : "告警"
  if (kind === "storage") {
    if ((asset.activePowerKw ?? 0) < -0.1) return "充电"
    if ((asset.activePowerKw ?? 0) > 0.1) return "放电"
    return "待机"
  }
  return "运行"
}

function nodeType(kind: ScadaNodeKind) {
  if (kind === "busbar") return "scadaBusbar"
  if (["isolator", "breaker", "meter", "transformer", "inverter", "pcs"].includes(kind)) return "scadaStructural"
  return "scadaAsset"
}

function fallbackPorts(kind: ScadaNodeKind): NonNullable<MicrogridTopology["nodes"][number]["ports"]> {
  if (kind === "utility" || kind === "pv") return [{ id: "out", side: "bottom", direction: "output", offset: 0.5 }]
  if (["storage", "charger", "lighting", "load"].includes(kind)) return [{ id: "in", side: "top", direction: "input", offset: 0.5 }]
  return [
    { id: "in", side: "top", direction: "input", offset: 0.5 },
    { id: "out", side: "bottom", direction: "output", offset: 0.5 },
  ]
}

function orientPorts(ports: NonNullable<MicrogridTopology["nodes"][number]["ports"]>, direction: ScadaLayoutDirection) {
  const sides = { top: "left", right: "top", bottom: "right", left: "bottom" } as const
  return ports.map((port) => ({
    ...port,
    offset: port.offsetByLayout?.[direction] ?? port.offset,
    side: direction === "TB" ? port.side : sides[port.side],
  }))
}

function edgeDirection(asset: MicrogridAsset | undefined, source: string, target: string) {
  if (!asset) return false
  if (asset.assetType === "storage") return (asset.activePowerKw ?? 0) > 0
  if (asset.assetType === "pv") return false
  if (source === "grid" || target === "grid") return (asset.activePowerKw ?? 0) < 0
  return false
}

export function createScadaRuntimeModel(topology: MicrogridTopology, options: { direction?: ScadaLayoutDirection } = {}): ScadaRuntimeModel {
  const direction = options.direction ?? topology.layout?.direction ?? "TB"
  const assets = new Map((topology.assets ?? []).map((asset) => [asset.code, asset]))
  const grid = assets.get("PCC")
  const nodes = topology.nodes.map((node) => {
    const kind = normalizeKind(node.kind)
    const asset = node.assetCode ? assets.get(node.assetCode) : undefined
    const inheritedAsset = asset ?? (["isolator", "breaker", "meter", "transformer", "busbar"].includes(kind) ? grid : undefined)
    const tone = getAssetTone(inheritedAsset)
    const data: ScadaNodeData = {
      label: node.label,
      kind,
      asset,
      tone,
      energized: inheritedAsset?.online ?? true,
      statusLabel: assetStatus(asset, kind),
      subtitle: node.meta ?? (kind === "transformer" ? "10kV / 0.4kV" : kind === "busbar" ? "AC 400V" : undefined),
      ports: orientPorts(node.ports?.length ? node.ports : fallbackPorts(kind), direction),
      orientation: direction,
    }
    return {
      id: node.id,
      type: nodeType(kind),
      position: { x: node.x ?? 0, y: node.y ?? 0 },
      data,
      selectable: true,
      draggable: false,
      connectable: false,
    }
  })
  const laidOut = autoLayoutScadaScene(topology, nodes, direction)
  const edges = topology.edges.map((edge, index) => {
    const asset = edge.assetCode ? assets.get(edge.assetCode) : grid
    const tone = getAssetTone(asset)
    return {
      id: edge.id ?? `edge-${index + 1}`,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      type: "scadaFeeder",
      data: {
        energized: asset?.online ?? true,
        reverse: edgeDirection(asset, edge.source, edge.target),
        powerKw: asset?.activePowerKw ?? null,
        tone,
      },
      selectable: false,
    }
  })
  return {
    nodes: laidOut.nodes,
    edges,
    canvas: laidOut.canvas,
  }
}
