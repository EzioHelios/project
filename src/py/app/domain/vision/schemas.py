"""Validated camera and recognition contracts."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CameraRecognitionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enabled: bool = False
    rtsp_url: str = Field(default="", max_length=1000)
    playback_path: str = Field(default="", max_length=200, pattern=r"^(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?$")
    area_id: int | None = None
    equipment_id: int | None = None
    equipment_type: Literal["forklift"] = "forklift"
    task_ref: str = Field(default="", max_length=64)
    operation_type: Literal["inbound_putaway", "outbound_picking", "internal_transfer", "loading_unloading"] = (
        "internal_transfer"
    )
    material_code: str = Field(default="", max_length=64)
    material_name: str = Field(default="", max_length=128)
    batch_no: str = Field(default="", max_length=64)
    quantity: float = Field(default=1, gt=0, allow_inf_nan=False)
    unit: str = Field(default="pcs", min_length=1, max_length=16)
    weight_kg: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    exclusive_equipment: bool = False
    demo_source: bool = False
    confidence_threshold: float = Field(default=0.5, ge=0.1, le=1)
    movement_threshold: float = Field(default=12, gt=0, le=640)
    history_seconds: float = Field(default=1, ge=0.2, le=10)
    idle_seconds: float = Field(default=1, ge=0.2, le=10)
    lost_seconds: float = Field(default=2, ge=0.5, le=30)
    min_duration_seconds: float = Field(default=1, ge=0.2, le=60)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_source(self) -> CameraRecognitionConfig:
        if self.enabled and (urlsplit(self.rtsp_url).scheme != "rtsp" or not urlsplit(self.rtsp_url).hostname):
            msg = "启用识别前请填写有效的 RTSP 视频源"
            raise ValueError(msg)
        return self


class RecognitionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_key: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=64)
    track_id: int = Field(ge=0)
    started_at: datetime
    ended_at: datetime
    duration_seconds: float = Field(gt=0, le=86400, allow_inf_nan=False)
    confidence: float = Field(ge=0, le=1)
    end_reason: Literal["idle", "left_scene", "stream_end", "config_changed", "stopped"]
    single_subject: bool
    model_version: str = Field(min_length=1, max_length=128)
    config_revision: int = Field(ge=1)
    evidence_jpeg: str | None = Field(default=None, max_length=600000)

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "识别时间必须包含时区"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def valid_interval(self) -> RecognitionEvent:
        span = (self.ended_at - self.started_at).total_seconds()
        if span <= 0 or self.duration_seconds > span + 0.1:
            msg = "有效作业时长不能超过起止时间"
            raise ValueError(msg)
        return self


class RecognitionHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    config_revision: int
    status: Literal["running", "stopped", "error"]
    timestamp: datetime
    detected_count: int = Field(ge=0, le=1000)
    working_count: int = Field(ge=0, le=1000)
    frames_processed: int = Field(ge=0)
    model_version: str = Field(max_length=128)
    message: str = Field(default="", max_length=300)
    preview_jpeg: str | None = Field(default=None, max_length=600000)
