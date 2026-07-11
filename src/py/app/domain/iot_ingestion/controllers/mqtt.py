"""Tenant-scoped administration APIs for heterogeneous MQTT ingestion."""
# ruff: noqa: EM101, EM102, PLR2004, TRY003, TRY004

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from litestar import Controller, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.energy.controllers._utils import model_to_dict, ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MQTT_BODY = Body()
SUPPORTED_PARSER_CODES = {"szscada_scada_v1"}
SOURCE_FIELDS = {
    "code",
    "name",
    "broker_host",
    "broker_port",
    "username_env",
    "password_env",
    "client_id",
    "tls_enabled",
    "enabled",
}
SUBSCRIPTION_FIELDS = {
    "source_id",
    "topic_filter",
    "parser_code",
    "contract_version",
    "qos",
    "expected_interval_seconds",
    "enabled",
}
BINDING_FIELDS = {
    "subscription_id",
    "gateway_key",
    "meter_key",
    "selector_name_pattern",
    "equipment_id",
    "external_device_id",
    "temporary_address",
    "identity_status",
    "scaling_mode",
    "multiplier",
}
MAPPING_FIELDS = {
    "binding_id",
    "source_tag",
    "source_name_suffix",
    "point_code",
    "point_name",
    "unit",
    "multiplier",
    "mapping_version",
    "enabled",
}


