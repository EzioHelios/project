import { describe, expect, test } from "vitest"
import { getScadaNodeDimensions } from "@/components/microgrid/scada/scada-layout"
import { createScadaRuntimeModel } from "@/components/microgrid/scada/scada-scene-adapter"
import type { MicrogridAsset, MicrogridTopology } from "@/lib/api/hooks/microgrid"

const storage: MicrogridAsset = {
  id: 1,
  siteId: 1,
  code: "BESS-01",
  name: "储能系统",
  assetType: "storage",
  ratedPowerKw: 500,
  ratedEnergyKwh: 1000,
  controllable: true,
  parameters: {},
  sourceKind: "enterprise_assumption",
  sourceName: "祥泰演示",
  confidenceLevel: 0.5,
  online: true,
  operatingMode: "shadow",
  activePowerKw: -72,
  socPct: 52,
  temperatureC: 31.4,
  alarmLevel: "normal",
  observedAt: "2026-08-12T08:00:00+08:00",
  stateSourceKind: "simulated",
}

describe("SCADA scene adapter", () => {
  test("uses a compact horizontal geometry that remains legible in the admin workbench", () => {
    expect(getScadaNodeDimensions("busbar", "LR")).toEqual({ width: 64, height: 600 })
    expect(getScadaNodeDimensions("breaker", "LR")).toEqual({ width: 78, height: 112 })
    expect(getScadaNodeDimensions("utility", "LR")).toEqual({ width: 160, height: 112 })
  })

  test("maps topology nodes to readonly runtime nodes", () => {
    const topology: MicrogridTopology = {
      configured: true,
      nodes: [{ id: "bess", kind: "storage", assetCode: "BESS-01", label: "储能系统", x: 10, y: 20 }],
      edges: [],
      assets: [storage],
    }
    const model = createScadaRuntimeModel(topology)
    expect(model.nodes[0]).toMatchObject({ id: "bess", type: "scadaAsset", draggable: false, connectable: false })
    expect(model.nodes[0]?.data).toMatchObject({ statusLabel: "充电", tone: "simulated" })
  })

  test("uses the storage power sign to animate flow direction", () => {
    const topology: MicrogridTopology = {
      configured: true,
      nodes: [
        { id: "bus", kind: "busbar", label: "主母线", x: 0, y: 0 },
        { id: "bess", kind: "storage", assetCode: "BESS-01", label: "储能系统", x: 100, y: 0 },
      ],
      edges: [{ id: "bus-bess", source: "bus", target: "bess", assetCode: "BESS-01" }],
      assets: [storage],
    }
    expect(createScadaRuntimeModel(topology).edges[0]?.data?.reverse).toBe(false)
    expect(createScadaRuntimeModel({ ...topology, assets: [{ ...storage, activePowerKw: 90 }] }).edges[0]?.data?.reverse).toBe(true)
  })

  test("auto-layouts topology and preserves explicit electrical terminals", () => {
    const topology: MicrogridTopology = {
      configured: true,
      layout: { algorithm: "dagre", direction: "TB" },
      nodes: [
        { id: "bus", kind: "busbar", label: "主母线", ports: [{ id: "storage-out", side: "bottom", direction: "output", offset: 0.2 }] },
        { id: "bess", kind: "storage", assetCode: "BESS-01", label: "储能系统", ports: [{ id: "in", side: "top", direction: "input" }] },
      ],
      edges: [{ id: "bus-bess", source: "bus", sourceHandle: "storage-out", target: "bess", targetHandle: "in", assetCode: "BESS-01" }],
      assets: [storage],
    }
    const model = createScadaRuntimeModel(topology)
    const bus = model.nodes.find((node) => node.id === "bus")
    const bess = model.nodes.find((node) => node.id === "bess")

    expect(model.edges[0]).toMatchObject({ sourceHandle: "storage-out", targetHandle: "in" })
    expect(bus?.data.ports[0]).toMatchObject({ id: "storage-out", side: "bottom", offset: 0.2 })
    expect((bess?.position.y ?? 0) > (bus?.position.y ?? 0)).toBe(true)
  })

  test("rotates terminal sides and uses layout-specific offsets in LR mode", () => {
    const topology: MicrogridTopology = {
      configured: true,
      layout: { algorithm: "dagre", direction: "TB" },
      nodes: [
        {
          id: "bus",
          kind: "busbar",
          label: "主母线",
          ports: [{ id: "storage-out", side: "bottom", direction: "output", offset: 0.2 }],
        },
        {
          id: "bess",
          kind: "storage",
          assetCode: "BESS-01",
          label: "储能系统",
          ports: [{ id: "in", side: "top", direction: "input", offset: 0.2, offsetByLayout: { TB: 0.214, LR: 0.5 } }],
        },
      ],
      edges: [{ id: "bus-bess", source: "bus", sourceHandle: "storage-out", target: "bess", targetHandle: "in", assetCode: "BESS-01" }],
      assets: [storage],
    }
    const model = createScadaRuntimeModel(topology, { direction: "LR" })
    const bus = model.nodes.find((node) => node.id === "bus")
    const bess = model.nodes.find((node) => node.id === "bess")

    expect(bus?.data.ports[0]).toMatchObject({ side: "right", offset: 0.2 })
    expect(bess?.data.ports[0]).toMatchObject({ side: "left", offset: 0.5 })
    expect((bess?.position.x ?? 0) > (bus?.position.x ?? 0)).toBe(true)
    const busAnchorY = (bus?.position.y ?? 0) + 0.2 * Number(bus?.style?.height)
    const bessAnchorY = (bess?.position.y ?? 0) + 0.5 * Number(bess?.style?.height)
    expect(busAnchorY).toBeCloseTo(bessAnchorY, 6)
  })
})
