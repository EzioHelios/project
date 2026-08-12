import { type EdgeProps, getSmoothStepPath } from "@xyflow/react"
import { cn } from "@/lib/utils"
import type { ScadaRuntimeEdge } from "./types"

export function ScadaFeederEdge({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<ScadaRuntimeEdge>) {
  const [path] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 2, offset: 14 })
  return (
    <g className={cn("scada-feeder", `is-${data?.tone ?? "normal"}`, data?.energized && "is-energized", data?.reverse && "is-reverse")}>
      <path className="scada-feeder-base" d={path} />
      {data?.energized && Math.abs(data.powerKw ?? 0) > 0.1 && <path className="scada-feeder-flow" d={path} />}
    </g>
  )
}
