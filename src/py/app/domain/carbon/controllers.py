"""碳管理相关接口控制器（Litestar Controller）。

目标：
- 尽量与原 Django `dataapp.urls` / `views` 提供的 `/api/...` 路径兼容
- 逐步使用 SQLAlchemy / 视图查询来实现相同的统计与查询逻辑
"""

import datetime
import re
from collections import defaultdict
from decimal import Decimal
from statistics import median
from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter
from dateutil.relativedelta import MO, relativedelta
from litestar import Controller, Request, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService
from app.domain.carbon.deps import (
    provide_alarm_event_service,
    provide_ammeter_index_value_service,
    provide_api_result_key_mapping_service,
    provide_area_service,
    provide_carbon_audit_log_service,
    provide_device_point_service,
    provide_device_service,
    provide_device_type_service,
    provide_emission_factor_service,
    provide_employee_commute_service,
    provide_energy_storage_value_service,
    provide_energy_type_service,
    provide_enterprise_info_service,
    provide_in_money_service,
    provide_iot_telemetry_service,
    provide_monitor_equipment_service,
    provide_monitor_sector_photo_service,
    provide_monitor_sector_service,
    provide_out_money_service,
    provide_scope1_mobile_combustion_service,
    provide_scope1_refrigerant_leak_service,
    provide_scope1_stationary_combustion_service,
    provide_scope2_electricity_bill_service,
    provide_scope2_meter_aggregate_service,
    provide_scope2_purchased_energy_service,
    provide_scope3_third_party_transport_service,
    provide_scope3_waste_disposal_service,
    provide_vedio_alarm_event_service,
    provide_video_monitor_service,
    provide_warning_rule_service,
)

from . import services

# 排放因子与常量（根据 Django views.py 同步）
from .emission_calculator import compute_emission_result
from .utils import _CKYQZMJ as CKYQZMJ
from .utils import GF_CJPL_PFYZ, YD_CPFL_PFYZ, calc_day_ygtq_cpfl
from .validation import (
    CarbonValidationError,
    validate_amount_non_negative,
    validate_billing_month,
    validate_consumption,
    validate_date_not_future,
    validate_period_start_end,
)

SOURCE_KIND_REAL = "activity_data"
SOURCE_KIND_DERIVED = "meter_aggregate"
SOURCE_KIND_MANUAL_BILL = "manual_bill"
SOURCE_KIND_DEMO_SEED = "demo_seed"
SOURCE_KIND_FALLBACK = "raw_meter_fallback"
SOURCE_KIND_ESTIMATE = "historical_estimate"
DEMO_SEED_MARKER = "[demo_seed]"
DEVICE_TYPE_ID_TO_CODE = {
    1: "meter",
    2: "pv_inverter",
    3: "storage_bms",
    4: "charger",
    5: "forklift",
    6: "crane",
    7: "weighbridge",
    8: "automation_equipment",
    9: "camera",
}
DEVICE_TYPE_CODE_TO_ID = {code: identifier for identifier, code in DEVICE_TYPE_ID_TO_CODE.items()}
CATEGORY_TO_DEVICE_TYPE_ID = {0: DEVICE_TYPE_CODE_TO_ID["meter"], 1: DEVICE_TYPE_CODE_TO_ID["pv_inverter"], 2: DEVICE_TYPE_CODE_TO_ID["camera"]}
DEVICE_TYPE_ID_TO_CATEGORY = {value: key for key, value in CATEGORY_TO_DEVICE_TYPE_ID.items()}
ROOT_AREA_CODE = "ROOT"
AREA_TYPE_OPTIONS = {"site", "building", "workshop", "warehouse", "zone", "line", "station", "utility", "other"}
DEFAULT_DEVICE_POINT_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "meter": [
        {"point_code": "active_power", "point_name": "有功功率", "unit": "kW", "value_type": "float", "source_field": "active_power", "is_alarm_enabled": True},
        {"point_code": "voltage_a", "point_name": "A相电压", "unit": "V", "value_type": "float", "source_field": "voltage_a"},
        {"point_code": "current_a", "point_name": "A相电流", "unit": "A", "value_type": "float", "source_field": "current_a"},
        {"point_code": "total_energy", "point_name": "累计电量", "unit": "kWh", "value_type": "float", "source_field": "total_energy"},
    ],
    "pv_inverter": [
        {"point_code": "power_kw", "point_name": "发电功率", "unit": "kW", "value_type": "float", "source_field": "power_kw", "is_alarm_enabled": True},
        {"point_code": "daily_energy_kwh", "point_name": "日发电量", "unit": "kWh", "value_type": "float", "source_field": "daily_energy_kwh"},
        {"point_code": "cumulative_energy_kwh", "point_name": "累计发电量", "unit": "kWh", "value_type": "float", "source_field": "cumulative_energy_kwh"},
    ],
    "storage_bms": [
        {"point_code": "soc", "point_name": "SOC", "unit": "%", "value_type": "float", "source_field": "soc", "is_alarm_enabled": True},
        {"point_code": "soh", "point_name": "SOH", "unit": "%", "value_type": "float", "source_field": "soh"},
        {"point_code": "charge_power_kw", "point_name": "充电功率", "unit": "kW", "value_type": "float", "source_field": "charge_power_kw"},
        {"point_code": "discharge_power_kw", "point_name": "放电功率", "unit": "kW", "value_type": "float", "source_field": "discharge_power_kw"},
        {"point_code": "temperature_c", "point_name": "温度", "unit": "℃", "value_type": "float", "source_field": "temperature_c"},
    ],
    "charger": [
        {"point_code": "status", "point_name": "充电状态", "unit": None, "value_type": "enum", "source_field": "status", "is_alarm_enabled": True},
        {"point_code": "power_kw", "point_name": "充电功率", "unit": "kW", "value_type": "float", "source_field": "power_kw"},
        {"point_code": "session_energy_kwh", "point_name": "本次充电量", "unit": "kWh", "value_type": "float", "source_field": "session_energy_kwh"},
        {"point_code": "cumulative_energy_kwh", "point_name": "累计充电量", "unit": "kWh", "value_type": "float", "source_field": "cumulative_energy_kwh"},
    ],
}
DEFAULT_DEVICE_TYPES: tuple[dict[str, Any], ...] = (
    {"id": 1, "code": "meter", "name": "电表", "energy_type": "electricity", "is_energy_device": True, "default_protocol": "http_yunji"},
    {"id": 2, "code": "pv_inverter", "name": "光伏逆变器", "energy_type": "electricity", "is_energy_device": True, "default_protocol": "mqtt"},
    {"id": 3, "code": "storage_bms", "name": "储能 BMS", "energy_type": "electricity", "is_energy_device": True, "default_protocol": "mqtt"},
    {"id": 4, "code": "charger", "name": "充电桩", "energy_type": "electricity", "is_energy_device": True, "default_protocol": "mqtt"},
    {"id": 5, "code": "forklift", "name": "叉车", "energy_type": "diesel", "is_special_equipment": True},
    {"id": 6, "code": "crane", "name": "起重设备", "energy_type": "electricity", "is_special_equipment": True},
    {"id": 7, "code": "weighbridge", "name": "地磅", "energy_type": "electricity", "is_special_equipment": True},
    {"id": 8, "code": "automation_equipment", "name": "自动化设备", "energy_type": "electricity"},
    {"id": 9, "code": "camera", "name": "摄像头", "default_protocol": "rtsp"},
)