class MqttIngestionConfigurationController(Controller):
    """Manage MQTT source contracts without persisting broker secrets in application data."""

    tags = ["MQTT Ingestion"]

    @get("/api/iot-ingestion/mqtt-sources", guards=[requires_superuser])
    async def list_sources(self, db_session: AsyncSession, limit: int = 100, offset: int = 0) -> Response[dict]:
        return Response(content=ok_data(await _list_models(db_session, m.MqttDataSource, limit, offset)))

    @post("/api/iot-ingestion/mqtt-sources", guards=[requires_superuser])
    async def create_source(self, db_session: AsyncSession, data: dict[str, Any] = MQTT_BODY) -> Response[dict]:
        try:
            payload = _source_payload(data, creating=True)
        except ValueError as exc:
            return _bad_request(exc)
        obj = m.MqttDataSource(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/iot-ingestion/mqtt-sources/{source_id:int}", guards=[requires_superuser])
    async def update_source(
        self, db_session: AsyncSession, source_id: int, data: dict[str, Any] = MQTT_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.MqttDataSource, source_id)
        if obj is None:
            return _not_found("MQTT 数据源不存在")
        try:
            _assign(obj, _source_payload(data, creating=False))
        except ValueError as exc:
            return _bad_request(exc)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/iot-ingestion/mqtt-subscriptions", guards=[requires_superuser])
    async def list_subscriptions(
        self, db_session: AsyncSession, source_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> Response[dict]:
        statement = select(m.MqttSubscription)
        if source_id is not None:
            statement = statement.where(m.MqttSubscription.source_id == source_id)
        return Response(
            content=ok_data(await _list_statement(db_session, statement, m.MqttSubscription, limit, offset))
        )

    @post("/api/iot-ingestion/mqtt-subscriptions", guards=[requires_superuser])
    async def create_subscription(self, db_session: AsyncSession, data: dict[str, Any] = MQTT_BODY) -> Response[dict]:
        try:
            payload = _subscription_payload(data, creating=True)
            await _require_source(db_session, payload["source_id"])
        except ValueError as exc:
            return _bad_request(exc)
        obj = m.MqttSubscription(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/iot-ingestion/mqtt-subscriptions/{subscription_id:int}", guards=[requires_superuser])
    async def update_subscription(
        self, db_session: AsyncSession, subscription_id: int, data: dict[str, Any] = MQTT_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.MqttSubscription, subscription_id)
        if obj is None:
            return _not_found("MQTT 订阅不存在")
        try:
            payload = _subscription_payload(data, creating=False)
            if "source_id" in payload:
                await _require_source(db_session, payload["source_id"])
            _assign(obj, payload)
        except ValueError as exc:
            return _bad_request(exc)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/iot-ingestion/mqtt-device-bindings", guards=[requires_superuser])
    async def list_bindings(
        self, db_session: AsyncSession, subscription_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> Response[dict]:
        statement = select(m.MqttDeviceBinding)
        if subscription_id is not None:
            statement = statement.where(m.MqttDeviceBinding.subscription_id == subscription_id)
        return Response(
            content=ok_data(await _list_statement(db_session, statement, m.MqttDeviceBinding, limit, offset))
        )

    @post("/api/iot-ingestion/mqtt-device-bindings", guards=[requires_superuser])
    async def create_binding(self, db_session: AsyncSession, data: dict[str, Any] = MQTT_BODY) -> Response[dict]:
        try:
            payload = _binding_payload(data, creating=True)
            await _require_subscription(db_session, payload["subscription_id"])
        except ValueError as exc:
            return _bad_request(exc)
        obj = m.MqttDeviceBinding(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/iot-ingestion/mqtt-device-bindings/{binding_id:int}", guards=[requires_superuser])
    async def update_binding(
        self, db_session: AsyncSession, binding_id: int, data: dict[str, Any] = MQTT_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.MqttDeviceBinding, binding_id)
        if obj is None:
            return _not_found("MQTT 设备绑定不存在")
        try:
            payload = _binding_payload(data, creating=False)
            if "subscription_id" in payload:
                await _require_subscription(db_session, payload["subscription_id"])
            _assign(obj, payload)
        except ValueError as exc:
            return _bad_request(exc)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/iot-ingestion/mqtt-point-mappings", guards=[requires_superuser])
    async def list_mappings(
        self, db_session: AsyncSession, binding_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> Response[dict]:
        statement = select(m.MqttPointMapping)
        if binding_id is not None:
            statement = statement.where(m.MqttPointMapping.binding_id == binding_id)
        return Response(
            content=ok_data(await _list_statement(db_session, statement, m.MqttPointMapping, limit, offset))
        )

    @post("/api/iot-ingestion/mqtt-point-mappings", guards=[requires_superuser])
    async def create_mapping(self, db_session: AsyncSession, data: dict[str, Any] = MQTT_BODY) -> Response[dict]:
        try:
            payload = _mapping_payload(data, creating=True)
            await _require_binding(db_session, payload["binding_id"])
        except ValueError as exc:
            return _bad_request(exc)
        obj = m.MqttPointMapping(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/iot-ingestion/mqtt-point-mappings/{mapping_id:int}", guards=[requires_superuser])
    async def update_mapping(
        self, db_session: AsyncSession, mapping_id: int, data: dict[str, Any] = MQTT_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.MqttPointMapping, mapping_id)
        if obj is None:
            return _not_found("MQTT 点位映射不存在")
        try:
            payload = _mapping_payload(data, creating=False)
            if "binding_id" in payload:
                await _require_binding(db_session, payload["binding_id"])
            _assign(obj, payload)
        except ValueError as exc:
            return _bad_request(exc)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/iot-ingestion/mqtt-messages", guards=[requires_superuser])
    async def list_messages(
        self,
        db_session: AsyncSession,
        source_id: int | None = None,
        subscription_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        statement = select(m.MqttInboundMessage)
        if source_id is not None:
            statement = statement.where(m.MqttInboundMessage.source_id == source_id)
        if subscription_id is not None:
            statement = statement.where(m.MqttInboundMessage.subscription_id == subscription_id)
        if status is not None:
            statement = statement.where(m.MqttInboundMessage.status == status)
        data = await _list_statement(db_session, statement, m.MqttInboundMessage, limit, offset)
        for row in data["items"]:
            row.pop("payload", None)
        return Response(content=ok_data(data))


async def _list_models(db_session: AsyncSession, model: type[Any], limit: int, offset: int) -> dict[str, Any]:
    return await _list_statement(db_session, select(model), model, limit, offset)


async def _list_statement(
    db_session: AsyncSession, statement: Any, model: type[Any], limit: int, offset: int
) -> dict[str, Any]:
    limited = max(1, min(limit, 200))
    safe_offset = max(offset, 0)
    total = await db_session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = (await db_session.scalars(statement.order_by(model.id.desc()).offset(safe_offset).limit(limited))).all()
    return {"items": [model_to_dict(row) for row in rows], "total": total or 0, "limit": limited, "offset": safe_offset}


def _source_payload(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    payload = _allowed(data, SOURCE_FIELDS)
    if creating:
        _require(payload, "code", "name", "broker_host", "client_id")
    if "broker_port" in payload:
        payload["broker_port"] = _positive_int(payload["broker_port"], "broker_port")
    return payload


def _subscription_payload(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    payload = _allowed(data, SUBSCRIPTION_FIELDS)
    if creating:
        _require(payload, "source_id", "topic_filter", "parser_code")
    if "source_id" in payload:
        payload["source_id"] = _positive_int(payload["source_id"], "source_id")
    if "parser_code" in payload and payload["parser_code"] not in SUPPORTED_PARSER_CODES:
        raise ValueError(f"parser_code must be one of: {', '.join(sorted(SUPPORTED_PARSER_CODES))}")
    if "qos" in payload:
        payload["qos"] = _positive_int(payload["qos"], "qos", allow_zero=True)
        if payload["qos"] > 2:
            raise ValueError("qos must be 0, 1, or 2")
    if "expected_interval_seconds" in payload:
        payload["expected_interval_seconds"] = _positive_int(
            payload["expected_interval_seconds"], "expected_interval_seconds"
        )
    return payload


def _binding_payload(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    payload = _allowed(data, BINDING_FIELDS)
    if creating:
        _require(
            payload,
            "subscription_id",
            "gateway_key",
            "meter_key",
            "selector_name_pattern",
            "external_device_id",
            "temporary_address",
        )
    if "subscription_id" in payload:
        payload["subscription_id"] = _positive_int(payload["subscription_id"], "subscription_id")
    if "equipment_id" in payload and payload["equipment_id"] is not None:
        payload["equipment_id"] = _positive_int(payload["equipment_id"], "equipment_id")
    if "multiplier" in payload:
        payload["multiplier"] = _decimal(payload["multiplier"], "multiplier")
    return payload


def _mapping_payload(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    payload = _allowed(data, MAPPING_FIELDS)
    if creating:
        _require(payload, "binding_id", "source_tag", "point_code")
    if "binding_id" in payload:
        payload["binding_id"] = _positive_int(payload["binding_id"], "binding_id")
    if "multiplier" in payload:
        payload["multiplier"] = _decimal(payload["multiplier"], "multiplier")
    return payload


def _allowed(data: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("request body must be an object")
    return {key: value for key, value in data.items() if key in fields and value is not None}


def _require(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if not str(payload.get(field, "")).strip()]
    if missing:
        raise ValueError(f"required fields: {', '.join(missing)}")


def _positive_int(value: Any, field: str, *, allow_zero: bool = False) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"{field} must be positive")
    return result


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for field, value in payload.items():
        setattr(obj, field, value)


async def _require_source(db_session: AsyncSession, source_id: int) -> m.MqttDataSource:
    source = await db_session.get(m.MqttDataSource, source_id)
    if source is None:
        raise ValueError("MQTT 数据源不存在或不属于当前企业租户")
    return source


async def _require_subscription(db_session: AsyncSession, subscription_id: int) -> m.MqttSubscription:
    subscription = await db_session.get(m.MqttSubscription, subscription_id)
    if subscription is None:
        raise ValueError("MQTT 订阅不存在或不属于当前企业租户")
    return subscription


async def _require_binding(db_session: AsyncSession, binding_id: int) -> m.MqttDeviceBinding:
    binding = await db_session.get(m.MqttDeviceBinding, binding_id)
    if binding is None:
        raise ValueError("MQTT 设备绑定不存在或不属于当前企业租户")
    return binding


def _bad_request(exc: ValueError) -> Response[dict]:
    return Response(content={"code": 400, "msg": str(exc)}, status_code=400)


def _not_found(message: str) -> Response[dict]:
    return Response(content={"code": 404, "msg": message}, status_code=404)
