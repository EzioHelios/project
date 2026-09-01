from __future__ import annotations

from app.db import models as m
from app.domain.analytics.controllers.operations import EnergyOperationsCompatibilityController


def make_controller() -> EnergyOperationsCompatibilityController:
    return EnergyOperationsCompatibilityController.__new__(EnergyOperationsCompatibilityController)


def test_mobile_alert_id_parser_accepts_alarm_and_video_ids() -> None:
    controller = make_controller()

    assert controller._split_alert_id("alarm:12") == ("alarm", 12)
    assert controller._split_alert_id("video:8") == ("video", 8)
    assert controller._split_alert_id("alarm:not-number") is None
    assert controller._split_alert_id("other:1") is None


def test_alarm_status_label_maps_mobile_action_states() -> None:
    assert EnergyOperationsCompatibilityController._alarm_status_label(m.AlarmEvent(is_handle=True)) == "已处理"
    assert EnergyOperationsCompatibilityController._alarm_status_label(m.AlarmEvent(status="acknowledged")) == "已确认"
    assert EnergyOperationsCompatibilityController._alarm_status_label(m.AlarmEvent(status="work_order")) == "已转工单"
    assert EnergyOperationsCompatibilityController._alarm_status_label(m.AlarmEvent(status="processing")) == "处理中"
    assert EnergyOperationsCompatibilityController._alarm_status_label(m.AlarmEvent(status="open")) == "待处理"


def test_mobile_work_order_is_derived_from_operational_alert() -> None:
    controller = make_controller()
    alert = {
        "id": "alarm:15",
        "source": "alarm",
        "record_id": 15,
        "alert_type": "用能告警",
        "severity": "high",
        "title": "照明回路用电波动",
        "area_name": "总装仓储区",
        "object_name": "照明回路电表",
        "status": "待处理",
        "occurred_at": "2026-09-01T10:00:00",
        "description": "超过阈值",
    }

    work_order = controller._to_work_order(alert)

    assert work_order["id"] == "wo:alarm:15"
    assert work_order["source_alert_id"] == "alarm:15"
    assert work_order["task_type"] == "能耗异常处置"
    assert work_order["priority"] == "高"
    assert work_order["status"] == "待分派"
    assert "提交处理结果" in work_order["actions"]


def test_mobile_work_order_status_follows_alert_lifecycle() -> None:
    controller = make_controller()

    assert controller._work_order_status({"status": "已处理", "record_id": 1}) == "已完成"
    assert controller._work_order_status({"status": "已确认", "record_id": 1}) == "待接单"
    assert controller._work_order_status({"status": "已转工单", "record_id": 1}) == "待接单"
    assert controller._work_order_status({"status": "处理中", "record_id": 1}) == "处理中"
    assert controller._work_order_status({"status": "待处理", "record_id": 2}) == "待接单"
    assert controller._work_order_status({"status": "待处理", "record_id": 3}) == "待分派"
