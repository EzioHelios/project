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
from litestar.exceptions import ClientException
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select, text
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
from app.domain.carbon.real_company_package_importer import (
    import_real_company_package,
    list_real_company_package_summaries,
    resolve_real_company_package_dir,
    summarize_real_company_package,
)
from app.domain.energy.controllers._utils import ok_data

from . import services

# 排放因子与常量（根据 Django views.py 同步）
from .emission_calculator import compute_emission_result
from .utils import _CKYQZMJ as CKYQZMJ
from .utils import GF_CJPL_PFYZ, YD_CPFL_PFYZ, calc_day_ygtq_cpfl
from .validation import (
    CarbonValidationError,
    validate_amount_non_negative,
    validate_consumption,
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


class CarbonDataCollectionWorkbookController(Controller):
    tags = ["Carbon"]

    @get("/api/carbon/data-collection-workbooks/spec", guards=[requires_superuser])
    async def get_data_collection_workbook_spec(self) -> Response[dict]:
        from app.domain.carbon.data_collection_workbook import data_collection_workbook_spec

        return Response(content=ok_data(data_collection_workbook_spec()))

    @get("/api/carbon/data-collection-workbooks/template", guards=[requires_superuser])
    async def download_data_collection_workbook_template(self) -> Response[bytes]:
        from app.domain.carbon.data_collection_workbook import build_data_collection_template_bytes

        return Response(
            content=build_data_collection_template_bytes(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="energy-carbon-data-collection-template.xlsx"'},
        )

    @get("/api/carbon/real-company-packages", guards=[requires_superuser])
    async def list_real_company_packages(self) -> Response[dict]:
        packages = [_summary_payload(item) for item in list_real_company_package_summaries()]
        return Response(content=ok_data({"items": packages, "total": len(packages)}))

    @post("/api/carbon/real-company-packages/{enterprise_code:str}/import", guards=[requires_superuser])
    async def import_real_company_package_endpoint(
        self,
        db_session: AsyncSession,
        enterprise_code: str,
        data: dict | None = None,
    ) -> Response[dict]:
        dry_run = bool((data or {}).get("dry_run", False))
        try:
            package_dir = resolve_real_company_package_dir(enterprise_code)
            package_summary = summarize_real_company_package(package_dir)
            result = await import_real_company_package(db_session, package_dir, dry_run=dry_run)
        except ValueError as exc:
            raise ClientException(detail=str(exc), status_code=400) from exc

        return Response(
            content=ok_data(
                {
                    "enterprise_code": result.enterprise_code,
                    "enterprise_name": package_summary.enterprise_name,
                    "tenant_slug": result.tenant_slug,
                    "team_id": result.team_id,
                    "dry_run": result.dry_run,
                    "package_path": package_summary.package_path,
                    "imported": result.imported,
                    "skipped": result.skipped,
                    "source_missing_pages": result.source_missing_pages,
                    "dataset_rows": package_summary.dataset_rows,
                    "page_status_counts": package_summary.page_status_counts,
                    "missing_datasets": package_summary.missing_datasets,
                }
            )
        )

    @post("/api/carbon/data-collection-workbooks/preview", guards=[requires_superuser], status_code=200)
    async def preview_data_collection_workbook_endpoint(self, data: dict) -> Response[dict]:
        workbook_base64 = str(data.get("workbook_base64") or "")
        if not workbook_base64:
            raise ClientException(detail="缺少 workbook_base64", status_code=400)
        try:
            from app.domain.carbon.data_collection_workbook import preview_data_collection_workbook_base64

            preview = preview_data_collection_workbook_base64(workbook_base64)
        except ValueError as exc:
            raise ClientException(detail=str(exc), status_code=400) from exc

        return Response(content=ok_data(preview))

    @post("/api/carbon/data-collection-workbooks/import", guards=[requires_superuser])
    async def import_data_collection_workbook_endpoint(
        self,
        db_session: AsyncSession,
        data: dict,
    ) -> Response[dict]:
        workbook_base64 = str(data.get("workbook_base64") or "")
        dry_run = bool(data.get("dry_run", False))
        if not workbook_base64:
            raise ClientException(detail="缺少 workbook_base64", status_code=400)
        try:
            from app.domain.carbon.data_collection_workbook import import_data_collection_workbook_base64

            result = await import_data_collection_workbook_base64(
                db_session,
                workbook_base64,
                dry_run=dry_run,
            )
        except ValueError as exc:
            raise ClientException(detail=str(exc), status_code=400) from exc

        return Response(
            content=ok_data(
                {
                    "enterprise_code": result.enterprise_code,
                    "tenant_slug": result.tenant_slug,
                    "team_id": result.team_id,
                    "dry_run": result.dry_run,
                    "imported": result.imported,
                    "skipped": result.skipped,
                    "source_missing_pages": result.source_missing_pages,
                }
            )
        )


def _summary_payload(summary: object) -> dict:
    return {
        "enterprise_code": summary.enterprise_code,
        "enterprise_name": summary.enterprise_name,
        "tenant_slug": summary.tenant_slug,
        "package_path": summary.package_path,
        "dataset_rows": summary.dataset_rows,
        "page_status_counts": summary.page_status_counts,
        "missing_datasets": summary.missing_datasets,
    }


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
    missing_note = "未找到匹配的排放因子，当前记录无法形成稳定 CO2e 结果。"
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
        if str(record.treatment_method or "").startswith("unknown"):
            missing_note = "原始资料未提供废弃物处置方式或可追溯因子，当前记录无法形成稳定 CO2e 结果。"
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
            "computation_note": missing_note,
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
        if _scope2_snapshot_ready(record):
            data.update(_scope2_snapshot_fields(data, source_kind=source_kind or SOURCE_KIND_MANUAL_BILL))
        else:
            data.update(await _build_scope_record_computation(record, session, source_kind=source_kind or SOURCE_KIND_MANUAL_BILL))
        return data
    if isinstance(record, m.Scope2PurchasedEnergy):
        if _scope2_snapshot_ready(record):
            data.update(_scope2_snapshot_fields(data, source_kind=source_kind or "purchased_energy"))
        else:
            data.update(await _build_purchased_energy_snapshot_payload(data, session))
        return data
    if isinstance(record, m.Scope2MeterAggregate):
        if _scope2_snapshot_ready(record):
            data.update(_scope2_snapshot_fields(data, source_kind=source_kind or SOURCE_KIND_DERIVED))
        else:
            data.update(await _build_scope_record_computation(record, session, source_kind=source_kind or SOURCE_KIND_DERIVED))
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
        return "系统初始化"
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
