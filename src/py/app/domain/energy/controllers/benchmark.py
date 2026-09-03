from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.energy.policy_benchmark_sync import available_policy_sources, sync_policy_benchmark_library
from app.domain.energy.queries.benchmark import (
    METRICS,
    TARGET_TYPES,
    EnergyBenchmarkGenerateCommand,
    EnergyBenchmarkQuery,
    EnergyBenchmarkQueryService,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


PROFILE_FIELDS = {
    "name",
    "industry_name",
    "scenario",
    "library_type",
    "source_name",
    "source_url",
    "source_hash",
    "source_file_name",
    "standard_code",
    "version_status",
    "valid_from",
    "valid_to",
    "is_enabled",
    "remark",
}
ITEM_FIELDS = {
    "profile_id",
    "target_type",
    "target_code",
    "target_name",
    "metric_code",
    "metric_name",
    "benchmark_value",
    "unit",
    "standard_code",
    "source_url",
    "source_hash",
    "applicable_industry",
    "applicable_category",
    "applicable_condition",
    "metric_direction",
    "advanced_value",
    "saving_value",
    "access_value",
    "baseline_value",
    "advanced_level",
    "saving_level",
    "access_level",
    "standard_level",
    "version_status",
    "reference_standard",
    "excellent_value",
    "warning_threshold_pct",
    "severe_threshold_pct",
    "source_name",
    "confidence_level",
    "is_enabled",
    "remark",
}
BENCHMARK_BODY = Body()


class EnergyBenchmarkController(Controller):
    tags = ["Energy"]

    @get("/api/energy/benchmark/profiles")
    async def list_energy_benchmark_profiles(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        library_type: str | None = None,
        is_enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if keyword:
            conditions.append(
                (m.EnergyBenchmarkProfile.name.ilike(f"%{keyword.strip()}%"))
                | (m.EnergyBenchmarkProfile.industry_name.ilike(f"%{keyword.strip()}%"))
                | (m.EnergyBenchmarkProfile.scenario.ilike(f"%{keyword.strip()}%"))
            )
        if is_enabled is not None:
            conditions.append(m.EnergyBenchmarkProfile.is_enabled.is_(is_enabled))
        if library_type:
            conditions.append(m.EnergyBenchmarkProfile.library_type == library_type)
        stmt = select(m.EnergyBenchmarkProfile).where(*conditions).order_by(m.EnergyBenchmarkProfile.id.desc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/benchmark/profiles")
    async def create_energy_benchmark_profile(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        payload = _profile_payload(data, require_name=True)
        if isinstance(payload, Response):
            return payload
        obj = m.EnergyBenchmarkProfile(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/benchmark/profiles/{profile_id:int}")
    async def update_energy_benchmark_profile(
        self,
        db_session: AsyncSession,
        profile_id: int,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.EnergyBenchmarkProfile, profile_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = _profile_payload(data, require_name=False)
        if isinstance(payload, Response):
            return payload
        for key, value in payload.items():
            setattr(obj, key, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/benchmark/profiles/{profile_id:int}", status_code=200)
    async def delete_energy_benchmark_profile(self, db_session: AsyncSession, profile_id: int) -> Response[dict]:
        obj = await db_session.get(m.EnergyBenchmarkProfile, profile_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/energy/benchmark/items")
    async def list_energy_benchmark_items(
        self,
        db_session: AsyncSession,
        profile_id: int | None = None,
        target_type: str | None = None,
        metric_code: str | None = None,
        standard_code: str | None = None,
        applicable_category: str | None = None,
        keyword: str | None = None,
        is_enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if profile_id is not None:
            conditions.append(m.EnergyBenchmarkItem.profile_id == profile_id)
        if target_type and target_type != "all":
            conditions.append(m.EnergyBenchmarkItem.target_type == target_type)
        if metric_code and metric_code != "all":
            conditions.append(m.EnergyBenchmarkItem.metric_code == metric_code)
        if standard_code:
            conditions.append(m.EnergyBenchmarkItem.standard_code.ilike(f"%{standard_code.strip()}%"))
        if applicable_category:
            conditions.append(m.EnergyBenchmarkItem.applicable_category.ilike(f"%{applicable_category.strip()}%"))
        if keyword:
            value = f"%{keyword.strip()}%"
            conditions.append(
                (m.EnergyBenchmarkItem.target_name.ilike(value))
                | (m.EnergyBenchmarkItem.target_code.ilike(value))
                | (m.EnergyBenchmarkItem.metric_name.ilike(value))
                | (m.EnergyBenchmarkItem.standard_code.ilike(value))
                | (m.EnergyBenchmarkItem.applicable_category.ilike(value))
            )
        if is_enabled is not None:
            conditions.append(m.EnergyBenchmarkItem.is_enabled.is_(is_enabled))
        stmt = select(m.EnergyBenchmarkItem).where(*conditions).order_by(m.EnergyBenchmarkItem.id.desc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/benchmark/items")
    async def create_energy_benchmark_item(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        payload = await _item_payload(db_session, data, require_required=True)
        if isinstance(payload, Response):
            return payload
        obj = m.EnergyBenchmarkItem(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/benchmark/items/{item_id:int}")
    async def update_energy_benchmark_item(
        self,
        db_session: AsyncSession,
        item_id: int,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.EnergyBenchmarkItem, item_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = await _item_payload(db_session, data, require_required=False)
        if isinstance(payload, Response):
            return payload
        for key, value in payload.items():
            setattr(obj, key, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/benchmark/items/{item_id:int}", status_code=200)
    async def delete_energy_benchmark_item(self, db_session: AsyncSession, item_id: int) -> Response[dict]:
        obj = await db_session.get(m.EnergyBenchmarkItem, item_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/energy/benchmark/generate-from-history")
    async def generate_energy_benchmark_from_history(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        return await _generate_from_history_response(db_session, data)

    @post("/api/energy/benchmark/internal-baseline/generate")
    async def generate_internal_energy_benchmark(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        return await _generate_from_history_response(db_session, data)

    @get("/api/energy/benchmark/policy-sources")
    async def list_energy_benchmark_policy_sources(self) -> Response[dict]:
        return Response(content=ok_data({"items": available_policy_sources()}))

    @post("/api/energy/benchmark/policy-library/sync")
    async def sync_energy_benchmark_policy_library(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        sources = _source_keys(data.get("source") or data.get("sources"))
        result = await sync_policy_benchmark_library(db_session, sources, apply=bool(data.get("apply")))
        return Response(content=ok_data(asdict(result)))

    @post("/api/energy/benchmark/import/preview")
    async def preview_energy_benchmark_import(
        self,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        rows = _parse_import_rows(str(data.get("csv_text") or ""))
        return Response(content=ok_data(_preview_rows(rows)))

    @post("/api/energy/benchmark/import/apply")
    async def apply_energy_benchmark_import(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BENCHMARK_BODY,
    ) -> Response[dict]:
        profile_id = data.get("profile_id")
        if not profile_id:
            return Response(content={"code": 400, "msg": "请选择标杆方案"}, status_code=400)
        rows = _parse_import_rows(str(data.get("csv_text") or ""))
        preview = _preview_rows(rows)
        if preview["invalid_count"]:
            return Response(content={"code": 400, "msg": "导入数据存在错误", "data": preview}, status_code=400)
        created = 0
        for row in rows:
            payload = {
                **row,
                "profile_id": int(profile_id),
                "benchmark_value": row.get("benchmark_value") or row.get("advanced_value") or row.get("baseline_value"),
                "is_enabled": row.get("is_enabled", True),
            }
            clean = await _item_payload(db_session, payload, require_required=True)
            if isinstance(clean, Response):
                return clean
            obj = m.EnergyBenchmarkItem(**clean)
            db_session.add(obj)
            created += 1
        await db_session.commit()
        return Response(content=ok_data({"created": created}))

    @get("/api/energy/benchmark/baseline")
    async def get_energy_benchmark_baseline(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).baseline(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/summary")
    async def get_energy_benchmark_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).summary(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/coverage")
    async def get_energy_benchmark_coverage(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).coverage(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/comparisons")
    async def get_energy_benchmark_comparisons(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).comparisons(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/distribution")
    async def get_energy_benchmark_distribution(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).distribution(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/trend")
    async def get_energy_benchmark_trend(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).trend(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/detail")
    async def get_energy_benchmark_detail(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).detail(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/conclusions")
    async def get_energy_benchmark_conclusions(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).conclusions(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))

    @get("/api/energy/benchmark/recommendations")
    async def get_energy_benchmark_recommendations(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        profile_id: int | None = None,
        target_type: str | None = "device",
        target_code: str | None = None,
        metric_code: str | None = "kwh_per_run_hour",
        area_id: str | None = None,
        library_type: str | None = None,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyBenchmarkQueryService(db_session).recommendations(
            _query(period_start, period_end, profile_id, target_type, target_code, metric_code, area_id, library_type, limit)
        )
        return Response(content=ok_data(data))


def _query(
    period_start: str | None,
    period_end: str | None,
    profile_id: int | None,
    target_type: str | None,
    target_code: str | None,
    metric_code: str | None,
    area_id: str | None,
    library_type: str | None,
    limit: int,
) -> EnergyBenchmarkQuery:
    return EnergyBenchmarkQuery(
        period_start=period_start,
        period_end=period_end,
        profile_id=profile_id,
        target_type=target_type,
        target_code=target_code,
        metric_code=metric_code,
        area_id=area_id,
        library_type=library_type,
        limit=limit,
    )


async def _generate_from_history_response(db_session: AsyncSession, data: dict[str, Any]) -> Response[dict]:
    command = EnergyBenchmarkGenerateCommand(
        period_start=data.get("period_start"),
        period_end=data.get("period_end"),
        target_type=data.get("target_type") if data.get("target_type") in TARGET_TYPES else "device",
        metric_code=data.get("metric_code") if data.get("metric_code") in METRICS else "kwh_per_run_hour",
        profile_name=str(data.get("profile_name") or "行业标杆方案"),
        method=str(data.get("method") or "best_period"),
    )
    result = await EnergyBenchmarkQueryService(db_session).generate_from_history(command)
    return Response(content=ok_data(result))


def _profile_payload(data: dict[str, Any], *, require_name: bool) -> dict[str, Any] | Response[dict]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in PROFILE_FIELDS}
    if require_name and not str(payload.get("name") or "").strip():
        return Response(content={"code": 400, "msg": "方案名称不能为空"}, status_code=400)
    if "name" in payload:
        payload["name"] = str(payload["name"]).strip()
    return payload


async def _item_payload(db_session: AsyncSession, data: dict[str, Any], *, require_required: bool) -> dict[str, Any] | Response[dict]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in ITEM_FIELDS}
    if require_required:
        missing = [key for key in ("profile_id", "target_type", "metric_code", "benchmark_value") if payload.get(key) in (None, "")]
        if missing:
            return Response(content={"code": 400, "msg": f"缺少字段: {', '.join(missing)}"}, status_code=400)
    if "profile_id" in payload:
        profile = await db_session.get(m.EnergyBenchmarkProfile, int(payload["profile_id"]))
        if profile is None:
            return Response(content={"code": 400, "msg": "标杆方案不存在"}, status_code=400)
    if "target_type" in payload and payload["target_type"] not in TARGET_TYPES:
        return Response(content={"code": 400, "msg": "标杆对象类型无效"}, status_code=400)
    if "metric_code" in payload:
        metric = METRICS.get(str(payload["metric_code"]))
        if metric is None:
            return Response(content={"code": 400, "msg": "指标编码无效"}, status_code=400)
        payload.setdefault("metric_name", metric["name"])
        payload.setdefault("unit", metric["unit"])
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if value == "":
        return None
    if key in {"valid_from", "valid_to"} and isinstance(value, str) and value:
        return date.fromisoformat(value)
    if key in {
        "benchmark_value",
        "excellent_value",
        "warning_threshold_pct",
        "severe_threshold_pct",
        "advanced_value",
        "saving_value",
        "access_value",
        "baseline_value",
    } and value is not None:
        return Decimal(str(value))
    return value


def _page(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


def _limit(value: int) -> int:
    return max(1, min(value, 200))


def _source_keys(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _parse_import_rows(csv_text: str) -> list[dict[str, Any]]:
    if not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    rows = []
    for raw in reader:
        row = {_normalize_import_key(key): (value.strip() if isinstance(value, str) else value) for key, value in raw.items() if key}
        rows.append({key: _coerce_import_value(key, value) for key, value in row.items() if value not in (None, "")})
    return rows


def _normalize_import_key(key: str) -> str:
    mapping = {
        "对象类型": "target_type",
        "对象编码": "target_code",
        "对象名称": "target_name",
        "指标编码": "metric_code",
        "指标名称": "metric_name",
        "标杆值": "benchmark_value",
        "单位": "unit",
        "标准编号": "standard_code",
        "适用行业": "applicable_industry",
        "适用分类": "applicable_category",
        "适用条件": "applicable_condition",
        "参考标准": "reference_standard",
        "指标方向": "metric_direction",
        "先进水平": "advanced_value",
        "节能水平": "saving_value",
        "准入水平": "access_value",
        "基准水平": "baseline_value",
    }
    return mapping.get(key.strip(), key.strip())


def _coerce_import_value(key: str, value: Any) -> Any:
    if key in {"benchmark_value", "advanced_value", "saving_value", "access_value", "baseline_value"}:
        return Decimal(str(value))
    if key in {"warning_threshold_pct", "severe_threshold_pct"}:
        return Decimal(str(value))
    if key == "is_enabled":
        return str(value).lower() not in {"false", "0", "否", "停用"}
    return value


def _preview_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    preview = []
    valid_count = 0
    invalid_count = 0
    for index, row in enumerate(rows, start=1):
        errors = [
            f"缺少{field}"
            for field in ("target_type", "metric_code", "benchmark_value")
            if row.get(field) in (None, "")
        ]
        if row.get("target_type") and row["target_type"] not in TARGET_TYPES:
            errors.append("对象类型无效")
        if row.get("metric_code") and row["metric_code"] not in METRICS:
            errors.append("指标编码无效")
        valid = not errors
        valid_count += int(valid)
        invalid_count += int(not valid)
        preview.append({"row_number": index, "valid": valid, "errors": errors, "row": row})
    return {"items": preview, "valid_count": valid_count, "invalid_count": invalid_count, "total": len(rows)}
