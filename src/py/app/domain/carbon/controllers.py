"""碳管理相关接口控制器（Litestar Controller）。

目标：
- 尽量与原 Django `dataapp.urls` / `views` 提供的 `/api/...` 路径兼容
- 逐步使用 SQLAlchemy / 视图查询来实现相同的统计与查询逻辑
"""

import datetime
import re
from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter
from dateutil.relativedelta import MO, relativedelta
from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.carbon.deps import (
    provide_alarm_event_service,
    provide_ammeter_index_value_service,
    provide_api_result_key_mapping_service,
    provide_carbon_audit_log_service,
    provide_emission_factor_service,
    provide_employee_commute_service,
    provide_energy_storage_value_service,
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
    provide_scope3_third_party_transport_service,
    provide_scope3_waste_disposal_service,
    provide_vedio_alarm_event_service,
    provide_video_monitor_service,
    provide_warning_rule_service,
)

from . import services
from .utils import _CKYQZMJ as CKYQZMJ

# 排放因子与常量（根据 Django views.py 同步）
from .utils import GF_CJPL_PFYZ, YD_CPFL_PFYZ, calc_day_ygtq_cpfl
from .validation import (
    CarbonValidationError,
    validate_amount_non_negative,
    validate_billing_month,
    validate_consumption,
    validate_date_not_future,
    validate_period_start_end,
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

    @get(path="/api/page1/ckxxgk", exclude_from_auth=True)
    async def get_page1_ck_information(self, enterprise_info_service: services.EnterpriseInfoService) -> Response[dict]:
        db_obj = await enterprise_info_service.get_one_or_none()
        data = db_obj.to_dict() if db_obj else {}
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/jcdwzxtj", exclude_from_auth=True)
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

    @get(path="/api/page3/ckqy/ljydtj", exclude_from_auth=True)
    async def get_page3_yd_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_yd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page3/gfqy/ljfdtj", exclude_from_auth=True)
    async def get_page3_gffd_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_gffd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page3/cdzqy/ljydtj", exclude_from_auth=True)
    async def get_page3_cdz_statis(self, db_session: AsyncSession) -> Response[dict]:
        data = await self._get_common_cdzyd_statis(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/ydfdzl/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page1/ydfdzl/qypx/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page3/ydfdtj/chart/{stat_type:str}", exclude_from_auth=True)
    async def get_page3_fdyd_statis_for_chart(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        rets = await self._get_common_fdyd_statis_for_chart(db_session, stat_type)
        mapping = await self._get_api_result_key_mapping(db_session)
        new_rets = [{mapping.get(k, k): v for k, v in r.items()} for r in rets]
        return Response(content={"code": 200, "msg": "获取成功", "data": new_rets})

    @get(path="/api/hwpm/show/num", exclude_from_auth=True)
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

    @get(path="/api/page4/tpfltj", exclude_from_auth=True)
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

    @get(path="/api/page4/tpflzl/{stat_type:str}", exclude_from_auth=True)
    async def get_page4_cpf_zl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        data = await self._get_common_cpf_zl(db_session, stat_type)
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/ydfdtj/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page1/tpfgl/{stat_type:str}", exclude_from_auth=True)
    async def get_page1_tpfgl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        return await self._get_page1_cpf_gl_impl(db_session, stat_type)

    @get(path="/api/page1/cpfgl/{stat_type:str}", exclude_from_auth=True)
    async def get_page1_cpfgl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        return await self._get_page1_cpf_gl_impl(db_session, stat_type)

    @get(path="/api/page4/tpfl/ckqypx/{stat_type:str}", exclude_from_auth=True)
    async def get_page4_cpfl_qy(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        yj_table = f"yj_area_{stat_type}_sum_view"
        today = datetime.date.today()
        where = f"day='{today}'" if stat_type == "day" else (f"week='{today - relativedelta(weekday=MO(-1))}'" if stat_type == "week" else (f"month='{today.replace(day=1)}'" if stat_type == "month" else f"year={today.year}"))
        sql = f"select area_id, area_name, zygdn from {yj_table} where {where} order by zygdn desc"
        res = await db_session.execute(text(sql))
        rets = [{"area_id": r[0], "area_name": r[1], "zygdn": r[2], "cpfl": round(float(r[2]) * YD_CPFL_PFYZ, 3) if r[2] else 0.0} for r in res.fetchall() if r[0] != "29710"]
        rets.sort(key=lambda x: x["cpfl"], reverse=True)
        return Response(content={"code": 200, "msg": "获取成功", "data": rets})

    @get(path="/api/page4/tpfl/year", exclude_from_auth=True)
    async def get_page4_year_cpfl(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text(f"select zygdn, zygdn_dif from yj_year_sum_view where year={datetime.date.today().year}"))
        r = res.fetchone()
        now_cpfl = round(float(r[0]) * YD_CPFL_PFYZ, 3) if r and r[0] is not None else 0.0
        diff = round(float(r[1]) * YD_CPFL_PFYZ, 3) if r and r[1] is not None else 0.0
        last_cpfl = round(now_cpfl - diff, 3)
        ratio = round(diff * 100 / last_cpfl) if last_cpfl > 0 else 0
        return Response(content={"code": 200, "msg": "获取成功", "data": {"year_cpfl": now_cpfl, "year_cpfl_bh": ratio, "last_year_cpfl": last_cpfl, "last_year_dif": diff}})

    @get(path="/api/page4/tpfltj/chart/{stat_type:str}", exclude_from_auth=True)
    async def get_page4_pfl_statis_for_chart(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        rets = await self._get_common_fdyd_statis_for_chart(db_session, stat_type)
        mapping = await self._get_api_result_key_mapping(db_session)
        new_rets = []
        for r in rets:
            yd_cpf = round(float(r["ydl"]) * YD_CPFL_PFYZ, 3) if r["ydl"] else 0.0
            gf_cjp = round(float(r["fdl"]) * GF_CJPL_PFYZ, 3) if r["fdl"] else 0.0
            new_rets.append({mapping.get("dt", "dt"): r["dt"], mapping.get("human_dt", "human_dt"): r["human_dt"], mapping.get("yd_cpf", "yd_cpf"): yd_cpf, mapping.get("gf_cjp", "gf_cjp"): gf_cjp, mapping.get("jpf", "jpf"): round(yd_cpf - gf_cjp, 3)})
        return Response(content={"code": 200, "msg": "获取成功", "data": new_rets})

    @get(path="/api/page3/zjyj", exclude_from_auth=True)
    async def get_page3_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), case when event_type=1 then '设备故障' when event_type=2 then '用电异常' when event_type=3 then '发电异常' else '碳排放异常' end, to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type in (1,2,3) and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page3/latestyj", exclude_from_auth=True)
    async def get_page3_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), case when event_type=1 then '设备故障' when event_type=2 then '用电异常' when event_type=3 then '发电异常' else '碳排放异常' end, to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type in (1,2,3) and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/zjyj", exclude_from_auth=True)
    async def get_page4_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), '碳排放异常', to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type = 4 and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/latestyj", exclude_from_auth=True)
    async def get_page4_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        sql = "select id, COALESCE(name, '整个仓库'), '碳排放异常', to_char(event_time,'YYYY-MM-DD HH24:MI:SS'), event_desc, case when is_handle then '已处理' else '未处理' end from alarm_event_view where event_type = 4 and is_handle = false order by event_time desc limit 10"
        res = await db_session.execute(text(sql))
        headers = ["id", "区域名称", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page3/yjtj/qypx/{stat_type:str}", exclude_from_auth=True)
    async def get_page3_yjtj_2(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        today = datetime.date.today()
        dt = today if stat_type == "day" else (today - datetime.timedelta(days=today.weekday()))
        sql = f"select COALESCE(sector_id, 'P0'), COALESCE(name, '整个仓库'), count(*) as count from alarm_event_view where {stat_type}='{dt}' and event_type in (2,3) and is_handle = false group by sector_id, name order by count desc"
        res = await db_session.execute(text(sql))
        headers = ["区域ID", "区域名", "预警次数"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page4/yjtj/qypx/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page3/yjtj/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page4/yjtj/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page4/qytpfyj/{stat_type:str}", exclude_from_auth=True)
    async def get_page4_qy_tpfyj(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        """碳能协同：各区域碳排放预警"""
        dt = self._dt_for_stat_type(stat_type)
        sql = f"""select case when sector_id is null then 'P0' else sector_id end, case when sector_id is null then '整个仓库' else name end, event_desc
            from alarm_event_view where event_type=4 and {stat_type}='{dt}' and is_handle = false order by event_time desc limit 10"""
        res = await db_session.execute(text(sql))
        header = ["区域ID", "区域名称", "事件描述"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(header, r)) for r in res.fetchall()]})

    @get(path="/api/page4/cktpfqd/chart/{stat_type:str}", exclude_from_auth=True)
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

    @get(path="/api/page1/yjzl/{stat_type:str}", exclude_from_auth=True)
    async def get_page1_yjzl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        dt = self._dt_for_stat_type(stat_type)
        res_total = await db_session.execute(text(f"select count(1) from alarm_event_view where {stat_type}='{dt}' and is_handle = false"))
        total = res_total.scalar() or 0
        return Response(content={"code": 200, "msg": "获取成功", "data": {"total_alarm_count": total, "qyyj": [], "lxyj": []}})

    @get(path="/api/page1/zjyj", exclude_from_auth=True)
    async def get_page1_zjyj(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        rows = await alarm_event_service.list(limit=5, order_by="event_time desc")
        data = [{"desc": r.event_desc, "time": r.event_time.strftime("%Y-%m-%d %H:%M:%S") if r.event_time else "", "type": r.event_type} for r in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page1/latestwj", exclude_from_auth=True)
    async def get_page1_latestwj(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        rows = await alarm_event_service.list(limit=5, order_by="event_time desc")
        data = [{"desc": r.event_desc, "time": r.event_time.strftime("%Y-%m-%d %H:%M:%S") if r.event_time else "", "type": r.event_type} for r in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})


class CarbonMapController(Controller):
    tags = ["CarbonMap"]
    signature_types = [Response]
    dependencies = {"monitor_sector_service": provide_monitor_sector_service}

    @get(path="/api/map/popup/{area_id:str}", exclude_from_auth=True)
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

    @get(path="/api/map/monitorSector/list", exclude_from_auth=True)
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
    }

    @post(path="/api/zjyj/handleEvents", exclude_from_auth=True)
    async def handle_events_zjyj(self, alarm_event_service: services.AlarmEventService, data: dict) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleEvents", exclude_from_auth=True)
    async def handle_events(self, alarm_event_service: services.AlarmEventService, data: dict) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllEvents", exclude_from_auth=True)
    async def handle_all_events_zjyj(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle == False)
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllEvents", exclude_from_auth=True)
    async def handle_all_events(self, alarm_event_service: services.AlarmEventService) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle == False)
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleVideoEvents", exclude_from_auth=True)
    async def handle_video_events_zjyj(self, vedio_alarm_event_service: services.VedioAlarmEventService, data: dict) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleVideoEvents", exclude_from_auth=True)
    async def handle_video_events(self, vedio_alarm_event_service: services.VedioAlarmEventService, data: dict) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": id, "is_handle": True} for id in ids])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllVideoEvents", exclude_from_auth=True)
    async def handle_all_video_events_zjyj(self, vedio_alarm_event_service: services.VedioAlarmEventService) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle == False)
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllVideoEvents", exclude_from_auth=True)
    async def handle_all_video_events(self, vedio_alarm_event_service: services.VedioAlarmEventService) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle == False)
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/pullVedioAlarmEvent", exclude_from_auth=True)
    async def pull_vedio_alarm_event(
        self,
        data: dict,
        video_monitor_service: services.VideoMonitorService,
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
        return Response(content={
            "code": 200,
            "msg": "拉取报警事件成功",
            "data": {"totalCount": len(rets), "alarmEvents": [_serialize(r) for r in rets]},
        })


class CarbonVideoController(Controller):
    tags = ["CarbonVideo"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]
    dependencies = {
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "video_monitor_service": provide_video_monitor_service,
    }

    @get(path="/api/page2/yjzl/{stat_type:str}", exclude_from_auth=True)
    async def get_page2_yjzl(self, db_session: AsyncSession, stat_type: str = "day") -> Response[dict]:
        today = datetime.date.today()
        dt = today if stat_type == "day" else (today - datetime.timedelta(days=today.weekday()))
        res = await db_session.execute(text(f"select count(1) from vedio_alarm_event_view where {stat_type}='{dt}' and is_handle = false"))
        return Response(content={"code": 200, "msg": "获取成功", "data": {"total_alarm_count": res.scalar(), "qyyj": [], "lxyj": []}})

    @get(path="/api/page2/spgl", exclude_from_auth=True)
    async def get_page2_spgl(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select status, count(*) from dataapp_videomonitor group by status"))
        mapping = {0: "在线", 1: "故障"}
        data = [{"id": i+1, "name": mapping.get(r[0], "未知"), "num": r[1]} for i, r in enumerate(res.fetchall())]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page2/spjk", exclude_from_auth=True)
    async def get_page2_spjk(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select location, status, f_area from dataapp_videomonitor"))
        mapping = {0: "在线", 1: "故障"}
        data = [{"location": r[0], "status": r[1], "status_name": mapping.get(r[1]), "f_area": r[2]} for r in res.fetchall()]
        return Response(content={"code": 200, "msg": "获取成功", "data": data})

    @get(path="/api/page2/zjyj", exclude_from_auth=True)
    async def get_page2_zjyj(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select id, location, case when event_type=1 then '未佩戴安全帽' when event_type=2 then '烟火' when event_type=3 then '火点' else '区域入侵' end, to_char(event_time,'YYYY-MM-DD HH24:MI'), event_desc, case when is_handle then '已处理' else '未处理' end from vedio_alarm_event_view where is_handle=false order by event_time desc limit 10"))
        headers = ["id", "监控位置", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/page2/latestyj", exclude_from_auth=True)
    async def get_page2_latestyj(self, db_session: AsyncSession) -> Response[dict]:
        res = await db_session.execute(text("select id, location, case when event_type=1 then '未佩戴安全帽' when event_type=2 then '烟火' when event_type=3 then '火点' else '区域入侵' end, to_char(event_time,'YYYY-MM-DD HH24:MI'), event_desc, case when is_handle then '已处理' else '未处理' end from vedio_alarm_event_view where is_handle=false order by event_time desc limit 10"))
        headers = ["id", "监控位置", "事件类型", "发生时间", "事件描述", "事件状态"]
        return Response(content={"code": 200, "msg": "获取成功", "data": [dict(zip(headers, r)) for r in res.fetchall()]})

    @get(path="/api/map/vedio/popup/{vid:int}", exclude_from_auth=True)
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

    @get(path="/api/map/videos", exclude_from_auth=True)
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

    @get(path="/api/page3/cnsy", exclude_from_auth=True)
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
    limit_clamped = max(1, min(limit, 100))
    offset_clamped = max(0, offset)
    filters: list[Any] = [LimitOffset(limit_clamped, offset_clamped)]
    order = "asc" if sort_order == "asc" else "desc"
    if sort_field and hasattr(model, sort_field):
        filters.append(OrderBy(getattr(model, sort_field), order))
    search_value = (search or keyword or "").strip()
    if search_value and search_fields:
        filters.append(SearchFilter(field_name=set(search_fields), value=search_value, ignore_case=True))
    rows, total = await service.list_and_count(*(conditions or []), *filters)
    return _paged_payload([model_to_dict(row) for row in rows], total, limit_clamped, offset_clamped)


class CarbonCRUDController(Controller):
    """Scope 1/2/3 碳数据 CRUD 与审核（参考 xtck_deploy 与 PRD 5）。"""
    tags = ["CarbonCRUD"]
    signature_types = [Response]
    dependencies = {
        "scope1_mobile_service": provide_scope1_mobile_combustion_service,
        "scope1_stationary_service": provide_scope1_stationary_combustion_service,
        "scope1_refrigerant_service": provide_scope1_refrigerant_leak_service,
        "scope2_bill_service": provide_scope2_electricity_bill_service,
        "scope3_waste_service": provide_scope3_waste_disposal_service,
        "scope3_transport_service": provide_scope3_third_party_transport_service,
        "emission_factor_service": provide_emission_factor_service,
        "employee_commute_service": provide_employee_commute_service,
        "iot_telemetry_service": provide_iot_telemetry_service,
        "audit_log_service": provide_carbon_audit_log_service,
        "monitor_sector_service": provide_monitor_sector_service,
        "monitor_sector_photo_service": provide_monitor_sector_photo_service,
        "monitor_equipment_service": provide_monitor_equipment_service,
        "video_monitor_service": provide_video_monitor_service,
        "warning_rule_service": provide_warning_rule_service,
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "api_result_key_mapping_service": provide_api_result_key_mapping_service,
        "energy_storage_value_service": provide_energy_storage_value_service,
        "ammeter_index_value_service": provide_ammeter_index_value_service,
        "in_money_service": provide_in_money_service,
        "out_money_service": provide_out_money_service,
    }

    async def _safe_create_audit_log(
        self,
        audit_log_service: services.CarbonAuditLogService,
        data: dict[str, Any],
    ) -> None:
        """创建审核日志的安全包装，避免因审计表问题导致业务接口 500。

        当前审计表（dataapp_auditlog）可能不存在或结构与模型有差异，
        直接 create() 会导致 session PendingRollbackError 传播到主业务。
        这里先检查表是否存在，不存在则直接跳过。
        """
        try:
            # 尝试写入审计日志；如果表不存在或字段不匹配，捕获后 rollback session
            await audit_log_service.create(data, auto_commit=True)
        except Exception:
            # 表不存在 / 字段不匹配时需要显式 rollback，避免 session 处于 broken 状态
            try:
                session = audit_log_service.repository.session
                await session.rollback()
            except Exception:
                pass

    # ---------- Scope1 移动源 ----------
    @get("/api/carbon/scope1-mobile-combustion", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/scope1-mobile-combustion/{record_id:int}", exclude_from_auth=True)
    async def get_scope1_mobile(
        self, record_id: int, scope1_mobile_service: services.Scope1MobileCombustionService
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope1-mobile-combustion", exclude_from_auth=True)
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope1-mobile-combustion/{record_id:int}", exclude_from_auth=True)
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
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope1-mobile-combustion/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope1_mobile(
        self, record_id: int, scope1_mobile_service: services.Scope1MobileCombustionService
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        # 按照内置 UserService 的用法，delete 期望传入主键 ID
        await scope1_mobile_service.delete(record_id)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope1_mobile(
        self,
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope1_mobile_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope1_mobile(
        self,
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_mobile_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        # 数据库字段为 TIMESTAMP WITHOUT TIME ZONE，这里去掉 tzinfo，避免 asyncpg 报错
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_mobile_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-mobile-combustion/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope1_mobile(
        self,
        record_id: int,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1MobileCombustion", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 固定源 ----------
    @get("/api/carbon/scope1-stationary-combustion", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/scope1-stationary-combustion/{record_id:int}", exclude_from_auth=True)
    async def get_scope1_stationary(
        self, record_id: int, scope1_stationary_service: services.Scope1StationaryCombustionService
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope1-stationary-combustion", exclude_from_auth=True)
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope1-stationary-combustion/{record_id:int}", exclude_from_auth=True)
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
        await scope1_stationary_service.update(item_id=record_id, data=data, auto_commit=True)
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope1-stationary-combustion/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope1_stationary(
        self, record_id: int, scope1_stationary_service: services.Scope1StationaryCombustionService
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope1_stationary_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope1_stationary(
        self,
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope1_stationary_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope1_stationary(
        self,
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_stationary_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_stationary_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-stationary-combustion/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope1_stationary(
        self,
        record_id: int,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1StationaryCombustion", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 逸散（制冷剂）完整 CRUD + 审核 ----------
    @get("/api/carbon/scope1-refrigerant-leak/{record_id:int}", exclude_from_auth=True)
    async def get_scope1_refrigerant(
        self, record_id: int, scope1_refrigerant_service: services.Scope1RefrigerantLeakService
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope1-refrigerant-leak", exclude_from_auth=True)
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope1-refrigerant-leak/{record_id:int}", exclude_from_auth=True)
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
        await scope1_refrigerant_service.update(item_id=record_id, data=data, auto_commit=True)
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope1-refrigerant-leak/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope1_refrigerant(
        self, record_id: int, scope1_refrigerant_service: services.Scope1RefrigerantLeakService
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope1_refrigerant_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope1_refrigerant(
        self,
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope1_refrigerant_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope1_refrigerant(
        self,
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope1_refrigerant_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope1_refrigerant_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope1-refrigerant-leak/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope1_refrigerant(
        self,
        record_id: int,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope1RefrigerantLeak", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope2 电费账单 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope2-electricity-bill/{record_id:int}", exclude_from_auth=True)
    async def get_scope2_bill(
        self, record_id: int, scope2_bill_service: services.Scope2ElectricityBillService
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope2-electricity-bill", exclude_from_auth=True)
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
        obj = await scope2_bill_service.create(payload, auto_commit=True)
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope2-electricity-bill/{record_id:int}", exclude_from_auth=True)
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
        await scope2_bill_service.update(item_id=record_id, data=data, auto_commit=True)
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope2-electricity-bill/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope2_bill(
        self, record_id: int, scope2_bill_service: services.Scope2ElectricityBillService
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope2_bill_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope2_bill(
        self,
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope2_bill_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope2_bill(
        self,
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope2_bill_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope2_bill_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope2-electricity-bill/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope2_bill(
        self,
        record_id: int,
        scope2_bill_service: services.Scope2ElectricityBillService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope2ElectricityBill", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope3 废弃物 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope3-waste-disposal/{record_id:int}", exclude_from_auth=True)
    async def get_scope3_waste(
        self, record_id: int, scope3_waste_service: services.Scope3WasteDisposalService
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope3-waste-disposal", exclude_from_auth=True)
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope3-waste-disposal/{record_id:int}", exclude_from_auth=True)
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
        await scope3_waste_service.update(item_id=record_id, data=data, auto_commit=True)
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope3-waste-disposal/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope3_waste(
        self, record_id: int, scope3_waste_service: services.Scope3WasteDisposalService
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope3_waste_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope3_waste(
        self,
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope3_waste_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope3_waste(
        self,
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope3_waste_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope3_waste_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope3-waste-disposal/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope3_waste(
        self,
        record_id: int,
        scope3_waste_service: services.Scope3WasteDisposalService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3WasteDisposal", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope3 外购运输 完整 CRUD + 审核 ----------
    @get("/api/carbon/scope3-third-party-transport/{record_id:int}", exclude_from_auth=True)
    async def get_scope3_transport(
        self, record_id: int, scope3_transport_service: services.Scope3ThirdPartyTransportService
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "data": model_to_dict(obj)})

    @post("/api/carbon/scope3-third-party-transport", exclude_from_auth=True)
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/carbon/scope3-third-party-transport/{record_id:int}", exclude_from_auth=True)
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
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/carbon/scope3-third-party-transport/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_scope3_transport(
        self, record_id: int, scope3_transport_service: services.Scope3ThirdPartyTransportService
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可删除"}, status_code=400)
        await scope3_transport_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/submit", exclude_from_auth=True)
    async def submit_scope3_transport(
        self,
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_DRAFT:
            return Response(content={"code": 400, "msg": "仅草稿可提交"}, status_code=400)
        await scope3_transport_service.update(
            item_id=record_id,
            data={"status": STATUS_PENDING},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_SUBMIT, "comment": "提交审核"},
        )
        return Response(content={"code": 200, "msg": "已提交审核"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/approve", exclude_from_auth=True)
    async def approve_scope3_transport(
        self,
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
    ) -> Response[dict]:
        obj = await scope3_transport_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.status != STATUS_PENDING:
            return Response(content={"code": 400, "msg": "仅待审核可通过"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope3_transport_service.update(
            item_id=record_id,
            data={"status": STATUS_APPROVED, "approved_at": now},
            auto_commit=True,
        )
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_APPROVE, "comment": "审核通过"},
        )
        return Response(content={"code": 200, "msg": "已通过"})

    @post("/api/carbon/scope3-third-party-transport/{record_id:int}/reject", exclude_from_auth=True)
    async def reject_scope3_transport(
        self,
        record_id: int,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        audit_log_service: services.CarbonAuditLogService,
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
        await self._safe_create_audit_log(
            audit_log_service,
            {"record_type": "Scope3ThirdPartyTransport", "record_id": record_id, "action": AUDIT_ACTION_REJECT, "comment": reason},
        )
        return Response(content={"code": 200, "msg": "已驳回"})

    # ---------- Scope1 逸散 / Scope2 / Scope3：列表 + 待审核汇总 ----------
    @get("/api/carbon/scope1-refrigerant-leak", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/scope2-electricity-bill", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/scope3-waste-disposal", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/scope3-third-party-transport", exclude_from_auth=True)
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
        return Response(content=page)

    @get("/api/carbon/emission-factors", exclude_from_auth=True)
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

    @get("/api/carbon/factor-library/overview", exclude_from_auth=True)
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

    @get("/api/carbon/factor-library/records", exclude_from_auth=True)
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

    @get("/api/carbon/factor-library/records/{record_id:int}", exclude_from_auth=True)
    async def get_factor_library_record(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        item = await db_session.get(m.CarbonFactorRawRecord, record_id)
        if item is None:
            return Response(content={"code": 404, "msg": "记录不存在", "data": None}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": _augment_raw_factor_record_dict(model_to_dict(item))})

    @get("/api/carbon/factor-library/categories", exclude_from_auth=True)
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

    @get("/api/carbon/factor-library/category-tree", exclude_from_auth=True)
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

    @get("/api/carbon/iot-telemetry", exclude_from_auth=True)
    async def list_iot_telemetry(
        self,
        db_session: AsyncSession,
        site_id: str | None = None,
        device_id: str | None = None,
        limit: int = 200,
    ) -> Response[dict]:
        """IoT 时序数据简单列表查询（主要用于前端检索和排查）。"""
        filters = []
        model = m.IotTelemetry
        if site_id:
            filters.append(model.site_id == site_id)
        if device_id:
            filters.append(model.device_id == device_id)
        limit_clamped = max(10, min(limit, 1000))
        stmt = select(model).order_by(model.reading_time.desc()).limit(limit_clamped)
        if filters:
            stmt = stmt.where(*filters)
        items = (await db_session.execute(stmt)).scalars().all()
        return Response(content={"code": 200, "data": [model_to_dict(i) for i in items]})

    @get("/api/carbon/audit-logs", exclude_from_auth=True)
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

    @get("/api/carbon/pending", exclude_from_auth=True)
    async def list_pending(
        self,
        scope1_mobile_service: services.Scope1MobileCombustionService,
        scope1_stationary_service: services.Scope1StationaryCombustionService,
        scope1_refrigerant_service: services.Scope1RefrigerantLeakService,
        scope2_bill_service: services.Scope2ElectricityBillService,
        scope3_waste_service: services.Scope3WasteDisposalService,
        scope3_transport_service: services.Scope3ThirdPartyTransportService,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        """待审核列表：汇总所有类型中 status=pending 的记录（审核工作台用）。"""
        out: list[dict] = []
        for name, svc, model in [
            ("Scope1MobileCombustion", scope1_mobile_service, m.Scope1MobileCombustion),
            ("Scope1StationaryCombustion", scope1_stationary_service, m.Scope1StationaryCombustion),
            ("Scope1RefrigerantLeak", scope1_refrigerant_service, m.Scope1RefrigerantLeak),
            ("Scope2ElectricityBill", scope2_bill_service, m.Scope2ElectricityBill),
            ("Scope3WasteDisposal", scope3_waste_service, m.Scope3WasteDisposal),
            ("Scope3ThirdPartyTransport", scope3_transport_service, m.Scope3ThirdPartyTransport),
        ]:
            items = await svc.list(model.status == STATUS_PENDING, LimitOffset(limit + offset, 0), OrderBy(model.id, "desc"))
            for i in items:
                out.append({"record_type": name, "record_id": i.id, **model_to_dict(i)})
        out.sort(key=lambda row: int(row.get("record_id") or 0), reverse=True)
        limit_clamped = max(1, min(limit, 100))
        offset_clamped = max(0, offset)
        return Response(content=_paged_payload(out[offset_clamped : offset_clamped + limit_clamped], len(out), limit_clamped, offset_clamped))

    # ---------- 数据管理: 区域 / 终端 / 视频 / 规则配置 ----------
    @get("/api/data/monitor-sectors", exclude_from_auth=True)
    async def list_monitor_sectors(
        self,
        db_session: AsyncSession,
        monitor_sector_service: services.MonitorSectorService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            monitor_sector_service,
            m.MonitorSector,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "area", "description"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        sector_ids = [row["id"] for row in page["items"] if row.get("id") is not None]
        if sector_ids:
            photos = (
                await db_session.execute(select(m.MonitorSectorPhoto).where(m.MonitorSectorPhoto.sector_id.in_(sector_ids)).order_by(m.MonitorSectorPhoto.id.desc()))
            ).scalars().all()
            photos_by_sector: dict[int, list[dict[str, Any]]] = {}
            for photo in photos:
                if photo.sector_id is not None:
                    photos_by_sector.setdefault(photo.sector_id, []).append(model_to_dict(photo))
            equipment_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.sector_id, func.count()).where(m.MonitorEquipment.sector_id.in_(sector_ids)).group_by(m.MonitorEquipment.sector_id)
                    )
                ).all()
            )
            for row in page["items"]:
                sector_id = row.get("id")
                row["photos"] = photos_by_sector.get(sector_id, [])
                row["equipment_count"] = equipment_counts.get(sector_id, 0)
        return Response(content=page)

    @post("/api/data/monitor-sectors", exclude_from_auth=True)
    async def create_monitor_sector(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = m.MonitorSector(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/monitor-sectors/{record_id:int}", exclude_from_auth=True)
    async def update_monitor_sector(self, db_session: AsyncSession, record_id: int, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = await db_session.get(m.MonitorSector, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/monitor-sectors/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_monitor_sector(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.MonitorSector, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/data/monitor-sector-photos", exclude_from_auth=True)
    async def create_monitor_sector_photo(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = m.MonitorSectorPhoto(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @delete("/api/data/monitor-sector-photos/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_monitor_sector_photo(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.MonitorSectorPhoto, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/monitor-equipments", exclude_from_auth=True)
    async def list_monitor_equipments(
        self,
        db_session: AsyncSession,
        monitor_equipment_service: services.MonitorEquipmentService,
        keyword: str | None = None,
        search: str | None = None,
        sector_id: int | None = None,
        category: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if sector_id:
            conditions.append(m.MonitorEquipment.sector_id == sector_id)
        if category is not None:
            conditions.append(m.MonitorEquipment.category == category)
        page = await _list_page(
            monitor_equipment_service,
            m.MonitorEquipment,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "code2", "supplier", "location"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        sector_ids = [row["sector_id"] for row in page["items"] if row.get("sector_id") is not None]
        if sector_ids:
            sectors = (await db_session.execute(select(m.MonitorSector.id, m.MonitorSector.name).where(m.MonitorSector.id.in_(sector_ids)))).all()
            sector_names = dict(sectors)
            for row in page["items"]:
                row["sector_name"] = sector_names.get(row.get("sector_id"))
        return Response(content=page)

    @post("/api/data/monitor-equipments", exclude_from_auth=True)
    async def create_monitor_equipment(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        _coerce_datetime_fields(data, ["install_time"])
        obj = m.MonitorEquipment(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/monitor-equipments/{record_id:int}", exclude_from_auth=True)
    async def update_monitor_equipment(self, db_session: AsyncSession, record_id: int, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = await db_session.get(m.MonitorEquipment, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        _coerce_datetime_fields(data, ["install_time"])
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/monitor-equipments/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_monitor_equipment(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.MonitorEquipment, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/video-monitors", exclude_from_auth=True)
    async def list_video_monitors(
        self,
        video_monitor_service: services.VideoMonitorService,
        keyword: str | None = None,
        search: str | None = None,
        status: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if status is not None:
            conditions.append(m.VideoMonitor.status == status)
        page = await _list_page(
            video_monitor_service,
            m.VideoMonitor,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["location", "f_area", "ip_address", "brand", "b_model"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/video-monitors", exclude_from_auth=True)
    async def create_video_monitor(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = m.VideoMonitor(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/video-monitors/{record_id:int}", exclude_from_auth=True)
    async def update_video_monitor(self, db_session: AsyncSession, record_id: int, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = await db_session.get(m.VideoMonitor, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/video-monitors/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_video_monitor(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.VideoMonitor, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/warning-rules", exclude_from_auth=True)
    async def list_warning_rules(
        self,
        warning_rule_service: services.WarningRuleService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.WarningRule.event_type == event_type)
        page = await _list_page(
            warning_rule_service,
            m.WarningRule,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["name", "description", "table_name"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/warning-rules", exclude_from_auth=True)
    async def create_warning_rule(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = m.WarningRule(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/warning-rules/{record_id:int}", exclude_from_auth=True)
    async def update_warning_rule(self, db_session: AsyncSession, record_id: int, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = await db_session.get(m.WarningRule, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/warning-rules/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_warning_rule(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.WarningRule, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/api-result-key-mappings", exclude_from_auth=True)
    async def list_api_result_key_mappings(
        self,
        api_result_key_mapping_service: services.ApiResultKeyMappingService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            api_result_key_mapping_service,
            m.ApiResultKeyMapping,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["key_name", "cn_name"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    @post("/api/data/api-result-key-mappings", exclude_from_auth=True)
    async def create_api_result_key_mapping(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = m.ApiResultKeyMapping(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/api-result-key-mappings/{record_id:int}", exclude_from_auth=True)
    async def update_api_result_key_mapping(self, db_session: AsyncSession, record_id: int, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = await db_session.get(m.ApiResultKeyMapping, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/api-result-key-mappings/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_api_result_key_mapping(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.ApiResultKeyMapping, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/energy-storage", exclude_from_auth=True)
    async def get_energy_storage_setting(self, db_session: AsyncSession) -> Response[dict]:
        obj = (await db_session.execute(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))).scalars().first()
        return Response(content={"code": 200, "msg": "获取成功", "data": model_to_dict(obj) if obj else None})

    @post("/api/data/energy-storage", exclude_from_auth=True)
    async def save_energy_storage_setting(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_BODY) -> Response[dict]:
        obj = (await db_session.execute(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))).scalars().first()
        if obj is None:
            obj = m.EnergyStorageValue(**_payload_without_none(data))
            db_session.add(obj)
        else:
            for field, value in _payload_without_none(data).items():
                setattr(obj, field, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "保存成功", "data": model_to_dict(obj)})

    # ---------- 数据管理: 事件处理 / 流水只读 ----------
    @get("/api/data/alarm-events", exclude_from_auth=True)
    async def list_alarm_events(
        self,
        alarm_event_service: services.AlarmEventService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        is_handle: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "event_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.AlarmEvent.event_type == event_type)
        if is_handle is not None:
            conditions.append(m.AlarmEvent.is_handle == is_handle)
        page = await _list_page(
            alarm_event_service,
            m.AlarmEvent,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["event_desc"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/alarm-events/{record_id:int}/handle", exclude_from_auth=True)
    async def handle_alarm_event(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.AlarmEvent, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        obj.is_handle = True
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已处理"})

    @post("/api/data/alarm-events/handle-batch", exclude_from_auth=True)
    async def handle_alarm_events_batch(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_OPTIONAL_BODY) -> Response[dict]:
        ids = data.get("ids") or []
        stmt = select(m.AlarmEvent).where(m.AlarmEvent.is_handle.is_(False))
        if ids:
            stmt = stmt.where(m.AlarmEvent.id.in_(ids))
        items = (await db_session.execute(stmt)).scalars().all()
        for item in items:
            item.is_handle = True
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已批量处理", "data": {"count": len(items)}})

    @get("/api/data/video-alarm-events", exclude_from_auth=True)
    async def list_video_alarm_events(
        self,
        vedio_alarm_event_service: services.VedioAlarmEventService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        is_handle: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "event_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.VedioAlarmEvent.event_type == event_type)
        if is_handle is not None:
            conditions.append(m.VedioAlarmEvent.is_handle == is_handle)
        page = await _list_page(
            vedio_alarm_event_service,
            m.VedioAlarmEvent,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["event_desc"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/video-alarm-events/{record_id:int}/handle", exclude_from_auth=True)
    async def handle_video_alarm_event(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.VedioAlarmEvent, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        obj.is_handle = True
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已处理"})

    @post("/api/data/video-alarm-events/handle-batch", exclude_from_auth=True)
    async def handle_video_alarm_events_batch(self, db_session: AsyncSession, data: dict[str, Any] = ADMIN_OPTIONAL_BODY) -> Response[dict]:
        ids = data.get("ids") or []
        stmt = select(m.VedioAlarmEvent).where(m.VedioAlarmEvent.is_handle.is_(False))
        if ids:
            stmt = stmt.where(m.VedioAlarmEvent.id.in_(ids))
        items = (await db_session.execute(stmt)).scalars().all()
        for item in items:
            item.is_handle = True
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已批量处理", "data": {"count": len(items)}})

    @get("/api/data/in-money", exclude_from_auth=True)
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

    @get("/api/data/out-money", exclude_from_auth=True)
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

    @get("/api/data/ammeter-values", exclude_from_auth=True)
    async def list_ammeter_values(
        self,
        ammeter_index_value_service: services.AmmeterIndexValueService,
        keyword: str | None = None,
        search: str | None = None,
        area_id: str | None = None,
        ammeter_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "reading_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if area_id:
            conditions.append(m.AmmeterIndexValue.area_id == area_id)
        if ammeter_id:
            conditions.append(m.AmmeterIndexValue.ammeter_id == ammeter_id)
        page = await _list_page(
            ammeter_index_value_service,
            m.AmmeterIndexValue,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["ammeter_id", "ammeter_name", "address", "area_name"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    # ---------- 数据管理：员工通勤 ----------
    @get("/api/data/employee-commute", exclude_from_auth=True)
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

    @post("/api/data/employee-commute", exclude_from_auth=True)
    async def create_employee_commute(
        self,
        employee_commute_service: services.EmployeeCommuteService,
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
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/data/employee-commute/{record_id:int}", exclude_from_auth=True)
    async def update_employee_commute(
        self,
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
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
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/employee-commute/{record_id:int}", exclude_from_auth=True, status_code=200)
    async def delete_employee_commute(
        self,
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
    ) -> Response[dict]:
        """删除员工通勤记录。"""
        obj = await employee_commute_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await employee_commute_service.delete(obj, auto_commit=True)
        return Response(content={"code": 200, "msg": "已删除"})