def _audit_request_details(request: Request[Any, Any, Any]) -> tuple[str | None, str | None]:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def _log_security_audit(
    audit_service: AuditLogService,
    request: Request[Any, Any, Any],
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    ip_address, user_agent = _audit_request_details(request)
    await audit_service.log_action(
        action=action,
        actor_id=request.user.id,
        actor_email=request.user.email,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _handle_db_view_error(_request: Any, exc: Exception) -> Response[dict[str, Any]]:
    """Handle database errors (e.g. missing views) gracefully in dashboard endpoints."""
    return Response(
        content={"code": 500, "msg": f"数据查询失败: {exc!s}", "data": None},
        status_code=200,
    )


class CarbonDashboardController(Controller):
    """碳管理大屏相关接口."""

    tags = ["Carbon"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]
    dependencies = {
        "enterprise_info_service": provide_enterprise_info_service,
        "monitor_equipment_service": provide_monitor_equipment_service,
        "api_result_key_mapping_service": provide_api_result_key_mapping_service,
        "alarm_event_service": provide_alarm_event_service,
    }

    @get(path="/api/page1/ckxxgk")
    async def get_page1_ck_information(self, enterprise_info_service: services.EnterpriseInfoService) -> Response[dict]:
        db_obj = await enterprise_info_service.get_one_or_none()
        data = db_obj.to_dict() if db_obj else {}
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/jcdwzxtj")
    async def get_page1_jcdw_statis(self, monitor_equipment_service: services.MonitorEquipmentService) -> Response[dict]:
        ret = {"ydzs": 0, "ydzx": 0, "ydgz": 0, "fdzs": 0, "fdzx": 0, "fdgz": 0, "spzs": 0, "spzx": 0, "spgz": 0}
        rows = await monitor_equipment_service.list()
        category_mapping = {0: "yd", 1: "fd", 2: "sp"}
        status_mapping = {0: "zx", 1: "gz"}
        for row in rows:
            cat = row.category
            st = row.status
            if cat is None or st is None:
                continue
            base = category_mapping.get(cat)
            if not base:
                continue
            ret[f"{base}zs"] += 1
            key = f"{base}{status_mapping.get(st, '')}"
            if key in ret:
                ret[key] += 1
        return Response(content={"code": 200, "msg": "获取成功", "data": ret})

    @staticmethod
    async def _get_common_yd_statis(db_session: AsyncSession) -> dict:
        today = datetime.date.today()
        sw = today - relativedelta(weekday=MO(-1))
        sm = today.replace(day=1)
        sql = f"""
        select day_lj_zygdn, week_lj_zygdn, month_lj_zygdn, year_lj_zygdn from
             (select 1 as id, zygdn as year_lj_zygdn from yj_year_sum_view where year = {today.year}) a
             left join
             (select 1 as id, zygdn as month_lj_zygdn from yj_month_sum_view where month = '{sm}') b on a.id=b.id
             left join
             (select 1 as id, zygdn as week_lj_zygdn from yj_week_sum_view where week = '{sw}') c on a.id=c.id
             left join
             (select 1 as id, zygdn as day_lj_zygdn from yj_day_sum_view where day = '{today}') d on a.id=d.id;
        """
        result = await db_session.execute(text(sql))
        row = result.fetchone()
        headers = ["yd_day_lj_zygdn", "yd_week_lj_zygdn", "yd_month_lj_zygdn", "yd_year_lj_zygdn"]
        return dict(zip(headers, [float(x) if x is not None else 0.0 for x in row])) if row else dict.fromkeys(headers, 0.0)

    @staticmethod
    async def _get_common_gffd_statis(db_session: AsyncSession) -> dict:
        today = datetime.date.today()
        sw = today - relativedelta(weekday=MO(-1))
        sm = today.replace(day=1)
        sql = f"""
        select day_lj_nygdnsz, week_lj_nygdnsz, month_lj_nygdnsz, year_lj_nygdnsz from
          (select 1 as id, nygdnsz2 as year_lj_nygdnsz from hw_gf_year_sum_view where year = {today.year}) a
              left join
          (select 1 as id, nygdnsz2 as month_lj_nygdnsz from hw_gf_month_sum_view where month = '{sm}') b on a.id = b.id
              left join
          (select 1 as id, nygdnsz2 as week_lj_nygdnsz from hw_gf_week_sum_view where week = '{sw}') c on a.id = c.id
              left join
          (select 1 as id, nygdnsz2 as day_lj_nygdnsz from hw_gf_day_sum_view where day = '{today}') d on a.id = d.id;
        """
        result = await db_session.execute(text(sql))
        row = result.fetchone()
        headers = ["gf_day_lj_nygdnsz", "gf_week_lj_nygdnsz", "gf_month_lj_nygdnsz", "gf_year_lj_nygdnsz"]
        return dict(zip(headers, [float(x) if x is not None else 0.0 for x in row])) if row else dict.fromkeys(headers, 0.0)

    @staticmethod
    async def _get_common_cdzyd_statis(db_session: AsyncSession) -> dict:
        today = datetime.date.today()
        sw = today - relativedelta(weekday=MO(-1))
        sm = today.replace(day=1)
        sql = f"""
        select day_lj_zygdnsz, week_lj_zygdnsz, month_lj_zygdnsz, year_lj_zygdnsz from
         (select 1 as id, zygdnsz as year_lj_zygdnsz from hw_cdz_area_year_sum_view where year = {today.year}) a
             left join
         (select 1 as id, zygdnsz as month_lj_zygdnsz from hw_cdz_area_month_sum_view where month = '{sm}') b on a.id = b.id
             left join
         (select 1 as id, zygdnsz as week_lj_zygdnsz from hw_cdz_area_week_sum_view where week = '{sw}') c on a.id = c.id
             left join
         (select 1 as id, zygdnsz as day_lj_zygdnsz from hw_cdz_area_day_sum_view where day = '{today}') d on a.id = d.id;
        """
        result = await db_session.execute(text(sql))
        row = result.fetchone()
        headers = ["cdz_day_lj_zygdnsz", "cdz_week_lj_zygdnsz", "cdz_month_lj_zygdnsz", "cdz_year_lj_zygdnsz"]
        return dict(zip(headers, [float(x) if x is not None else 0.0 for x in row])) if row else dict.fromkeys(headers, 0.0)

    @staticmethod
    async def _get_common_fdyd_statis_for_chart(db_session: AsyncSession, stat_type: str) -> list[dict]:
        today = datetime.date.today()
        if stat_type == "day":
            sql = f"select hour, concat(hour,'时'), zygdn, nygdnsz2, (zygdn-nygdnsz2) from yj_day_hour_sum_view a left join hw_gf_day_hour_sum_view b on a.hour=b.hour where a.day='{today}'"
        elif stat_type == "week":
            sw = today - datetime.timedelta(days=today.weekday())
            ew = sw + datetime.timedelta(days=6)
            sql = f"select a.day, to_char(a.day, 'MM月DD日'), zygdn, nygdnsz2, (zygdn - nygdnsz2) from yj_day_sum_view a left join hw_gf_day_sum_view b on a.day = b.day where a.day >= '{sw}' and a.day <= '{ew}'"
        elif stat_type == "month":
            sm = today.replace(day=1)
            em = sm + relativedelta(months=1, days=-1)
            sql = f"select a.day, to_char(a.day, 'DD日'), zygdn, nygdnsz2, (zygdn - nygdnsz2) from yj_day_sum_view a left join hw_gf_day_sum_view b on a.day = b.day where a.day>='{sm}' and a.day <='{em}'"
        else:
            sql = f"select a.month, to_char(a.month,'MM月'), zygdn, nygdnsz2, (zygdn - nygdnsz2) from yj_month_sum_view a left join hw_gf_month_sum_view b on a.month = b.month where extract(year from a.month) = {today.year}"

        result = await db_session.execute(text(sql))
        rows = result.fetchall()
        headers = ["dt", "human_dt", "ydl", "fdl", "wgdl"]
        return [dict(zip(headers, r)) for r in rows]

    @staticmethod
    async def _get_api_result_key_mapping(db_session: AsyncSession) -> dict[str, str]:
        result = await db_session.execute(m.ApiResultKeyMapping.__table__.select())
        rows = result.mappings().all()
        return {row["key_name"]: row["cn_name"] for row in rows}

    @get(path="/api/page3/ckqy/ljydtj")
    async def get_page3_yd_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_yd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page3/gfqy/ljfdtj")
    async def get_page3_gffd_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_gffd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page3/cdzqy/ljydtj")
    async def get_page3_cdz_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_cdzyd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/ydfdzl/{stat_type:str}")
    async def get_page1_ydfdzl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        yj_table, gf_table = f"yj_{stat_type}_sum_view", f"hw_gf_{stat_type}_sum_view"
        today = datetime.date.today()
        where = f"day='{today}'" if stat_type == "day" else (f"week='{today - relativedelta(weekday=MO(-1))}'" if stat_type == "week" else (f"month='{today.replace(day=1)}'" if stat_type == "month" else f"year={today.year}"))

        sql_yd = f"select zygdn, zygdn_ratio from {yj_table} where {where}"
        res_yd = await db_session.execute(text(sql_yd))
        r_yd = res_yd.fetchone()
        ret_yd = {f"ydl_{stat_type}_value": r_yd[0] if r_yd and r_yd[0] else 0, f"ydl_{stat_type}_ratio": r_yd[1] * 100 if r_yd and r_yd[1] else "-"}

        sql_fd = f"select nygdnsz2, nygdnsz2_ratio from {gf_table} where {where}"
        res_fd = await db_session.execute(text(sql_fd))
        r_fd = res_fd.fetchone()
        ret_fd = {f"fdl_{stat_type}_value": r_fd[0] if r_fd and r_fd[0] else 0, f"fdl_{stat_type}_ratio": r_fd[1] * 100 if r_fd and r_fd[1] else "-"}

        return Response(content={"code": 200, "msg": "获取成功", "data": {**ret_yd, **ret_fd}})

    @get(path="/api/page1/ydfdzl/qypx/{stat_type:str}")
    async def get_page1_ydfdzl_qy(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        yj_table, gf_table = f"yj_area_{stat_type}_sum_view", f"hw_gf_area_{stat_type}_sum_view"
        today = datetime.date.today()
        where = f"day='{today}'" if stat_type == "day" else (f"week='{today - relativedelta(weekday=MO(-1))}'" if stat_type == "week" else (f"month='{today.replace(day=1)}'" if stat_type == "month" else f"year={today.year}"))

        sql_yd = f"select area_id, area_name, zygdn from {yj_table} where {where} order by zygdn desc"
        res_yd = await db_session.execute(text(sql_yd))
        ret_yds = [{"area_id": r[0], "area_name": r[1], "zygdn": float(r[2]) if r[2] else 0.0} for r in res_yd.fetchall() if r[0] != "29710"]

        sql_fd = f"select area_id, area_name, nygdnsz2 from {gf_table} where {where} order by nygdnsz2 desc"
        res_fd = await db_session.execute(text(sql_fd))
        ret_fds = [{"area_id": r[0], "area_name": r[1], "nygdnsz2": float(r[2]) if r[2] else 0.0} for r in res_fd.fetchall()]

        return Response(content={"code": 200, "msg": "获取成功", "data": {"yd": ret_yds, "fd": ret_fds}})

    @get(path="/api/page3/ydfdtj/chart/{stat_type:str}")
    async def get_page3_fdyd_statis_for_chart(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        rets = await self._get_common_fdyd_statis_for_chart(db_session, stat_type)
        mapping = await self._get_api_result_key_mapping(db_session)
        new_rets = [{mapping.get(k, k): v for k, v in r.items()} for r in rets]
        return Response(content={"code": 200, "msg": "获取成功", "data": new_rets})

    @get(path="/api/hwpm/show/num")
    async def get_hwpm_show_num(self, db_session: AsyncSession) -> Response[dict]:
        ret_cdz = await self._get_common_cdzyd_statis(db_session)
        ret_yd = await self._get_common_yd_statis(db_session)
        ret_fd = await self._get_common_gffd_statis(db_session)
        ret_jtpf = {
            "day_jcpf": round(float(ret_yd["yd_day_lj_zygdn"]) * YD_CPFL_PFYZ - float(ret_fd["gf_day_lj_nygdnsz"]) * GF_CJPL_PFYZ, 3),
            "week_jcpf": round(float(ret_yd["yd_week_lj_zygdn"]) * YD_CPFL_PFYZ - float(ret_fd["gf_week_lj_nygdnsz"]) * GF_CJPL_PFYZ, 3),
            "month_jcpf": round(float(ret_yd["yd_month_lj_zygdn"]) * YD_CPFL_PFYZ - float(ret_fd["gf_month_lj_nygdnsz"]) * GF_CJPL_PFYZ, 3),
            "year_jcpf": round(float(ret_yd["yd_year_lj_zygdn"]) * YD_CPFL_PFYZ - float(ret_fd["gf_year_lj_nygdnsz"]) * GF_CJPL_PFYZ, 3),
        }
        data = {**ret_cdz, **ret_yd, **ret_fd, **ret_jtpf}
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @staticmethod
    async def _get_common_cpf_zl(db_session: AsyncSession, stat_type: str = "day") -> dict:
        today = datetime.date.today()
        where = f"a.day='{today}'" if stat_type == "day" else (f"a.week='{today - relativedelta(weekday=MO(-1))}'" if stat_type == "week" else (f"a.month='{today.replace(day=1)}'" if stat_type == "month" else f"a.year={today.year}"))
        table = f"yj_{stat_type}_sum_view"
        gf_table = f"hw_gf_{stat_type}_sum_view"
        sql = f"select zygdn, nygdnsz2 from {table} a left join {gf_table} b on a.{stat_type}=b.{stat_type} where {where}"
        result = await db_session.execute(text(sql))
        r = result.fetchone()
        y, g = (float(r[0]) if r and r[0] is not None else 0.0, float(r[1]) if r and r[1] is not None else 0.0)
        yd_cpfl, gf_cjpl = round(y * YD_CPFL_PFYZ, 3), round(g * GF_CJPL_PFYZ, 3)
        return {"yd_cpfl": yd_cpfl, "gf_cjpl": gf_cjpl, "jcpfl": round(yd_cpfl - gf_cjpl, 3)}

    @get(path="/api/page4/tpfltj")
    async def get_page4_cpf_statis(self, db_session: AsyncSession) -> Response[dict]:
        ret_yd = await self._get_common_yd_statis(db_session)
        ret_fd = await self._get_common_gffd_statis(db_session)
        def calc(y_key, g_key):
             y = float(ret_yd.get(y_key, 0)) * YD_CPFL_PFYZ
             g = float(ret_fd.get(g_key, 0)) * GF_CJPL_PFYZ
             return round(y - g, 3)
        ret = {
            "day_jcpf": calc("yd_day_lj_zygdn", "gf_day_lj_nygdnsz"),
            "week_jcpf": calc("yd_week_lj_zygdn", "gf_week_lj_nygdnsz"),
            "month_jcpf": calc("yd_month_lj_zygdn", "gf_month_lj_nygdnsz"),
            "year_jcpf": calc("yd_year_lj_zygdn", "gf_year_lj_nygdnsz"),
        }
        return Response(content={"code": 200, "msg": "获取成功", "data": ret})

    @get(path="/api/page4/tpflzl/{stat_type:str}")
    async def get_page4_cpf_zl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        data = await self._get_common_cpf_zl(db_session, stat_type)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/ydfdtj/{stat_type:str}")
    async def get_page1_ydfd_statis(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        data = await self._get_common_cpf_zl(db_session, stat_type)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    async def _get_page1_cpf_gl_impl(self, db_session: AsyncSession, stat_type: str) -> Response[dict]:
        ret = await self._get_common_cpf_zl(db_session, stat_type)
        ret["store_area"] = CKYQZMJ
        day_ygtq_cpfl = await calc_day_ygtq_cpfl(db_session)
        factors = {"day": 1, "week": 5, "month": 22, "year": 250}
        ygtq_cpfl = day_ygtq_cpfl * factors.get(stat_type, 1)
        ret["ygtq_cpfl"] = round(ygtq_cpfl, 2)
        try:
            res_crk = await db_session.execute(text(f"select zje from crkje_{stat_type}_sum_view limit 1"))
            r_crk = res_crk.fetchone()
            crk_zje = float(r_crk[0]) if r_crk and r_crk[0] else 0.0
        except Exception:
            crk_zje = 0.0
        ret["crk_zje"] = round(crk_zje / 10000, 2)
        ret["yd_cpfqd"] = round((ret["yd_cpfl"] + ygtq_cpfl) / ret["crk_zje"], 2) if ret["crk_zje"] else "-"
        ret["czcsy"] = abs(round(ret["jcpfl"] * 50.0 / 10000, 1))
        return Response(content={"code": 200, "msg": "获取成功", "data": ret})

    @get(path="/api/page1/tpfgl/{stat_type:str}")
    async def get_page1_tpfgl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        return await self._get_page1_cpf_gl_impl(db_session, stat_type)

    @get(path="/api/page1/cpfgl/{stat_type:str}")
    async def get_page1_cpfgl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        return await self._get_page1_cpf_gl_impl(db_session, stat_type)

    @get(path="/api/page4/tpfl/ckqypx/{stat_type:str}")
    async def get_page4_cpfl_qy(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        yj_table = f"yj_area_{stat_type}_sum_view"
        today = datetime.date.today()
        where = f"day='{today}'" if stat_type == "day" else (f"week='{today - relativedelta(weekday=MO(-1))}'" if stat_type == "week" else (f"month='{today.replace(day=1)}'" if stat_type == "month" else f"year={today.year}"))
        sql = f"select area_id, area_name, zygdn from {yj_table} where {where} order by zygdn desc"
        res = await db_session.execute(text(sql))
        rets = [{"area_id": r[0], "area_name": r[1], "zygdn": r[2], "cpfl": round(float(r[2]) * YD_CPFL_PFYZ, 3) if r[2] else 0.0} for r in res.fetchall() if r[0] != "29710"]
        rets.sort(key=lambda x: x["cpfl"], reverse=True)
        return Response(content={"code": 200, "msg": "获取成功", "data": rets})

    @get(path="/api/page4/tpfl/year")
    async def get_page4_year_cpfl(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text(f"select zygdn, zygdn_dif from yj_year_sum_view where year={datetime.date.today().year}"))
        r = res.fetchone()
        now_cpfl = round(float(r[0]) * YD_CPFL_PFYZ, 3) if r and r[0] is not None else 0.0
        diff = round(float(r[1]) * YD_CPFL_PFYZ, 3) if r and r[1] is not None else 0.0
        last_cpfl = round(now_cpfl - diff, 3)
        ratio = round(diff * 100 / last_cpfl) if last_cpfl > 0 else 0
        return Response(content={"code": 200, "msg": "获取成功", "data": {"year_cpfl": now_cpfl, "year_cpfl_bh": ratio, "last_year_cpfl": last_cpfl, "last_year_dif": diff}})

    @get(path="/api/page4/tpfltj/chart/{stat_type:str}")
    async def get_page4_pfl_statis_for_chart(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        rets = await self._get_common_fdyd_statis_for_chart(db_session, stat_type)
        mapping = await self._get_api_result_key_mapping(db_session)
        new_rets = []
        for r in rets:
            yd_cpf = round(float(r["ydl"]) * YD_CPFL_PFYZ, 3) if r["ydl"] else 0.0
            gf_cjp = round(float(r["fdl"]) * GF_CJPL_PFYZ, 3) if r["fdl"] else 0.0
            new_rets.append({mapping.get("dt", "dt"): r["dt"], mapping.get("human_dt", "human_dt"): r["human_dt"], mapping.get("yd_cpf", "yd_cpf"): yd_cpf, mapping.get("gf_cjp", "gf_cjp"): gf_cjp, mapping.get("jpf", "jpf"): round(yd_cpf - gf_cjp, 3)})
        return Response(content={"code": 200, "msg": "获取成功", "data": new_rets})

    @get(path="/api/page3/zjyj")
    async def get_page3_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), case when event_type=1 then '设备故障' when event_type=2 then '用电异常' when event_type=3 then '发电异常' else '碳排放异常' end, to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type in (1,2,3) and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page3/latestyj")
    async def get_page3_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), case when event_type=1 then '设备故障' when event_type=2 then '用电异常' when event_type=3 then '发电异常' else '碳排放异常' end, to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type in (1,2,3) and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/zjyj")
    async def get_page4_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), '碳排放异常', to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type = 4 and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/latestyj")
    async def get_page4_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), '碳排放异常', to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type = 4 and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page3/yjtj/qypx/{stat_type:str}")
    async def get_page3_yjtj_2(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        today = datetime.date.today()
        dt = today if stat_type == "day" else (today - datetime.timedelta(days=today.weekday()))
        sql = f"select COALESCE(sector_id, 'P0'), COALESCE(name, '整个仓库'), count(*) as count from alarm_event_view where {stat_type}='{dt}' and event_type in (2,3) and is_handle = false group by sector_id, name order by count desc"
        res = await db_session.execute(text(sql))
        headers = ["区域ID", "区域名", "预警次数"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/yjtj/qypx/{stat_type:str}")
    async def get_page4_yjtj_2(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        today = datetime.date.today()
        dt = today if stat_type == "day" else (today - datetime.timedelta(days=today.weekday()))
        sql = f"select COALESCE(sector_id, 'P0'), COALESCE(name, '整个仓库'), count(*) as count from alarm_event_view where {stat_type}='{dt}' and event_type = 4 and is_handle = false group by sector_id, name order by count desc"
        res = await db_session.execute(text(sql))
        headers = ["区域ID", "区域名", "预警次数"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @staticmethod
    def _dt_for_stat_type(stat_type: str) -> str | int:
        """与 Django 一致：day=昨日，week=本周一，month=本月1日，year=年。"""
        today = datetime.date.today()
        if stat_type == "day":
            dt = today - datetime.timedelta(days=1)
        elif stat_type == "week":
            dt = today - datetime.timedelta(days=today.weekday())
        elif stat_type == "month":
            dt = today.replace(day=1)
        else:
            dt = today.year
        return str(dt) if isinstance(dt, datetime.date) else dt

    @get(path="/api/page3/yjtj/{stat_type:str}")
    async def get_page3_yjtj(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        """电能监测：预警统计"""
        dt = self._dt_for_stat_type(stat_type)
        sql1 = f"select count(1) from alarm_event_view where {stat_type}='{dt}' and (event_type=2 or event_type=3) and is_handle = false"
        r1 = (await db_session.execute(text(sql1))).scalar() or 0
        sql2 = f"select count(1) from alarm_event_view where {stat_type}='{dt}' and event_type=2 and is_handle = false"
        r2 = (await db_session.execute(text(sql2))).scalar() or 0
        sql3 = f"select count(1) from alarm_event_view where {stat_type}='{dt}' and event_type=3 and is_handle = false"
        r3 = (await db_session.execute(text(sql3))).scalar() or 0
        sql4 = f"""select case when sector_id is null then 'P0' else sector_id end, case when sector_id is null then '整个仓库' else name end, count(*) from alarm_event_view
            where {stat_type}='{dt}' and (event_type=2 or event_type=3) and is_handle = false group by sector_id, name order by count desc"""
        rs4 = (await db_session.execute(text(sql4))).fetchall()
        result = {"total_alarm_count": r1, "fdycyj": r3, "ydycyj": r2, "qyyj": [dict(zip(["区域ID", "区域名", "预警次数"], r)) for r in rs4]}
        return Response(content={"code": 200, "msg": "获取成功", "data": result})

    @get(path="/api/page4/yjtj/{stat_type:str}")
    async def get_page4_yjtj(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        """碳能协同：预警统计"""
        dt = self._dt_for_stat_type(stat_type)
        sql1 = f"select count(1) from alarm_event_view where {stat_type}='{dt}' and event_type=4 and is_handle = false"
        r1 = (await db_session.execute(text(sql1))).scalar() or 0
        sql2 = f"""select case when sector_id is null then 'P0' else sector_id end, case when sector_id is null then '整个仓库' else name end, count(*) from alarm_event_view
            where {stat_type}='{dt}' and event_type=4 and is_handle = false group by sector_id, name order by count desc"""
        rs4 = (await db_session.execute(text(sql2))).fetchall()
        result = {"total_alarm_count": r1, "qyyj": [dict(zip(["区域ID", "区域名", "预警次数"], r)) for r in rs4]}
        return Response(content={"code": 200, "msg": "获取成功", "data": result})

    @get(path="/api/page4/qytpfyj/{stat_type:str}")
    async def get_page4_qy_tpfyj(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        """碳能协同：各区域碳排放预警"""
        dt = self._dt_for_stat_type(stat_type)
        sql = f"""select case when sector_id is null then 'P0' else sector_id end, case when sector_id is null then '整个仓库' else name end, event_desc
            from alarm_event_view where event_type=4 and {stat_type}='{dt}' and is_handle = false order by event_time desc limit 10"""
        res = await db_session.execute(text(sql))
        header = ["区域ID", "区域名称", "事件描述"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(header, r)) for r in res.fetchall()]})

    @get(path="/api/page4/cktpfqd/chart/{stat_type:str}")
    async def get_page4_cktpfqd_statis_for_chart(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        """碳能协同：仓库碳排放强度图表"""
        today = datetime.date.today()
        weekday = today.weekday()
        if stat_type == "day":
            sql = f"""select aa.hour, aa.human_hour, round(aa.tpfl,3), round(aa.zje2/10000,3), round(aa.tpfl*10000/aa.zje2,6) from (
                select hour, concat(hour,'时') as human_hour, zygdn, zygdn*{YD_CPFL_PFYZ} as tpfl, (select avg(zje)/24 from crkje_day_sum_view) as zje2
                from yj_day_hour_sum_view where day = '{today}' order by hour) aa"""
        elif stat_type == "week":
            sw = today - datetime.timedelta(days=weekday)
            ew = sw + datetime.timedelta(days=6)
            sql = f"""select aa.day, aa.human_day, round(aa.tpfl,3), round(aa.zje2/10000,3), round(aa.tpfl*10000/aa.zje2,6) from (
                select a.*, a.zygdn*{YD_CPFL_PFYZ} as tpfl, round(case when b.zje is null then (select avg(zje) from crkje_day_sum_view) else b.zje end, 3) as zje2
                from (select day, to_char(day, 'MM月DD日') as human_day, zygdn from yj_day_sum_view where day >= '{sw}' and day <= '{ew}' order by day) a
                left join (select * from crkje_day_sum_view where day >= '{sw}' and day <= '{ew}') b on a.day = b.day) aa"""
        elif stat_type == "month":
            fd = today.replace(day=1)
            ld = fd + relativedelta(months=1, days=-1)
            sql = f"""select aa.day, aa.human_day, round(aa.tpfl,3), round(aa.zje2/10000,3), round(aa.tpfl*10000/aa.zje2,6) from (
                select a.*, a.zygdn*{YD_CPFL_PFYZ} as tpfl, round(case when b.zje is null then (select avg(zje) from crkje_day_sum_view) else b.zje end, 3) as zje2
                from (select day, to_char(day,'DD日') as human_day, zygdn from yj_day_sum_view where day>='{fd}' and day<='{ld}' order by day) a
                left join (select * from crkje_day_sum_view where day>='{fd}' and day<='{ld}') b on a.day = b.day) aa"""
        else:
            y = today.year
            sql = f"""select aa.month, aa.human_month, round(aa.tpfl,3), round(aa.zje2/10000,3), round(aa.tpfl*10000/aa.zje2,6) from (
                select a.month, to_char(a.month,'MM月') as human_month, zygdn, zygdn*{YD_CPFL_PFYZ} as tpfl,
                round(case when b.zje is null then (select avg(zje)*30 from crkje_day_sum_view) else b.zje end, 3) as zje2
                from (select month, zygdn from yj_month_sum_view where extract(year from date_trunc('year', month)) = {y} order by month) a
                left join (select month, zje from crkje_month_sum_view where extract(year from date_trunc('year', month)) = {y} order by month) b on a.month = b.month) aa"""
        res = await db_session.execute(text(sql))
        headers = ["日期1", "日期", "碳排放量(kgCo2)", "出入库总金额(万元)", "碳排放强度(kgCo2/万元)"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page1/yjzl/{stat_type:str}")
    async def get_page1_yjzl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        dt = self._dt_for_stat_type(stat_type)
        res_total = await db_session.execute(text(f"select count(1) from alarm_event_view where {stat_type}='{dt}' and is_handle = false"))
        total = res_total.scalar() or 0
        return Response(content={"code": 200, "msg": "获取成功", "data": {"total_alarm_count": total, "qyyj": [], "lxyj": []}})

    @get(path="/api/page1/zjyj")
    async def get_page1_zjyj(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        rows = await alarm_event_service.list(limit=5, order_by="event_time desc")
        data = [{"desc": r.event_desc, "time": r.event_time.strftime("%Y-%m-%d %H:%M:%S") if r.event_time else "", "type": r.event_type} for r in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/latestwj")
    async def get_page1_latestwj(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        rows = await alarm_event_service.list(limit=5, order_by="event_time desc")
        data = [{"desc": r.event_desc, "time": r.event_time.strftime("%Y-%m-%d %H:%M:%S") if r.event_time else "", "type": r.event_type} for r in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})


class CarbonMapController(Controller):
    tags = ["CarbonMap"]
    signature_types = [Response]
    dependencies = {"monitor_sector_service": provide_monitor_sector_service}

    @get(path="/api/map/popup/{area_id:str}")
    async def get_map_popup(
        self, area_id: str, db_session: AsyncSession, monitor_sector_service: services.MonitorSectorService
    ) -> Response[dict]:
        """获取地图 popup 信息：区域名称、照片、当日/周/月/年用电或发电统计。"""
        result: dict[str, Any] = {"pictures": [], "popupVals": []}
        try:
            aid = int(area_id)
        except ValueError:
            return Response(content={"code": 200, "msg": "监控区域不存在", "data": result})
        q = select(m.MonitorSector).where(m.MonitorSector.area_id == aid).options(selectinload(m.MonitorSector.photos))
        sector = (await db_session.execute(q)).scalar_one_or_none()
        if not sector:
            return Response(content={"code": 200, "msg": "监控区域不存在", "data": result})
        result["name"] = sector.name or ""
        if sector.photos:
            for p in sector.photos:
                if p.path:
                    result["pictures"].append(p.path if p.path.startswith("http") else f"/media/{p.path}")
        today = datetime.date.today()
        sw = today - datetime.timedelta(days=today.weekday())
        sm = today.replace(day=1)
        year = today.year
        ret_list: list[dict] = []
        if area_id in ("29712", "29714"):
            for label, col, val in [
                ("day", "day", f"'{today}'"),
                ("week", "week", f"'{sw}'"),
                ("month", "month", f"'{sm}'"),
                ("year", "year", str(year)),
            ]:
                tbl = f"hw_gf_area_{label}_sum_view"
                sql = f"select area_id, area_name, nygdnsz2, round(nygdnsz2*{GF_CJPL_PFYZ},4) from {tbl} where area_id='{area_id}' and {col}={val}"
                r = (await db_session.execute(text(sql))).fetchone()
                headers = ["区域ID", "区域名称", "今日发电量", "今日碳减排量"] if label == "day" else ["区域ID", "区域名称", "本周发电量", "本周碳减排量"] if label == "week" else ["区域ID", "区域名称", "本月发电量", "本月碳减排量"] if label == "month" else ["区域ID", "区域名称", "本年发电量", "本年碳减排量"]
                if r:
                    ret_list.append(dict(zip(headers, r)))
        elif area_id == "29713":
            for label, col, val in [
                ("day", "day", f"'{today}'"),
                ("week", "week", f"'{sw}'"),
                ("month", "month", f"'{sm}'"),
                ("year", "year", str(year)),
            ]:
                tbl = f"hw_cdz_area_{label}_sum_view"
                sql = f"select area_id, area_name, zygdnsz, round(zygdnsz*{YD_CPFL_PFYZ},4) from {tbl} where area_id='29713' and {col}={val}"
                r = (await db_session.execute(text(sql))).fetchone()
                headers = ["区域ID", "区域名称", "今日用电量", "今日碳排放量"] if label == "day" else ["区域ID", "区域名称", "本周用电量", "本周碳排放量"] if label == "week" else ["区域ID", "区域名称", "本月用电量", "本月碳排放量"] if label == "month" else ["区域ID", "区域名称", "本年用电量", "本年碳排放量"]
                if r:
                    ret_list.append(dict(zip(headers, r)))
        else:
            for label, col, val in [
                ("day", "day", f"'{today}'"),
                ("week", "week", f"'{sw}'"),
                ("month", "month", f"'{sm}'"),
                ("year", "year", str(year)),
            ]:
                tbl = f"yj_area_{label}_sum_view"
                sql = f"select area_id, area_name, zygdn, round(zygdn*{YD_CPFL_PFYZ},4) from {tbl} where area_id='{area_id}' and {col}={val}"
                r = (await db_session.execute(text(sql))).fetchone()
                headers = ["区域ID", "区域名称", "今日用电量", "今日碳排放量"] if label == "day" else ["区域ID", "区域名称", "本周用电量", "本周碳排放量"] if label == "week" else ["区域ID", "区域名称", "本月用电量", "本月碳排放量"] if label == "month" else ["区域ID", "区域名称", "本年用电量", "本年碳排放量"]
                if r:
                    ret_list.append(dict(zip(headers, r)))
        result["popupVals"] = ret_list
        return Response(content={"code": 200, "msg": "获取成功", "data": result})

    @get(path="/api/map/monitorSector/list")
    async def get_all_monitor_sector(self, monitor_sector_service: services.MonitorSectorService) -> Response[dict]:
        rows = await monitor_sector_service.list(m.MonitorSector.is_enable.is_(True))
        data = [{"code": r.code, "name": r.name, "area_id": r.area_id, "description": r.description, "pictures": []} for r in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})


def _parse_vedio_event_time(date_string: str | None) -> datetime.datetime | None:
    """解析回调中的日期时间字符串，如 2023-08-31T17:02:15.080+08:00"""
    if not date_string:
        return None
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(date_string)
    except Exception:
        try:
            return datetime.datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        except Exception:
            return None


class CarbonEventController(Controller):
    tags = ["CarbonEvent"]
    signature_types = [Response]
    dependencies = {
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "video_monitor_service": provide_video_monitor_service,
        "security_audit_service": provide_audit_log_service,
    }

    @post(path="/api/zjyj/handleEvents", guards=[requires_superuser])
    async def handle_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.batch-handle",
            target_type="alarm_event",
            details={"batch_size": len(ids), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleEvents", guards=[requires_superuser])
    async def handle_events(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.batch-handle",
            target_type="alarm_event",
            details={"batch_size": len(ids)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllEvents", guards=[requires_superuser])
    async def handle_all_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle == False)
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.handle-all",
            target_type="alarm_event",
            details={"batch_size": len(unhandled), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllEvents", guards=[requires_superuser])
    async def handle_all_events(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle == False)
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.handle-all",
            target_type="alarm_event",
            details={"batch_size": len(unhandled)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleVideoEvents", guards=[requires_superuser])
    async def handle_video_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.batch-handle",
            target_type="video_alarm_event",
            details={"batch_size": len(ids), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleVideoEvents", guards=[requires_superuser])
    async def handle_video_events(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.batch-handle",
            target_type="video_alarm_event",
            details={"batch_size": len(ids)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllVideoEvents", guards=[requires_superuser])
    async def handle_all_video_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle == False)
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.handle-all",
            target_type="video_alarm_event",
            details={"batch_size": len(unhandled), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllVideoEvents", guards=[requires_superuser])
    async def handle_all_video_events(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle == False)
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.handle-all",
            target_type="video_alarm_event",
            details={"batch_size": len(unhandled)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/pullVedioAlarmEvent", guards=[requires_superuser])
    async def pull_vedio_alarm_event(
        self,
        request: Request[Any, Any, Any],
        data: dict,
        video_monitor_service: services.VideoMonitorService,
        security_audit_service: AuditLogService,
        db_session: AsyncSession,
    ) -> Response[dict]:
        """接收摄像头报警回调，创建 VedioAlarmEvent（与 Django pull_vedio_alarm_event 一致）"""
        json_data = data.get("json") or data
        rets: list[m.VedioAlarmEvent] = []
        all_vms = await video_monitor_service.list()
        ip_to_vm: dict[str, Any] = {str(v.ip_address): v for v in all_vms if getattr(v, "ip_address", None)}

        def vm_by_ip(ip: str | None) -> Any:
            return ip_to_vm.get(ip or "") if ip else None

        def make_event(
            event_type: int, event_desc: str, event_time: datetime.datetime | None, ip_addr: str | None
        ) -> m.VedioAlarmEvent:
            vm = vm_by_ip(ip_addr)
            return m.VedioAlarmEvent(
                event_type=event_type,
                event_desc=event_desc,
                event_time=event_time or datetime.datetime.now(datetime.UTC),
                equipment_id=vm.id if vm else None,
                is_handle=False,
            )

        if "params" in json_data and "events" in json_data["params"]:
            for evt in json_data["params"]["events"]:
                evt_data = evt.get("data") or {}
                if evt_data.get("eventType") == "AIOPResultData":
                    event_desc = f"{evt_data.get('channelName', '')} 监控到 【未带安全帽】 事件"
                    event_time = _parse_vedio_event_time(evt_data.get("dateTime"))
                    created = make_event(1, event_desc, event_time, evt_data.get("ipAddress"))
                    db_session.add(created)
                    await db_session.flush()
                    rets.append(created)
                elif evt_data.get("eventType") == "fielddetection":
                    event_desc = f"{evt_data.get('channelName', '')} 监控到 【区域入侵】 事件"
                    event_time = _parse_vedio_event_time(evt_data.get("dateTime"))
                    created = make_event(4, event_desc, event_time, evt_data.get("ipAddress"))
                    db_session.add(created)
                    await db_session.flush()
                    rets.append(created)
        if "eventType" in json_data:
            if json_data["eventType"] == "fireDetection":
                ip_addr = json_data.get("ipAddress")
                vms = [v for v in all_vms if getattr(v, "ip_address", None) == ip_addr]
                loc = vms[0].location if vms else json_data.get("eventDescription", "")
                event_desc = f"{loc} 监控到 【火点】 事件"
                event_time = _parse_vedio_event_time(json_data.get("dateTime"))
                created = make_event(3, event_desc, event_time, ip_addr)
                db_session.add(created)
                await db_session.flush()
                rets.append(created)
            elif json_data["eventType"] == "smokeAndFireDetection":
                ip_addr = json_data.get("ipAddress")
                vms = [v for v in all_vms if getattr(v, "ip_address", None) == ip_addr]
                loc = vms[0].location if vms else json_data.get("eventDescription", "")
                event_desc = f"{loc} 监控到 【烟火】 事件"
                event_time = _parse_vedio_event_time(json_data.get("dateTime"))
                created = make_event(2, event_desc, event_time, ip_addr)
                db_session.add(created)
                await db_session.flush()
                rets.append(created)

        def _serialize(e: m.VedioAlarmEvent) -> dict:
            return {
                "id": e.id,
                "event_type": e.event_type,
                "event_desc": e.event_desc,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "equipment_id": e.equipment_id,
                "is_handle": e.is_handle,
                "add_time": e.add_time.isoformat() if getattr(e, "add_time", None) else None,
            }
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.pull",
            target_type="video_alarm_event",
            details={"batch_size": len(rets)},
        )
        return Response(content={"code": 200, "msg": "拉取报警事件成功", "data": {"totalCount": len(rets), "alarmEvents": [_serialize(r) for r in rets]}})


class CarbonVideoController(Controller):
    tags = ["CarbonVideo"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]
    dependencies = {
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "video_monitor_service": provide_video_monitor_service,
    }

    @get(path="/api/page2/yjzl/{stat_type:str}")
    async def get_page2_yjzl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        today = datetime.date.today()
        dt = today if stat_type == "day" else (today - datetime.timedelta(days=today.weekday()))
        res = await db_session.execute(text(f"select count(1) from vedio_alarm_event_view where {stat_type}='{dt}' and is_handle = false"))
        return Response(content={"code": 200, "msg": "获取成功", "data": {"total_alarm_count": res.scalar(), "qyyj": [], "lxyj": []}})

    @get(path="/api/page2/spgl")
    async def get_page2_spgl(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select status, count(*) from dataapp_videomonitor group by status"))
        mapping = {0: "在线", 1: "故障"}
        data = [{"id": i+1, "name": mapping.get(r[0], "未知"), "num": r[1]} for i, r in enumerate(res.fetchall())]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page2/spjk")
    async def get_page2_spjk(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select location, status, f_area from dataapp_videomonitor"))
        mapping = {0: "在线", 1: "故障"}
        data = [{"location": r[0], "status": r[1], "status_name": mapping.get(r[1]), "f_area": r[2]} for r in res.fetchall()]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page2/zjyj")
    async def get_page2_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select id, location, case when event_type=1 then '未佩戴安全帽' when event_type=2 then '烟火' when event_type=3 then '火点' else '区域入侵' end, to_char(event_time,'YYYY-MM-DD HH24:MI'), event_desc, case when is_handle then '已处理' else '未处理' end from vedio_alarm_event_view where is_handle=false order by event_time desc limit 10"))
        headers = ["id", "监控位置", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page2/latestyj")
    async def get_page2_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select id, location, case when event_type=1 then '未佩戴安全帽' when event_type=2 then '烟火' when event_type=3 then '火点' else '区域入侵' end, to_char(event_time,'YYYY-MM-DD HH24:MI'), event_desc, case when is_handle then '已处理' else '未处理' end from vedio_alarm_event_view where is_handle=false order by event_time desc limit 10"))
        headers = ["id", "监控位置", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/map/vedio/popup/{vid:int}")
    async def get_vedio_map_popup(
        self, vid: int, db_session: AsyncSession
    ) -> Response[dict]:
        """获取视频监控地图 popup 信息"""
        vm = await db_session.get(m.VideoMonitor, vid)
        if not vm:
            return Response(content={"code": 200, "msg": "监控区域不存在"})
        data: dict[str, Any] = {
            "id": vm.id, "location": vm.location, "f_area": vm.f_area, "f_area_type": vm.f_area_type,
            "video_url": vm.video_url, "status": vm.status, "ip_address": vm.ip_address,
            "install_height": vm.install_height, "install_method": vm.install_method, "vedio_type": vm.vedio_type,
            "pixel": vm.pixel, "brand": vm.brand, "b_model": vm.b_model, "install_time": vm.install_time,
            "install_x": vm.install_x, "install_y": vm.install_y, "add_time": vm.add_time.isoformat() if vm.add_time else None,
        }
        data["webRtcUrl"] = str(vm.id)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/map/videos")
    async def get_all_videos(self, video_monitor_service: services.VideoMonitorService) -> Response[dict]:
        """获取所有视频流信息（与 Django 返回结构一致）"""
        vms = await video_monitor_service.list()
        ret: dict[str, Any] = {
            "channel_defaults": {},
            "server": {
                "debug": True, "http_debug": False, "http_demo": True, "http_dir": "web",
                "http_login": "demo", "http_password": "demo", "http_port": ":8083",
                "https": False, "https_auto_tls": False, "https_auto_tls_name": "", "https_cert": "server.crt", "https_key": "server.key", "https_port": ":443",
                "ice_credential": "", "ice_servers": ["stun:stun.l.google.com:19302"], "ice_username": "",
                "log_level": "debug", "rtsp_port": ":5541",
                "token": {"backend": "http://127.0.0.1/test.php", "enable": False},
                "webrtc_port_max": 0, "webrtc_port_min": 0,
            },
        }
        streams: dict[str, dict] = {}
        for vm in vms:
            streams[str(vm.id)] = {"channels": {"0": {"url": vm.video_url or ""}}, "name": vm.location or ""}
        ret["streams"] = streams
        return Response(content={"code": 200, "msg": "获取成功", "data": ret})


class CarbonEnergyController(Controller):
    tags = ["CarbonEnergy"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]

    @get(path="/api/page3/cnsy")
    async def get_energy_storage_data(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select cn1, ratio1, cn2, ratio2, cn_total, ratio_total from dataapp_energystoragevalue order by id desc limit 1"))
        r = res.fetchone()
        if r:
            data = {"cn1": round(r[0]), "ratio1": round(r[1] * 100), "cn2": round(r[2]), "ratio2": round(r[3] * 100), "cn_total": round(r[4]), "ratio_total": round(r[5] * 100)}
            return Response(content={"code": 200, "msg": "获取成功", "data": data})
        return Response(content={"code": 200, "msg": "暂无数据"})


def model_to_dict(obj: Any) -> dict:
    """将 ORM 对象转为可 JSON 序列化的字典。"""
    if not obj:
        return {}
    import uuid
    from decimal import Decimal
    result = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        # 处理不可直接 JSON 序列化的类型
        if isinstance(val, (datetime.date, datetime.datetime)):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, uuid.UUID):
            val = str(val)
        result[c.name] = val
    return result


def _area_label(area: m.MonitorSector | None) -> str | None:
    if area is None:
        return None
    return area.name or area.code


def _serialize_area(
    area: m.MonitorSector,
    *,
    equipment_count: int = 0,
    child_count: int = 0,
    include_parent: bool = False,
) -> dict[str, Any]:
    data = model_to_dict(area)
    data["is_enabled"] = bool(area.is_enable is not False)
    data["remark"] = area.remark or area.description
    data["child_count"] = child_count
    data["equipment_count"] = equipment_count
    if include_parent and area.parent is not None:
        data["parent"] = {"id": area.parent.id, "code": area.parent.code, "name": _area_label(area.parent)}
    return data


def _serialize_device_type(device_type: m.DeviceType, *, child_count: int = 0) -> dict[str, Any]:
    data = model_to_dict(device_type)
    data["child_count"] = child_count
    return data


def _serialize_device(
    device: m.MonitorEquipment,
    *,
    area: m.MonitorSector | None = None,
    device_type: m.DeviceType | None = None,
    parent_device: m.MonitorEquipment | None = None,
    child_device_count: int = 0,
    point_count: int = 0,
) -> dict[str, Any]:
    data = model_to_dict(device)
    resolved_area = area
    resolved_type = device_type
    resolved_parent = parent_device
    data["area_id"] = device.sector_id
    data["area_name"] = _area_label(resolved_area)
    data["is_enabled"] = bool(device.is_enable is not False)
    data["location_desc"] = device.location
    data["owner_department"] = device.owner_unit
    data["parent_device"] = (
        {
            "id": resolved_parent.id,
            "code": resolved_parent.code,
            "name": resolved_parent.name or resolved_parent.code,
        }
        if resolved_parent is not None
        else None
    )
    data["device_type"] = (
        {
            "id": resolved_type.id,
            "code": resolved_type.code,
            "name": resolved_type.name,
        }
        if resolved_type is not None
        else None
    )
    data["area"] = (
        {"id": resolved_area.id, "code": resolved_area.code, "name": _area_label(resolved_area)}
        if resolved_area is not None
        else None
    )
    data["child_device_count"] = child_device_count
    data["point_count"] = point_count
    return data


def _build_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {node["id"]: {**node, "children": []} for node in nodes}
    roots: list[dict[str, Any]] = []
    for node in by_id.values():
        parent_id = node.get("parent_id")
        if parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)
    for node in by_id.values():
        node["children"].sort(key=lambda item: (item.get("sort_index") or 0, item.get("name") or item.get("code") or ""))
    roots.sort(key=lambda item: (item.get("sort_index") or 0, item.get("name") or item.get("code") or ""))
    return roots


async def _ensure_root_area(db_session: AsyncSession) -> m.MonitorSector:
    root = await db_session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == ROOT_AREA_CODE))
    if root is not None:
        return root
    next_id = int((await db_session.execute(select(func.coalesce(func.max(m.MonitorSector.id), 0) + 1))).scalar_one())
    root = m.MonitorSector(
        id=next_id,
        code=ROOT_AREA_CODE,
        name="区域主数据",
        area_type="site",
        path=f"/{next_id}",
        level=0,
        sort_index=0,
        description="系统根节点",
        remark="系统自动创建的根区域",
        is_enable=False,
    )
    db_session.add(root)
    await db_session.commit()
    await db_session.refresh(root)
    return root


async def _rebuild_area_path(db_session: AsyncSession, area: m.MonitorSector) -> None:
    if area.parent_id is None:
        area.path = f"/{area.id}"
        area.level = 0
        return
    parent = await db_session.get(m.MonitorSector, area.parent_id)
    if parent is None:
        area.parent_id = None
        area.path = f"/{area.id}"
        area.level = 0
        return
    parent_path = parent.path or f"/{parent.id}"
    parent_level = parent.level or 0
    area.path = f"{parent_path}/{area.id}"
    area.level = parent_level + 1


async def _update_area_descendant_paths(db_session: AsyncSession, area: m.MonitorSector) -> None:
    descendants = (
        await db_session.execute(
            select(m.MonitorSector).where(m.MonitorSector.parent_id == area.id).order_by(m.MonitorSector.sort_index.asc(), m.MonitorSector.id.asc())
        )
    ).scalars().all()
    for child in descendants:
        await _rebuild_area_path(db_session, child)
        await _update_area_descendant_paths(db_session, child)


async def _is_descendant_area(db_session: AsyncSession, area_id: int, candidate_parent_id: int) -> bool:
    area = await db_session.get(m.MonitorSector, area_id)
    parent = await db_session.get(m.MonitorSector, candidate_parent_id)
    if area is None or parent is None:
        return False
    area_path = area.path or f"/{area.id}"
    parent_path = parent.path or f"/{parent.id}"
    return parent_path.startswith(f"{area_path}/")


async def _get_area_subtree_ids(db_session: AsyncSession, area_id: int) -> list[int]:
    area = await db_session.get(m.MonitorSector, area_id)
    if area is None:
        return []
    path = area.path or f"/{area.id}"
    rows = (
        await db_session.execute(select(m.MonitorSector.id).where(m.MonitorSector.path.like(f"{path}%")))
    ).scalars().all()
    return [int(item) for item in rows]


async def _get_device_type_subtree_ids(db_session: AsyncSession, device_type_id: int) -> list[int]:
    rows = (
        await db_session.execute(select(m.DeviceType.id, m.DeviceType.parent_id).order_by(m.DeviceType.id.asc()))
    ).all()
    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for identifier, parent_id in rows:
        children_by_parent[parent_id].append(identifier)
    queue = [device_type_id]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        queue.extend(children_by_parent.get(current, []))
    return sorted(seen)


async def _is_descendant_device(db_session: AsyncSession, device_id: int, parent_device_id: int) -> bool:
    current_parent_id = parent_device_id
    seen: set[int] = set()
    while current_parent_id is not None and current_parent_id not in seen:
        if current_parent_id == device_id:
            return True
        seen.add(current_parent_id)
        current_parent_id = await db_session.scalar(
            select(m.MonitorEquipment.parent_device_id).where(m.MonitorEquipment.id == current_parent_id)
        )
    return False


_FACTOR_UNIT_PATTERN = re.compile(r"(tC/TJ|TJ/万t|10⁴t|万t|tCO2|tCO₂|tC|kg|CH4|CH₄|CO2|CO₂|N2O|N₂O|%|m3|m³|Gg)", re.IGNORECASE)


def _looks_like_factor_unit(value: str) -> bool:
    return bool(_FACTOR_UNIT_PATTERN.search(value.strip()))


def _augment_raw_factor_record_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Add display-oriented fields for matrix-style official raw factor records."""
    if data.get("library_code") != "G04":
        data["display_factor_name"] = data.get("factor_name")
        data["display_factor_unit_raw"] = data.get("factor_unit_raw")
        return data

    raw_payload = data.get("raw_payload") if isinstance(data.get("raw_payload"), dict) else {}
    row_cells = raw_payload.get("rowCells") if isinstance(raw_payload, dict) else []
    row_cells = row_cells if isinstance(row_cells, list) else []
    header = raw_payload.get("header") if isinstance(raw_payload, dict) else {}
    header_value = str(header.get("value") or "").strip() if isinstance(header, dict) else ""
    factor_value = str(data.get("factor_value_raw") or "").strip()

    unit = data.get("factor_unit_raw")
    dimensions: list[str] = []
    for cell in row_cells:
        if not isinstance(cell, dict):
            continue
        value = str(cell.get("value") or "").strip()
        value_en = str(cell.get("valueEn") or "").strip()
        for candidate in (value, value_en):
            if candidate and not unit and _looks_like_factor_unit(candidate):
                unit = candidate
        if not value or value == factor_value or _looks_like_factor_unit(value):
            continue
        if value not in dimensions:
            dimensions.append(value)

    if header_value and header_value not in dimensions:
        dimensions.append(header_value)

    if dimensions:
        data["display_factor_name"] = " - ".join(dimensions)
        data["matrix_dimensions"] = dimensions
    else:
        data["display_factor_name"] = re.sub(r"\s*-\s*纵\d+\s*", " - ", str(data.get("factor_name") or "")).strip(" -")
        data["matrix_dimensions"] = []
    data["display_factor_unit_raw"] = unit
    return data


# 审核状态与审计动作（参考 xtck_deploy admin AuditActionMixin）
STATUS_DRAFT = "draft"
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
AUDIT_ACTION_SUBMIT = "submit"
AUDIT_ACTION_APPROVE = "approve"
AUDIT_ACTION_REJECT = "reject"
ADMIN_BODY = Body()
ADMIN_OPTIONAL_BODY = Body(default={})
PURCHASED_SCOPE2_ENERGY_CODES = {"purchased_heat", "purchased_steam", "purchased_cooling"}


def _coerce_date_fields(data: dict[str, Any], fields: list[str]) -> None:
    """将指定字段的 ISO 日期字符串转换为 date 对象，避免 asyncpg DataError。"""
    for field in fields:
        val = data.get(field)
        if isinstance(val, str):
            try:
                data[field] = datetime.date.fromisoformat(val)
            except ValueError:
                pass


def _carbon_defaults() -> dict:
    """填报默认数据特征（PRD 3.0）。"""
    return {
        "data_source": "metered",
        "collection_method": "manual",
        "confidence_level": "high",
        "data_year_type": "actual",
        "status": STATUS_DRAFT,
    }


def _payload_without_none(data: dict[str, Any]) -> dict[str, Any]:
    """Drop client-side empty values before writing simple admin records."""
    return {k: v for k, v in data.items() if v is not None}


def _coerce_datetime_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val:
            try:
                data[field] = datetime.datetime.fromisoformat(val)
            except ValueError:
                try:
                    data[field] = datetime.datetime.combine(datetime.date.fromisoformat(val), datetime.time.min)
                except ValueError:
                    pass


def _coerce_int_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            try:
                data[field] = int(val)
            except ValueError:
                pass


def _coerce_float_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            try:
                data[field] = float(val)
            except ValueError:
                pass


def _coerce_decimal_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if val in (None, ""):
            continue
        try:
            data[field] = val if isinstance(val, Decimal) else Decimal(str(val))
        except Exception:  # noqa: BLE001
            pass


def _strip_string_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str):
            data[field] = val.strip() or None


def _sync_monitor_equipment_type_fields(data: dict[str, Any]) -> None:
    device_type_id = data.get("device_type_id")
    category = data.get("category")
    if isinstance(device_type_id, str) and device_type_id.strip():
        try:
            device_type_id = data["device_type_id"] = int(device_type_id)
        except ValueError:
            device_type_id = None
    if isinstance(category, str) and category.strip():
        try:
            category = data["category"] = int(category)
        except ValueError:
            category = None

    if device_type_id is not None and "category" not in data:
        mapped_category = DEVICE_TYPE_ID_TO_CATEGORY.get(device_type_id)
        if mapped_category is not None:
            data["category"] = mapped_category
    elif category is not None and "device_type_id" not in data:
        mapped_device_type_id = CATEGORY_TO_DEVICE_TYPE_ID.get(category)
        if mapped_device_type_id is not None:
            data["device_type_id"] = mapped_device_type_id


def _sync_monitor_equipment_identifier_fields(data: dict[str, Any]) -> None:
    asset_code = data.get("asset_code")
    external_device_id = data.get("external_device_id")
    code = data.get("code")

    if isinstance(asset_code, str):
        asset_code = asset_code.strip() or None
        data["asset_code"] = asset_code
    if isinstance(external_device_id, str):
        external_device_id = external_device_id.strip() or None
        data["external_device_id"] = external_device_id
    if isinstance(code, str):
        code = code.strip() or None
        data["code"] = code

    if not external_device_id and code:
        data["external_device_id"] = code


def _normalize_area_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "is_enabled" in payload and "is_enable" not in payload:
        payload["is_enable"] = payload.pop("is_enabled")
    else:
        payload.pop("is_enabled", None)
    if "remark" in payload and "description" not in payload:
        payload["description"] = payload["remark"]
    payload["remark"] = payload.get("remark") or payload.get("description")
    if "area_type" in payload and isinstance(payload["area_type"], str):
        area_type = payload["area_type"].strip().lower()
        payload["area_type"] = area_type if area_type in AREA_TYPE_OPTIONS else "other"
    _coerce_int_fields(payload, ["parent_id", "level", "sort_index", "area_id"])
    return payload


def _normalize_device_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "area_id" in payload and "sector_id" not in payload:
        payload["sector_id"] = payload["area_id"]
    payload.pop("area_id", None)
    if "location_desc" in payload and "location" not in payload:
        payload["location"] = payload["location_desc"]
    payload.pop("location_desc", None)
    if "owner_department" in payload and "owner_unit" not in payload:
        payload["owner_unit"] = payload["owner_department"]
    payload.pop("owner_department", None)
    if "is_enabled" in payload and "is_enable" not in payload:
        payload["is_enable"] = payload["is_enabled"]
    payload.pop("is_enabled", None)
    _coerce_datetime_fields(payload, ["install_time", "last_inspection_at", "inspection_due_at"])
    _coerce_int_fields(payload, ["sector_id", "device_type_id", "category", "sort_index", "parent_device_id"])
    _coerce_float_fields(payload, ["rated_power_kw"])
    _sync_monitor_equipment_type_fields(payload)
    _sync_monitor_equipment_identifier_fields(payload)
    return payload


async def _ensure_default_device_points(db_session: AsyncSession, equipment: m.MonitorEquipment) -> None:
    device_type_id = equipment.device_type_id
    if device_type_id is None:
        return
    device_type_code = DEVICE_TYPE_ID_TO_CODE.get(device_type_id)
    if not device_type_code:
        return
    templates = DEFAULT_DEVICE_POINT_TEMPLATES.get(device_type_code)
    if not templates:
        return

    existing_codes = {
        row[0]
        for row in (
            await db_session.execute(
                select(m.DevicePoint.point_code).where(m.DevicePoint.device_id == equipment.id)
            )
        ).all()
    }
    for template in templates:
        if template["point_code"] in existing_codes:
            continue
        db_session.add(
            m.DevicePoint(
                device_id=equipment.id,
                point_code=template["point_code"],
                point_name=template["point_name"],
                unit=template["unit"],
                value_type=template["value_type"],
                source_field=template["source_field"],
                sampling_interval_seconds=300,
                is_enabled=True,
                is_alarm_enabled=template.get("is_alarm_enabled", False),
            )
        )


async def _ensure_default_device_types(db_session: AsyncSession) -> None:
    existing_rows = (await db_session.execute(select(m.DeviceType.id, m.DeviceType.code))).all()
    existing_codes = {code for _identifier, code in existing_rows}
    existing_ids = {int(identifier) for identifier, _code in existing_rows}
    missing = [item for item in DEFAULT_DEVICE_TYPES if item["code"] not in existing_codes]
    if not missing:
        return
    next_id = max(existing_ids, default=0) + 1
    for item in missing:
        payload = dict(item)
        payload_id = int(payload["id"])
        if payload_id in existing_ids:
            payload["id"] = next_id
            next_id += 1
        existing_ids.add(int(payload["id"]))
        db_session.add(m.DeviceType(**payload))
    await db_session.commit()


def _matches_keyword(row: dict[str, Any], keyword: str | None, fields: list[str]) -> bool:
    if not keyword:
        return True
    needle = keyword.strip().lower()
    if not needle:
        return True
    return any(needle in str(row.get(field) or "").lower() for field in fields)


def _slice_rows(rows: list[dict[str, Any]], limit: int = 200, offset: int = 0) -> dict[str, Any]:
    limit_clamped = max(10, min(limit, 1000))
    offset_clamped = max(0, offset)
    return {
        "items": rows[offset_clamped : offset_clamped + limit_clamped],
        "total": len(rows),
        "limit": limit_clamped,
        "offset": offset_clamped,
    }


def _paged_payload(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


def _jsonable_mapping(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _build_list_filters(
    model: Any,
    *,
    limit: int,
    offset: int,
    search: str | None,
    keyword: str | None,
    search_fields: list[str] | None,
    sort_field: str,
    sort_order: str,
) -> tuple[list[Any], int, int]:
    limit_clamped = max(1, min(limit, 100))
    offset_clamped = max(0, offset)
    filters: list[Any] = [LimitOffset(limit_clamped, offset_clamped)]
    order = "asc" if sort_order == "asc" else "desc"
    if sort_field and hasattr(model, sort_field):
        filters.append(OrderBy(getattr(model, sort_field), order))
    search_value = (search or keyword or "").strip()
    if search_value and search_fields:
        filters.append(SearchFilter(field_name=set(search_fields), value=search_value, ignore_case=True))
    return filters, limit_clamped, offset_clamped


async def _list_page(
    service: Any,
    model: Any,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    keyword: str | None = None,
    search_fields: list[str] | None = None,
    sort_field: str = "id",
    sort_order: str = "desc",
    conditions: list[Any] | None = None,
) -> dict[str, Any]:
    filters, limit_clamped, offset_clamped = _build_list_filters(
        model,
        limit=limit,
        offset=offset,
        search=search,
        keyword=keyword,
        search_fields=search_fields,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    rows, total = await service.list_and_count(*(conditions or []), *filters)
    return _paged_payload([model_to_dict(row) for row in rows], total, limit_clamped, offset_clamped)


async def _list_rows(
    service: Any,
    model: Any,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    keyword: str | None = None,
    search_fields: list[str] | None = None,
    sort_field: str = "id",
    sort_order: str = "desc",
    conditions: list[Any] | None = None,
) -> list[Any]:
    filters, _, _ = _build_list_filters(
        model,
        limit=limit,
        offset=offset,
        search=search,
        keyword=keyword,
        search_fields=search_fields,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    return await service.list(*(conditions or []), *filters)


def _format_decimal(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value if isinstance(value, Decimal) else Decimal(str(value)))


def _compute_year_from_date(value: str | datetime.date | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value.year
    if isinstance(value, str):
        try:
            if len(value) == 7:
                return datetime.date.fromisoformat(f"{value}-01").year
            return datetime.date.fromisoformat(value[:10]).year
        except ValueError:
            return None
    return None


def _decimal_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


async def _load_energy_type(session: AsyncSession, code: str) -> m.EnergyType | None:
    return await session.scalar(select(m.EnergyType).where(m.EnergyType.code == code, m.EnergyType.is_enabled.is_(True)))


def _normalized_energy_unit(value: str | None) -> str:
    return (value or "").strip().replace("³", "3").replace(" ", "").lower()


async def _convert_to_energy_factor_unit(
    session: AsyncSession,
    *,
    energy_type: m.EnergyType,
    amount: Decimal,
    from_unit: str | None,
) -> tuple[Decimal | None, str | None, Decimal | None, str | None]:
    factor_unit = energy_type.original_unit
    if not factor_unit:
        return None, None, None, None
    if _normalized_energy_unit(from_unit) == _normalized_energy_unit(factor_unit):
        return amount, factor_unit, Decimal(1), "原始单位与折标基准单位一致"
    conversion = await session.scalar(
        select(m.EnergyUnitConversion).where(
            m.EnergyUnitConversion.energy_type_code == energy_type.code,
            m.EnergyUnitConversion.is_enabled.is_(True),
            func.lower(func.replace(func.replace(func.trim(m.EnergyUnitConversion.from_unit), "³", "3"), " ", "")) == _normalized_energy_unit(from_unit),
            func.lower(func.replace(func.replace(func.trim(m.EnergyUnitConversion.to_unit), "³", "3"), " ", "")) == _normalized_energy_unit(factor_unit),
        )
    )
    if conversion is None:
        return None, factor_unit, None, None
    factor = _decimal_value(conversion.multiply_factor)
    return amount * factor, factor_unit, factor, conversion.conversion_factor_source


async def _build_purchased_energy_snapshot_payload(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    energy_type_code = str(payload.get("energy_type_code") or "").strip()
    if energy_type_code not in PURCHASED_SCOPE2_ENERGY_CODES:
        raise CarbonValidationError("Scope2 外购能源仅允许外购热力、外购蒸汽、外购冷量。")

    energy_type = await _load_energy_type(session, energy_type_code)
    if not energy_type or energy_type.default_scope != "scope2" or energy_type.category != "purchased_energy":
        raise CarbonValidationError("能源品种字典缺少有效的 Scope2 外购能源口径。")

    amount = _decimal_value(payload.get("amount"))
    if amount is None:
        raise CarbonValidationError("能源消费量不能为空。")
    validate_consumption(amount, "能源消费量")

    factor_amount, factor_unit, unit_conversion_factor, unit_conversion_source = await _convert_to_energy_factor_unit(
        session,
        energy_type=energy_type,
        amount=amount,
        from_unit=str(payload.get("unit") or energy_type.original_unit or ""),
    )
    standard_amount = _decimal_value(payload.get("standard_amount"))
    standard_unit = payload.get("standard_unit") or energy_type.standard_unit
    factor = _decimal_value(energy_type.standard_factor)
    if standard_amount is None and factor is not None and factor_amount is not None:
        standard_amount = factor_amount * factor
    tce_amount = _decimal_value(payload.get("tce_amount"))
    if tce_amount is None and standard_amount is not None and standard_unit == "kgce":
        tce_amount = standard_amount / Decimal(1000)

    factor_payload: dict[str, Any] = {
        "calc_status": "missing_factor",
        "factor_source": None,
        "factor_year": _compute_year_from_date(payload.get("period_start")),
        "factor_unit": None,
        "activity_amount": _format_decimal(amount),
        "activity_unit": payload.get("unit"),
        "computed_co2e": None,
        "computation_note": (
            "暂未匹配外购热力/蒸汽/冷量排放因子，已完成能耗折标口径。"
            if factor_amount is not None
            else f"缺少 {payload.get('unit')} 到 {factor_unit or '折标基准单位'} 的单位换算，未计算折标煤。"
        ),
    }
    try:
        computation = await compute_emission_result(
            session,
            "scope2",
            "purchased_energy",
            energy_type_code,
            amount,
            str(payload.get("unit") or energy_type.original_unit or ""),
            _compute_year_from_date(payload.get("period_start")),
        )
    except CarbonValidationError:
        computation = None
    if computation is not None:
        factor_payload = {
            "calc_status": "ready",
            "factor_source": computation.factor_source,
            "factor_year": computation.factor_year,
            "factor_unit": computation.factor_unit,
            "activity_amount": _format_decimal(computation.activity_amount),
            "activity_unit": computation.activity_unit,
            "computed_co2e": _format_decimal(computation.co2e),
            "computation_note": "按外购能源活动量与匹配排放因子计算。",
        }

    return {
        "energy_type_name": payload.get("energy_type_name") or energy_type.name,
        "standard_amount": _format_decimal(standard_amount),
        "standard_unit": standard_unit,
        "tce_amount": _format_decimal(tce_amount),
        "standard_code": payload.get("standard_code") or energy_type.standard_code,
        "conversion_factor_source": payload.get("conversion_factor_source")
        or "; ".join(item for item in [unit_conversion_source, energy_type.conversion_factor_source] if item),
        **factor_payload,
    }


async def _build_scope_record_computation(record: Any, session: AsyncSession, *, source_kind: str | None = None) -> dict[str, Any]:
    model_type = type(record)
    resolved_source_kind = _record_source_kind(record, source_kind)
    computation = None
    note = ""
    if model_type is m.Scope1MobileCombustion:
        computation = await compute_emission_result(
            session, "scope1", "fuel", record.fuel_type, record.amount, record.unit, _compute_year_from_date(record.record_date)
        )
        note = "按活动量与燃料排放因子计算。"
    elif model_type is m.Scope1StationaryCombustion:
        computation = await compute_emission_result(
            session, "scope1", "fuel", record.fuel_type, record.amount, record.unit, _compute_year_from_date(record.period_start)
        )
        note = "按固定源燃料消耗量与因子计算。"
    elif model_type is m.Scope1RefrigerantLeak:
        computation = await compute_emission_result(
            session, "scope1", "refrigerant", record.refrigerant_type, record.amount_kg, "kg", _compute_year_from_date(record.fill_date)
        )
        note = "按制冷剂用量与逸散因子计算。"
    elif model_type is m.Scope2ElectricityBill:
        computation = await compute_emission_result(
            session, "scope2", "electricity", "grid_electricity", record.total_kwh, "kWh", _compute_year_from_date(record.billing_month)
        )
        note = "按人工电费账单总电量计算。"
        resolved_source_kind = SOURCE_KIND_MANUAL_BILL
    elif model_type is m.Scope2MeterAggregate:
        if record.calc_status != "ready":
            return {
                "source_kind": resolved_source_kind,
                "data_origin": _data_origin_for_source_kind(resolved_source_kind),
                "calc_status": record.calc_status,
                "factor_source": None,
                "factor_year": None,
                "factor_unit": None,
                "activity_amount": _format_decimal(record.total_kwh),
                "activity_unit": "kWh",
                "computed_co2e": None,
                "computation_note": record.aggregation_note or "聚合结果不可核算，请先修复采样数据。",
            }
        computation = await compute_emission_result(
            session, "scope2", "electricity", "grid_electricity", record.total_kwh or 0, "kWh", _compute_year_from_date(record.billing_month)
        )
        note = record.aggregation_note or "按月度电表首末读数差值聚合后计算。"
        resolved_source_kind = SOURCE_KIND_DERIVED
    elif model_type is m.Scope3WasteDisposal:
        computation = await compute_emission_result(
            session, "scope3", "waste", record.category, record.weight_ton, "t", _compute_year_from_date(record.date)
        )
        note = "按废弃物重量与处置因子计算。"
    elif model_type is m.Scope3ThirdPartyTransport:
        ton_km = Decimal(str(record.distance_km)) * Decimal(str(record.load_ton))
        computation = await compute_emission_result(
            session, "scope3", "transport", record.vehicle_type, ton_km, "t·km", None
        )
        note = "按吨公里与运输因子计算。"

    if computation is None:
        activity_amount, activity_unit = _fallback_activity_snapshot(record)
        return {
            "source_kind": resolved_source_kind,
            "data_origin": _data_origin_for_source_kind(resolved_source_kind),
            "calc_status": "missing_factor",
            "factor_source": None,
            "factor_year": _compute_year_from_date(_scope_record_period(record)),
            "factor_unit": None,
            "activity_amount": activity_amount,
            "activity_unit": activity_unit,
            "computed_co2e": None,
            "computation_note": "未找到匹配的排放因子，当前记录无法形成稳定 CO2e 结果。",
        }

    return {
        "source_kind": resolved_source_kind,
        "data_origin": _data_origin_for_source_kind(resolved_source_kind),
        "calc_status": "ready",
        "factor_source": computation.factor_source,
        "factor_year": computation.factor_year,
        "factor_unit": computation.factor_unit,
        "activity_amount": _format_decimal(computation.activity_amount),
        "activity_unit": computation.activity_unit,
        "computed_co2e": _format_decimal(computation.co2e),
        "computation_note": note,
    }


def _scope2_snapshot_fields(data: dict[str, Any], *, source_kind: str) -> dict[str, Any]:
    return {
        "source_kind": source_kind,
        "data_origin": _data_origin_for_source_kind(source_kind),
        "calc_status": data.get("calc_status"),
        "factor_source": data.get("factor_source"),
        "factor_year": data.get("factor_year"),
        "factor_unit": data.get("factor_unit"),
        "activity_amount": _format_decimal(data.get("activity_amount")),
        "activity_unit": data.get("activity_unit"),
        "computed_co2e": _format_decimal(data.get("computed_co2e")),
        "computation_note": data.get("computation_note"),
    }


def _mutable_record_data(record: Any) -> dict[str, Any]:
    data = model_to_dict(record)
    for key in ("id", "created_at", "updated_at"):
        data.pop(key, None)
    return data


async def _build_scope2_snapshot_payload(
    model_type: type[m.Scope2ElectricityBill] | type[m.Scope2MeterAggregate] | type[m.Scope2PurchasedEnergy],
    payload: dict[str, Any],
    session: AsyncSession,
    *,
    source_kind: str,
) -> dict[str, Any]:
    if model_type is m.Scope2PurchasedEnergy:
        return await _build_purchased_energy_snapshot_payload(payload, session)
    record = model_type(**payload)
    computation = await _build_scope_record_computation(record, session, source_kind=source_kind)
    return {
        "calc_status": computation["calc_status"],
        "factor_source": computation["factor_source"],
        "factor_year": computation["factor_year"],
        "factor_unit": computation["factor_unit"],
        "activity_amount": computation["activity_amount"],
        "activity_unit": computation["activity_unit"],
        "computed_co2e": computation["computed_co2e"],
        "computation_note": computation["computation_note"],
    }


async def _refresh_scope2_snapshot(
    record: m.Scope2ElectricityBill | m.Scope2MeterAggregate | m.Scope2PurchasedEnergy,
    service: services.Scope2ElectricityBillService | services.Scope2MeterAggregateService | services.Scope2PurchasedEnergyService,
    *,
    source_kind: str,
) -> Any:
    payload = _mutable_record_data(record)
    payload.update(await _build_scope2_snapshot_payload(type(record), payload, service.repository.session, source_kind=source_kind))
    await service.update(item_id=record.id, data=payload, auto_commit=True)
    return await service.get_one(id=record.id)


def _scope2_snapshot_ready(record: Any) -> bool:
    return bool(record.calc_status == "ready" and record.computed_co2e is not None)


async def _serialize_scope_record(record: Any, session: AsyncSession, *, source_kind: str | None = None) -> dict[str, Any]:
    data = model_to_dict(record)
    if isinstance(record, m.Scope2ElectricityBill):
        data.update(_scope2_snapshot_fields(data, source_kind=source_kind or SOURCE_KIND_MANUAL_BILL))
        return data
    if isinstance(record, m.Scope2PurchasedEnergy):
        data.update(_scope2_snapshot_fields(data, source_kind=source_kind or "purchased_energy"))
        return data
    if isinstance(record, m.Scope2MeterAggregate):
        data.update(_scope2_snapshot_fields(data, source_kind=source_kind or SOURCE_KIND_DERIVED))
        return data
    data.update(await _build_scope_record_computation(record, session, source_kind=source_kind))
    return data


async def _augment_page_items(
    page: dict[str, Any], items: list[Any], session: AsyncSession, *, source_kind: str | None = None
) -> dict[str, Any]:
    page["items"] = [await _serialize_scope_record(item, session, source_kind=source_kind) for item in items]
    page["data"] = page["items"]
    return page


def _month_window(billing_month: str) -> tuple[datetime.datetime, datetime.datetime]:
    month_start = datetime.datetime.fromisoformat(f"{billing_month}-01T00:00:00")
    month_end = month_start + relativedelta(months=1)
    return month_start, month_end


def _month_string(value: datetime.date | datetime.datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date().strftime("%Y-%m")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m")
    if isinstance(value, str):
        candidate = value.strip()
        if len(candidate) >= 7:
            return candidate[:7]
    return None


def _sort_month_key(value: str | None) -> tuple[int, int]:
    if not value:
        return (0, 0)
    try:
        year, month = value.split("-", 1)
        return (int(year), int(month))
    except (ValueError, TypeError):
        return (0, 0)


def _months_back(end_month: str, count: int = 12) -> list[str]:
    end_date = datetime.date.fromisoformat(f"{end_month}-01")
    return [(end_date - relativedelta(months=index)).strftime("%Y-%m") for index in range(count - 1, -1, -1)]


def _month_span(start_month: str, end_month: str) -> list[str]:
    start_date = _month_start_date(start_month)
    end_date = _month_start_date(end_month)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    months: list[str] = []
    cursor = start_date
    while cursor <= end_date:
        months.append(cursor.strftime("%Y-%m"))
        year = cursor.year + (cursor.month // 12)
        month = (cursor.month % 12) + 1
        cursor = datetime.date(year, month, 1)
    return months


def _month_start_date(value: str) -> datetime.date:
    return datetime.date.fromisoformat(f"{value}-01")


def _median_value(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _historical_fit_kwh(
    seasonal_values: list[float],
    recent_values: list[float],
    baseline_values: list[float],
) -> float | None:
    baseline_median = _median_value(baseline_values)
    if baseline_median is None:
        return None

    weighted_parts: list[tuple[float, float]] = []
    seasonal_median = _median_value(seasonal_values)
    recent_median = _median_value(recent_values)

    if seasonal_median is not None:
        weighted_parts.append((0.55, seasonal_median))
    if recent_median is not None:
        weighted_parts.append((0.3 if seasonal_median is not None else 0.7, recent_median))
    weighted_parts.append((0.15 if seasonal_median is not None else 0.3, baseline_median))

    total_weight = sum(weight for weight, _ in weighted_parts)
    estimate = sum(weight * value for weight, value in weighted_parts) / total_weight

    sorted_values = sorted(baseline_values)
    high_index = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * 0.8)))
    capped_high = sorted_values[high_index]
    max_value = sorted_values[-1]
    estimate = min(estimate, max(capped_high, baseline_median), max_value)
    return round(max(estimate, 0.0), 4)


def _seed_months(end_month: str, count: int = 6) -> list[str]:
    return _months_back(end_month, count)


def _scope_record_label(record_type: str) -> str:
    return {
        "Scope1MobileCombustion": "[范围1] 移动源燃烧",
        "Scope1StationaryCombustion": "[范围1] 固定源燃烧",
        "Scope1RefrigerantLeak": "[范围1] 制冷剂逸散",
        "Scope2ElectricityBill": "[范围2] 账单补录",
        "Scope2MeterAggregate": "[范围2] 电表聚合",
        "Scope2PurchasedEnergy": "[范围2] 外购热力/蒸汽/冷量",
        "Scope3WasteDisposal": "[范围3] 废弃物处理",
        "Scope3ThirdPartyTransport": "[范围3] 外购运输",
    }.get(record_type, record_type)


def _scope_group_label(record_type: str) -> str:
    if record_type.startswith("Scope1"):
        return "范围1"
    if record_type.startswith("Scope2"):
        return "范围2"
    if record_type.startswith("Scope3"):
        return "范围3"
    return "其他"


def _scope_trend_key(scope_label: str) -> str | None:
    return {
        "范围1": "scope1_co2e",
        "范围2": "scope2_co2e",
        "范围3": "scope3_co2e",
    }.get(scope_label)


def _scope_display_name(record: Any) -> str:
    if isinstance(record, m.Scope1MobileCombustion):
        return record.asset_name or record.asset_id or record.fuel_type
    if isinstance(record, m.Scope1StationaryCombustion):
        return record.facility_name or record.fuel_type
    if isinstance(record, m.Scope1RefrigerantLeak):
        return record.device_name or record.device_id or record.refrigerant_type
    if isinstance(record, m.Scope2ElectricityBill):
        return record.account_number
    if isinstance(record, m.Scope2PurchasedEnergy):
        return record.facility_name or record.supplier_name or record.energy_type_name or record.energy_type_code
    if isinstance(record, m.Scope2MeterAggregate):
        return record.ammeter_name or record.ammeter_id
    if isinstance(record, m.Scope3WasteDisposal):
        return record.vendor_name or record.category
    if isinstance(record, m.Scope3ThirdPartyTransport):
        return record.waybill_no or record.vehicle_type
    return type(record).__name__


def _scope_record_period(record: Any) -> str | None:
    if isinstance(record, m.Scope1MobileCombustion):
        return _month_string(record.record_date)
    if isinstance(record, m.Scope1StationaryCombustion):
        return _month_string(record.period_start)
    if isinstance(record, m.Scope1RefrigerantLeak):
        return _month_string(record.fill_date)
    if isinstance(record, (m.Scope2ElectricityBill, m.Scope2MeterAggregate)):
        return getattr(record, "billing_month", None)
    if isinstance(record, m.Scope2PurchasedEnergy):
        return _month_string(record.period_start)
    if isinstance(record, m.Scope3WasteDisposal):
        return _month_string(record.date)
    if isinstance(record, m.Scope3ThirdPartyTransport):
        return _month_string(record.created_at)
    return None


def _record_remark(record: Any) -> str:
    value = getattr(record, "remark", None)
    return str(value or "")


def _record_attachment(record: Any) -> str | None:
    value = getattr(record, "attachment", None)
    if value in (None, ""):
        return None
    return str(value)


def _is_demo_seed_record(record: Any) -> bool:
    return DEMO_SEED_MARKER in _record_remark(record)


def _record_source_kind(record: Any, default: str | None = None) -> str:
    if isinstance(record, m.Scope2ElectricityBill):
        return SOURCE_KIND_MANUAL_BILL
    if isinstance(record, m.Scope2PurchasedEnergy):
        return "purchased_energy"
    if isinstance(record, m.Scope2MeterAggregate):
        return SOURCE_KIND_DERIVED
    if _is_demo_seed_record(record):
        return SOURCE_KIND_DEMO_SEED
    return default or SOURCE_KIND_REAL


def _data_origin_for_source_kind(source_kind: str | None) -> str:
    if source_kind == SOURCE_KIND_DERIVED:
        return "derived"
    if source_kind == SOURCE_KIND_ESTIMATE:
        return "estimated"
    if source_kind == SOURCE_KIND_DEMO_SEED:
        return "demo_seed"
    if source_kind == SOURCE_KIND_FALLBACK:
        return "fallback"
    return "real"


def _source_kind_label(source_kind: str | None) -> str:
    if source_kind == SOURCE_KIND_DERIVED:
        return "电表聚合"
    if source_kind == SOURCE_KIND_MANUAL_BILL:
        return "账单补录"
    if source_kind == SOURCE_KIND_DEMO_SEED:
        return "演示样例"
    if source_kind == SOURCE_KIND_FALLBACK:
        return "明细回退"
    if source_kind == SOURCE_KIND_ESTIMATE:
        return "历史估算"
    if source_kind == SOURCE_KIND_REAL:
        return "活动数据"
    return source_kind or "未标注"


def _fallback_activity_snapshot(record: Any) -> tuple[float | None, str | None]:
    if isinstance(record, m.Scope2MeterAggregate):
        return _format_decimal(record.total_kwh), "kWh"
    if isinstance(record, m.Scope2ElectricityBill):
        return _format_decimal(record.total_kwh), "kWh"
    if isinstance(record, m.Scope1MobileCombustion):
        return _format_decimal(record.amount), record.unit
    if isinstance(record, m.Scope1StationaryCombustion):
        return _format_decimal(record.amount), record.unit
    if isinstance(record, m.Scope1RefrigerantLeak):
        return _format_decimal(record.amount_kg), "kg"
    if isinstance(record, m.Scope3WasteDisposal):
        return _format_decimal(record.weight_ton), "t"
    if isinstance(record, m.Scope3ThirdPartyTransport):
        value = Decimal(str(record.distance_km)) * Decimal(str(record.load_ton))
        return _format_decimal(value), "t·km"
    return None, None


class CarbonAnalyticsController(Controller):
    """统一能碳分析与追溯接口。"""

    tags = ["CarbonAnalytics"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]

    @staticmethod
    async def _latest_energy_month(db_session: AsyncSession) -> str | None:
        meter_month = await db_session.scalar(select(func.max(m.Scope2MeterAggregate.billing_month)))
        if meter_month:
            return str(meter_month)
        bill_month = await db_session.scalar(select(func.max(m.Scope2ElectricityBill.billing_month)))
        if bill_month:
            return str(bill_month)
        raw_last = await db_session.scalar(select(func.max(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        return _month_string(raw_last)

    @staticmethod
    async def _recent_scope2_backfill_months(db_session: AsyncSession, months: int = 12) -> list[str]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        if not latest_month:
            return []
        month_keys = _months_back(latest_month, max(1, min(months, 24)))
        raw_start = _month_window(month_keys[0])[0]
        raw_end = _month_window(month_keys[-1])[1]
        rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=raw_start, month_end=raw_end)
        valid_months = {str(row["billing_month"]) for row in rows if float(row.get("total_kwh") or 0.0) > 0}
        return [month for month in month_keys if month in valid_months]

    @staticmethod
    async def _raw_history_month_range(db_session: AsyncSession) -> tuple[str | None, str | None]:
        first_time = await db_session.scalar(select(func.min(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        last_time = await db_session.scalar(select(func.max(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        return (_month_string(first_time), _month_string(last_time))

    @staticmethod
    async def _scope2_factor_for_month(db_session: AsyncSession, billing_month: str) -> dict[str, Any] | None:
        try:
            result = await compute_emission_result(
                db_session,
                "scope2",
                "electricity",
                "grid_electricity",
                1,
                "kWh",
                _compute_year_from_date(billing_month),
            )
        except CarbonValidationError:
            return None
        if result is None:
            return None
        return {
            "factor_source": result.factor_source,
            "factor_year": result.factor_year,
            "factor_unit": result.factor_unit,
            "factor_value": _format_decimal(result.co2e),
        }

    @staticmethod
    async def _historical_scope2_estimates_for_month(
        db_session: AsyncSession,
        billing_month: str,
        current_rows: list[m.Scope2MeterAggregate] | None = None,
    ) -> list[dict[str, Any]]:
        if current_rows is None:
            current_rows = (
                await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == billing_month))
            ).scalars().all()

        candidates = [
            row
            for row in current_rows
            if row.ammeter_id and (row.calc_status != "ready" or float(row.total_kwh or 0.0) <= 0.0)
        ]
        if not candidates:
            return []

        candidate_ids = sorted({str(row.ammeter_id) for row in candidates if row.ammeter_id})
        history_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(
                    m.Scope2MeterAggregate.ammeter_id.in_(candidate_ids),
                    m.Scope2MeterAggregate.billing_month < billing_month,
                    m.Scope2MeterAggregate.calc_status == "ready",
                    m.Scope2MeterAggregate.total_kwh.is_not(None),
                    m.Scope2MeterAggregate.total_kwh > 0,
                )
                .order_by(m.Scope2MeterAggregate.ammeter_id.asc(), m.Scope2MeterAggregate.billing_month.asc())
            )
        ).scalars().all()

        history_by_meter: dict[str, list[m.Scope2MeterAggregate]] = defaultdict(list)
        for row in history_rows:
            if row.ammeter_id:
                history_by_meter[str(row.ammeter_id)].append(row)

        factor = await CarbonAnalyticsController._scope2_factor_for_month(db_session, billing_month)
        factor_value = float(factor["factor_value"]) if factor and factor.get("factor_value") is not None else None
        target_month_token = billing_month[-2:]

        estimates: list[dict[str, Any]] = []
        for candidate in candidates:
            meter_key = str(candidate.ammeter_id)
            history = history_by_meter.get(meter_key, [])
            baseline_values = [float(row.total_kwh or 0.0) for row in history if float(row.total_kwh or 0.0) > 0.0]
            if len(baseline_values) < 2:
                continue

            seasonal_values = [
                float(row.total_kwh or 0.0)
                for row in history
                if row.billing_month and str(row.billing_month).endswith(target_month_token) and float(row.total_kwh or 0.0) > 0.0
            ]
            recent_values = baseline_values[-6:]
            estimate_kwh = _historical_fit_kwh(seasonal_values, recent_values, baseline_values)
            if estimate_kwh is None or estimate_kwh <= 0:
                continue

            if len(seasonal_values) >= 2 or len(recent_values) >= 4:
                confidence = "high"
            elif len(baseline_values) >= 3:
                confidence = "medium"
            else:
                confidence = "low"

            estimate_co2e = round(estimate_kwh * factor_value, 6) if factor_value is not None else None
            estimates.append(
                {
                    "record_type": "Scope2HistoricalEstimate",
                    "record_id": None,
                    "display_name": candidate.ammeter_name or candidate.ammeter_id,
                    "ammeter_id": candidate.ammeter_id,
                    "ammeter_name": candidate.ammeter_name,
                    "area_id": candidate.area_id,
                    "area_name": candidate.area_name,
                    "period": billing_month,
                    "billing_month": billing_month,
                    "source_kind": SOURCE_KIND_ESTIMATE,
                    "data_origin": _data_origin_for_source_kind(SOURCE_KIND_ESTIMATE),
                    "total_kwh": estimate_kwh,
                    "computed_co2e": estimate_co2e,
                    "calc_status": "estimated",
                    "status": STATUS_DRAFT,
                    "factor_source": factor["factor_source"] if factor else None,
                    "factor_year": factor["factor_year"] if factor else None,
                    "confidence": confidence,
                    "history_months": len(baseline_values),
                    "computation_note": f"基于{len(baseline_values)}个历史有效月进行季节/近期中位数拟合。",
                }
            )
        return estimates

    @staticmethod
    async def _raw_meter_rollups(
        db_session: AsyncSession,
        *,
        month_start: datetime.datetime,
        month_end: datetime.datetime,
    ) -> list[dict[str, Any]]:
        sql = text(
            """
            select
                to_char(date_trunc('month', reading_time), 'YYYY-MM') as billing_month,
                ammeter_id,
                max(ammeter_name) as ammeter_name,
                coalesce(max(area_id), '') as area_id,
                coalesce(max(area_name), '未分区') as area_name,
                min(reading_time) as first_reading_time,
                max(reading_time) as last_reading_time,
                min(zygdn) as start_total_energy,
                max(zygdn) as end_total_energy,
                greatest(max(zygdn) - min(zygdn), 0) as total_kwh,
                count(*) as sample_count
            from dataapp_ammeterindexvalue
            where
                reading_time >= :month_start
                and reading_time < :month_end
                and reading_time is not null
                and ammeter_id is not null
                and zygdn is not null
            group by 1, ammeter_id
            order by total_kwh desc nulls last, ammeter_id asc
            """
        )
        rows = (await db_session.execute(sql, {"month_start": month_start, "month_end": month_end})).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    async def _load_scope_records(db_session: AsyncSession) -> list[dict[str, Any]]:
        model_specs: list[tuple[str, Any, str | None]] = [
            ("Scope1MobileCombustion", m.Scope1MobileCombustion, SOURCE_KIND_REAL),
            ("Scope1StationaryCombustion", m.Scope1StationaryCombustion, SOURCE_KIND_REAL),
            ("Scope1RefrigerantLeak", m.Scope1RefrigerantLeak, SOURCE_KIND_REAL),
            ("Scope2ElectricityBill", m.Scope2ElectricityBill, SOURCE_KIND_MANUAL_BILL),
            ("Scope2MeterAggregate", m.Scope2MeterAggregate, SOURCE_KIND_DERIVED),
            ("Scope2PurchasedEnergy", m.Scope2PurchasedEnergy, "purchased_energy"),
            ("Scope3WasteDisposal", m.Scope3WasteDisposal, SOURCE_KIND_REAL),
            ("Scope3ThirdPartyTransport", m.Scope3ThirdPartyTransport, SOURCE_KIND_REAL),
        ]
        records: list[dict[str, Any]] = []
        for record_type, model, source_kind in model_specs:
            rows = (await db_session.execute(select(model).where(model.status != STATUS_REJECTED))).scalars().all()
            for row in rows:
                serialized = await _serialize_scope_record(row, db_session, source_kind=_record_source_kind(row, source_kind))
                records.append(
                    {
                        "record_type": record_type,
                        "scope": _scope_group_label(record_type),
                        "record_label": _scope_record_label(record_type),
                        "display_name": _scope_display_name(row),
                        "period": _scope_record_period(row),
                        "row": row,
                        "data": serialized,
                    }
                )
        return records

    @staticmethod
    async def _build_energy_series(db_session: AsyncSession, months: list[str]) -> list[dict[str, Any]]:
        if not months:
            return []
        ready_meter_stmt = (
            select(
                m.Scope2MeterAggregate.billing_month,
                func.sum(m.Scope2MeterAggregate.total_kwh),
                func.sum(m.Scope2MeterAggregate.computed_co2e),
                func.count(m.Scope2MeterAggregate.id),
            )
            .where(
                m.Scope2MeterAggregate.billing_month.in_(months),
                m.Scope2MeterAggregate.calc_status == "ready",
            )
            .group_by(m.Scope2MeterAggregate.billing_month)
        )
        ready_bill_stmt = (
            select(
                m.Scope2ElectricityBill.billing_month,
                func.sum(m.Scope2ElectricityBill.total_kwh),
                func.sum(m.Scope2ElectricityBill.computed_co2e),
                func.count(m.Scope2ElectricityBill.id),
            )
            .where(
                m.Scope2ElectricityBill.billing_month.in_(months),
                m.Scope2ElectricityBill.calc_status == "ready",
            )
            .group_by(m.Scope2ElectricityBill.billing_month)
        )
        meter_rows = {
            str(month): {
                "energy_kwh": _format_decimal(energy) or 0.0,
                "carbon_co2e": _format_decimal(carbon) or 0.0,
                "record_count": int(count or 0),
            }
            for month, energy, carbon, count in (await db_session.execute(ready_meter_stmt)).all()
        }
        bill_rows = {
            str(month): {
                "energy_kwh": _format_decimal(energy) or 0.0,
                "carbon_co2e": _format_decimal(carbon) or 0.0,
                "record_count": int(count or 0),
            }
            for month, energy, carbon, count in (await db_session.execute(ready_bill_stmt)).all()
        }

        raw_start = _month_window(months[0])[0]
        raw_end = _month_window(months[-1])[1]
        raw_rows = await CarbonAnalyticsController._raw_meter_rollups(
            db_session,
            month_start=raw_start,
            month_end=raw_end,
        )
        raw_by_month: dict[str, dict[str, Any]] = defaultdict(lambda: {"energy_kwh": 0.0, "record_count": 0})
        for row in raw_rows:
            month = str(row["billing_month"])
            raw_by_month[month]["energy_kwh"] += float(row["total_kwh"] or 0.0)
            raw_by_month[month]["record_count"] += 1

        series: list[dict[str, Any]] = []
        for month in months:
            if month in meter_rows:
                series.append({"period": month, "source_kind": "meter_aggregate", **meter_rows[month]})
                continue
            if month in bill_rows:
                series.append({"period": month, "source_kind": "manual_bill", **bill_rows[month]})
                continue
            raw_data = raw_by_month.get(month)
            carbon_co2e = None
            if raw_data and raw_data["energy_kwh"] > 0:
                factor = await CarbonAnalyticsController._scope2_factor_for_month(db_session, month)
                carbon_co2e = round(raw_data["energy_kwh"] * (factor["factor_value"] or 0.0), 6) if factor else None
            series.append(
                {
                    "period": month,
                    "source_kind": "raw_meter_fallback" if raw_data and raw_data["energy_kwh"] > 0 else "empty",
                    "energy_kwh": raw_data["energy_kwh"] if raw_data else 0.0,
                    "carbon_co2e": carbon_co2e,
                    "record_count": raw_data["record_count"] if raw_data else 0,
                }
            )
        return series

    @get("/api/carbon/analytics/overview")
    async def get_analytics_overview(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_series = await self._build_energy_series(db_session, _months_back(latest_month, 1) if latest_month else [])
        current_energy = energy_series[-1] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "source_kind": "empty"}
        previous_month = _month_string((datetime.date.fromisoformat(f"{latest_month}-01") - relativedelta(months=1)) if latest_month else None)
        previous_energy_series = await self._build_energy_series(db_session, [previous_month] if previous_month else [])
        previous_energy = previous_energy_series[0] if previous_energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0}

        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        equipment_rows = (
            await db_session.execute(
                select(
                    m.MonitorEquipment.category,
                    func.count(m.MonitorEquipment.id),
                    func.sum(case((m.MonitorEquipment.status == 0, 1), else_=0)),
                )
                .group_by(m.MonitorEquipment.category)
            )
        ).all()
        category_names = {0: "用电终端", 1: "发电终端", 2: "视频终端"}
        monitor_stats = [
            {
                "category": category_names.get(category, f"分类{category}"),
                "total": int(total or 0),
                "online": int(online or 0),
                "fault": max(int(total or 0) - int(online or 0), 0),
            }
            for category, total, online in equipment_rows
        ]

        scope_records = await self._load_scope_records(db_session)
        pending_count = sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING)
        approved_count = sum(1 for item in scope_records if item["data"].get("status") == STATUS_APPROVED)
        carbon_total = sum(float(item["data"].get("computed_co2e") or 0.0) for item in scope_records)
        scope_totals: dict[str, float] = defaultdict(float)
        for item in scope_records:
            scope_totals[item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        alarm_total = await db_session.scalar(select(func.count(m.AlarmEvent.id))) or 0
        alarm_unhandled = await db_session.scalar(select(func.count(m.AlarmEvent.id)).where(m.AlarmEvent.is_handle.is_(False))) or 0
        video_alarm_total = await db_session.scalar(select(func.count(m.VedioAlarmEvent.id))) or 0
        video_alarm_unhandled = await db_session.scalar(select(func.count(m.VedioAlarmEvent.id)).where(m.VedioAlarmEvent.is_handle.is_(False))) or 0

        current_energy_value = float(current_energy.get("energy_kwh") or 0.0)
        previous_energy_value = float(previous_energy.get("energy_kwh") or 0.0)
        current_carbon_value = carbon_total
        previous_carbon_value = None
        energy_delta_ratio = ((current_energy_value - previous_energy_value) / previous_energy_value * 100) if previous_energy_value else None
        carbon_delta_ratio = None if previous_carbon_value in (None, 0) else ((current_carbon_value - previous_carbon_value) / previous_carbon_value * 100)

        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "enterprise": enterprise.to_dict() if enterprise else {},
                    "kpis": [
                        {"id": "energy", "label": "当期用电量", "value": round(current_energy_value, 2), "unit": "kWh", "ratio": round(energy_delta_ratio, 2) if energy_delta_ratio is not None else None},
                        {"id": "carbon", "label": "已纳入碳排", "value": round(current_carbon_value, 2), "unit": "kgCO2e", "ratio": round(carbon_delta_ratio, 2) if carbon_delta_ratio is not None else None},
                        {"id": "pending", "label": "待审核记录", "value": pending_count, "unit": "条"},
                        {"id": "alerts", "label": "未处理预警", "value": int(alarm_unhandled) + int(video_alarm_unhandled), "unit": "条"},
                    ],
                    "monitor_stats": monitor_stats,
                    "workflow": {
                        "pending_count": pending_count,
                        "approved_count": approved_count,
                        "total_records": len(scope_records),
                    },
                    "alerts": {
                        "alarm_total": int(alarm_total),
                        "alarm_unhandled": int(alarm_unhandled),
                        "video_alarm_total": int(video_alarm_total),
                        "video_alarm_unhandled": int(video_alarm_unhandled),
                    },
                    "scope_totals": [{"name": scope, "value": round(value, 2)} for scope, value in scope_totals.items()],
                    "source_mix": {
                        "source_kind": current_energy.get("source_kind"),
                        "energy_kwh": round(current_energy_value, 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    },
                },
            }
        )

    @get("/api/carbon/analytics/trend")
    async def get_analytics_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        if not latest_month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"series": [], "months": []}})
        month_keys = _months_back(latest_month, max(3, min(months, 24)))
        energy_series = await self._build_energy_series(db_session, month_keys)
        carbon_records = await self._load_scope_records(db_session)
        scope_month_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for item in carbon_records:
            month = item["period"]
            if not month:
                continue
            scope_month_totals[month][item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        series = []
        for item in energy_series:
            month = item["period"]
            scope1 = scope_month_totals[month].get("范围1", 0.0)
            scope2 = float(item.get("carbon_co2e") or 0.0)
            scope3 = scope_month_totals[month].get("范围3", 0.0)
            series.append(
                {
                    "period": month,
                    "energy_kwh": round(float(item.get("energy_kwh") or 0.0), 2),
                    "scope1_co2e": round(scope1, 2),
                    "scope2_co2e": round(scope2, 2),
                    "scope3_co2e": round(scope3, 2),
                    "carbon_co2e": round(scope1 + scope2 + scope3, 2),
                    "source_kind": item.get("source_kind"),
                }
            )
        return Response(content={"code": 200, "msg": "获取成功", "data": {"months": month_keys, "series": series}})

    @get("/api/carbon/analytics/ranking")
    async def get_analytics_ranking(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_rows: list[dict[str, Any]] = []
        diagnostics = {"source_kind": "empty"}
        if latest_month:
            ready_rows = (
                await db_session.execute(
                    select(m.Scope2MeterAggregate)
                    .where(
                        m.Scope2MeterAggregate.billing_month == latest_month,
                        m.Scope2MeterAggregate.calc_status == "ready",
                    )
                    .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
                )
            ).scalars().all()
            if ready_rows:
                energy_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in ready_rows]
                diagnostics["source_kind"] = "meter_aggregate"
            else:
                month_start, month_end = _month_window(latest_month)
                energy_rows = await self._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
                diagnostics["source_kind"] = "raw_meter_fallback"

        energy_by_area: dict[str, float] = defaultdict(float)
        for row in energy_rows:
            area_name = str(row.get("area_name") or "未分区")
            energy_by_area[area_name] += float(row.get("total_kwh") or 0.0)

        carbon_records = await self._load_scope_records(db_session)
        carbon_by_type: dict[str, float] = defaultdict(float)
        for item in carbon_records:
            carbon_by_type[item["record_label"]] += float(item["data"].get("computed_co2e") or 0.0)

        area_events = (
            await db_session.execute(
                select(m.MonitorSector.name, func.count(m.AlarmEvent.id))
                .join(m.AlarmEvent, m.AlarmEvent.sector_id == m.MonitorSector.id)
                .group_by(m.MonitorSector.name)
                .order_by(func.count(m.AlarmEvent.id).desc())
                .limit(10)
            )
        ).all()

        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "diagnostics": diagnostics,
                    "energy_by_area": [{"name": name, "value": round(value, 2)} for name, value in sorted(energy_by_area.items(), key=lambda item: item[1], reverse=True)[:10]],
                    "carbon_by_type": [{"name": name, "value": round(value, 2)} for name, value in sorted(carbon_by_type.items(), key=lambda item: item[1], reverse=True)[:10]],
                    "alerts_by_area": [{"name": name or "未命名区域", "value": int(total)} for name, total in area_events],
                },
            }
        )

    @get("/api/carbon/analytics/efficiency")
    async def get_analytics_efficiency(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_series = await self._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "record_count": 0, "source_kind": "empty"}
        scope_records = await self._load_scope_records(db_session)
        status_totals: dict[str, int] = defaultdict(int)
        source_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"energy_kwh": 0.0, "carbon_co2e": 0.0, "records": 0.0})
        for item in scope_records:
            status_totals[str(item["data"].get("status") or STATUS_DRAFT)] += 1
            source = str(item["data"].get("source_kind") or item["scope"])
            source_totals[source]["carbon_co2e"] += float(item["data"].get("computed_co2e") or 0.0)
            source_totals[source]["records"] += 1
            if item["record_type"] in {"Scope2ElectricityBill", "Scope2MeterAggregate"}:
                source_totals[source]["energy_kwh"] += float(item["data"].get("total_kwh") or 0.0)

        storage = await db_session.scalar(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))
        source_mix = [
            {
                "name": name,
                "energy_kwh": round(values["energy_kwh"], 2),
                "carbon_co2e": round(values["carbon_co2e"], 2),
                "record_count": int(values["records"]),
            }
            for name, values in sorted(source_totals.items(), key=lambda item: item[1]["carbon_co2e"], reverse=True)
        ]
        if not source_mix and float(current_energy.get("energy_kwh") or 0.0) > 0:
            source_mix = [
                {
                    "name": str(current_energy.get("source_kind") or "raw_meter_fallback"),
                    "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                    "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    "record_count": int(current_energy.get("record_count") or 0),
                }
            ]
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "source_mix": source_mix,
                    "workflow": [{"name": name, "value": total} for name, total in status_totals.items()],
                    "energy_efficiency": {
                        "source_kind": current_energy.get("source_kind"),
                        "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                        "record_count": int(current_energy.get("record_count") or 0),
                    },
                    "storage": model_to_dict(storage) if storage else {},
                },
            }
        )

    @get("/api/carbon/energy-flow")
    async def get_energy_flow(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        month = billing_month or await self._latest_energy_month(db_session)
        if not month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"billing_month": None, "nodes": [], "links": [], "diagnostics": {"source_kind": "empty"}}})
        meter_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.billing_month == month)
                .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
            )
        ).scalars().all()
        diagnostics = {
            "source_kind": "meter_aggregate",
            "ready_count": sum(1 for row in meter_rows if row.calc_status == "ready"),
            "invalid_count": sum(1 for row in meter_rows if row.calc_status != "ready"),
            "used_fallback": False,
            "zero_ready_count": sum(1 for row in meter_rows if row.calc_status == "ready" and float(row.total_kwh or 0.0) <= 0),
        }
        flow_rows: list[dict[str, Any]]
        if meter_rows:
            flow_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in meter_rows if row.total_kwh]
        else:
            month_start, month_end = _month_window(month)
            flow_rows = await self._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
            diagnostics["source_kind"] = "raw_meter_fallback"
            diagnostics["used_fallback"] = True
        nodes: dict[str, dict[str, Any]] = {
            "grid": {"id": "grid", "name": "外部购电", "category": "source"},
        }
        links: list[dict[str, Any]] = []
        total_energy_kwh = 0.0
        for row in flow_rows:
            area_name = str(row.get("area_name") or "未分区")
            area_id = f"area:{area_name}"
            meter_name = str(row.get("ammeter_name") or row.get("display_name") or row.get("ammeter_id") or "未知电表")
            meter_id = f"meter:{row.get('ammeter_id') or meter_name}"
            result_id = f"result:{meter_id}:{month}"
            value = float(row.get("total_kwh") or 0.0)
            if value <= 0:
                continue
            total_energy_kwh += value
            nodes.setdefault(area_id, {"id": area_id, "name": area_name, "category": "area"})
            nodes.setdefault(meter_id, {"id": meter_id, "name": meter_name, "category": "meter"})
            nodes.setdefault(result_id, {"id": result_id, "name": f"{meter_name} 核算结果", "category": "result", "value": round(value, 2)})
            links.append({"source": "grid", "target": area_id, "value": round(value, 2)})
            links.append({"source": area_id, "target": meter_id, "value": round(value, 2)})
            links.append({"source": meter_id, "target": result_id, "value": round(value, 2)})
        diagnostics["total_energy_kwh"] = round(total_energy_kwh, 2)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "billing_month": month,
                    "title": "仓库级能流图",
                    "unit": "kWh",
                    "nodes": list(nodes.values()),
                    "links": links,
                    "diagnostics": diagnostics,
                },
            }
        )

    @get("/api/carbon/carbon-flow")
    async def get_carbon_flow(self, db_session: AsyncSession) -> Response[dict]:
        records = await self._load_scope_records(db_session)
        nodes: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []
        total_co2e = 0.0
        for item in records:
            co2e = float(item["data"].get("computed_co2e") or 0.0)
            if co2e <= 0:
                continue
            total_co2e += co2e
            scope_id = f"scope:{item['scope']}"
            activity_id = f"activity:{item['record_type']}:{item['display_name']}"
            factor_name = str(item["data"].get("factor_source") or "未命名因子")
            factor_year = item["data"].get("factor_year")
            factor_id = f"factor:{factor_name}:{factor_year or 'na'}"
            result_id = f"result:{item['record_type']}"
            nodes.setdefault(scope_id, {"id": scope_id, "name": item["scope"], "category": "scope"})
            nodes.setdefault(activity_id, {"id": activity_id, "name": item["display_name"], "category": "activity"})
            nodes.setdefault(factor_id, {"id": factor_id, "name": f"{factor_name}{f' / {factor_year}' if factor_year else ''}", "category": "factor"})
            nodes.setdefault(result_id, {"id": result_id, "name": item["record_label"], "category": "result"})
            links.append({"source": scope_id, "target": activity_id, "value": round(co2e, 2)})
            links.append({"source": activity_id, "target": factor_id, "value": round(co2e, 2)})
            links.append({"source": factor_id, "target": result_id, "value": round(co2e, 2)})
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "title": "范围级碳流图",
                    "unit": "kgCO2e",
                    "nodes": list(nodes.values()),
                    "links": links,
                    "diagnostics": {
                        "record_count": len(records),
                        "total_co2e": round(total_co2e, 2),
                        "empty_record_types": sorted({_scope_record_label(item["record_type"]) for item in records if item["data"].get("computed_co2e") is None}),
                    },
                },
            }
        )

    @get("/api/carbon/ledger/energy")
    async def get_energy_ledger(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        items: list[dict[str, Any]] = []
        bill_rows = (await db_session.execute(select(m.Scope2ElectricityBill).where(m.Scope2ElectricityBill.status != STATUS_REJECTED))).scalars().all()
        for row in bill_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="manual_bill")
            items.append(
                {
                    "record_type": "Scope2ElectricityBill",
                    "record_id": row.id,
                    "display_name": row.account_number,
                    "area_name": None,
                    "period": row.billing_month,
                    "source_kind": SOURCE_KIND_MANUAL_BILL,
                    "data_origin": data.get("data_origin"),
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        meter_rows = (await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.status != STATUS_REJECTED))).scalars().all()
        for row in meter_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="meter_aggregate")
            items.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    "area_name": row.area_name,
                    "period": row.billing_month,
                    "source_kind": SOURCE_KIND_DERIVED,
                    "data_origin": data.get("data_origin"),
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        if billing_month and (source_kind in (None, SOURCE_KIND_ESTIMATE)):
            current_month_rows = [row for row in meter_rows if row.billing_month == billing_month]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_month_rows)
            for index, row in enumerate(estimate_rows):
                items.append(
                    {
                        "record_type": "Scope2HistoricalEstimate",
                        "record_id": -(index + 1),
                        "display_name": row.get("display_name"),
                        "area_name": row.get("area_name"),
                        "period": row.get("billing_month"),
                        "source_kind": SOURCE_KIND_ESTIMATE,
                        "total_kwh": row.get("total_kwh"),
                        "computed_co2e": row.get("computed_co2e"),
                        "calc_status": row.get("calc_status"),
                        "status": row.get("status"),
                        "factor_source": row.get("factor_source"),
                    }
                )
        if billing_month:
            items = [item for item in items if item["period"] == billing_month]
        if source_kind:
            items = [item for item in items if item["source_kind"] == source_kind]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return Response(content=page)

    @get("/api/carbon/ledger/carbon")
    async def get_carbon_ledger(
        self,
        db_session: AsyncSession,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        records = await self._load_scope_records(db_session)
        items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "source_kind": item["data"].get("source_kind"),
                "data_origin": item["data"].get("data_origin"),
                "activity_amount": item["data"].get("activity_amount"),
                "activity_unit": item["data"].get("activity_unit"),
                "computed_co2e": item["data"].get("computed_co2e"),
                "factor_source": item["data"].get("factor_source"),
                "factor_year": item["data"].get("factor_year"),
            }
            for item in records
        ]
        if scope:
            items = [item for item in items if item["scope"] == scope]
        if status:
            items = [item for item in items if item["status"] == status]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return Response(content=page)

    @get("/api/carbon/ledger/record/{record_type:str}/{record_id:int}")
    async def get_carbon_ledger_record_detail(
        self,
        db_session: AsyncSession,
        record_type: str,
        record_id: int,
    ) -> Response[dict]:
        model_map = {
            "Scope1MobileCombustion": m.Scope1MobileCombustion,
            "Scope1StationaryCombustion": m.Scope1StationaryCombustion,
            "Scope1RefrigerantLeak": m.Scope1RefrigerantLeak,
            "Scope2ElectricityBill": m.Scope2ElectricityBill,
            "Scope2MeterAggregate": m.Scope2MeterAggregate,
            "Scope3WasteDisposal": m.Scope3WasteDisposal,
            "Scope3ThirdPartyTransport": m.Scope3ThirdPartyTransport,
        }
        model = model_map.get(record_type)
        if model is None:
            return Response(content={"code": 404, "msg": "未知的记录类型"}, status_code=404)
        row = await db_session.get(model, record_id)
        if row is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        data = await _serialize_scope_record(
            row,
            db_session,
            source_kind="manual_bill" if record_type == "Scope2ElectricityBill" else "meter_aggregate" if record_type == "Scope2MeterAggregate" else None,
        )
        audit_logs = (
            await db_session.execute(
                select(m.CarbonAuditLog)
                .where(m.CarbonAuditLog.record_type == record_type, m.CarbonAuditLog.record_id == record_id)
                .order_by(m.CarbonAuditLog.created_at.desc())
            )
        ).scalars().all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "record_type": record_type,
                    "record_label": _scope_record_label(record_type),
                    "record_id": record_id,
                    "source": model_to_dict(row),
                    "computation": data,
                    "audit_logs": [model_to_dict(log) for log in audit_logs],
                },
            }
        )


class EnergyCarbonCenterController(Controller):
    """能碳中心聚合接口。"""

    tags = ["EnergyCarbonCenter"]
    signature_types = [Response]
    dependencies = {
        "scope2_meter_aggregate_service": provide_scope2_meter_aggregate_service,
        "security_audit_service": provide_audit_log_service,
    }

    @staticmethod
    def _record_model_map() -> dict[str, type]:
        return {
            "Scope1MobileCombustion": m.Scope1MobileCombustion,
            "Scope1StationaryCombustion": m.Scope1StationaryCombustion,
            "Scope1RefrigerantLeak": m.Scope1RefrigerantLeak,
            "Scope2ElectricityBill": m.Scope2ElectricityBill,
            "Scope2MeterAggregate": m.Scope2MeterAggregate,
            "Scope3WasteDisposal": m.Scope3WasteDisposal,
            "Scope3ThirdPartyTransport": m.Scope3ThirdPartyTransport,
        }

    async def _get_record_detail(self, db_session: AsyncSession, record_type: str, record_id: int) -> dict[str, Any] | None:
        model = self._record_model_map().get(record_type)
        if model is None:
            return None
        row = await db_session.get(model, record_id)
        if row is None:
            return None
        source_kind = "manual_bill" if record_type == "Scope2ElectricityBill" else "meter_aggregate" if record_type == "Scope2MeterAggregate" else None
        computation = await _serialize_scope_record(row, db_session, source_kind=source_kind)
        audit_logs = (
            await db_session.execute(
                select(m.CarbonAuditLog)
                .where(m.CarbonAuditLog.record_type == record_type, m.CarbonAuditLog.record_id == record_id)
                .order_by(m.CarbonAuditLog.created_at.desc())
            )
        ).scalars().all()
        return {
            "record_type": record_type,
            "record_label": _scope_record_label(record_type),
            "record_id": record_id,
            "source": model_to_dict(row),
            "computation": computation,
            "audit_logs": [model_to_dict(log) for log in audit_logs],
        }

    async def _demo_seed_operator_id(self, db_session: AsyncSession) -> Any:
        return await db_session.scalar(select(m.User.id).where(m.User.email == "ec-admin@example.com"))

    async def _clear_demo_seed_records(self, db_session: AsyncSession) -> dict[str, int]:
        deleted: dict[str, int] = {}
        for record_type, model in self._record_model_map().items():
            if not hasattr(model, "remark"):
                continue
            ids = [
                item[0]
                for item in (
                    await db_session.execute(
                        select(model.id).where(model.remark.is_not(None), model.remark.contains(DEMO_SEED_MARKER))
                    )
                ).all()
            ]
            if not ids:
                continue
            await db_session.execute(
                m.CarbonAuditLog.__table__.delete().where(
                    m.CarbonAuditLog.record_type == record_type,
                    m.CarbonAuditLog.record_id.in_(ids),
                )
            )
            await db_session.execute(model.__table__.delete().where(model.id.in_(ids)))
            deleted[record_type] = len(ids)
        await db_session.commit()
        return deleted

    async def _clear_imputed_meter_rows(self, db_session: AsyncSession, month_keys: list[str]) -> int:
        if not month_keys:
            return 0
        month_start, _ = _month_window(month_keys[0])
        _, month_end = _month_window(month_keys[-1])
        stmt = m.AmmeterIndexValue.__table__.delete().where(
            m.AmmeterIndexValue.data_source == 99,
            m.AmmeterIndexValue.reading_time >= month_start,
            m.AmmeterIndexValue.reading_time < month_end,
        )
        result = await db_session.execute(stmt)
        return int(result.rowcount or 0)

    async def _sync_ammeter_index_sequence(self, db_session: AsyncSession) -> None:
        sequence_name = await db_session.scalar(
            text("SELECT pg_get_serial_sequence('dataapp_ammeterindexvalue', 'id')")
        )
        if not sequence_name:
            return
        max_id = int(await db_session.scalar(text("SELECT COALESCE(MAX(id), 0) FROM dataapp_ammeterindexvalue")) or 0)
        quoted_sequence = str(sequence_name).replace("'", "''")
        await db_session.execute(text(f"SELECT setval('{quoted_sequence}', :max_id, true)"), {"max_id": max_id})

    async def _impute_raw_scope2_history(
        self,
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        month_keys: list[str],
    ) -> dict[str, Any]:
        if not month_keys:
            return {
                "months": [],
                "deleted_imputed_rows": 0,
                "inserted_imputed_rows": 0,
                "estimated_months": 0,
                "estimate_details": [],
                "rebuilt_count": 0,
                "ready_count": 0,
                "invalid_count": 0,
                "rebuild_details": [],
            }

        deleted_imputed_rows = await self._clear_imputed_meter_rows(db_session, month_keys)
        await self._sync_ammeter_index_sequence(db_session)

        # First rebuild against current raw data so estimation is based on a fresh monthly baseline.
        for billing_month in month_keys:
            await CarbonCRUDController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month)

        inserted_imputed_rows = 0
        estimate_details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            current_rows = (
                await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == billing_month))
            ).scalars().all()
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_rows)
            if not estimate_rows:
                continue

            month_start, month_end = _month_window(billing_month)
            raw_rows = (
                await db_session.execute(
                    select(m.AmmeterIndexValue)
                    .where(
                        m.AmmeterIndexValue.reading_time >= month_start,
                        m.AmmeterIndexValue.reading_time < month_end,
                        m.AmmeterIndexValue.ammeter_id.is_not(None),
                    )
                    .order_by(m.AmmeterIndexValue.ammeter_id.asc(), m.AmmeterIndexValue.reading_time.asc(), m.AmmeterIndexValue.id.asc())
                )
            ).scalars().all()
            samples_by_meter: dict[str, list[m.AmmeterIndexValue]] = defaultdict(list)
            for row in raw_rows:
                if row.ammeter_id:
                    samples_by_meter[str(row.ammeter_id)].append(row)

            created_for_month = 0
            for row in estimate_rows:
                ammeter_id = str(row.get("ammeter_id") or "")
                if not ammeter_id:
                    continue
                samples = samples_by_meter.get(ammeter_id, [])
                usable = [sample for sample in samples if sample.zygdn is not None]
                if not usable:
                    continue
                first = usable[0]
                last_sample = samples[-1]
                target_time = min(
                    (last_sample.reading_time or month_start) + datetime.timedelta(minutes=1),
                    month_end - datetime.timedelta(seconds=1),
                )
                if last_sample.reading_time and target_time <= last_sample.reading_time:
                    target_time = last_sample.reading_time + datetime.timedelta(seconds=1)
                if target_time >= month_end:
                    continue

                first_value = float(first.zygdn or 0.0)
                last_value = float(usable[-1].zygdn or 0.0)
                estimate_kwh = float(row.get("total_kwh") or 0.0)
                synthetic_total = max(last_value, first_value + estimate_kwh)

                imputed = m.AmmeterIndexValue(
                    equipment_id=last_sample.equipment_id or first.equipment_id,
                    zygdn=synthetic_total,
                    fygdn=last_sample.fygdn,
                    zwgdn=last_sample.zwgdn,
                    fwgdn=last_sample.fwgdn,
                    zygdnsz=last_sample.zygdnsz,
                    fygdnsz=last_sample.fygdnsz,
                    zwgdnsz=last_sample.zwgdnsz,
                    fwgdnsz=last_sample.fwgdnsz,
                    reading_time=target_time,
                    ammeter_id=last_sample.ammeter_id or first.ammeter_id,
                    ammeter_name=last_sample.ammeter_name or first.ammeter_name,
                    address=last_sample.address or first.address,
                    area_id=last_sample.area_id or first.area_id,
                    area_name=last_sample.area_name or first.area_name,
                    radio=last_sample.radio,
                    start_time=last_sample.start_time,
                    end_time=last_sample.end_time,
                    data_source=99,
                    add_time=datetime.datetime.utcnow(),
                )
                db_session.add(imputed)
                created_for_month += 1
                inserted_imputed_rows += 1

            if created_for_month:
                estimate_details.append(
                    {
                        "billing_month": billing_month,
                        "estimated_rows": created_for_month,
                    }
                )
                await self._sync_ammeter_index_sequence(db_session)

        await db_session.flush()

        rebuilt_count = 0
        ready_count = 0
        invalid_count = 0
        rebuild_details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            rows = await CarbonCRUDController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month)
            rebuilt_count += len(rows)
            ready_month = sum(1 for row in rows if row.calc_status == "ready")
            invalid_month = len(rows) - ready_month
            ready_count += ready_month
            invalid_count += invalid_month
            rebuild_details.append(
                {
                    "billing_month": billing_month,
                    "rebuilt_count": len(rows),
                    "ready_count": ready_month,
                    "invalid_count": invalid_month,
                }
            )

        await db_session.commit()
        return {
            "months": month_keys,
            "deleted_imputed_rows": deleted_imputed_rows,
            "inserted_imputed_rows": inserted_imputed_rows,
            "estimated_months": len(estimate_details),
            "estimate_details": estimate_details,
            "rebuilt_count": rebuilt_count,
            "ready_count": ready_count,
            "invalid_count": invalid_count,
            "rebuild_details": rebuild_details,
        }

    async def _seed_demo_scope_records(self, db_session: AsyncSession, months: int = 6) -> dict[str, int]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session) or datetime.date.today().strftime("%Y-%m")
        month_keys = _seed_months(latest_month, max(3, min(months, 6)))
        operator_id = await self._demo_seed_operator_id(db_session)
        created: dict[str, int] = defaultdict(int)
        pending_logs: list[dict[str, Any]] = []

        def month_date(month: str, day: int = 1) -> datetime.date:
            return _month_start_date(month).replace(day=min(day, 28))

        common_feature_fields = {
            "data_source": "demo_seed",
            "collection_method": "manual_demo",
            "confidence_level": "medium",
            "data_year_type": "calendar_year",
        }

        seeded_rows: list[tuple[str, Any, str]] = []
        for index, month in enumerate(month_keys):
            seeded_rows.extend(
                [
                    (
                        "Scope1MobileCombustion",
                        m.Scope1MobileCombustion(
                            record_date=month_date(month, 5),
                            asset_id=f"FK-{index + 1:02d}",
                            asset_name=f"园区叉车 {index + 1}",
                            fuel_type="diesel" if index % 2 == 0 else "gasoline",
                            amount=Decimal("118.5") + Decimal(index * 9),
                            unit="L",
                            mileage_km=Decimal(1280) + Decimal(index * 90),
                            work_hours=Decimal(72) + Decimal(index * 4),
                            attachment=None if index == 0 else f"/demo/evidence/scope1-mobile-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围1移动源演示记录",
                            status=STATUS_PENDING if index == 0 else STATUS_APPROVED,
                            approved_at=None if index == 0 else datetime.datetime.combine(month_date(month, 24), datetime.time.min),
                            data_year=month_date(month, 5).year,
                            **common_feature_fields,
                        ),
                        "提交待审" if index == 0 else "审核通过",
                    ),
                    (
                        "Scope1StationaryCombustion",
                        m.Scope1StationaryCombustion(
                            facility_name=f"备用发电机房 {index + 1}",
                            period_start=month_date(month, 1),
                            period_end=month_date(month, 28),
                            fuel_type="natural_gas" if index % 2 == 0 else "diesel",
                            amount=Decimal(420) + Decimal(index * 35),
                            unit="m³" if index % 2 == 0 else "L",
                            meter_reading_start=Decimal(1000) + Decimal(index * 120),
                            meter_reading_end=Decimal(1100) + Decimal(index * 140),
                            attachment=f"/demo/evidence/scope1-stationary-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围1固定源演示记录",
                            status=STATUS_APPROVED,
                            approved_at=datetime.datetime.combine(month_date(month, 23), datetime.time.min),
                            data_year=month_date(month, 1).year,
                            **common_feature_fields,
                        ),
                        "审核通过",
                    ),
                    (
                        "Scope1RefrigerantLeak",
                        m.Scope1RefrigerantLeak(
                            device_id=f"AC-{index + 1:02d}",
                            device_name=f"冷机组 {index + 1}",
                            fill_date=month_date(month, 12),
                            refrigerant_type="r410a" if index != 1 else "unknown_refrigerant",
                            amount_kg=Decimal("2.6") + Decimal(index) / Decimal(10),
                            leak_type="maintenance" if index % 2 == 0 else "leak",
                            attachment=None,
                            remark=f"{DEMO_SEED_MARKER} 范围1制冷剂演示记录",
                            status=STATUS_REJECTED if index == 1 else STATUS_PENDING,
                            reject_reason="因子未匹配，需确认制冷剂类型" if index == 1 else None,
                            data_year=month_date(month, 12).year,
                            **common_feature_fields,
                        ),
                        "驳回" if index == 1 else "提交待审",
                    ),
                    (
                        "Scope3WasteDisposal",
                        m.Scope3WasteDisposal(
                            date=month_date(month, 18),
                            category="waste_municipal_incineration" if index % 2 == 0 else "waste_unknown",
                            weight_ton=Decimal("4.2") + Decimal(index) / Decimal(2),
                            treatment_method="incineration" if index % 2 == 0 else "outsourced",
                            vendor_name=f"再生资源服务商 {index + 1}",
                            attachment=None if index == 2 else f"/demo/evidence/scope3-waste-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围3废弃物演示记录",
                            status=STATUS_PENDING if index in {0, 2} else STATUS_APPROVED,
                            approved_at=None if index in {0, 2} else datetime.datetime.combine(month_date(month, 26), datetime.time.min),
                            data_year=month_date(month, 18).year,
                            **common_feature_fields,
                        ),
                        "提交待审" if index in {0, 2} else "审核通过",
                    ),
                    (
                        "Scope3ThirdPartyTransport",
                        m.Scope3ThirdPartyTransport(
                            waybill_no=f"WB-{month.replace('-', '')}-{index + 1:02d}",
                            origin="苏州工业园区仓",
                            destination=f"华东客户点位 {index + 1}",
                            vehicle_type="transport_heavy_truck" if index % 2 == 0 else "transport_light_truck",
                            distance_km=Decimal(286) + Decimal(index * 12),
                            load_ton=Decimal("14.5") + Decimal(index) / Decimal(2),
                            fuel_amount=None,
                            attachment=f"/demo/evidence/scope3-transport-{month}.pdf" if index != 3 else None,
                            remark=f"{DEMO_SEED_MARKER} 范围3运输演示记录",
                            status=STATUS_APPROVED if index % 2 == 0 else STATUS_PENDING,
                            approved_at=datetime.datetime.combine(month_date(month, 25), datetime.time.min) if index % 2 == 0 else None,
                            created_at=datetime.datetime.combine(month_date(month, 20), datetime.time.min),
                            data_year=month_date(month, 20).year,
                            **common_feature_fields,
                        ),
                        "审核通过" if index % 2 == 0 else "提交待审",
                    ),
                ]
            )

        rows_by_type: dict[str, list[Any]] = defaultdict(list)
        for record_type, row, _log_comment in seeded_rows:
            db_session.add(row)
            rows_by_type[record_type].append(row)
            created[record_type] += 1

        await db_session.flush()

        for record_type, row, log_comment in seeded_rows:
            pending_logs.append(
                {
                    "record_type": record_type,
                    "record_id": row.id,
                    "action": AUDIT_ACTION_APPROVE if row.status == STATUS_APPROVED else AUDIT_ACTION_REJECT if row.status == STATUS_REJECTED else AUDIT_ACTION_SUBMIT,
                    "operator_id": operator_id,
                    "comment": log_comment,
                    "created_at": getattr(row, "approved_at", None) or datetime.datetime.utcnow(),
                }
            )

        if pending_logs:
            await db_session.execute(m.CarbonAuditLog.__table__.insert(), pending_logs)
        await db_session.commit()
        return dict(created)

    async def _build_monitor_area_summary(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        sectors = (
            await db_session.execute(select(m.MonitorSector).options(selectinload(m.MonitorSector.photos)).order_by(m.MonitorSector.id.asc()))
        ).scalars().all()
        equipment_counts = {
            sector_id: {"total": 0, "online": 0, "fault": 0}
            for sector_id in [sector.id for sector in sectors]
        }
        equipment_rows = (
            await db_session.execute(select(m.MonitorEquipment.id, m.MonitorEquipment.sector_id, m.MonitorEquipment.status, m.MonitorEquipment.category))
        ).all()
        for equipment_id, sector_id, status, _category in equipment_rows:
            if sector_id not in equipment_counts:
                continue
            equipment_counts[sector_id]["total"] += 1
            if status == 0:
                equipment_counts[sector_id]["online"] += 1
            else:
                equipment_counts[sector_id]["fault"] += 1

        alert_rows = (
            await db_session.execute(
                select(m.AlarmEvent.sector_id, func.count(m.AlarmEvent.id), func.sum(case((m.AlarmEvent.is_handle.is_(False), 1), else_=0)))
                .group_by(m.AlarmEvent.sector_id)
            )
        ).all()
        alert_map = {sector_id: {"total": int(total or 0), "unhandled": int(unhandled or 0)} for sector_id, total, unhandled in alert_rows}

        video_rows = (
            await db_session.execute(select(m.VideoMonitor.f_area, func.count(m.VideoMonitor.id), func.sum(case((m.VideoMonitor.status == 0, 1), else_=0))).group_by(m.VideoMonitor.f_area))
        ).all()
        video_map = {str(area or ""): {"total": int(total or 0), "online": int(online or 0)} for area, total, online in video_rows}

        items: list[dict[str, Any]] = []
        for sector in sectors:
            equipment = equipment_counts.get(sector.id, {"total": 0, "online": 0, "fault": 0})
            alerts = alert_map.get(sector.id, {"total": 0, "unhandled": 0})
            videos = video_map.get(str(sector.name or ""), {"total": 0, "online": 0})
            total_objects = max(equipment["total"] + videos["total"], 1)
            online_objects = equipment["online"] + videos["online"]
            status = "高风险" if alerts["unhandled"] > 3 or equipment["fault"] > 0 else "稳定"
            items.append(
                {
                    "id": sector.id,
                    "name": sector.name or f"区域{sector.id}",
                    "area_id": sector.area_id,
                    "description": sector.description,
                    "equipment_total": equipment["total"],
                    "equipment_online": equipment["online"],
                    "equipment_fault": equipment["fault"],
                    "video_total": videos["total"],
                    "video_online": videos["online"],
                    "alert_total": alerts["total"],
                    "alert_unhandled": alerts["unhandled"],
                    "health_ratio": round((online_objects / total_objects) * 100, 1),
                    "status": status,
                    "photo_count": len(sector.photos or []),
                }
            )
        return items

    async def _build_unified_alerts(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        area_names = {
            sector_id: sector_name or f"区域{sector_id}"
            for sector_id, sector_name in (await db_session.execute(select(m.MonitorSector.id, m.MonitorSector.name))).all()
        }
        equipment_names = {
            equipment_id: equipment_name or equipment_code
            for equipment_id, equipment_name, equipment_code in (await db_session.execute(select(m.MonitorEquipment.id, m.MonitorEquipment.name, m.MonitorEquipment.code))).all()
        }
        video_names = {
            video_id: location or f"视频点位{video_id}"
            for video_id, location in (await db_session.execute(select(m.VideoMonitor.id, m.VideoMonitor.location))).all()
        }

        alarm_rows = (await db_session.execute(select(m.AlarmEvent).order_by(m.AlarmEvent.event_time.desc().nullslast(), m.AlarmEvent.id.desc()))).scalars().all()
        severity_map = {1: "high", 2: "medium", 3: "medium", 4: "high"}
        type_map = {1: "设备告警", 2: "用能告警", 3: "发电告警", 4: "碳告警"}
        for row in alarm_rows:
            alerts.append(
                {
                    "id": f"alarm:{row.id}",
                    "source": "alarm",
                    "record_id": row.id,
                    "alert_type": type_map.get(row.event_type, "业务告警"),
                    "severity": severity_map.get(row.event_type, "medium"),
                    "title": row.event_desc or type_map.get(row.event_type, "业务告警"),
                    "area_name": area_names.get(row.sector_id, "未分区"),
                    "object_name": equipment_names.get(row.equipment_id, f"设备{row.equipment_id}" if row.equipment_id else "未关联对象"),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
            )

        video_alert_rows = (
            await db_session.execute(select(m.VedioAlarmEvent).order_by(m.VedioAlarmEvent.event_time.desc().nullslast(), m.VedioAlarmEvent.id.desc()))
        ).scalars().all()
        video_type_map = {1: "未佩戴安全帽", 2: "烟火", 3: "火点", 4: "区域入侵"}
        video_severity_map = {1: "medium", 2: "high", 3: "high", 4: "medium"}
        for row in video_alert_rows:
            alerts.append(
                {
                    "id": f"video:{row.id}",
                    "source": "video",
                    "record_id": row.id,
                    "alert_type": "视频告警",
                    "severity": video_severity_map.get(row.event_type, "medium"),
                    "title": video_type_map.get(row.event_type, "视频告警"),
                    "area_name": "视频监控",
                    "object_name": video_names.get(row.equipment_id, f"视频{row.equipment_id}" if row.equipment_id else "未关联视频"),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
            )

        invalid_aggregates = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.calc_status != "ready")
                .order_by(m.Scope2MeterAggregate.billing_month.desc(), m.Scope2MeterAggregate.id.desc())
            )
        ).scalars().all()
        for row in invalid_aggregates:
            alerts.append(
                {
                    "id": f"carbon:{row.id}",
                    "source": "carbon",
                    "record_id": row.id,
                    "record_type": "Scope2MeterAggregate",
                    "alert_type": "碳告警",
                    "severity": "high",
                    "title": "范围2聚合不可核算",
                    "area_name": row.area_name or "未分区",
                    "object_name": row.ammeter_name or row.ammeter_id,
                    "status": "待处理" if row.status != STATUS_APPROVED else "已处理",
                    "occurred_at": row.updated_at.isoformat() if row.updated_at else row.created_at.isoformat() if row.created_at else None,
                    "description": row.aggregation_note or row.computation_note or "聚合快照未形成有效核算结果",
                }
            )

        alerts.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
        return alerts

    async def _build_quality_issues(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        recent_months = await CarbonAnalyticsController._recent_scope2_backfill_months(db_session, 12)
        if recent_months:
            energy_series = await CarbonAnalyticsController._build_energy_series(db_session, recent_months)
            for item in energy_series:
                if item.get("source_kind") != SOURCE_KIND_FALLBACK:
                    continue
                period = str(item.get("period") or "")
                energy_value = round(float(item.get("energy_kwh") or 0.0), 2)
                issues.append(
                    {
                        "id": f"fallback:{period}",
                        "issue_code": "raw_meter_fallback_in_use",
                        "issue_type": "回退来源",
                        "severity": "medium",
                        "module": "范围2聚合",
                        "object_name": "月度用电核算",
                        "period": period,
                        "message": f"当前账期仍在使用电表明细回退，正式聚合快照缺失。回退电量 {energy_value} kWh。",
                    }
                )
                issues.append(
                    {
                        "id": f"missing-aggregate:{period}",
                        "issue_code": "missing_scope2_aggregate",
                        "issue_type": "缺失聚合",
                        "severity": "high",
                        "module": "范围2聚合",
                        "object_name": "月度用电核算",
                        "period": period,
                        "message": "存在原始电表数据，但未形成正式 Scope2 聚合记录。",
                    }
                )

        invalid_aggregates = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.calc_status != "ready")
                .order_by(m.Scope2MeterAggregate.billing_month.desc(), m.Scope2MeterAggregate.id.desc())
            )
        ).scalars().all()
        for row in invalid_aggregates:
            issue_code = "invalid_scope2_delta" if row.calc_status == "invalid_delta" else "insufficient_scope2_samples"
            issue_type = "异常增量" if row.calc_status == "invalid_delta" else "采样不足"
            issues.append(
                {
                    "id": f"aggregate:{row.id}",
                    "issue_code": issue_code,
                    "issue_type": issue_type,
                    "severity": "high",
                    "module": "范围2聚合",
                    "object_name": row.ammeter_name or row.ammeter_id,
                    "period": row.billing_month,
                    "message": row.aggregation_note or row.computation_note or "聚合记录未形成有效核算结果",
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                }
            )

        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        for item in scope_records:
            data = item["data"]
            if data.get("computed_co2e") is None:
                issues.append(
                    {
                        "id": f"record:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_computed_co2e",
                        "issue_type": "缺失核算结果",
                        "severity": "medium",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": data.get("computation_note") or "记录尚未形成有效 CO2e 结果",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if not data.get("factor_source"):
                issues.append(
                    {
                        "id": f"factor:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_factor_binding",
                        "issue_type": "缺失因子",
                        "severity": "high",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "当前记录缺少有效因子来源信息。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("status") == STATUS_PENDING and not _record_attachment(item["row"]):
                issues.append(
                    {
                        "id": f"evidence:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_evidence",
                        "issue_type": "缺失凭证",
                        "severity": "medium",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "当前记录待审核，但未附带业务凭证。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("status") == STATUS_PENDING and (not data.get("factor_source") or data.get("computed_co2e") is None):
                issues.append(
                    {
                        "id": f"audit:{item['record_type']}:{item['row'].id}",
                        "issue_code": "audit_blocked",
                        "issue_type": "审核阻塞",
                        "severity": "high",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "待审核记录存在因子或结果缺口，当前无法形成稳定审核结论。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("source_kind") == SOURCE_KIND_DEMO_SEED:
                issues.append(
                    {
                        "id": f"demo:{item['record_type']}:{item['row'].id}",
                        "issue_code": "demo_seed_present",
                        "issue_type": "演示样例",
                        "severity": "low",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "该记录为演示样例，仅用于工作台展示闭环。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
        issues.sort(key=lambda item: (str(item.get("period") or ""), item["id"]), reverse=True)
        return issues

    async def _trend_data(self, db_session: AsyncSession, months: int) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        if not latest_month:
            return {"series": [], "months": []}
        month_keys = _months_back(latest_month, max(3, min(months, 24)))
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, month_keys)
        carbon_records = await CarbonAnalyticsController._load_scope_records(db_session)
        scope_month_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for item in carbon_records:
            month = item["period"]
            if not month:
                continue
            scope_month_totals[month][item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        series = []
        for item in energy_series:
            month = item["period"]
            scope1 = scope_month_totals[month].get("范围1", 0.0)
            scope2 = float(item.get("carbon_co2e") or 0.0)
            scope3 = scope_month_totals[month].get("范围3", 0.0)
            series.append(
                {
                    "period": month,
                    "energy_kwh": round(float(item.get("energy_kwh") or 0.0), 2),
                    "scope1_co2e": round(scope1, 2),
                    "scope2_co2e": round(scope2, 2),
                    "scope3_co2e": round(scope3, 2),
                    "carbon_co2e": round(scope1 + scope2 + scope3, 2),
                    "source_kind": item.get("source_kind"),
                }
            )
        return {"months": month_keys, "series": series}

    async def _ranking_data(self, db_session: AsyncSession) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_rows: list[dict[str, Any]] = []
        diagnostics = {"source_kind": "empty"}
        if latest_month:
            ready_rows = (
                await db_session.execute(
                    select(m.Scope2MeterAggregate)
                    .where(
                        m.Scope2MeterAggregate.billing_month == latest_month,
                        m.Scope2MeterAggregate.calc_status == "ready",
                    )
                    .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
                )
            ).scalars().all()
            if ready_rows:
                energy_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in ready_rows]
                diagnostics["source_kind"] = "meter_aggregate"
            else:
                month_start, month_end = _month_window(latest_month)
                energy_rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
                diagnostics["source_kind"] = "raw_meter_fallback"

        energy_by_area: dict[str, float] = defaultdict(float)
        for row in energy_rows:
            area_name = str(row.get("area_name") or "未分区")
            energy_by_area[area_name] += float(row.get("total_kwh") or 0.0)

        carbon_records = await CarbonAnalyticsController._load_scope_records(db_session)
        carbon_by_type: dict[str, float] = defaultdict(float)
        for item in carbon_records:
            carbon_by_type[item["record_label"]] += float(item["data"].get("computed_co2e") or 0.0)

        area_events = (
            await db_session.execute(
                select(m.MonitorSector.name, func.count(m.AlarmEvent.id))
                .join(m.AlarmEvent, m.AlarmEvent.sector_id == m.MonitorSector.id)
                .group_by(m.MonitorSector.name)
                .order_by(func.count(m.AlarmEvent.id).desc())
                .limit(10)
            )
        ).all()
        return {
            "latest_month": latest_month,
            "diagnostics": diagnostics,
            "energy_by_area": [{"name": name, "value": round(value, 2)} for name, value in sorted(energy_by_area.items(), key=lambda item: item[1], reverse=True)[:10]],
            "carbon_by_type": [{"name": name, "value": round(value, 2)} for name, value in sorted(carbon_by_type.items(), key=lambda item: item[1], reverse=True)[:10]],
            "alerts_by_area": [{"name": name or "未命名区域", "value": int(total)} for name, total in area_events],
        }

    async def _efficiency_data(self, db_session: AsyncSession) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "record_count": 0, "source_kind": "empty"}
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        status_totals: dict[str, int] = defaultdict(int)
        source_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"energy_kwh": 0.0, "carbon_co2e": 0.0, "records": 0.0})
        for item in scope_records:
            status_totals[str(item["data"].get("status") or STATUS_DRAFT)] += 1
            source = str(item["data"].get("source_kind") or item["scope"])
            source_totals[source]["carbon_co2e"] += float(item["data"].get("computed_co2e") or 0.0)
            source_totals[source]["records"] += 1
            if item["record_type"] in {"Scope2ElectricityBill", "Scope2MeterAggregate"}:
                source_totals[source]["energy_kwh"] += float(item["data"].get("total_kwh") or 0.0)

        storage = await db_session.scalar(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))
        source_mix = [
            {
                "name": name,
                "energy_kwh": round(values["energy_kwh"], 2),
                "carbon_co2e": round(values["carbon_co2e"], 2),
                "record_count": int(values["records"]),
            }
            for name, values in sorted(source_totals.items(), key=lambda item: item[1]["carbon_co2e"], reverse=True)
        ]
        if not source_mix and float(current_energy.get("energy_kwh") or 0.0) > 0:
            source_mix = [
                {
                    "name": str(current_energy.get("source_kind") or "raw_meter_fallback"),
                    "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                    "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    "record_count": int(current_energy.get("record_count") or 0),
                }
            ]
        return {
            "latest_month": latest_month,
            "source_mix": source_mix,
            "workflow": [{"name": name, "value": total} for name, total in status_totals.items()],
            "energy_efficiency": {
                "source_kind": current_energy.get("source_kind"),
                "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                "record_count": int(current_energy.get("record_count") or 0),
            },
            "storage": model_to_dict(storage) if storage else {},
        }

    async def _energy_flow_data(self, db_session: AsyncSession, billing_month: str | None = None) -> dict[str, Any]:
        month = billing_month or await CarbonAnalyticsController._latest_energy_month(db_session)
        if not month:
            return {"billing_month": None, "title": "仓库级能流图", "unit": "kWh", "nodes": [], "links": [], "diagnostics": {"source_kind": "empty"}}
        meter_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.billing_month == month)
                .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
            )
        ).scalars().all()
        diagnostics = {
            "source_kind": "meter_aggregate",
            "ready_count": sum(1 for row in meter_rows if row.calc_status == "ready"),
            "invalid_count": sum(1 for row in meter_rows if row.calc_status != "ready"),
            "zero_ready_count": sum(1 for row in meter_rows if row.calc_status == "ready" and float(row.total_kwh or 0.0) <= 0),
            "used_fallback": False,
        }
        flow_rows: list[dict[str, Any]]
        estimate_rows: list[dict[str, Any]] = []
        if meter_rows:
            flow_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in meter_rows if row.total_kwh]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, month, meter_rows)
        else:
            month_start, month_end = _month_window(month)
            flow_rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
            diagnostics["source_kind"] = "raw_meter_fallback"
            diagnostics["used_fallback"] = True
        if estimate_rows:
            flow_rows = [*flow_rows, *estimate_rows]
        nodes: dict[str, dict[str, Any]] = {"grid": {"id": "grid", "name": "外部购电", "category": "source"}}
        links: list[dict[str, Any]] = []
        area_totals: dict[str, float] = {}
        total_energy_kwh = 0.0
        for row in flow_rows:
            area_name = str(row.get("area_name") or "未分区")
            value = float(row.get("total_kwh") or 0.0)
            if value <= 0:
                continue
            total_energy_kwh += value
            area_totals[area_name] = area_totals.get(area_name, 0.0) + value
        for area_name, value in sorted(area_totals.items(), key=lambda item: item[1], reverse=True):
            area_id = f"area:{area_name}"
            result_id = f"result:{area_name}:{month}"
            nodes.setdefault(area_id, {"id": area_id, "name": area_name, "category": "area", "value": round(value, 2)})
            nodes.setdefault(
                result_id,
                {
                    "id": result_id,
                    "name": f"{area_name} 核算结果",
                    "category": "result",
                    "value": round(value, 2),
                },
            )
            links.append({"source": "grid", "target": area_id, "value": round(value, 2)})
            links.append({"source": area_id, "target": result_id, "value": round(value, 2)})
        diagnostics["total_energy_kwh"] = round(total_energy_kwh, 2)
        diagnostics["positive_area_count"] = len(area_totals)
        diagnostics["estimated_count"] = len(estimate_rows)
        diagnostics["estimated_energy_kwh"] = round(sum(float(row.get("total_kwh") or 0.0) for row in estimate_rows), 4)
        return {"billing_month": month, "title": "仓库级能流图", "unit": "kWh", "nodes": list(nodes.values()), "links": links, "diagnostics": diagnostics}

    async def _energy_ledger_page(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        bill_rows = (await db_session.execute(select(m.Scope2ElectricityBill).where(m.Scope2ElectricityBill.status != STATUS_REJECTED))).scalars().all()
        for row in bill_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="manual_bill")
            items.append(
                {
                    "record_type": "Scope2ElectricityBill",
                    "record_id": row.id,
                    "display_name": row.account_number,
                    "area_name": None,
                    "period": row.billing_month,
                    "source_kind": "manual_bill",
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        meter_rows = (await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.status != STATUS_REJECTED))).scalars().all()
        for row in meter_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="meter_aggregate")
            items.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    "area_name": row.area_name,
                    "period": row.billing_month,
                    "source_kind": "meter_aggregate",
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        if billing_month and (source_kind in (None, SOURCE_KIND_ESTIMATE)):
            current_month_rows = [row for row in meter_rows if row.billing_month == billing_month]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_month_rows)
            for index, row in enumerate(estimate_rows):
                items.append(
                    {
                        "record_type": "Scope2HistoricalEstimate",
                        "record_id": -(index + 1),
                        "display_name": row.get("display_name"),
                        "area_name": row.get("area_name"),
                        "period": row.get("billing_month"),
                        "source_kind": SOURCE_KIND_ESTIMATE,
                        "total_kwh": row.get("total_kwh"),
                        "computed_co2e": row.get("computed_co2e"),
                        "calc_status": row.get("calc_status"),
                        "status": row.get("status"),
                        "factor_source": row.get("factor_source"),
                    }
                )
        if billing_month:
            items = [item for item in items if item["period"] == billing_month]
        if source_kind:
            items = [item for item in items if item["source_kind"] == source_kind]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return {"items": page["items"], "total": page["total"], "limit": page["limit"], "offset": page["offset"]}

    async def _carbon_ledger_page(
        self,
        db_session: AsyncSession,
        scope_filter: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "source_kind": item["data"].get("source_kind"),
                "activity_amount": item["data"].get("activity_amount"),
                "activity_unit": item["data"].get("activity_unit"),
                "computed_co2e": item["data"].get("computed_co2e"),
                "factor_source": item["data"].get("factor_source"),
                "factor_year": item["data"].get("factor_year"),
            }
            for item in records
        ]
        if scope_filter:
            items = [item for item in items if item["scope"] == scope_filter]
        if status:
            items = [item for item in items if item["status"] == status]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return {"items": page["items"], "total": page["total"], "limit": page["limit"], "offset": page["offset"]}

    def _build_alert_facets(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_source: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        by_area: dict[str, int] = defaultdict(int)
        for item in items:
            by_source[str(item["source"])] += 1
            by_severity[str(item["severity"])] += 1
            by_status[str(item["status"])] += 1
            by_area[str(item.get("area_name") or "未分区")] += 1
        return {
            "by_source": [{"name": name, "value": value} for name, value in sorted(by_source.items(), key=lambda pair: pair[1], reverse=True)],
            "by_severity": [{"name": name, "value": value} for name, value in sorted(by_severity.items(), key=lambda pair: pair[1], reverse=True)],
            "by_status": [{"name": name, "value": value} for name, value in sorted(by_status.items(), key=lambda pair: pair[1], reverse=True)],
            "by_area": [{"name": name, "value": value} for name, value in sorted(by_area.items(), key=lambda pair: pair[1], reverse=True)[:10]],
        }

    def _build_alert_trend(self, items: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        current_month = datetime.date.today().replace(day=1)
        month_labels = []
        for offset in range(months - 1, -1, -1):
            month = current_month - relativedelta(months=offset)
            month_labels.append(month.strftime("%Y-%m"))
        counts = {label: {"period": label, "alerts_count": 0, "handled_count": 0} for label in month_labels}
        for item in items:
            occurred_at = item.get("occurred_at")
            month_key = str(occurred_at or "")[:7]
            if month_key in counts:
                counts[month_key]["alerts_count"] += 1
                if item.get("status") == "已处理":
                    counts[month_key]["handled_count"] += 1
        return list(counts.values())

    async def _build_dashboard_completion(self, db_session: AsyncSession) -> dict[str, Any]:
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        issues = await self._build_quality_issues(db_session)
        alerts = await self._build_unified_alerts(db_session)
        total_records = max(len(scope_records), 1)
        issue_impacts = {
            (
                str(item.get("record_type") or item.get("module") or "unknown"),
                str(item.get("record_id") or item.get("period") or item["id"]),
            )
            for item in issues
            if item.get("severity") != "low"
        }
        return {
            "carbon_completion_rate": round(sum(1 for item in scope_records if item["data"].get("computed_co2e")) / total_records * 100, 1),
            "approval_completion_rate": round(sum(1 for item in scope_records if item["data"].get("status") == STATUS_APPROVED) / total_records * 100, 1),
            "quality_completion_rate": round(max(0.0, 100 - (len(issue_impacts) / total_records * 100)), 1),
            "alert_closure_rate": round(sum(1 for item in alerts if item["status"] == "已处理") / max(len(alerts), 1) * 100, 1),
        }

    async def _build_recent_activities(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        alerts = await self._build_unified_alerts(db_session)
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        activities: list[dict[str, Any]] = []
        for item in alerts[:6]:
            activities.append(
                {
                    "type": "alert",
                    "title": item["title"],
                    "subtitle": item.get("area_name") or item.get("object_name") or "监测对象",
                    "time": item.get("occurred_at"),
                    "status": item.get("status"),
                }
            )
        for item in scope_records[:6]:
            activities.append(
                {
                    "type": "carbon",
                    "title": item["display_name"],
                    "subtitle": f"{item['record_label']} · {item['period']}",
                    "time": item["period"],
                    "status": item["data"].get("status"),
                }
            )
        activities.sort(key=lambda row: str(row.get("time") or ""), reverse=True)
        return activities[:10]

    def _build_carbon_scope_trend(self, records: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        latest_month = None
        month_keys = [item.get("period") for item in records if item.get("period")]
        if month_keys:
            latest_month = max(month_keys)
        if not latest_month:
            latest_month = datetime.date.today().strftime("%Y-%m")
        labels = _months_back(latest_month, months)
        series = {
            label: {
                "period": label,
                "scope1_co2e": 0.0,
                "scope2_co2e": 0.0,
                "scope3_co2e": 0.0,
                "carbon_co2e": 0.0,
            }
            for label in labels
        }
        for item in records:
            period = item.get("period")
            if period not in series:
                continue
            value = float(item["data"].get("computed_co2e") or 0.0)
            key = _scope_trend_key(str(item.get("scope") or ""))
            if key in series[period]:
                series[period][key] += value
                series[period]["carbon_co2e"] += value
        return list(series.values())

    def _build_carbon_flow(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {
            "scope1": {"id": "scope1", "name": "范围1", "category": "scope"},
            "scope2": {"id": "scope2", "name": "范围2", "category": "scope"},
            "scope3": {"id": "scope3", "name": "范围3", "category": "scope"},
        }
        links: list[dict[str, Any]] = []
        grouped: dict[tuple[str, str], float] = defaultdict(float)
        for item in records:
            scope = item["scope"]
            scope_node = "scope1" if scope == "范围1" else "scope2" if scope == "范围2" else "scope3"
            source_kind = str(item["data"].get("source_kind") or item["record_label"])
            result_name = f"{item['record_label']}结果"
            source_node = f"src:{scope}:{source_kind}"
            result_node = f"res:{scope}:{item['record_type']}"
            value = float(item["data"].get("computed_co2e") or 0.0)
            nodes.setdefault(source_node, {"id": source_node, "name": _source_kind_label(source_kind), "category": "source"})
            nodes.setdefault(result_node, {"id": result_node, "name": result_name, "category": "result"})
            grouped[(scope_node, source_node)] += value
            grouped[(source_node, result_node)] += value
        for (source, target), value in grouped.items():
            if value <= 0:
                continue
            links.append({"source": source, "target": target, "value": round(value, 2)})
        return {"title": "碳流图", "unit": "kgCO2e", "nodes": list(nodes.values()), "links": links}

    def _build_quality_trend(self, issues: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        current_month = datetime.date.today().replace(day=1)
        labels = [(current_month - relativedelta(months=offset)).strftime("%Y-%m") for offset in range(months - 1, -1, -1)]
        buckets = {label: {"period": label, "alerts_count": 0, "handled_count": 0, "energy_kwh": 0.0, "carbon_co2e": 0.0} for label in labels}
        for item in issues:
            month_key = str(item.get("period") or "")[:7]
            if month_key in buckets:
                buckets[month_key]["alerts_count"] += 1
                if item.get("severity") != "high":
                    buckets[month_key]["handled_count"] += 1
        return list(buckets.values())

    def _build_factor_usage(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        by_scope: dict[str, int] = defaultdict(int)
        missing_by_scope: dict[str, int] = defaultdict(int)
        by_source: dict[str, int] = defaultdict(int)
        for item in records:
            by_scope[item["scope"]] += 1
            factor_source = str(item["data"].get("factor_source") or "缺失因子")
            by_source[factor_source] += 1
            if not item["data"].get("factor_source"):
                missing_by_scope[item["scope"]] += 1
        return {
            "scope_distribution": [{"name": name, "value": value} for name, value in sorted(by_scope.items())],
            "missing_by_scope": [{"name": name, "value": value} for name, value in sorted(missing_by_scope.items())],
            "factor_source_distribution": [{"name": name, "value": value} for name, value in sorted(by_source.items(), key=lambda pair: pair[1], reverse=True)[:10]],
        }

    @get("/api/energy-carbon/dashboard/overview")
    async def get_dashboard_overview(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, _months_back(latest_month, 1) if latest_month else [])
        current_energy = energy_series[-1] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "source_kind": "empty", "record_count": 0}
        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        alerts = await self._build_unified_alerts(db_session)
        issues = await self._build_quality_issues(db_session)
        health = await self._build_monitor_area_summary(db_session)
        risk_items = [item for item in alerts if item["severity"] == "high" and item["status"] == "待处理"][:5]
        issue_impacts = {
            (
                str(item.get("record_type") or item.get("module") or "unknown"),
                str(item.get("record_id") or item.get("period") or item["id"]),
            )
            for item in issues
            if item.get("severity") != "low"
        }
        quality_rate = round(max(0.0, 100 - (len(issue_impacts) / max(len(scope_records), 1) * 100)), 1)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "enterprise": enterprise.to_dict() if enterprise else {},
                    "kpis": [
                        {"id": "energy", "label": "总能耗", "value": round(float(current_energy.get("energy_kwh") or 0.0), 2), "unit": "kWh"},
                        {"id": "carbon", "label": "总碳排", "value": round(sum(float(item["data"].get("computed_co2e") or 0.0) for item in scope_records), 2), "unit": "kgCO2e"},
                        {"id": "alerts", "label": "异常数", "value": len(alerts), "unit": "条"},
                        {"id": "unhandled", "label": "未处理告警", "value": sum(1 for item in alerts if item["status"] == "待处理"), "unit": "条"},
                        {"id": "pending", "label": "待审核", "value": sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING), "unit": "条"},
                        {"id": "quality", "label": "数据完整率", "value": quality_rate, "unit": "%"},
                    ],
                    "trend_summary": {
                        "source_kind": current_energy.get("source_kind"),
                        "data_origin": _data_origin_for_source_kind(current_energy.get("source_kind")),
                        "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    },
                    "risk_items": risk_items,
                    "todo_items": [
                        {"label": "待处理告警", "value": sum(1 for item in alerts if item["status"] == "待处理")},
                        {"label": "待审核记录", "value": sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING)},
                        {"label": "质量问题", "value": len(issues)},
                    ],
                    "health_matrix": health[:6],
                    "completion": await self._build_dashboard_completion(db_session),
                    "recent_activities": await self._build_recent_activities(db_session),
                    "quick_links": [
                        {"label": "监测中心", "to": "/energy-carbon/monitor"},
                        {"label": "告警中心", "to": "/energy-carbon/alerts"},
                        {"label": "碳盘查", "to": "/energy-carbon/carbon"},
                        {"label": "能流分析", "to": "/energy-carbon/flows"},
                        {"label": "数据质量", "to": "/energy-carbon/quality"},
                        {"label": "因子数据库", "to": "/energy-carbon/factors"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/dashboard/completion")
    async def get_dashboard_completion(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._build_dashboard_completion(db_session)})

    @get("/api/energy-carbon/dashboard/recent-activities")
    async def get_dashboard_recent_activities(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": await self._build_recent_activities(db_session)}})

    @get("/api/energy-carbon/dashboard/trend")
    async def get_dashboard_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._trend_data(db_session, months)})

    @get("/api/energy-carbon/dashboard/health")
    async def get_dashboard_health(self, db_session: AsyncSession) -> Response[dict]:
        health = await self._build_monitor_area_summary(db_session)
        alerts = await self._build_unified_alerts(db_session)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "areas": health,
                    "summary": {
                        "area_count": len(health),
                        "stable_count": sum(1 for item in health if item["status"] == "稳定"),
                        "risk_count": sum(1 for item in health if item["status"] != "稳定"),
                        "high_alert_count": sum(1 for item in alerts if item["severity"] == "high" and item["status"] == "待处理"),
                    },
                },
            }
        )

    @get("/api/energy-carbon/energy/summary")
    async def get_energy_summary(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        latest_month = ranking.get("latest_month")
        ledger = await self._energy_ledger_page(db_session, latest_month, None, 12, 0)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "energy_by_area": ranking.get("energy_by_area", []),
                    "alerts_by_area": ranking.get("alerts_by_area", []),
                    "carbon_by_type": ranking.get("carbon_by_type", []),
                    "source_mix": efficiency.get("source_mix", []),
                    "energy_efficiency": efficiency.get("energy_efficiency", {}),
                    "workflow": efficiency.get("workflow", []),
                    "diagnostics": ranking.get("diagnostics", []),
                    "ledger": ledger.get("items", []),
                },
            }
        )

    @get("/api/energy-carbon/energy/trend")
    async def get_energy_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._trend_data(db_session, months)})

    @get("/api/energy-carbon/energy/structure")
    async def get_energy_structure(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"source_mix": efficiency.get("source_mix", []), "energy_by_area": ranking.get("energy_by_area", []), "alerts_by_area": ranking.get("alerts_by_area", [])}})

    @get("/api/energy-carbon/energy/intensity")
    async def get_energy_intensity(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0}
        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        total_kwh = float(current_energy.get("energy_kwh") or 0.0)
        store_area = float(enterprise.store_area or 0.0) if enterprise else 0.0
        park_area = float(enterprise.park_area or 0.0) if enterprise else 0.0
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "metrics": [
                        {"label": "总用电量", "value": round(total_kwh, 2), "unit": "kWh"},
                        {"label": "单位仓储面积能耗", "value": round(total_kwh / store_area, 4) if store_area else None, "unit": "kWh/㎡"},
                        {"label": "单位园区面积能耗", "value": round(total_kwh / park_area, 4) if park_area else None, "unit": "kWh/㎡"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/energy/ranking")
    async def get_energy_ranking(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._ranking_data(db_session)})

    @get("/api/energy-carbon/energy/ledger-preview")
    async def get_energy_ledger_preview(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 12,
        offset: int = 0,
    ) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._energy_ledger_page(db_session, billing_month, source_kind, limit, offset)})

    @get("/api/energy-carbon/energy/diagnostics")
    async def get_energy_diagnostics(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": ranking.get("latest_month"),
                    "diagnostics": ranking.get("diagnostics", []),
                    "workflow": efficiency.get("workflow", []),
                    "storage": efficiency.get("storage", {}),
                },
            }
        )

    @get("/api/energy-carbon/monitor/areas")
    async def list_monitor_areas(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": await self._build_monitor_area_summary(db_session)}})

    @get("/api/energy-carbon/monitor/devices")
    async def list_monitor_devices(
        self,
        db_session: AsyncSession,
        sector_id: int | None = None,
        status: int | None = None,
        category: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        stmt = select(m.MonitorEquipment).options(selectinload(m.MonitorEquipment.sector)).order_by(m.MonitorEquipment.sort_index.asc().nullslast(), m.MonitorEquipment.id.desc())
        if sector_id:
            stmt = stmt.where(m.MonitorEquipment.sector_id == sector_id)
        if status is not None:
            stmt = stmt.where(m.MonitorEquipment.status == status)
        if category is not None:
            stmt = stmt.where(m.MonitorEquipment.category == category)
        rows = (await db_session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        items = []
        for row in rows:
            alert_count = int(
                (
                    await db_session.execute(select(func.count(m.AlarmEvent.id)).where(m.AlarmEvent.equipment_id == row.id, m.AlarmEvent.is_handle.is_(False)))
                ).scalar_one()
            )
            items.append(
                {
                    "id": row.id,
                    "name": row.name or row.code,
                    "code": row.code,
                    "category": row.category,
                    "sector_id": row.sector_id,
                    "sector_name": row.sector.name if row.sector else None,
                    "status": row.status,
                    "trip_state": row.trip_state,
                    "location": row.location,
                    "protocol": row.protocol,
                    "alert_unhandled": alert_count,
                }
            )
        total_stmt = select(func.count()).select_from(m.MonitorEquipment)
        if sector_id:
            total_stmt = total_stmt.where(m.MonitorEquipment.sector_id == sector_id)
        if status is not None:
            total_stmt = total_stmt.where(m.MonitorEquipment.status == status)
        if category is not None:
            total_stmt = total_stmt.where(m.MonitorEquipment.category == category)
        total = int((await db_session.execute(total_stmt)).scalar_one())
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items, "total": total, "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}")
    async def get_monitor_device_detail(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        device = (
            await db_session.execute(select(m.MonitorEquipment).options(selectinload(m.MonitorEquipment.sector)).where(m.MonitorEquipment.id == device_id))
        ).scalars().first()
        if not device:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        meter_samples = (
            await db_session.execute(select(m.AmmeterIndexValue).where(m.AmmeterIndexValue.equipment_id == device_id).order_by(m.AmmeterIndexValue.reading_time.desc().nullslast()).limit(12))
        ).scalars().all()
        alarms = (
            await db_session.execute(select(m.AlarmEvent).where(m.AlarmEvent.equipment_id == device_id).order_by(m.AlarmEvent.event_time.desc().nullslast()).limit(10))
        ).scalars().all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "device": {
                        "id": device.id,
                        "name": device.name or device.code,
                        "code": device.code,
                        "category": device.category,
                        "status": device.status,
                        "trip_state": device.trip_state,
                        "sector_name": device.sector.name if device.sector else None,
                        "location": device.location,
                        "protocol": device.protocol,
                        "install_time": device.install_time.isoformat() if device.install_time else None,
                    },
                    "meter_samples": [model_to_dict(item) for item in meter_samples],
                    "alerts": [model_to_dict(item) for item in alarms],
                },
            }
        )

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/timeseries")
    async def get_monitor_device_timeseries(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        samples = (
            await db_session.execute(
                select(m.AmmeterIndexValue).where(m.AmmeterIndexValue.equipment_id == device_id).order_by(m.AmmeterIndexValue.reading_time.asc().nullslast()).limit(48)
            )
        ).scalars().all()
        points = [
            {
                "period": item.reading_time.strftime("%m-%d %H:%M") if item.reading_time else f"样本{index + 1}",
                "energy_kwh": float(item.zygdn or item.zygdnsz or 0.0),
                "carbon_co2e": 0.0,
            }
            for index, item in enumerate(samples)
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": points}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/alerts")
    async def get_monitor_device_alerts(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        alarms = (
            await db_session.execute(select(m.AlarmEvent).where(m.AlarmEvent.equipment_id == device_id).order_by(m.AlarmEvent.event_time.desc().nullslast()).limit(20))
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in alarms]}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/videos")
    async def get_monitor_device_videos(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        device = await db_session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.id == device_id))
        if not device or not device.sector_id:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        sector_name = await db_session.scalar(select(m.MonitorSector.name).where(m.MonitorSector.id == device.sector_id))
        if not sector_name:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        videos = (
            await db_session.execute(select(m.VideoMonitor).where(m.VideoMonitor.f_area == sector_name).limit(8))
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in videos]}})

    @get("/api/energy-carbon/alerts")
    async def list_energy_center_alerts(
        self,
        db_session: AsyncSession,
        source: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        if source and source != "all":
            items = [item for item in items if item["source"] == source]
        if status and status != "all":
            items = [item for item in items if item["status"] == status]
        if severity and severity != "all":
            items = [item for item in items if item["severity"] == severity]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/alerts/summary")
    async def get_energy_center_alert_summary(self, db_session: AsyncSession) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        facets = self._build_alert_facets(items)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "total": len(items),
                    "unhandled": sum(1 for item in items if item["status"] == "待处理"),
                    "high_risk": sum(1 for item in items if item["severity"] == "high"),
                    "today_added": sum(1 for item in items if str(item.get("occurred_at") or "").startswith(datetime.date.today().isoformat())),
                    "avg_handle_hours": None,
                    **facets,
                },
            }
        )

    @get("/api/energy-carbon/alerts/facets")
    async def get_energy_center_alert_facets(self, db_session: AsyncSession) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_alert_facets(items)})

    @get("/api/energy-carbon/alerts/trend")
    async def get_energy_center_alert_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_alert_trend(items, months)}})

    @get("/api/energy-carbon/alerts/{alert_id:str}")
    async def get_energy_center_alert_detail(self, db_session: AsyncSession, alert_id: str) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        match = next((item for item in items if item["id"] == alert_id), None)
        if not match:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        history = [
            {"label": "发生", "value": match.get("occurred_at")},
            {"label": "当前状态", "value": match.get("status")},
            {"label": "风险等级", "value": match.get("severity")},
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {**match, "history": history}})

    @get("/api/energy-carbon/alerts/{alert_id:str}/history")
    async def get_energy_center_alert_history(self, db_session: AsyncSession, alert_id: str) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        match = next((item for item in items if item["id"] == alert_id), None)
        if not match:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [{"stage": "发现", "time": match.get("occurred_at"), "status": match.get("status")}]}})

    @get("/api/energy-carbon/flows/energy")
    async def get_energy_center_flow(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._energy_flow_data(db_session, billing_month)})

    @get("/api/energy-carbon/flows/energy-balance")
    async def get_energy_balance(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        month = billing_month or await CarbonAnalyticsController._latest_energy_month(db_session)
        if not month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"billing_month": None, "table": [], "diagnostics": []}})
        flow = await self._energy_flow_data(db_session, month)
        total_input = float(flow.get("diagnostics", {}).get("total_energy_kwh") or 0.0)
        ready_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == month, m.Scope2MeterAggregate.calc_status == "ready")
            )
        ).scalars().all()
        invalid_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == month, m.Scope2MeterAggregate.calc_status != "ready")
            )
        ).scalars().all()
        distributed = round(sum(float(row.total_kwh or 0.0) for row in ready_rows), 2)
        losses = round(max(total_input - distributed, 0.0), 2)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "billing_month": month,
                    "table": [
                        {"label": "输入", "value": round(total_input, 2), "unit": "kWh"},
                        {"label": "已聚合利用", "value": distributed, "unit": "kWh"},
                        {"label": "损耗/缺失", "value": losses, "unit": "kWh"},
                    ],
                    "diagnostics": [
                        {"label": "可核算电表数", "value": len(ready_rows)},
                        {"label": "不可核算电表数", "value": len(invalid_rows)},
                        {"label": "正向能耗区域", "value": flow.get("diagnostics", {}).get("positive_area_count", 0)},
                        {"label": "零增量区域", "value": flow.get("diagnostics", {}).get("zero_ready_count", 0)},
                        {"label": "历史估算点位", "value": flow.get("diagnostics", {}).get("estimated_count", 0)},
                        {"label": "历史估算电量", "value": f"{flow.get('diagnostics', {}).get('estimated_energy_kwh', 0)} kWh"},
                        {"label": "回退来源", "value": "是" if flow.get("diagnostics", {}).get("used_fallback") else "否"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/flows/energy-diagnostics")
    async def get_energy_flow_diagnostics(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        flow = await self._energy_flow_data(db_session, billing_month)
        return Response(content={"code": 200, "msg": "获取成功", "data": flow.get("diagnostics", {})})

    @get("/api/energy-carbon/flows/energy-top-links")
    async def get_energy_flow_top_links(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        flow = await self._energy_flow_data(db_session, billing_month)
        node_map = {item["id"]: item["name"] for item in flow.get("nodes", [])}
        top_links = [
            {**item, "source": node_map.get(item["source"], item["source"]), "target": node_map.get(item["target"], item["target"])}
            for item in sorted(flow.get("links", []), key=lambda item: item["value"], reverse=True)[:10]
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": top_links}})

    @get("/api/energy-carbon/carbon/records")
    async def list_energy_center_carbon_records(
        self,
        db_session: AsyncSession,
        scope_filter: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        ledger = await self._carbon_ledger_page(db_session, scope_filter, status, limit, offset)
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        summary = {
            "total": len(records),
            "pending": sum(1 for item in records if item["data"].get("status") == STATUS_PENDING),
            "approved": sum(1 for item in records if item["data"].get("status") == STATUS_APPROVED),
            "missing_factor": sum(1 for item in records if not item["data"].get("factor_source")),
            "missing_result": sum(1 for item in records if item["data"].get("computed_co2e") is None),
            "rejected": sum(1 for item in records if item["data"].get("status") == STATUS_REJECTED),
        }
        return Response(content={"code": 200, "msg": "获取成功", "data": {**ledger, "summary": summary}})

    @get("/api/energy-carbon/carbon/summary")
    async def get_energy_center_carbon_summary(self, db_session: AsyncSession) -> Response[dict]:
        ledger = await self._carbon_ledger_page(db_session, None, None, 500, 0)
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        usage = self._build_factor_usage(records)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"summary": ledger.get("items", []), "usage": usage, "totals": ledger.get("total", 0)}})

    @get("/api/energy-carbon/carbon/records/{record_type:str}/{record_id:int}")
    async def get_energy_center_carbon_record(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": detail})

    @get("/api/energy-carbon/carbon/pending")
    async def list_energy_center_pending(self, db_session: AsyncSession, limit: int = 20, offset: int = 0) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        pending_items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "factor_source": item["data"].get("factor_source"),
                "computed_co2e": item["data"].get("computed_co2e"),
            }
            for item in records
            if item["data"].get("status") == STATUS_PENDING
        ]
        pending_items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": pending_items[offset : offset + limit], "total": len(pending_items), "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/carbon/trend")
    async def get_energy_center_carbon_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_carbon_scope_trend(records, months)}})

    @get("/api/energy-carbon/carbon/flow")
    async def get_energy_center_carbon_flow(self, db_session: AsyncSession) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_carbon_flow(records)})

    @get("/api/energy-carbon/carbon/evidence/{record_type:str}/{record_id:int}")
    async def get_energy_center_carbon_evidence(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        source = detail.get("source", {})
        attachments = []
        if isinstance(source, dict) and source.get("attachment"):
            attachments.append({"label": "业务附件", "path": source.get("attachment")})
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": attachments}})

    @get("/api/energy-carbon/quality/issues")
    async def list_quality_issues(
        self,
        db_session: AsyncSession,
        issue_type: str | None = None,
        severity: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> Response[dict]:
        items = await self._build_quality_issues(db_session)
        if issue_type and issue_type != "all":
            items = [item for item in items if item["issue_type"] == issue_type]
        if severity and severity != "all":
            items = [item for item in items if item["severity"] == severity]
        summary: dict[str, int] = defaultdict(int)
        for item in items:
            summary[item["issue_type"]] += 1
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset, "summary": summary}})

    @get("/api/energy-carbon/quality/summary")
    async def get_quality_summary(self, db_session: AsyncSession) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        summary: dict[str, int] = defaultdict(int)
        by_module: dict[str, int] = defaultdict(int)
        for item in issues:
            summary[item["issue_type"]] += 1
            by_module[item["module"]] += 1
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "summary": summary,
                    "by_module": [{"name": name, "value": value} for name, value in sorted(by_module.items(), key=lambda pair: pair[1], reverse=True)],
                },
            }
        )

    @get("/api/energy-carbon/quality/trend")
    async def get_quality_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_quality_trend(issues, months)}})

    @get("/api/energy-carbon/quality/impact-ranking")
    async def get_quality_impact_ranking(self, db_session: AsyncSession) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        by_module: dict[str, int] = defaultdict(int)
        for item in issues:
            by_module[item["module"]] += 1
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [{"name": name, "value": value} for name, value in sorted(by_module.items(), key=lambda pair: pair[1], reverse=True)]}})

    @get("/api/energy-carbon/trace/{record_type:str}/{record_id:int}")
    async def get_trace(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        trace = [
            {"step": "采集/录入", "summary": detail["record_label"], "detail": detail["source"]},
            {"step": "核算", "summary": "活动量、因子与结果", "detail": detail["computation"]},
            {"step": "审核", "summary": f"{len(detail['audit_logs'])} 条审核日志", "detail": detail["audit_logs"]},
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"trace": trace, **detail}})

    @get("/api/energy-carbon/factors")
    async def list_energy_center_factors(
        self,
        db_session: AsyncSession,
        limit: int = 20,
        offset: int = 0,
        scope_filter: str | None = None,
    ) -> Response[dict]:
        stmt = select(m.EmissionFactor).order_by(m.EmissionFactor.year.desc(), m.EmissionFactor.id.desc())
        count_stmt = select(func.count()).select_from(m.EmissionFactor)
        if scope_filter:
            stmt = stmt.where(m.EmissionFactor.scope == scope_filter)
            count_stmt = count_stmt.where(m.EmissionFactor.scope == scope_filter)
        items = (await db_session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        total = int((await db_session.execute(count_stmt)).scalar_one())
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in items], "total": total, "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/factors/stats")
    async def get_energy_center_factor_stats(self, db_session: AsyncSession) -> Response[dict]:
        emission_total = int((await db_session.execute(select(func.count()).select_from(m.EmissionFactor))).scalar_one())
        active_total = int((await db_session.execute(select(func.count()).select_from(m.EmissionFactor).where(m.EmissionFactor.is_active.is_(True)))).scalar_one())
        library_total = int((await db_session.execute(select(func.count()).select_from(m.CarbonFactorLibrary))).scalar_one())
        raw_total = int((await db_session.execute(select(func.count()).select_from(m.CarbonFactorRawRecord))).scalar_one())
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        missing_factor_total = sum(1 for item in records if not item["data"].get("factor_source"))
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "emission_total": emission_total,
                    "active_total": active_total,
                    "library_total": library_total,
                    "raw_total": raw_total,
                    "used_total": len(records) - missing_factor_total,
                    "missing_factor_total": missing_factor_total,
                },
            }
        )

    @get("/api/energy-carbon/factors/usage")
    async def get_energy_center_factor_usage(self, db_session: AsyncSession) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_factor_usage(records)})

    @get("/api/energy-carbon/factors/categories")
    async def get_energy_center_factor_categories(self, db_session: AsyncSession) -> Response[dict]:
        rows = (
            await db_session.execute(select(m.EmissionFactor.scope, m.EmissionFactor.category, func.count(m.EmissionFactor.id)).group_by(m.EmissionFactor.scope, m.EmissionFactor.category))
        ).all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": [{"scope": scope, "category": category, "value": int(total)} for scope, category, total in rows],
                },
            }
        )

    @post("/api/energy-carbon/admin/backfill/raw-meter-history", guards=[requires_superuser])
    async def admin_backfill_raw_meter_history(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        start_month = str(data.get("start_month")).strip() if data.get("start_month") not in (None, "") else None
        end_month = str(data.get("end_month")).strip() if data.get("end_month") not in (None, "") else None
        raw_start_month, raw_end_month = await CarbonAnalyticsController._raw_history_month_range(db_session)
        effective_start = start_month or raw_start_month
        effective_end = end_month or raw_end_month
        if not effective_start or not effective_end:
            return Response(content={"code": 200, "msg": "暂无原始电表历史数据", "data": {"months": []}})
        month_keys = _month_span(effective_start, effective_end)
        result = await self._impute_raw_scope2_history(db_session, scope2_meter_aggregate_service, month_keys)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.scope2.backfill-raw-history",
            target_type="scope2_meter_aggregate",
            details={"query_scope": {"start_month": effective_start, "end_month": effective_end}, "batch_size": len(month_keys)},
        )
        return Response(content={"code": 200, "msg": "原始电表历史补全完成", "data": result})

    @post("/api/energy-carbon/admin/backfill/scope2", guards=[requires_superuser])
    async def admin_backfill_scope2(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        months = int(data.get("months") or 12)
        area_id = str(data.get("area_id")).strip() if data.get("area_id") not in (None, "") else None
        month_keys = await CarbonAnalyticsController._recent_scope2_backfill_months(db_session, months)
        rebuilt_count = 0
        ready_count = 0
        invalid_count = 0
        details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            rows = await CarbonCRUDController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month, area_id)
            rebuilt_count += len(rows)
            ready_month = sum(1 for row in rows if row.calc_status == "ready")
            invalid_month = len(rows) - ready_month
            ready_count += ready_month
            invalid_count += invalid_month
            details.append(
                {
                    "billing_month": billing_month,
                    "rebuilt_count": len(rows),
                    "ready_count": ready_month,
                    "invalid_count": invalid_month,
                }
            )
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.scope2.backfill",
            target_type="scope2_meter_aggregate",
            details={"batch_size": len(month_keys), "query_scope": {"months": months, "area_id": area_id}},
        )
        return Response(
            content={
                "code": 200,
                "msg": "范围2回填完成",
                "data": {
                    "months": month_keys,
                    "rebuilt_count": rebuilt_count,
                    "ready_count": ready_count,
                    "invalid_count": invalid_count,
                    "details": details,
                },
            }
        )

    @post("/api/energy-carbon/admin/seed/demo-carbon", guards=[requires_superuser])
    async def admin_seed_demo_carbon(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        months = int(data.get("months") or 6)
        deleted = await self._clear_demo_seed_records(db_session)
        created = await self._seed_demo_scope_records(db_session, months)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.demo.seed",
            target_type="demo_seed",
            details={"query_scope": {"months": months}, "deleted": deleted, "created": created},
        )
        return Response(content={"code": 200, "msg": "演示样例已重建", "data": {"deleted": deleted, "created": created}})

    @delete("/api/energy-carbon/admin/seed/demo-carbon", guards=[requires_superuser], status_code=200)
    async def admin_delete_demo_carbon(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        deleted = await self._clear_demo_seed_records(db_session)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.demo.delete",
            target_type="demo_seed",
            details={"deleted": deleted},
        )
        return Response(content={"code": 200, "msg": "演示样例已清理", "data": {"deleted": deleted}})


class CarbonCRUDController(Controller):
    """Scope 1/2/3 碳数据 CRUD 与审核（参考 xtck_deploy 与 PRD 5）。"""
    tags = ["CarbonCRUD"]
    signature_types = [Response]
    dependencies = {
        "scope1_mobile_service": provide_scope1_mobile_combustion_service,
        "scope1_stationary_service": provide_scope1_stationary_combustion_service,
        "scope1_refrigerant_service": provide_scope1_refrigerant_leak_service,
        "scope2_bill_service": provide_scope2_electricity_bill_service,
        "scope2_meter_aggregate_service": provide_scope2_meter_aggregate_service,
        "scope2_purchased_energy_service": provide_scope2_purchased_energy_service,
        "energy_type_service": provide_energy_type_service,
        "scope3_waste_service": provide_scope3_waste_disposal_service,
        "scope3_transport_service": provide_scope3_third_party_transport_service,
        "emission_factor_service": provide_emission_factor_service,
        "employee_commute_service": provide_employee_commute_service,
        "iot_telemetry_service": provide_iot_telemetry_service,
        "audit_log_service": provide_carbon_audit_log_service,
        "area_service": provide_area_service,
        "device_service": provide_device_service,
        "monitor_sector_service": provide_monitor_sector_service,
        "monitor_sector_photo_service": provide_monitor_sector_photo_service,
        "monitor_equipment_service": provide_monitor_equipment_service,
        "device_type_service": provide_device_type_service,
        "device_point_service": provide_device_point_service,
        "video_monitor_service": provide_video_monitor_service,
        "warning_rule_service": provide_warning_rule_service,
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "api_result_key_mapping_service": provide_api_result_key_mapping_service,
        "energy_storage_value_service": provide_energy_storage_value_service,
        "ammeter_index_value_service": provide_ammeter_index_value_service,
        "in_money_service": provide_in_money_service,
        "out_money_service": provide_out_money_service,
        "security_audit_service": provide_audit_log_service,
    }

    async def _create_audit_log(
        self,
        audit_log_service: services.CarbonAuditLogService,
        data: dict[str, Any],
    ) -> None:
        """Create an audit log entry and let failures abort the parent workflow."""
        await audit_log_service.create(data, auto_commit=True)

    async def _log_carbon_security_event(
        self,
        security_audit_service: AuditLogService,
        request: Request[Any, Any, Any],
        *,
        action: str,
        record_type: str,
        record_id: int | str,
        comment: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(details or {})
        payload.setdefault("record_type", record_type)
        payload.setdefault("record_id", record_id)
        if comment:
            payload.setdefault("reason", comment)
        await _log_security_audit(
            security_audit_service,
            request,
            action=action,
            target_type=record_type,
            target_id=str(record_id),
            target_label=comment,
            details=payload,
        )

    async def _log_admin_data_event(
        self,
        security_audit_service: AuditLogService,
        request: Request[Any, Any, Any],
        *,
        action: str,
        target_type: str,
        target_id: int | str | None = None,
        target_label: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(details or {})
        payload.setdefault("target_type", target_type)
        if target_id is not None:
            payload.setdefault("target_id", target_id)
        await _log_security_audit(
            security_audit_service,
            request,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_label=target_label,
            details=payload,
        )

    # ---------- Scope1 移动源 ----------
    @get("/api/carbon/scope1-mobile-combustion")
    async def list_scope1_mobile(
        self,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope1MobileCombustion.status == status] if status else []
        session = scope1_mobile_service.repository.session
        page = await _list_page(
            scope1_mobile_service,
            m.Scope1MobileCombustion,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["asset_id", "asset_name", "fuel_type", "unit", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope1_mobile_service,
            m.Scope1MobileCombustion,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["asset_id", "asset_name", "fuel_type", "unit", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session))

    @get("/api/carbon/scope1-mobile-combustion/{record_id:int}")
    async def get_scope1_mobile(
        self, record_id: int, scope1_mobile_service: services.Scope1MobileCombustionService
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_mobile_service.repository.session)})

    @post("/api/carbon/scope1-mobile-combustion")
    async def create_scope1_mobile(
        self,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_consumption(data.get("amount"), "消耗量")
            validate_date_not_future(data.get("record_date"), "使用日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["record_date"])
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        obj = await scope1_mobile_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_mobile_service.repository.session), "msg": "创建成功"})

    @patch("/api/carbon/scope1-mobile-combustion/{record_id:int}")
    async def update_scope1_mobile(
        self,
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "amount" in data:
                validate_consumption(data["amount"], "消耗量")
            if "record_date" in data:
                validate_date_not_future(data["record_date"], "使用日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["record_date"])
        await scope1_mobile_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope1_mobile_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope1_mobile_service.repository.session)})

    @delete("/api/carbon/scope1-mobile-combustion/{record_id:int}", status_code=200)
    async def delete_scope1_mobile(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        # 按照内置 UserService 的用法，delete 期望传入主键 ID
        await scope1_mobile_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope1MobileCombustion",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/submit")
    async def submit_scope1_mobile(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_mobile_service.repository.session)
        await scope1_mobile_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope1MobileCombustion",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope1_mobile(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_mobile_service.repository.session)
        # 数据库字段为 TIMESTAMP WITHOUT TIME ZONE，这里去掉 tzinfo，避免 asyncpg 报错
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_mobile_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope1MobileCombustion",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope1_mobile(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope1_mobile_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope1MobileCombustion",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 固定源 ----------
    @get("/api/carbon/scope1-stationary-combustion")
    async def list_scope1_stationary(
        self,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope1StationaryCombustion.status == status] if status else []
        session = scope1_stationary_service.repository.session
        page = await _list_page(
            scope1_stationary_service,
            m.Scope1StationaryCombustion,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["facility_name", "fuel_type", "unit", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope1_stationary_service,
            m.Scope1StationaryCombustion,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["facility_name", "fuel_type", "unit", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session))

    @get("/api/carbon/scope1-stationary-combustion/{record_id:int}")
    async def get_scope1_stationary(
        self, record_id: int, scope1_stationary_service: services.Scope1StationaryCombustionService
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_stationary_service.repository.session)})

    @post("/api/carbon/scope1-stationary-combustion")
    async def create_scope1_stationary(
        self,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_consumption(data.get("amount"), "消耗量")
            validate_period_start_end(data.get("period_start"), data.get("period_end"))
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["period_start", "period_end"])
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        obj = await scope1_stationary_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_stationary_service.repository.session), "msg": "创建成功"})

    @patch("/api/carbon/scope1-stationary-combustion/{record_id:int}")
    async def update_scope1_stationary(
        self,
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "amount" in data:
                validate_consumption(data["amount"], "消耗量")
            if "period_start" in data or "period_end" in data:
                validate_period_start_end(data.get("period_start") or obj.period_start, data.get("period_end") or obj.period_end)
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["period_start", "period_end"])
        await scope1_stationary_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope1_stationary_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope1_stationary_service.repository.session)})

    @delete("/api/carbon/scope1-stationary-combustion/{record_id:int}", status_code=200)
    async def delete_scope1_stationary(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope1_stationary_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/submit")
    async def submit_scope1_stationary(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_stationary_service.repository.session)
        await scope1_stationary_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope1_stationary(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_stationary_service.repository.session)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_stationary_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope1_stationary(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope1_stationary_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 逸散（制冷剂）完整 CRUD + 审核 ----------
    @get("/api/carbon/scope1-refrigerant-leak/{record_id:int}")
    async def get_scope1_refrigerant(
        self, record_id: int, scope1_refrigerant_service: services.Scope1RefrigerantLeakService
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_refrigerant_service.repository.session)})

    @post("/api/carbon/scope1-refrigerant-leak")
    async def create_scope1_refrigerant(
        self,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_consumption(data.get("amount_kg"), "填充量")
            validate_date_not_future(data.get("fill_date"), "填充日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["fill_date"])
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        obj = await scope1_refrigerant_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope1_refrigerant_service.repository.session), "msg": "创建成功"})

    @patch("/api/carbon/scope1-refrigerant-leak/{record_id:int}")
    async def update_scope1_refrigerant(
        self,
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "amount_kg" in data:
                validate_consumption(data["amount_kg"], "填充量")
            if "fill_date" in data:
                validate_date_not_future(data["fill_date"], "填充日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["fill_date"])
        await scope1_refrigerant_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope1_refrigerant_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope1_refrigerant_service.repository.session)})

    @delete("/api/carbon/scope1-refrigerant-leak/{record_id:int}", status_code=200)
    async def delete_scope1_refrigerant(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope1_refrigerant_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/submit")
    async def submit_scope1_refrigerant(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_refrigerant_service.repository.session)
        await scope1_refrigerant_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope1_refrigerant(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        await _build_scope_record_computation(obj, scope1_refrigerant_service.repository.session)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_refrigerant_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope1_refrigerant(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope1_refrigerant_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope2 电费账单 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope2-electricity-bill/{record_id:int}")
    async def get_scope2_bill(
        self, record_id: int, scope2_bill_service: services.Scope2ElectricityBillService
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope2_bill_service.repository.session, source_kind="manual_bill")})

    @post("/api/carbon/scope2-electricity-bill")
    async def create_scope2_bill(
        self,
        scope2_bill_service: services.Scope2ElectricityBillService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_consumption(data.get("total_kwh"), "总用电量")
            validate_billing_month(data.get("billing_month"))
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        try:
            payload.update(
                await _build_scope2_snapshot_payload(
                    m.Scope2ElectricityBill,
                    payload,
                    scope2_bill_service.repository.session,
                    source_kind="manual_bill",
                )
            )
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        obj = await scope2_bill_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope2_bill_service.repository.session, source_kind="manual_bill"), "msg": "创建成功"})

    @patch("/api/carbon/scope2-electricity-bill/{record_id:int}")
    async def update_scope2_bill(
        self,
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "total_kwh" in data:
                validate_consumption(data["total_kwh"], "总用电量")
            if "billing_month" in data:
                validate_billing_month(data["billing_month"])
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        payload = _mutable_record_data(obj)
        payload.update({k: v for k, v in data.items() if v is not None})
        try:
            payload.update(
                await _build_scope2_snapshot_payload(
                    m.Scope2ElectricityBill,
                    payload,
                    scope2_bill_service.repository.session,
                    source_kind="manual_bill",
                )
            )
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        await scope2_bill_service.update(item_id=record_id, data=payload, auto_commit=True)
        fresh = await scope2_bill_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope2_bill_service.repository.session, source_kind="manual_bill")})

    @delete("/api/carbon/scope2-electricity-bill/{record_id:int}", status_code=200)
    async def delete_scope2_bill(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope2_bill_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope2ElectricityBill",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/submit")
    async def submit_scope2_bill(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            try:
                obj = await _refresh_scope2_snapshot(obj, scope2_bill_service, source_kind="manual_bill")
            except CarbonValidationError as e:
                return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前账单尚未形成有效核算结果"}, status_code=400)
        await scope2_bill_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope2ElectricityBill",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope2_bill(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            try:
                obj = await _refresh_scope2_snapshot(obj, scope2_bill_service, source_kind="manual_bill")
            except CarbonValidationError as e:
                return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前账单尚未形成有效核算结果"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope2_bill_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope2ElectricityBill",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope2_bill(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope2_bill_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope2ElectricityBill",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope2 外购热力/蒸汽/冷量 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope2-purchased-energy/{record_id:int}")
    async def get_scope2_purchased_energy(
        self, record_id: int, scope2_purchased_energy_service: services.Scope2PurchasedEnergyService
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(
                    obj,
                    scope2_purchased_energy_service.repository.session,
                    source_kind="purchased_energy",
                ),
            }
        )

    @post("/api/carbon/scope2-purchased-energy")
    async def create_scope2_purchased_energy(
        self,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_period_start_end(data.get("period_start"), data.get("period_end"))
            validate_consumption(data.get("amount"), "能源消费量")
            _coerce_date_fields(data, ["period_start", "period_end"])
            payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
            payload.update(
                await _build_scope2_snapshot_payload(
                    m.Scope2PurchasedEnergy,
                    payload,
                    scope2_purchased_energy_service.repository.session,
                    source_kind="purchased_energy",
                )
            )
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        obj = await scope2_purchased_energy_service.create(payload, auto_commit=True)
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(
                    obj,
                    scope2_purchased_energy_service.repository.session,
                    source_kind="purchased_energy",
                ),
                "msg": "创建成功",
            }
        )

    @patch("/api/carbon/scope2-purchased-energy/{record_id:int}")
    async def update_scope2_purchased_energy(
        self,
        record_id: int,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            merged = _mutable_record_data(obj)
            merged.update({k: v for k, v in data.items() if v is not None})
            validate_period_start_end(merged.get("period_start"), merged.get("period_end"))
            validate_consumption(merged.get("amount"), "能源消费量")
            _coerce_date_fields(merged, ["period_start", "period_end"])
            merged.update(
                await _build_scope2_snapshot_payload(
                    m.Scope2PurchasedEnergy,
                    merged,
                    scope2_purchased_energy_service.repository.session,
                    source_kind="purchased_energy",
                )
            )
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        await scope2_purchased_energy_service.update(item_id=record_id, data=merged, auto_commit=True)
        fresh = await scope2_purchased_energy_service.get_one(id=record_id)
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(
                    fresh,
                    scope2_purchased_energy_service.repository.session,
                    source_kind="purchased_energy",
                ),
            }
        )

    @delete("/api/carbon/scope2-purchased-energy/{record_id:int}", status_code=200)
    async def delete_scope2_purchased_energy(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope2_purchased_energy_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope2-purchased-energy/{record_id:int}/submit")
    async def submit_scope2_purchased_energy(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        try:
            obj = await _refresh_scope2_snapshot(obj, scope2_purchased_energy_service, source_kind="purchased_energy")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        await scope2_purchased_energy_service.update(item_id=record_id, data={"status": STATUS_PENDING}, auto_commit=True)
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2PurchasedEnergy", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope2-purchased-energy/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope2_purchased_energy(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        try:
            obj = await _refresh_scope2_snapshot(obj, scope2_purchased_energy_service, source_kind="purchased_energy")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope2_purchased_energy_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2PurchasedEnergy", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope2-purchased-energy/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope2_purchased_energy(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope2_purchased_energy_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope2_purchased_energy_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2PurchasedEnergy", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope3 废弃物 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope3-waste-disposal/{record_id:int}")
    async def get_scope3_waste(
        self, record_id: int, scope3_waste_service: services.Scope3WasteDisposalService
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope3_waste_service.repository.session)})

    @post("/api/carbon/scope3-waste-disposal")
    async def create_scope3_waste(
        self,
        scope3_waste_service: services.Scope3WasteDisposalService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_consumption(data.get("weight_ton"), "重量")
            validate_date_not_future(data.get("date"), "产生日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["date"])
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        obj = await scope3_waste_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope3_waste_service.repository.session), "msg": "创建成功"})

    @patch("/api/carbon/scope3-waste-disposal/{record_id:int}")
    async def update_scope3_waste(
        self,
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "weight_ton" in data:
                validate_consumption(data["weight_ton"], "重量")
            if "date" in data:
                validate_date_not_future(data["date"], "产生日期")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["date"])
        await scope3_waste_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope3_waste_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope3_waste_service.repository.session)})

    @delete("/api/carbon/scope3-waste-disposal/{record_id:int}", status_code=200)
    async def delete_scope3_waste(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope3_waste_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope3WasteDisposal",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/submit")
    async def submit_scope3_waste(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await _build_scope_record_computation(obj, scope3_waste_service.repository.session)
        await scope3_waste_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope3WasteDisposal",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope3_waste(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        await _build_scope_record_computation(obj, scope3_waste_service.repository.session)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope3_waste_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope3WasteDisposal",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope3_waste(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope3_waste_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope3WasteDisposal",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope3 外购运输 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope3-third-party-transport/{record_id:int}")
    async def get_scope3_transport(
        self, record_id: int, scope3_transport_service: services.Scope3ThirdPartyTransportService
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope3_transport_service.repository.session)})

    @post("/api/carbon/scope3-third-party-transport")
    async def create_scope3_transport(
        self,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        try:
            validate_amount_non_negative(data.get("distance_km"), "运输距离")
            validate_amount_non_negative(data.get("load_ton"), "载货量")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        payload = {**_carbon_defaults(), **{k: v for k, v in data.items() if v is not None}}
        obj = await scope3_transport_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": await _serialize_scope_record(obj, scope3_transport_service.repository.session), "msg": "创建成功"})

    @patch("/api/carbon/scope3-third-party-transport/{record_id:int}")
    async def update_scope3_transport(
        self,
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "distance_km" in data:
                validate_amount_non_negative(data["distance_km"], "运输距离")
            if "load_ton" in data:
                validate_amount_non_negative(data["load_ton"], "载货量")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        await scope3_transport_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope3_transport_service.get_one(id=record_id)
        return Response(content={"code": 200, "msg": "更新成功", "data": await _serialize_scope_record(fresh, scope3_transport_service.repository.session)})

    @delete("/api/carbon/scope3-third-party-transport/{record_id:int}", status_code=200)
    async def delete_scope3_transport(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope3_transport_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/submit")
    async def submit_scope3_transport(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await _build_scope_record_computation(obj, scope3_transport_service.repository.session)
        await scope3_transport_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope3_transport(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        await _build_scope_record_computation(obj, scope3_transport_service.repository.session)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope3_transport_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope3_transport(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope3_transport_service.update(
            item_id=record_id,
            data={"status": STATUS_REJECTED, "reject_reason": reason},
            auto_commit=True,
        )
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 逸散 / Scope2 / Scope3：列表 + 待审核汇总 ----------
    @get("/api/carbon/scope1-refrigerant-leak")
    async def list_scope1_refrigerant(
        self,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope1RefrigerantLeak.status == status] if status else []
        session = scope1_refrigerant_service.repository.session
        page = await _list_page(
            scope1_refrigerant_service,
            m.Scope1RefrigerantLeak,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["device_id", "device_name", "refrigerant_type", "leak_type", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope1_refrigerant_service,
            m.Scope1RefrigerantLeak,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["device_id", "device_name", "refrigerant_type", "leak_type", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session))

    @get("/api/carbon/scope2-electricity-bill")
    async def list_scope2_bill(
        self,
        scope2_bill_service: services.Scope2ElectricityBillService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope2ElectricityBill.status == status] if status else []
        session = scope2_bill_service.repository.session
        page = await _list_page(
            scope2_bill_service,
            m.Scope2ElectricityBill,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["account_number", "billing_month", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope2_bill_service,
            m.Scope2ElectricityBill,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["account_number", "billing_month", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session, source_kind="manual_bill"))

    @get("/api/carbon/scope2-purchased-energy")
    async def list_scope2_purchased_energy(
        self,
        scope2_purchased_energy_service: services.Scope2PurchasedEnergyService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        energy_type_code: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if status:
            conditions.append(m.Scope2PurchasedEnergy.status == status)
        if energy_type_code:
            conditions.append(m.Scope2PurchasedEnergy.energy_type_code == energy_type_code)
        session = scope2_purchased_energy_service.repository.session
        page = await _list_page(
            scope2_purchased_energy_service,
            m.Scope2PurchasedEnergy,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["energy_type_code", "energy_type_name", "supplier_name", "area_name", "facility_name", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope2_purchased_energy_service,
            m.Scope2PurchasedEnergy,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["energy_type_code", "energy_type_name", "supplier_name", "area_name", "facility_name", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session, source_kind="purchased_energy"))

    @get("/api/carbon/scope3-waste-disposal")
    async def list_scope3_waste(
        self,
        scope3_waste_service: services.Scope3WasteDisposalService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope3WasteDisposal.status == status] if status else []
        session = scope3_waste_service.repository.session
        page = await _list_page(
            scope3_waste_service,
            m.Scope3WasteDisposal,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["category", "treatment_method", "vendor_name", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope3_waste_service,
            m.Scope3WasteDisposal,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["category", "treatment_method", "vendor_name", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session))

    @get("/api/carbon/scope3-third-party-transport")
    async def list_scope3_transport(
        self,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = [m.Scope3ThirdPartyTransport.status == status] if status else []
        session = scope3_transport_service.repository.session
        page = await _list_page(
            scope3_transport_service,
            m.Scope3ThirdPartyTransport,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["waybill_no", "origin", "destination", "vehicle_type", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        rows = await _list_rows(
            scope3_transport_service,
            m.Scope3ThirdPartyTransport,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["waybill_no", "origin", "destination", "vehicle_type", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=await _augment_page_items(page, rows, session))

    @get("/api/carbon/emission-factors")
    async def list_emission_factors(
        self,
        emission_factor_service: services.EmissionFactorService,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        scope: str | None = None,
        is_active: bool | None = None,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if scope:
            conditions.append(m.EmissionFactor.scope == scope)
        if is_active is not None:
            conditions.append(m.EmissionFactor.is_active == is_active)
        page = await _list_page(
            emission_factor_service,
            m.EmissionFactor,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["scope", "category", "sub_category", "unit", "factor_unit", "source", "source_system"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @get("/api/carbon/factor-library/overview")
    async def get_factor_library_overview(self, db_session: AsyncSession) -> Response[dict]:
        """Official factor asset library overview."""
        batch = (
            await db_session.execute(
                select(m.CarbonFactorImportBatch).order_by(m.CarbonFactorImportBatch.created_at.desc()).limit(1)
            )
        ).scalars().first()
        library_count = await db_session.scalar(select(func.count()).select_from(m.CarbonFactorLibrary))
        category_count = await db_session.scalar(select(func.count()).select_from(m.CarbonFactorCategory))
        leaf_category_count = await db_session.scalar(
            select(func.count()).select_from(m.CarbonFactorCategory).where(m.CarbonFactorCategory.is_leaf == True)
        )
        raw_record_count = await db_session.scalar(select(func.count()).select_from(m.CarbonFactorRawRecord))
        projection_candidate_count = await db_session.scalar(
            select(func.count())
            .select_from(m.CarbonFactorRawRecord)
            .where(m.CarbonFactorRawRecord.projection_status == "candidate")
        )
        calculation_factor_count = await db_session.scalar(select(func.count()).select_from(m.EmissionFactor))
        libraries = (
            await db_session.execute(
                select(m.CarbonFactorLibrary).order_by(
                    m.CarbonFactorLibrary.library_year.desc(),
                    m.CarbonFactorLibrary.library_code.asc(),
                )
            )
        ).scalars().all()
        data = {
            "batch": model_to_dict(batch) if batch else None,
            "library_count": library_count or 0,
            "category_count": category_count or 0,
            "leaf_category_count": leaf_category_count or 0,
            "raw_record_count": raw_record_count or 0,
            "projection_candidate_count": projection_candidate_count or 0,
            "calculation_factor_count": calculation_factor_count or 0,
            "libraries": [model_to_dict(item) for item in libraries],
        }
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get("/api/carbon/factor-library/records")
    async def list_factor_library_records(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        library_code: str | None = None,
        library_year: str | None = None,
        top_category: str | None = None,
        category_path_prefix: str | None = None,
        projection_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        """Search source-native factor records with pagination."""
        filters = []
        if library_code and library_code != "all":
            filters.append(m.CarbonFactorRawRecord.library_code == library_code)
        if library_year and library_year != "all":
            filters.append(m.CarbonFactorRawRecord.library_year == library_year)
        if top_category and top_category != "all":
            filters.append(m.CarbonFactorRawRecord.top_category == top_category)
        if category_path_prefix and category_path_prefix != "all":
            category_prefix = category_path_prefix.strip()
            filters.append(
                or_(
                    m.CarbonFactorRawRecord.category_path == category_prefix,
                    m.CarbonFactorRawRecord.category_path.ilike(f"{category_prefix} /%"),
                )
            )
        if projection_status and projection_status != "all":
            filters.append(m.CarbonFactorRawRecord.projection_status == projection_status)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    m.CarbonFactorRawRecord.factor_name.ilike(pattern),
                    m.CarbonFactorRawRecord.category_path.ilike(pattern),
                    m.CarbonFactorRawRecord.factor_unit_raw.ilike(pattern),
                    m.CarbonFactorRawRecord.provider.ilike(pattern),
                )
            )

        limit_clamped = max(10, min(limit, 200))
        offset_clamped = max(0, offset)
        total_stmt = select(func.count()).select_from(m.CarbonFactorRawRecord)
        rows_stmt = select(m.CarbonFactorRawRecord).order_by(m.CarbonFactorRawRecord.id.desc()).limit(limit_clamped).offset(offset_clamped)
        for item_filter in filters:
            total_stmt = total_stmt.where(item_filter)
            rows_stmt = rows_stmt.where(item_filter)

        total = await db_session.scalar(total_stmt)
        rows = (await db_session.execute(rows_stmt)).scalars().all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": [_augment_raw_factor_record_dict(model_to_dict(item)) for item in rows],
                    "total": total or 0,
                    "limit": limit_clamped,
                    "offset": offset_clamped,
                },
            }
        )

    @get("/api/carbon/factor-library/records/{record_id:int}")
    async def get_factor_library_record(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        item = await db_session.get(m.CarbonFactorRawRecord, record_id)
        if item is None:
            return Response(content={"code": 404, "msg": "记录不存在", "data": None}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": _augment_raw_factor_record_dict(model_to_dict(item))})

    @get("/api/carbon/factor-library/categories")
    async def list_factor_library_categories(
        self,
        db_session: AsyncSession,
        library_code: str | None = None,
        library_year: str | None = None,
    ) -> Response[dict]:
        stmt = select(m.CarbonFactorCategory).order_by(
            m.CarbonFactorCategory.library_year.desc(),
            m.CarbonFactorCategory.library_code.asc(),
            m.CarbonFactorCategory.category_path.asc(),
        )
        if library_code and library_code != "all":
            stmt = stmt.where(m.CarbonFactorCategory.library_code == library_code)
        if library_year and library_year != "all":
            stmt = stmt.where(m.CarbonFactorCategory.library_year == library_year)
        rows = (await db_session.execute(stmt)).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": [model_to_dict(item) for item in rows]})

    @get("/api/carbon/factor-library/category-tree")
    async def get_factor_library_category_tree(self, db_session: AsyncSession) -> Response[dict]:
        """Return category data as library-grouped expandable trees."""
        libraries = (
            await db_session.execute(
                select(m.CarbonFactorLibrary).order_by(
                    m.CarbonFactorLibrary.library_year.desc(),
                    m.CarbonFactorLibrary.library_code.asc(),
                )
            )
        ).scalars().all()
        categories = (
            await db_session.execute(
                select(m.CarbonFactorCategory).order_by(
                    m.CarbonFactorCategory.library_year.desc(),
                    m.CarbonFactorCategory.library_code.asc(),
                    m.CarbonFactorCategory.depth.asc(),
                )
            )
        ).scalars().all()

        nodes_by_id: dict[str, dict[str, Any]] = {}
        roots_by_library: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        for category in categories:
            raw_payload = category.raw_payload if isinstance(category.raw_payload, dict) else {}
            node = {
                "id": category.id,
                "source_category_id": category.source_category_id,
                "parent_source_category_id": category.parent_source_category_id,
                "category_code": raw_payload.get("code"),
                "library_year": category.library_year,
                "library_code": category.library_code,
                "category_name": category.category_name,
                "category_path": category.category_path,
                "depth": category.depth,
                "is_leaf": category.is_leaf,
                "children": [],
                "_sort_num": raw_payload.get("sortNum"),
            }
            nodes_by_id[category.source_category_id] = node

        for category in categories:
            node = nodes_by_id[category.source_category_id]
            parent_id = category.parent_source_category_id
            if parent_id and parent_id != "-1" and parent_id in nodes_by_id:
                nodes_by_id[parent_id]["children"].append(node)
            else:
                roots_by_library.setdefault((category.library_year, category.library_code), []).append(node)

        def sort_nodes(nodes: list[dict[str, Any]]) -> None:
            def sort_key(node: dict[str, Any]) -> tuple[int, str, str]:
                sort_num = node.get("_sort_num")
                sort_rank = sort_num if isinstance(sort_num, int) else 9999
                return (sort_rank, str(node.get("category_code") or ""), str(node.get("category_name") or ""))

            nodes.sort(key=sort_key)
            for node in nodes:
                sort_nodes(node["children"])
                node.pop("_sort_num", None)

        for roots in roots_by_library.values():
            sort_nodes(roots)

        known_library_keys = {(library.library_year, library.library_code) for library in libraries}
        category_counts: dict[tuple[str | None, str | None], int] = {}
        for category in categories:
            key = (category.library_year, category.library_code)
            category_counts[key] = category_counts.get(key, 0) + 1

        groups = [
            {
                "library_year": library.library_year,
                "library_code": library.library_code,
                "library_name": library.library_name,
                "institution": library.institution,
                "category_count": category_counts.get((library.library_year, library.library_code), 0),
                    "children": roots_by_library.get((library.library_year, library.library_code), []),
            }
            for library in libraries
        ]
        for (library_year, library_code), roots in roots_by_library.items():
            if (library_year, library_code) not in known_library_keys:
                groups.append(
                    {
                        "library_year": library_year,
                        "library_code": library_code,
                        "library_name": f"{library_year or ''} {library_code or ''}".strip(),
                        "institution": None,
                        "category_count": category_counts.get((library_year, library_code), 0),
                        "children": roots,
                    }
                )

        return Response(content={"code": 200, "msg": "获取成功", "data": {"groups": groups}})

    @get("/api/carbon/audit-logs")
    async def list_carbon_audit_logs(
        self,
        audit_log_service: services.CarbonAuditLogService,
        record_type: str | None = None,
        action: str | None = None,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        keyword: str | None = None,
        sort_field: str = "created_at",
        sort_order: str = "desc",
    ) -> Response[dict]:
        """碳业务审核操作日志列表（按时间倒序）。"""
        conditions = []
        if record_type:
            conditions.append(m.CarbonAuditLog.record_type == record_type)
        if action:
            conditions.append(m.CarbonAuditLog.action == action)
        page = await _list_page(
            audit_log_service,
            m.CarbonAuditLog,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["record_type", "action", "comment"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @get("/api/carbon/pending")
    async def list_pending(
        self,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        scope2_bill_service: services.Scope2ElectricityBillService,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        scope3_waste_service: services.Scope3WasteDisposalService,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        """待审核列表：汇总所有类型中 status=pending 的记录（审核工作台用）。"""
        out: list[dict] = []
        for name, svc, model, source_kind in [
            ("Scope1MobileCombustion", scope1_mobile_service, m.Scope1MobileCombustion, "activity_data"),
            ("Scope1StationaryCombustion", scope1_stationary_service, m.Scope1StationaryCombustion, "activity_data"),
            ("Scope1RefrigerantLeak", scope1_refrigerant_service, m.Scope1RefrigerantLeak, "activity_data"),
            ("Scope2ElectricityBill", scope2_bill_service, m.Scope2ElectricityBill, "manual_bill"),
            ("Scope2MeterAggregate", scope2_meter_aggregate_service, m.Scope2MeterAggregate, "meter_aggregate"),
            ("Scope3WasteDisposal", scope3_waste_service, m.Scope3WasteDisposal, "activity_data"),
            ("Scope3ThirdPartyTransport", scope3_transport_service, m.Scope3ThirdPartyTransport, "activity_data"),
        ]:
            items = await svc.list(model.status == STATUS_PENDING, LimitOffset(limit + offset, 0), OrderBy(model.id, "desc"))
            for i in items:
                out.append({"record_type": name, "record_id": i.id, **await _serialize_scope_record(i, svc.repository.session, source_kind=source_kind)})
        out.sort(key=lambda row: int(row.get("record_id") or 0), reverse=True)
        limit_clamped = max(1, min(limit, 100))
        offset_clamped = max(0, offset)
        return Response(content=_paged_payload(out[offset_clamped : offset_clamped + limit_clamped], len(out), limit_clamped, offset_clamped))

    async def _rebuild_scope2_meter_aggregates(
        self,
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        billing_month: str,
        area_id: str | None = None,
    ) -> list[m.Scope2MeterAggregate]:
        month_start, month_end = _month_window(billing_month)
        if area_id:
            await db_session.execute(
                m.Scope2MeterAggregate.__table__.delete().where(
                    m.Scope2MeterAggregate.billing_month == billing_month,
                    m.Scope2MeterAggregate.area_id == area_id,
                )
            )
        else:
            await db_session.execute(m.Scope2MeterAggregate.__table__.delete().where(m.Scope2MeterAggregate.billing_month == billing_month))

        stmt = (
            select(m.AmmeterIndexValue)
            .where(
                m.AmmeterIndexValue.reading_time >= month_start,
                m.AmmeterIndexValue.reading_time < month_end,
                m.AmmeterIndexValue.reading_time.is_not(None),
                m.AmmeterIndexValue.ammeter_id.is_not(None),
            )
            .order_by(m.AmmeterIndexValue.ammeter_id.asc(), m.AmmeterIndexValue.reading_time.asc(), m.AmmeterIndexValue.id.asc())
        )
        if area_id:
            stmt = stmt.where(m.AmmeterIndexValue.area_id == area_id)
        rows = (await db_session.execute(stmt)).scalars().all()

        grouped: dict[str, list[m.AmmeterIndexValue]] = {}
        for row in rows:
            if row.ammeter_id:
                grouped.setdefault(row.ammeter_id, []).append(row)

        created: list[m.Scope2MeterAggregate] = []
        for ammeter_id, samples in grouped.items():
            first = samples[0]
            usable = [sample for sample in samples if sample.zygdn is not None]
            note = None
            status = "ready"
            start_total = end_total = total_kwh = None
            last = first
            if len(usable) >= 2:
                first_usable = usable[0]
                last_usable = usable[-1]
                start_total = Decimal(str(first_usable.zygdn))
                end_total = Decimal(str(last_usable.zygdn))
                total_kwh = end_total - start_total
                last = last_usable
                if total_kwh < 0:
                    status = "invalid_delta"
                    note = "月度末值小于初值，无法形成有效用电量。"
                    total_kwh = None
            else:
                status = "insufficient_data"
                note = "月内采样不足，无法形成首末差值。"

            payload = {
                "source_kind": "meter_aggregate",
                "ammeter_id": ammeter_id,
                "ammeter_name": first.ammeter_name,
                "area_id": first.area_id,
                "area_name": first.area_name,
                "billing_month": billing_month,
                "first_reading_time": first.reading_time,
                "last_reading_time": last.reading_time,
                "start_total_energy": start_total,
                "end_total_energy": end_total,
                "total_kwh": total_kwh,
                "status": STATUS_DRAFT,
                "approved_at": None,
                "reject_reason": None,
                "calc_status": status,
                "factor_source": None,
                "factor_year": None,
                "factor_unit": None,
                "activity_amount": total_kwh,
                "activity_unit": "kWh",
                "computed_co2e": None,
                "computation_note": None,
                "aggregation_note": note,
            }
            if status == "ready":
                payload.update(
                    await _build_scope2_snapshot_payload(
                        m.Scope2MeterAggregate,
                        payload,
                        scope2_meter_aggregate_service.repository.session,
                        source_kind="meter_aggregate",
                    )
                )
            else:
                payload["computation_note"] = note or "聚合结果不可核算，请先修复采样数据。"
            created.append(await scope2_meter_aggregate_service.create(payload, auto_commit=False))

        await db_session.commit()
        return created

    @post("/api/carbon/scope2-meter-aggregate/rebuild", guards=[requires_superuser])
    async def rebuild_scope2_meter_aggregate(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        billing_month = str(data.get("billing_month") or "").strip()
        if not billing_month:
            return Response(content={"code": 400, "msg": "billing_month 为必填，格式 YYYY-MM"}, status_code=400)
        try:
            validate_billing_month(billing_month)
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        area_id = str(data.get("area_id")).strip() if data.get("area_id") not in (None, "") else None
        rows = await self._rebuild_scope2_meter_aggregates(db_session, scope2_meter_aggregate_service, billing_month, area_id)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.scope2-meter-aggregate.rebuild",
            record_type="Scope2MeterAggregate",
            record_id=billing_month,
            details={
                "billing_month": billing_month,
                "area_id": area_id,
                "rebuilt_count": len(rows),
                "ready_count": sum(1 for row in rows if row.calc_status == "ready"),
                "invalid_count": sum(1 for row in rows if row.calc_status != "ready"),
            },
        )
        return Response(
            content={
                "code": 200,
                "msg": "重建成功",
                "data": {
                    "billing_month": billing_month,
                    "rebuilt_count": len(rows),
                    "ready_count": sum(1 for row in rows if row.calc_status == "ready"),
                    "invalid_count": sum(1 for row in rows if row.calc_status != "ready"),
                },
            }
        )

    @delete("/api/carbon/scope2-meter-aggregate/{record_id:int}", status_code=200)
    async def delete_scope2_meter_aggregate(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_meter_aggregate_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope2_meter_aggregate_service.delete(record_id, auto_commit=True)
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.delete",
            record_type="Scope2MeterAggregate",
            record_id=record_id,
            details={"status_before": obj.status},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope2-meter-aggregate/{record_id:int}/submit")
    async def submit_scope2_meter_aggregate(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_meter_aggregate_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            try:
                obj = await _refresh_scope2_snapshot(obj, scope2_meter_aggregate_service, source_kind="meter_aggregate")
            except CarbonValidationError as e:
                return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        if obj.calc_status != "ready":
            return Response(content={"code": 400, "msg": obj.aggregation_note or "聚合结果不可核算，请先修复采样数据。"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前聚合记录尚未形成有效核算结果"}, status_code=400)
        await scope2_meter_aggregate_service.update(item_id=record_id, data={"status": STATUS_PENDING}, auto_commit=True)
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2MeterAggregate", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.submit",
            record_type="Scope2MeterAggregate",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_PENDING},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope2-meter-aggregate/{record_id:int}/approve", guards=[requires_superuser])
    async def approve_scope2_meter_aggregate(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await scope2_meter_aggregate_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            try:
                obj = await _refresh_scope2_snapshot(obj, scope2_meter_aggregate_service, source_kind="meter_aggregate")
            except CarbonValidationError as e:
                return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        if obj.calc_status != "ready":
            return Response(content={"code": 400, "msg": obj.aggregation_note or "聚合结果不可核算，请先修复采样数据。"}, status_code=400)
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前聚合记录尚未形成有效核算结果"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope2_meter_aggregate_service.update(item_id=record_id, data={"status": STATUS_APPROVED, "approved_at": now}, auto_commit=True)
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2MeterAggregate", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.approve",
            record_type="Scope2MeterAggregate",
            record_id=record_id,
            details={"status_before": obj.status, "status_after": STATUS_APPROVED},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope2-meter-aggregate/{record_id:int}/reject", guards=[requires_superuser])
    async def reject_scope2_meter_aggregate(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        audit_log_service: services.CarbonAuditLogService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        obj = await scope2_meter_aggregate_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可驳回"}, status_code=400)
        reason = (data.get("reason") or data.get("reject_reason") or "管理员驳回，请修改后重新提交")[:500]
        await scope2_meter_aggregate_service.update(item_id=record_id, data={"status": STATUS_REJECTED, "reject_reason": reason}, auto_commit=True)
        await self._create_audit_log(
            audit_log_service,
            {"record_type": "Scope2MeterAggregate", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        await self._log_carbon_security_event(
            security_audit_service,
            request,
            action="carbon.record.reject",
            record_type="Scope2MeterAggregate",
            record_id=record_id,
            comment=reason,
            details={"status_before": obj.status, "status_after": STATUS_REJECTED},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    @get("/api/carbon/scope2-records")
    async def list_scope2_records(
        self,
        db_session: AsyncSession,
        scope2_bill_service: services.Scope2ElectricityBillService,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        billing_month: str | None = None,
        source_kind: str | None = "meter_aggregate",
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        manual_total = 0
        manual_conditions = [m.Scope2ElectricityBill.status == status] if status else []
        if billing_month:
            manual_conditions.append(m.Scope2ElectricityBill.billing_month == billing_month)
        if source_kind in (None, "", "all", "manual_bill"):
            manual_total = int(
                (
                    await db_session.execute(
                        select(func.count()).select_from(m.Scope2ElectricityBill).where(*(manual_conditions or [text("1=1")]))
                    )
                ).scalar_one()
            )
            manual_rows = await scope2_bill_service.list(*(manual_conditions or []), LimitOffset(limit + offset, 0), OrderBy(m.Scope2ElectricityBill.id, "desc"))
        else:
            manual_rows = []

        aggregate_conditions = []
        if billing_month:
            aggregate_conditions.append(m.Scope2MeterAggregate.billing_month == billing_month)
        if status:
            aggregate_conditions.append(m.Scope2MeterAggregate.status == status)
        aggregate_total = 0
        if source_kind in (None, "", "all", "meter_aggregate"):
            aggregate_total = int(
                (
                    await db_session.execute(
                        select(func.count()).select_from(m.Scope2MeterAggregate).where(*(aggregate_conditions or [text("1=1")]))
                    )
                ).scalar_one()
            )
            aggregate_rows = await scope2_meter_aggregate_service.list(
                *(aggregate_conditions or []), LimitOffset(limit + offset, 0), OrderBy(m.Scope2MeterAggregate.id, "desc")
            )
        else:
            aggregate_rows = []

        records: list[dict[str, Any]] = []
        if source_kind in (None, "", "all", "manual_bill"):
            for row in manual_rows:
                records.append(
                    {
                        "record_type": "Scope2ElectricityBill",
                        "record_id": row.id,
                        "display_name": row.account_number,
                        **await _serialize_scope_record(row, scope2_bill_service.repository.session, source_kind="manual_bill"),
                    }
                )
        for row in aggregate_rows:
            records.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    **await _serialize_scope_record(row, scope2_meter_aggregate_service.repository.session, source_kind="meter_aggregate"),
                }
            )
        records.sort(key=lambda item: (str(item.get("billing_month") or ""), int(item.get("record_id") or 0)), reverse=True)
        limit_clamped = max(1, min(limit, 100))
        offset_clamped = max(0, offset)
        return Response(
            content=_paged_payload(
                records[offset_clamped : offset_clamped + limit_clamped],
                manual_total + aggregate_total,
                limit_clamped,
                offset_clamped,
            )
        )

    @get("/api/carbon/scope2-reconciliation")
    async def get_scope2_reconciliation(
        self,
        db_session: AsyncSession,
        billing_month: str,
    ) -> Response[dict]:
        try:
            validate_billing_month(billing_month)
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)

        bill_total = await db_session.scalar(
            select(func.coalesce(func.sum(m.Scope2ElectricityBill.total_kwh), 0)).where(m.Scope2ElectricityBill.billing_month == billing_month)
        )
        meter_total = await db_session.scalar(
            select(func.coalesce(func.sum(m.Scope2MeterAggregate.total_kwh), 0)).where(
                m.Scope2MeterAggregate.billing_month == billing_month,
                m.Scope2MeterAggregate.calc_status == "ready",
            )
        )
        missing_count = await db_session.scalar(
            select(func.count()).select_from(m.Scope2MeterAggregate).where(
                m.Scope2MeterAggregate.billing_month == billing_month,
                m.Scope2MeterAggregate.calc_status != "ready",
            )
        )
        bill_value = float(bill_total or 0)
        meter_value = float(meter_total or 0)
        diff = bill_value - meter_value
        diff_rate = round((diff / bill_value) * 100, 2) if bill_value else None
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "billing_month": billing_month,
                    "manual_bill_total_kwh": bill_value,
                    "meter_aggregate_total_kwh": meter_value,
                    "difference_kwh": diff,
                    "difference_rate": diff_rate,
                    "missing_meter_count": int(missing_count or 0),
                },
            }
        )

    @get("/api/data/in-money")
    async def list_in_money(
        self,
        in_money_service: services.InMoneyService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "add_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            in_money_service,
            m.InMoney,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["rkdbh", "gysmc", "gysbm", "wlbh", "wlms", "ckmc"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    @get("/api/data/out-money")
    async def list_out_money(
        self,
        out_money_service: services.OutMoneyService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "add_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            out_money_service,
            m.OutMoney,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["ckdbh", "xmmc", "wlbm", "wlms", "gysmc", "ckdd"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    # ---------- 数据管理：员工通勤 ----------
    @get("/api/data/employee-commute")
    async def list_employee_commute(
        self,
        employee_commute_service: services.EmployeeCommuteService,
        keyword: str | None = None,
        search: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        """员工通勤列表（与原系统 EmployeeCommute 对应）。"""
        conditions = [m.EmployeeCommute.category == category] if category else []
        page = await _list_page(
            employee_commute_service,
            m.EmployeeCommute,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["name", "category"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/employee-commute", guards=[requires_superuser])
    async def create_employee_commute(
        self,
        request: Request[Any, Any, Any],
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        """新增员工通勤记录。"""
        # mileage / unit_consumption 若传入则要求非负
        try:
            if "mileage" in data and data["mileage"] is not None:
                validate_amount_non_negative(data["mileage"], "里程")
            if "unit_consumption" in data and data["unit_consumption"] is not None:
                validate_amount_non_negative(data["unit_consumption"], "单位油耗")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)

        payload = {k: v for k, v in data.items() if v is not None}
        obj = await employee_commute_service.create(payload, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.create",
            target_type="EmployeeCommute",
            target_id=obj.id,
            target_label=obj.name,
            details={"category": obj.category},
        )
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/data/employee-commute/{record_id:int}", guards=[requires_superuser])
    async def update_employee_commute(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(),
    ) -> Response[dict]:
        """更新员工通勤记录。"""
        obj = await employee_commute_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)

        try:
            if "mileage" in data and data["mileage"] is not None:
                validate_amount_non_negative(data["mileage"], "里程")
            if "unit_consumption" in data and data["unit_consumption"] is not None:
                validate_amount_non_negative(data["unit_consumption"], "单位油耗")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)

        await employee_commute_service.update(item_id=record_id, data=data, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.update",
            target_type="EmployeeCommute",
            target_id=record_id,
            target_label=obj.name,
            details={"updated_fields": sorted(data.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/employee-commute/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_employee_commute(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        """删除员工通勤记录。"""
        obj = await employee_commute_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await employee_commute_service.delete(record_id, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.delete",
            target_type="EmployeeCommute",
            target_id=record_id,
            target_label=obj.name,
            details={"category": obj.category},
        )
        return Response(content={"code": 200, "msg": "已删除"})
