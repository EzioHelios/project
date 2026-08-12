import dagre from "@dagrejs/dagre"
import type { MicrogridTopology } from "@/lib/api/hooks/microgrid"
import type { ScadaLayoutDirection, ScadaNodeKind, ScadaRuntimeNode } from "./types"

const dimensions: Record<ScadaNodeKind, { width: number; height: number }> = {
  utility: { width: 210, height: 112 },
  pv: { width: 210, height: 112 },
  storage: { width: 210, height: 112 },
  charger: { width: 210, height: 112 },
  lighting: { width: 210, height: 112 },
  load: { width: 210, height: 112 },
  asset: { width: 210, height: 112 },
  isolator: { width: 112, height: 88 },
  breaker: { width: 112, height: 88 },
  meter: { width: 112, height: 94 },
  inverter: { width: 124, height: 96 },
  pcs: { width: 124, height: 96 },
  transformer: { width: 136, height: 112 },
  busbar: { width: 840, height: 76 },
}

const horizontalDimensions: Partial<Record<ScadaNodeKind, { width: number; height: number }>> = {
  utility: { width: 160, height: 112 },
  pv: { width: 160, height: 112 },
  storage: { width: 160, height: 112 },
  charger: { width: 160, height: 112 },
  lighting: { width: 160, height: 112 },
  load: { width: 160, height: 112 },
  asset: { width: 160, height: 112 },
  isolator: { width: 78, height: 112 },
  breaker: { width: 78, height: 112 },
  meter: { width: 78, height: 112 },
  inverter: { width: 90, height: 112 },
  pcs: { width: 90, height: 112 },
  transformer: { width: 92, height: 112 },
  busbar: { width: 64, height: 600 },
}

const MARGIN = 48

export function getScadaNodeDimensions(kind: ScadaNodeKind, direction: ScadaLayoutDirection = "TB") {
  if (direction === "LR") return horizontalDimensions[kind] ?? dimensions[kind]
  return dimensions[kind]
}

function portOffset(node: ScadaRuntimeNode, portId: string | undefined) {
  return node.data.ports.find((port) => port.id === portId)?.offset ?? 0.5
}

function chainBeforeBus(topology: MicrogridTopology, busId: string, tailId: string) {
  const chain = [tailId]
  let cursor = tailId
  while (true) {
    const predecessors = topology.edges.filter((edge) => edge.target === cursor && edge.source !== busId)
    if (predecessors.length !== 1) return chain
    cursor = predecessors[0]?.source ?? cursor
    chain.unshift(cursor)
  }
}

function chainAfterBus(topology: MicrogridTopology, busId: string, headId: string) {
  const chain = [headId]
  let cursor = headId
  while (true) {
    const successors = topology.edges.filter((edge) => edge.source === cursor && edge.target !== busId)
    if (successors.length !== 1) return chain
    cursor = successors[0]?.target ?? cursor
    chain.push(cursor)
  }
}

