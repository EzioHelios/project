"""Versioned SCADA scene contracts for microgrid operations views."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

SCADA_SCHEMA_VERSION = 3

PortSide = Literal["top", "right", "bottom", "left"]
PortDirection = Literal["input", "output"]


def _port(
    port_id: str,
    side: PortSide,
    direction: PortDirection,
    *,
    offset: float = 0.5,
    offset_by_layout: dict[str, float] | None = None,
    voltage_level: str | None = None,
) -> dict[str, Any]:
    return {
        "id": port_id,
        "side": side,
        "direction": direction,
        "offset": offset,
        "offsetByLayout": offset_by_layout,
        "voltageLevel": voltage_level,
    }


def _through_ports(voltage_level: str) -> list[dict[str, Any]]:
    return [
        _port("in", "top", "input", voltage_level=voltage_level),
        _port("out", "bottom", "output", voltage_level=voltage_level),
    ]


def _node(
    node_id: str,
    kind: str,
    label: str,
    ports: list[dict[str, Any]],
    *,
    asset_code: str | None = None,
    meta: str | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": kind,
        "assetCode": asset_code,
        "label": label,
        "meta": meta,
        "ports": ports,
    }


def _edge(
    edge_id: str,
    source: str,
    source_port: str,
    target: str,
    target_port: str,
    *,
    asset_code: str,
    voltage_level: str,
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": source_port,
        "target": target,
        "targetHandle": target_port,
        "assetCode": asset_code,
        "kind": "electrical_feeder",
        "voltageLevel": voltage_level,
    }


def xiangtai_scada_scene() -> dict[str, Any]:
    """Return the electrically ordered, auto-layout scene for the Xiangtai demo."""
    bus_ports = [
        _port("main-in", "top", "input", offset=0.14, voltage_level="AC400V"),
        _port("pv-in", "top", "input", offset=0.38, voltage_level="AC400V"),
        _port("storage-out", "bottom", "output", offset=0.12, voltage_level="AC400V"),
        _port("charger-out", "bottom", "output", offset=0.38, voltage_level="AC400V"),
        _port("lighting-out", "bottom", "output", offset=0.64, voltage_level="AC400V"),
        _port("load-out", "bottom", "output", offset=0.90, voltage_level="AC400V"),
    ]
    nodes = [
        _node(
            "grid",
            "utility",
            "10kV市电",
            [_port("out", "bottom", "output", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="AC10kV")],
            asset_code="PCC",
            meta="公共电网",
        ),
        _node("hv-isolator", "isolator", "高压隔离开关", _through_ports("AC10kV"), meta="QS-01"),
        _node("hv-breaker", "breaker", "高压进线断路器", _through_ports("AC10kV"), meta="QF-01"),
        _node("meter", "meter", "PCC双向计量", _through_ports("AC10kV"), asset_code="PCC", meta="关口计量"),
        _node("transformer", "transformer", "10/0.4kV变压器", _through_ports("AC10kV/AC400V"), meta="SCB-1250kVA"),
        _node("lv-main-breaker", "breaker", "低压总进线", _through_ports("AC400V"), asset_code="PCC", meta="QF-02"),
        _node("main-bus", "busbar", "0.4kV主母线", bus_ports, meta="AC400V · 1250kW"),
        _node(
            "pv",
            "pv",
            "屋顶光伏",
            [_port("out", "bottom", "output", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="DC")],
            asset_code="PV-01",
            meta="600kWp DC",
        ),
        _node(
            "pv-inverter", "inverter", "光伏逆变器", _through_ports("DC/AC400V"), asset_code="PV-01", meta="500kW AC"
        ),
        _node("pv-breaker", "breaker", "光伏并网断路器", _through_ports("AC400V"), asset_code="PV-01", meta="QF-PV"),
        _node(
            "storage-breaker", "breaker", "储能馈线断路器", _through_ports("AC400V"), asset_code="BESS-01", meta="QF-ES"
        ),
        _node("pcs", "pcs", "储能变流器 PCS", _through_ports("AC400V/DC"), asset_code="BESS-01", meta="双向500kW"),
        _node(
            "bess",
            "storage",
            "储能系统",
            [_port("in", "top", "input", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="DC")],
            asset_code="BESS-01",
            meta="1000kWh",
        ),
        _node(
            "ev-breaker", "breaker", "充电馈线断路器", _through_ports("AC400V"), asset_code="EVSE-GROUP", meta="QF-EV"
        ),
        _node(
            "charger",
            "charger",
            "充电桩群",
            [_port("in", "top", "input", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="AC400V")],
            asset_code="EVSE-GROUP",
            meta="8台 · 240kW",
        ),
        _node(
            "lighting-breaker",
            "breaker",
            "照明馈线断路器",
            _through_ports("AC400V"),
            asset_code="LIGHTING",
            meta="QF-LT",
        ),
        _node(
            "lighting",
            "lighting",
            "仓库照明",
            [_port("in", "top", "input", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="AC400V")],
            asset_code="LIGHTING",
            meta="最低服务44kW",
        ),
        _node(
            "load-breaker", "breaker", "作业负荷断路器", _through_ports("AC400V"), asset_code="WAREHOUSE", meta="QF-WH"
        ),
        _node(
            "load",
            "load",
            "仓储作业负荷",
            [_port("in", "top", "input", offset_by_layout={"TB": 0.214, "LR": 0.5}, voltage_level="AC400V")],
            asset_code="WAREHOUSE",
            meta="仓储作业母线",
        ),
    ]
    edges = [
        _edge("grid-hv-isolator", "grid", "out", "hv-isolator", "in", asset_code="PCC", voltage_level="AC10kV"),
        _edge(
            "hv-isolator-breaker", "hv-isolator", "out", "hv-breaker", "in", asset_code="PCC", voltage_level="AC10kV"
        ),
        _edge("hv-breaker-meter", "hv-breaker", "out", "meter", "in", asset_code="PCC", voltage_level="AC10kV"),
        _edge("meter-transformer", "meter", "out", "transformer", "in", asset_code="PCC", voltage_level="AC10kV"),
        _edge(
            "transformer-lv-main",
            "transformer",
            "out",
            "lv-main-breaker",
            "in",
            asset_code="PCC",
            voltage_level="AC400V",
        ),
        _edge("lv-main-bus", "lv-main-breaker", "out", "main-bus", "main-in", asset_code="PCC", voltage_level="AC400V"),
        _edge("pv-inverter", "pv", "out", "pv-inverter", "in", asset_code="PV-01", voltage_level="DC"),
        _edge(
            "inverter-pv-breaker", "pv-inverter", "out", "pv-breaker", "in", asset_code="PV-01", voltage_level="AC400V"
        ),
        _edge("pv-breaker-bus", "pv-breaker", "out", "main-bus", "pv-in", asset_code="PV-01", voltage_level="AC400V"),
        _edge(
            "bus-storage-breaker",
            "main-bus",
            "storage-out",
            "storage-breaker",
            "in",
            asset_code="BESS-01",
            voltage_level="AC400V",
        ),
        _edge(
            "storage-breaker-pcs", "storage-breaker", "out", "pcs", "in", asset_code="BESS-01", voltage_level="AC400V"
        ),
        _edge("pcs-bess", "pcs", "out", "bess", "in", asset_code="BESS-01", voltage_level="DC"),
        _edge(
            "bus-ev-breaker",
            "main-bus",
            "charger-out",
            "ev-breaker",
            "in",
            asset_code="EVSE-GROUP",
            voltage_level="AC400V",
        ),
        _edge(
            "ev-breaker-charger", "ev-breaker", "out", "charger", "in", asset_code="EVSE-GROUP", voltage_level="AC400V"
        ),
        _edge(
            "bus-lighting-breaker",
            "main-bus",
            "lighting-out",
            "lighting-breaker",
            "in",
            asset_code="LIGHTING",
            voltage_level="AC400V",
        ),
        _edge(
            "lighting-breaker-load",
            "lighting-breaker",
            "out",
            "lighting",
            "in",
            asset_code="LIGHTING",
            voltage_level="AC400V",
        ),
        _edge(
            "bus-load-breaker",
            "main-bus",
            "load-out",
            "load-breaker",
            "in",
            asset_code="WAREHOUSE",
            voltage_level="AC400V",
        ),
        _edge("load-breaker-load", "load-breaker", "out", "load", "in", asset_code="WAREHOUSE", voltage_level="AC400V"),
    ]
    return {
        "schemaVersion": SCADA_SCHEMA_VERSION,
        "canvas": {"width": 1440, "height": 1020},
        "layout": {
            "algorithm": "dagre",
            "direction": "TB",
            "rankSeparation": 80,
            "nodeSeparation": 34,
            "edgeSeparation": 18,
        },
        "nodes": nodes,
        "edges": edges,
    }


def validate_scada_scene(scene: dict[str, Any]) -> list[str]:
    """Return endpoint and port-reference errors for a SCADA scene."""
    nodes = {node.get("id"): node for node in scene.get("nodes", [])}
    ports = {node_id: {port.get("id") for port in node.get("ports", [])} for node_id, node in nodes.items()}
    errors: list[str] = []
    for edge in scene.get("edges", []):
        edge_id = edge.get("id", "unknown")
        source = edge.get("source")
        target = edge.get("target")
        if source not in nodes:
            errors.append(f"{edge_id}: unknown source {source}")
        elif edge.get("sourceHandle") not in ports[source]:
            errors.append(f"{edge_id}: unknown source port {edge.get('sourceHandle')}")
        if target not in nodes:
            errors.append(f"{edge_id}: unknown target {target}")
        elif edge.get("targetHandle") not in ports[target]:
            errors.append(f"{edge_id}: unknown target port {edge.get('targetHandle')}")
    return errors


def normalize_scada_scene(topology: dict[str, Any], *, site_code: str) -> dict[str, Any]:
    """Upgrade legacy topology JSON without mutating the persisted scene."""
    if int(topology.get("schemaVersion", 0) or 0) >= SCADA_SCHEMA_VERSION:
        return deepcopy(topology)
    if site_code == "xiangtai-taizhou":
        return xiangtai_scada_scene()

    result = deepcopy(topology)
    result["schemaVersion"] = SCADA_SCHEMA_VERSION
    result.setdefault("canvas", {"width": 960, "height": 720})
    result.setdefault(
        "layout",
        {"algorithm": "dagre", "direction": "TB", "rankSeparation": 72, "nodeSeparation": 30},
    )
    for node in result.get("nodes", []):
        node.setdefault("kind", "asset" if node.get("assetCode") else "busbar")
        node.setdefault("ports", _through_ports("unknown"))
    for index, edge in enumerate(result.get("edges", [])):
        edge.setdefault("id", f"edge-{index + 1}")
        edge.setdefault("kind", "electrical_feeder")
        edge.setdefault("sourceHandle", "out")
        edge.setdefault("targetHandle", "in")
    return result
