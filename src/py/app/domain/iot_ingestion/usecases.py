"""Application workflows for durable MQTT ingestion and metering projection."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from sqlalchemy import select

from app.db import models as m
from app.domain.iot_ingestion.domain import (
    ParsedPoint,
    PayloadValidationError,
    parse_szscada_scada_v1,
    payload_hash,
    temporary_equipment_code,
    temporary_external_device_id,
    temporary_meter_address,
)
from app.domain.metering.reading_facts import (
    SZSCADA_TAG_TO_POINT,
    MeterReadingFactInput,
    MeterReadingFactWriter,
    point_spec,
)
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ERR_SUBSCRIPTION_MISMATCH = "MQTT subscription does not match its data source."
ERR_MESSAGE_MISSING = "MQTT inbound message does not exist."
ERR_SUBSCRIPTION_MISSING = "MQTT subscription does not exist."
ERR_BINDING_EQUIPMENT_MISSING = "MQTT device binding does not have a platform device."


class MqttIngestionUseCase:
    """Receives durable protocol-neutral messages and dispatches configured projections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def receive_message(
        self,
        *,
        source_id: int,
        subscription_id: int,
        topic: str,
        payload: dict[str, Any],
    ) -> tuple[m.MqttInboundMessage, bool]:
        """Persist a raw message once before any parser or projection runs."""
        team_id = self._require_team_id()
        source = await self._session.get(m.MqttDataSource, source_id)
        subscription = await self._session.get(m.MqttSubscription, subscription_id)
        if source is None or source.team_id != team_id:
            raise PermissionDeniedException(detail="MQTT 数据源不属于当前企业租户。")
        if subscription is None or subscription.source_id != source_id or subscription.team_id != team_id:
            raise ValueError(ERR_SUBSCRIPTION_MISMATCH)

        digest = payload_hash(payload)
        existing = await self._session.scalar(
            select(m.MqttInboundMessage).where(
                m.MqttInboundMessage.source_id == source_id,
                m.MqttInboundMessage.payload_hash == digest,
            )
        )
        if existing is not None:
            return existing, False

        message = m.MqttInboundMessage(
            source_id=source_id,
            subscription_id=subscription_id,
            topic=topic,
            payload=payload,
            payload_hash=digest,
            contract_version=subscription.contract_version,
            status="received",
        )
        self._session.add(message)
        await self._session.commit()
        await self._session.refresh(message)
        return message, True

    async def process_message(self, message_id: int) -> m.MqttInboundMessage:
        """Parse and project one previously persisted message. Retry-safe through source-message uniqueness."""
        message = await self._session.get(m.MqttInboundMessage, message_id)
        if message is None:
            raise ValueError(ERR_MESSAGE_MISSING)
        if message.status == "processed":
            return message
        self._require_team_id()

        subscription = await self._session.get(m.MqttSubscription, message.subscription_id)
        if subscription is None:
            raise ValueError(ERR_SUBSCRIPTION_MISSING)
        if subscription.parser_code != "szscada_scada_v1":
            message.status = "rejected"
            message.error_code = "unsupported_parser"
            message.error_detail = f"unsupported parser: {subscription.parser_code}"
            await self._session.commit()
            return message

        message.dispatch_attempts += 1
        try:
            await self._process_szscada_metering(message, subscription)
            message.status = "processed"
            message.error_code = None
            message.error_detail = None
            message.processed_at = datetime.now(UTC).replace(tzinfo=None)
            await self._session.commit()
        except PayloadValidationError as exc:
            message.status = "rejected"
            message.error_code = "payload_validation"
            message.error_detail = str(exc)
            await self._session.commit()
        except ValueError as exc:
            message.status = "rejected"
            message.error_code = "projection_config"
            message.error_detail = str(exc)
            await self._session.commit()
        return message

    async def _process_szscada_metering(self, message: m.MqttInboundMessage, subscription: m.MqttSubscription) -> None:
        parsed = parse_szscada_scada_v1(message.payload)
        message.published_at = parsed.published_at
        points_by_meter: dict[int, list[ParsedPoint]] = defaultdict(list)
        for point in parsed.points:
            points_by_meter[point.meter_number].append(point)

        for meter_number, points in points_by_meter.items():
            binding = await self._resolve_binding(
                subscription=subscription,
                gateway_key=parsed.gateway_key,
                meter_number=meter_number,
            )
            await self._project_meter_points(
                message=message,
                binding=binding,
                points=points,
                reading_time=parsed.published_at,
            )

    async def _resolve_binding(
        self,
        *,
        subscription: m.MqttSubscription,
        gateway_key: str,
        meter_number: int,
    ) -> m.MqttDeviceBinding:
        meter_key = f"m{meter_number:03d}"
        binding = await self._session.scalar(
            select(m.MqttDeviceBinding).where(
                m.MqttDeviceBinding.subscription_id == subscription.id,
                m.MqttDeviceBinding.gateway_key == gateway_key,
                m.MqttDeviceBinding.meter_key == meter_key,
            )
        )
        if binding is not None:
            if binding.equipment_id is None:
                binding.equipment_id = await self._create_temporary_equipment(
                    gateway_key, meter_number, binding.external_device_id
                )
                await self._session.flush()
            return binding

        external_device_id = temporary_external_device_id(gateway_key, meter_number)
        equipment_id = await self._create_temporary_equipment(gateway_key, meter_number, external_device_id)
        binding = m.MqttDeviceBinding(
            subscription_id=subscription.id,
            gateway_key=gateway_key,
            meter_key=meter_key,
            selector_name_pattern=rf"^{meter_number}号电表",
            equipment_id=equipment_id,
            external_device_id=external_device_id,
            temporary_address=temporary_meter_address(gateway_key, meter_number),
            identity_status="temporary",
            scaling_mode="upstream_scaled",
            multiplier=Decimal(1),
        )
        self._session.add(binding)
        await self._session.flush()
        return binding

    async def _create_temporary_equipment(self, gateway_key: str, meter_number: int, external_device_id: str) -> int:
        code = temporary_equipment_code(gateway_key, meter_number)
        equipment = await self._session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.code == code))
        if equipment is not None:
            return equipment.id
        equipment = m.MonitorEquipment(
            code=code,
            name=f"SZSCADA 临时电表 {meter_number}",
            external_device_id=external_device_id,
            category=0,
            supplier="szscada",
            protocol="mqtt",
            data_acquisition_method="mqtt",
            status=0,
            is_enable=True,
        )
        self._session.add(equipment)
        await self._session.flush()
        return equipment.id

    async def _project_meter_points(
        self,
        *,
        message: m.MqttInboundMessage,
        binding: m.MqttDeviceBinding,
        points: list[ParsedPoint],
        reading_time: datetime,
    ) -> None:
        if binding.equipment_id is None:  # pragma: no cover - guarded by _resolve_binding.
            raise ValueError(ERR_BINDING_EQUIPMENT_MISSING)
        writer = MeterReadingFactWriter(self._session)
        readings: list[MeterReadingFactInput] = []
        for point in points:
            mapping = await self._resolve_mapping(binding, point)
            normalized_value = point.numeric_value * mapping.multiplier if point.numeric_value is not None else None
            readings.append(
                MeterReadingFactInput(
                    source_system="mqtt_szscada",
                    source_record_id=f"mqtt:{message.id}:{binding.id}:{point.source_tag}",
                    source_message_id=message.id,
                    binding_id=binding.id,
                    equipment_id=binding.equipment_id,
                    source_point_code=point.source_tag,
                    source_point_name=point.source_name,
                    point_code=mapping.point_code,
                    point_name=mapping.point_name,
                    raw_value=point.raw_value,
                    normalized_value=normalized_value,
                    unit=mapping.unit,
                    quality_status="valid" if point.is_valid else "invalid",
                    source_type=point.source_type,
                    reading_time=reading_time,
                    mapping_version=mapping.mapping_version,
                )
            )
        await writer.write_many(readings)

    async def _resolve_mapping(self, binding: m.MqttDeviceBinding, point: ParsedPoint) -> m.MqttPointMapping:
        mapping = await self._session.scalar(
            select(m.MqttPointMapping)
            .where(
                m.MqttPointMapping.binding_id == binding.id,
                m.MqttPointMapping.source_tag == point.source_tag,
                m.MqttPointMapping.enabled.is_(True),
            )
            .order_by(m.MqttPointMapping.id.desc())
        )
        if mapping is not None:
            return mapping
        point_code = SZSCADA_TAG_TO_POINT.get(point.source_tag)
        if point_code is None:
            msg = f"未配置 SZSCADA 点位映射: {point.source_tag}"
            raise PayloadValidationError(msg)
        spec = point_spec(point_code)
        mapping = m.MqttPointMapping(
            binding_id=binding.id,
            source_tag=point.source_tag,
            source_name_suffix=point.source_label,
            point_code=point_code,
            point_name=spec.point_name,
            unit=spec.unit,
            multiplier=Decimal(1),
            mapping_version="v1",
            enabled=True,
        )
        self._session.add(mapping)
        await self._session.flush()
        return mapping

    def _require_team_id(self) -> Any:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            raise PermissionDeniedException(detail="MQTT 接入写入需要明确的数据源企业租户。")
        return team_id