function busAwareLayout(topology: MicrogridTopology, nodes: ScadaRuntimeNode[], direction: ScadaLayoutDirection) {
  const bus = nodes.find((node) => node.data.kind === "busbar")
  if (!bus) return null
  const incoming = topology.edges.filter((edge) => edge.target === bus.id)
  const outgoing = topology.edges.filter((edge) => edge.source === bus.id)
  if (incoming.length === 0 && outgoing.length === 0) return null

  const nodeMap = new Map(nodes.map((node) => [node.id, node]))
  const incomingChains = incoming.map((edge) => ({ edge, ids: chainBeforeBus(topology, bus.id, edge.source) }))
  const outgoingChains = outgoing.map((edge) => ({ edge, ids: chainAfterBus(topology, bus.id, edge.target) }))
  const rankGap = direction === "LR" ? Math.min(topology.layout?.rankSeparation ?? 80, 38) : (topology.layout?.rankSeparation ?? 80)
  const busSize = getScadaNodeDimensions("busbar", direction)
  const positions = new Map<string, { x: number; y: number }>()

  if (direction === "TB") {
    const upstreamHeight = Math.max(
      0,
      ...incomingChains.map(({ ids }) => ids.reduce((total, id) => total + getScadaNodeDimensions(nodeMap.get(id)?.data.kind ?? "asset", direction).height + rankGap, 0)),
    )
    const busPosition = { x: MARGIN, y: MARGIN + upstreamHeight }
    positions.set(bus.id, busPosition)
    for (const { edge, ids } of incomingChains) {
      const anchorX = busPosition.x + portOffset(bus, edge.targetHandle) * busSize.width
      let cursorY = busPosition.y - rankGap
      for (const id of [...ids].reverse()) {
        const node = nodeMap.get(id)
        if (!node) continue
        const size = getScadaNodeDimensions(node.data.kind, direction)
        const nextEdge = topology.edges.find((candidate) => candidate.source === id && (candidate.target === bus.id || ids.includes(candidate.target)))
        positions.set(id, { x: anchorX - portOffset(node, nextEdge?.sourceHandle) * size.width, y: cursorY - size.height })
        cursorY -= size.height + rankGap
      }
    }
    for (const { edge, ids } of outgoingChains) {
      const anchorX = busPosition.x + portOffset(bus, edge.sourceHandle) * busSize.width
      let cursorY = busPosition.y + busSize.height + rankGap
      for (const id of ids) {
        const node = nodeMap.get(id)
        if (!node) continue
        const size = getScadaNodeDimensions(node.data.kind, direction)
        const previousEdge = topology.edges.find((candidate) => candidate.target === id && (candidate.source === bus.id || ids.includes(candidate.source)))
        positions.set(id, { x: anchorX - portOffset(node, previousEdge?.targetHandle) * size.width, y: cursorY })
        cursorY += size.height + rankGap
      }
    }
  } else {
    const upstreamWidth = Math.max(
      0,
      ...incomingChains.map(({ ids }) => ids.reduce((total, id) => total + getScadaNodeDimensions(nodeMap.get(id)?.data.kind ?? "asset", direction).width + rankGap, 0)),
    )
    const busPosition = { x: MARGIN + upstreamWidth, y: MARGIN }
    positions.set(bus.id, busPosition)
    for (const { edge, ids } of incomingChains) {
      const anchorY = busPosition.y + portOffset(bus, edge.targetHandle) * busSize.height
      let cursorX = busPosition.x - rankGap
      for (const id of [...ids].reverse()) {
        const node = nodeMap.get(id)
        if (!node) continue
        const size = getScadaNodeDimensions(node.data.kind, direction)
        const nextEdge = topology.edges.find((candidate) => candidate.source === id && (candidate.target === bus.id || ids.includes(candidate.target)))
        positions.set(id, { x: cursorX - size.width, y: anchorY - portOffset(node, nextEdge?.sourceHandle) * size.height })
        cursorX -= size.width + rankGap
      }
    }
    for (const { edge, ids } of outgoingChains) {
      const anchorY = busPosition.y + portOffset(bus, edge.sourceHandle) * busSize.height
      let cursorX = busPosition.x + busSize.width + rankGap
      for (const id of ids) {
        const node = nodeMap.get(id)
        if (!node) continue
        const size = getScadaNodeDimensions(node.data.kind, direction)
        const previousEdge = topology.edges.find((candidate) => candidate.target === id && (candidate.source === bus.id || ids.includes(candidate.source)))
        positions.set(id, { x: cursorX, y: anchorY - portOffset(node, previousEdge?.targetHandle) * size.height })
        cursorX += size.width + rankGap
      }
    }
  }

  if (positions.size !== nodes.length) return null
  const positioned = nodes.map((node) => {
    const size = getScadaNodeDimensions(node.data.kind, direction)
    return { ...node, position: positions.get(node.id) ?? node.position, style: size }
  })
  const width = Math.max(...positioned.map((node) => node.position.x + (node.style?.width as number))) + MARGIN
  const height = Math.max(...positioned.map((node) => node.position.y + (node.style?.height as number))) + MARGIN
  return { nodes: positioned, canvas: { width: Math.ceil(width), height: Math.ceil(height) } }
}

function dagreLayout(topology: MicrogridTopology, nodes: ScadaRuntimeNode[], direction: ScadaLayoutDirection) {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}))
  const layout = topology.layout
  graph.setGraph({
    rankdir: direction,
    ranksep: layout?.rankSeparation ?? 80,
    nodesep: layout?.nodeSeparation ?? 34,
    edgesep: layout?.edgeSeparation ?? 18,
    marginx: MARGIN,
    marginy: MARGIN,
    ranker: "network-simplex",
  })
  for (const node of nodes) graph.setNode(node.id, getScadaNodeDimensions(node.data.kind, direction))
  for (const edge of topology.edges) graph.setEdge(edge.source, edge.target)
  dagre.layout(graph)
  const positioned = nodes.map((node) => {
    const point = graph.node(node.id) as { x: number; y: number; width: number; height: number }
    return { ...node, position: { x: point.x - point.width / 2, y: point.y - point.height / 2 }, style: { width: point.width, height: point.height } }
  })
  const result = graph.graph() as { width?: number; height?: number }
  return { nodes: positioned, canvas: { width: Math.ceil(result.width ?? 1440), height: Math.ceil(result.height ?? 1020) } }
}

export function autoLayoutScadaScene(topology: MicrogridTopology, nodes: ScadaRuntimeNode[], direction: ScadaLayoutDirection) {
  return busAwareLayout(topology, nodes, direction) ?? dagreLayout(topology, nodes, direction)
}
