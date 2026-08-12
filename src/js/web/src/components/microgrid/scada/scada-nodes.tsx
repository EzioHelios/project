import { Handle, type NodeProps, Position } from "@xyflow/react"
import { Cable } from "lucide-react"
import type { CSSProperties, SVGProps } from "react"
import equipmentAtlas from "@/assets/microgrid/scada-equipment-atlas-v1.webp"
import { cn } from "@/lib/utils"
import type { ScadaNodeKind, ScadaRuntimeNode } from "./types"

type GlyphProps = SVGProps<SVGSVGElement>

const sidePositions = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
}

const atlasPositions: Partial<Record<ScadaNodeKind, string>> = {
  utility: "0% 0%",
  pv: "50% 0%",
  storage: "100% 0%",
  charger: "0% 100%",
  lighting: "50% 100%",
  load: "100% 100%",
}

function BreakerGlyph(props: GlyphProps) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 44" {...props}>
      <path d="M2 22h15M47 22h15" />
      <rect height="28" rx="2" width="30" x="17" y="8" />
      <path d="m23 14 18 16M41 14 23 30" />
    </svg>
  )
}

function IsolatorGlyph(props: GlyphProps) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 44" {...props}>
      <path d="M2 22h16M46 22h16M18 22l27-11" />
      <circle cx="18" cy="22" r="3" />
      <circle cx="46" cy="22" r="3" />
    </svg>
  )
}

function MeterGlyph(props: GlyphProps) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 52" {...props}>
      <path d="M2 26h10M52 26h10" />
      <circle cx="32" cy="26" r="20" />
      <path d="M21 32V20l11 9 11-9v12" />
    </svg>
  )
}

function TransformerGlyph(props: GlyphProps) {
  return (
    <svg aria-hidden="true" viewBox="0 0 82 58" {...props}>
      <path d="M41 0v11M41 47v11" />
      <circle cx="33" cy="29" r="18" />
      <circle cx="49" cy="29" r="18" />
    </svg>
  )
}

function ConverterGlyph({ bidirectional = false, ...props }: GlyphProps & { bidirectional?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 72 56" {...props}>
      <path d="M36 0v8M36 48v8" />
      <rect height="40" rx="3" width="52" x="10" y="8" />
      <path d="M16 28h40M22 20h9M22 36h9M39 19c4 0 4 4 8 4s4-4 8-4" />
      {bidirectional ? <path d="m39 34 5-4 5 4M49 40l-5 4-5-4" /> : <path d="m38 39 8-6 8 6" />}
    </svg>
  )
}

function NodePorts({ ports }: { ports: ScadaRuntimeNode["data"]["ports"] }) {
  return ports.map((port) => {
    const offset = `${Math.min(1, Math.max(0, port.offset ?? 0.5)) * 100}%`
    const style: CSSProperties = port.side === "top" || port.side === "bottom" ? { left: offset } : { top: offset }
    return (
      <Handle
        aria-label={`${port.id} ${port.voltageLevel ?? ""}`.trim()}
        className="scada-port"
        id={port.id}
        key={port.id}
        position={sidePositions[port.side]}
        style={style}
        type={port.direction === "output" ? "source" : "target"}
      />
    )
  })
}

function EquipmentIcon({ kind }: { kind: ScadaNodeKind }) {
  const position = atlasPositions[kind]
  if (!position) return <Cable className="scada-symbol-fallback" />
  return <span aria-hidden="true" className="scada-equipment-icon" style={{ backgroundImage: `url(${equipmentAtlas})`, backgroundPosition: position }} />
}

function powerLabel(value: number | null | undefined) {
  if (value === null || value === undefined) return "—"
  return `${Math.abs(value).toLocaleString("zh-CN", { maximumFractionDigits: 1 })} kW`
}

export function ScadaAssetNode({ data, selected }: NodeProps<ScadaRuntimeNode>) {
  return (
    <div className={cn("scada-asset-node", `is-${data.tone}`, selected && "is-selected", !data.energized && "is-deenergized")} data-kind={data.kind}>
      <NodePorts ports={data.ports} />
      <div className="scada-equipment-plate">
        <span className="scada-corner scada-corner-start" />
        <EquipmentIcon kind={data.kind} />
        <span className="scada-corner scada-corner-end" />
        {data.kind === "storage" && data.asset?.socPct !== null && data.asset?.socPct !== undefined && (
          <span className="scada-symbol-soc">SOC {Math.round(data.asset.socPct)}%</span>
        )}
      </div>
      <div className="scada-node-copy">
        <div className="scada-node-label">{data.label}</div>
        <div className="scada-node-value">{powerLabel(data.asset?.activePowerKw)}</div>
        <div className="scada-node-status">
          <span className="scada-status-dot" />
          {data.statusLabel}
        </div>
      </div>
    </div>
  )
}

export function ScadaStructuralNode({ data, selected }: NodeProps<ScadaRuntimeNode>) {
  const glyph =
    data.kind === "isolator" ? (
      <IsolatorGlyph className="scada-structural-glyph" />
    ) : data.kind === "breaker" ? (
      <BreakerGlyph className="scada-structural-glyph" />
    ) : data.kind === "meter" ? (
      <MeterGlyph className="scada-structural-glyph" />
    ) : data.kind === "inverter" ? (
      <ConverterGlyph className="scada-structural-glyph" />
    ) : data.kind === "pcs" ? (
      <ConverterGlyph bidirectional className="scada-structural-glyph" />
    ) : (
      <TransformerGlyph className="scada-structural-glyph" />
    )
  return (
    <div
      className={cn("scada-structural-node", `is-${data.tone}`, `is-${data.orientation.toLowerCase()}`, selected && "is-selected", !data.energized && "is-deenergized")}
      data-kind={data.kind}
    >
      <NodePorts ports={data.ports} />
      {glyph}
      <div className="scada-structural-label">{data.label}</div>
      <div className="scada-structural-meta">{data.subtitle ?? data.statusLabel}</div>
    </div>
  )
}

export function ScadaBusbarNode({ data, selected }: NodeProps<ScadaRuntimeNode>) {
  return (
    <div className={cn("scada-busbar-node", `is-${data.tone}`, `is-${data.orientation.toLowerCase()}`, selected && "is-selected", !data.energized && "is-deenergized")}>
      <div className="scada-busbar-ports">
        <NodePorts ports={data.ports} />
      </div>
      <div className="scada-busbar-line" />
      <div className="scada-busbar-copy">
        <span className="scada-busbar-title">{data.label}</span>
        <span className="scada-busbar-meta">{data.subtitle}</span>
      </div>
    </div>
  )
}
