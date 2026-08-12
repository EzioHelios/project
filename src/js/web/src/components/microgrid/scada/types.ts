import type { Edge, Node } from "@xyflow/react"
import type { MicrogridAsset, MicrogridTopology } from "@/lib/api/hooks/microgrid"

export type ScadaNodeKind =
  | "utility"
  | "isolator"
  | "breaker"
  | "meter"
  | "transformer"
  | "inverter"
  | "pcs"
  | "busbar"
  | "pv"
  | "storage"
  | "charger"
  | "lighting"
  | "load"
  | "asset"

export type ScadaStateTone = "normal" | "warning" | "alarm" | "offline" | "simulated"
export type ScadaLayoutDirection = "TB" | "LR"

export type ScadaNodeData = {
  label: string
  kind: ScadaNodeKind
  asset?: MicrogridAsset
  tone: ScadaStateTone
  energized: boolean
  statusLabel: string
  subtitle?: string
  ports: NonNullable<MicrogridTopology["nodes"][number]["ports"]>
  orientation: ScadaLayoutDirection
}

export type ScadaEdgeData = {
  energized: boolean
  reverse: boolean
  powerKw: number | null
  tone: ScadaStateTone
}

export type ScadaRuntimeNode = Node<ScadaNodeData>
export type ScadaRuntimeEdge = Edge<ScadaEdgeData>

export type ScadaSelection = ScadaNodeData & { nodeId: string }

export type ScadaRuntimeModel = {
  nodes: ScadaRuntimeNode[]
  edges: ScadaRuntimeEdge[]
  canvas: NonNullable<MicrogridTopology["canvas"]>
}
