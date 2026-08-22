# ruff: noqa: B008, PERF401, RUF001, RUF002, RUF003
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from advanced_alchemy.filters import LimitOffset, OrderBy
from litestar import Request, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select, text

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService  # noqa: TC001
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.controllers import (
    AUDIT_ACTION_APPROVE,
    AUDIT_ACTION_REJECT,
    AUDIT_ACTION_SUBMIT,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_REJECTED,
    _augment_page_items,
    _build_scope2_snapshot_payload,
    _build_scope_record_computation,
    _carbon_defaults,
    _coerce_date_fields,
    _list_page,
    _list_rows,
    _log_security_audit,
    _mutable_record_data,
    _paged_payload,
    _refresh_scope2_snapshot,
    _scope2_snapshot_ready,
    _serialize_scope_record,
)
from app.domain.carbon.deps import (
    provide_carbon_audit_log_service,
    provide_emission_factor_service,
    provide_energy_type_service,
    provide_scope1_mobile_combustion_service,
    provide_scope1_refrigerant_leak_service,
    provide_scope1_stationary_combustion_service,
    provide_scope2_electricity_bill_service,
    provide_scope2_meter_aggregate_service,
    provide_scope2_purchased_energy_service,
    provide_scope3_third_party_transport_service,
    provide_scope3_waste_disposal_service,
)
from app.domain.carbon.validation import (
    CarbonValidationError,
    validate_amount_non_negative,
    validate_billing_month,
    validate_consumption,
    validate_date_not_future,
    validate_period_start_end,
)
from app.domain.carbon_accounting.usecases.record_locks import CarbonAccountingRecordLockUseCase
from app.domain.metering.projection import ElectricityProjectionUseCase, reconcile_scope2_electricity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CarbonAccountingController:
    """Legacy helpers retained for non-writing analytics during the data migration.

    This class intentionally is not a Litestar controller. Scope-specific CRUD is
    retired; all new activity writes use ``/api/ghg-inventory``.
    """
    tags = ["Carbon Accounting"]
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
        "audit_log_service": provide_carbon_audit_log_service,
        "security_audit_service": provide_audit_log_service,
    }

    async def _create_audit_log(
        self,
        audit_log_service: services.CarbonAuditLogService,
        data: dict[str, Any],
    ) -> None:
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

    async def _locked_scope_record_response(
        self,
        session: AsyncSession,
        *,
        record_type: str,
        record_id: int,
    ) -> Response[dict] | None:
        try:
            await CarbonAccountingRecordLockUseCase(session).ensure_record_mutable(record_type, record_id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return None

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
        return Response(
            content={"code": 200, "data": await _serialize_scope_record(obj, scope1_mobile_service.repository.session)}
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope1_mobile_service.repository.session),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_mobile_service.repository.session,
            record_type="Scope1MobileCombustion",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(fresh, scope1_mobile_service.repository.session),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_mobile_service.repository.session,
            record_type="Scope1MobileCombustion",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope1MobileCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope1MobileCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope1MobileCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope1_stationary_service.repository.session),
            }
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope1_stationary_service.repository.session),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_stationary_service.repository.session,
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
        if obj.status == STATUS_APPROVED:
            return Response(content={"code": 400, "msg": "已通过记录不可修改"}, status_code=400)
        try:
            if "amount" in data:
                validate_consumption(data["amount"], "消耗量")
            if "period_start" in data or "period_end" in data:
                validate_period_start_end(
                    data.get("period_start") or obj.period_start, data.get("period_end") or obj.period_end
                )
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)
        _coerce_date_fields(data, ["period_start", "period_end"])
        await scope1_stationary_service.update(item_id=record_id, data=data, auto_commit=True)
        fresh = await scope1_stationary_service.get_one(id=record_id)
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(fresh, scope1_stationary_service.repository.session),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_stationary_service.repository.session,
            record_type="Scope1StationaryCombustion",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope1StationaryCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope1StationaryCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope1StationaryCombustion",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope1_refrigerant_service.repository.session),
            }
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope1_refrigerant_service.repository.session),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_refrigerant_service.repository.session,
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(fresh, scope1_refrigerant_service.repository.session),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope1_refrigerant_service.repository.session,
            record_type="Scope1RefrigerantLeak",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope1RefrigerantLeak",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope1RefrigerantLeak",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope1RefrigerantLeak",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(
                    obj, scope2_bill_service.repository.session, source_kind="manual_bill"
                ),
            }
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(
                    obj, scope2_bill_service.repository.session, source_kind="manual_bill"
                ),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope2_bill_service.repository.session,
            record_type="Scope2ElectricityBill",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(
                    fresh, scope2_bill_service.repository.session, source_kind="manual_bill"
                ),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope2_bill_service.repository.session,
            record_type="Scope2ElectricityBill",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope2ElectricityBill",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
        await reconcile_scope2_electricity(
            scope2_bill_service.repository.session,
            obj.billing_month,
        )
        await self._create_audit_log(
            audit_log_service,
            {
                "record_type": "Scope2ElectricityBill",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope2ElectricityBill",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        locked_response = await self._locked_scope_record_response(
            scope2_purchased_energy_service.repository.session,
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        locked_response = await self._locked_scope_record_response(
            scope2_purchased_energy_service.repository.session,
            record_type="Scope2PurchasedEnergy",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        await scope2_purchased_energy_service.update(
            item_id=record_id, data={"status": STATUS_PENDING}, auto_commit=True
        )
        await self._create_audit_log(
            audit_log_service,
            {
                "record_type": "Scope2PurchasedEnergy",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope2PurchasedEnergy",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope2PurchasedEnergy",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        return Response(
            content={"code": 200, "data": await _serialize_scope_record(obj, scope3_waste_service.repository.session)}
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope3_waste_service.repository.session),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope3_waste_service.repository.session,
            record_type="Scope3WasteDisposal",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(fresh, scope3_waste_service.repository.session),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope3_waste_service.repository.session,
            record_type="Scope3WasteDisposal",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope3WasteDisposal",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope3WasteDisposal",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope3WasteDisposal",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope3_transport_service.repository.session),
            }
        )

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
        return Response(
            content={
                "code": 200,
                "data": await _serialize_scope_record(obj, scope3_transport_service.repository.session),
                "msg": "创建成功",
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope3_transport_service.repository.session,
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
        return Response(
            content={
                "code": 200,
                "msg": "更新成功",
                "data": await _serialize_scope_record(fresh, scope3_transport_service.repository.session),
            }
        )

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
        locked_response = await self._locked_scope_record_response(
            scope3_transport_service.repository.session,
            record_type="Scope3ThirdPartyTransport",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            {
                "record_type": "Scope3ThirdPartyTransport",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            {
                "record_type": "Scope3ThirdPartyTransport",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
            {
                "record_type": "Scope3ThirdPartyTransport",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
            search_fields=[
                "energy_type_code",
                "energy_type_name",
                "supplier_name",
                "area_name",
                "facility_name",
                "remark",
            ],
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
            search_fields=[
                "energy_type_code",
                "energy_type_name",
                "supplier_name",
                "area_name",
                "facility_name",
                "remark",
            ],
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
            items = await svc.list(
                model.status == STATUS_PENDING, LimitOffset(limit + offset, 0), OrderBy(model.id, "desc")
            )
            for i in items:
                out.append(
                    {
                        "record_type": name,
                        "record_id": i.id,
                        **await _serialize_scope_record(i, svc.repository.session, source_kind=source_kind),
                    }
                )
        out.sort(key=lambda row: int(row.get("record_id") or 0), reverse=True)
        limit_clamped = max(1, min(limit, 100))
        offset_clamped = max(0, offset)
        return Response(
            content=_paged_payload(
                out[offset_clamped : offset_clamped + limit_clamped], len(out), limit_clamped, offset_clamped
            )
        )

    async def _rebuild_scope2_meter_aggregates(
        self,
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        billing_month: str,
        area_id: str | None = None,
    ) -> list[m.Scope2MeterAggregate]:
        del scope2_meter_aggregate_service
        result = await ElectricityProjectionUseCase(db_session).rebuild_month(billing_month, area_id=area_id)
        return list(
            (
                await db_session.scalars(
                    select(m.Scope2MeterAggregate).where(
                        m.Scope2MeterAggregate.billing_month == billing_month,
                        m.Scope2MeterAggregate.projection_run_id == result.run_id,
                    )
                )
            ).all()
        )

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
        try:
            rows = await self._rebuild_scope2_meter_aggregates(
                db_session, scope2_meter_aggregate_service, billing_month, area_id
            )
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
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
        locked_response = await self._locked_scope_record_response(
            scope2_meter_aggregate_service.repository.session,
            record_type="Scope2MeterAggregate",
            record_id=record_id,
        )
        if locked_response is not None:
            return locked_response
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
            return Response(
                content={"code": 400, "msg": obj.aggregation_note or "聚合结果不可核算，请先修复采样数据。"},
                status_code=400,
            )
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前聚合记录尚未形成有效核算结果"}, status_code=400)
        await scope2_meter_aggregate_service.update(
            item_id=record_id, data={"status": STATUS_PENDING}, auto_commit=True
        )
        await self._create_audit_log(
            audit_log_service,
            {
                "record_type": "Scope2MeterAggregate",
                "record_id": record_id,
                "action": AUDIT_ACTION_SUBMIT,
                "comment": "提交审核",
            },
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
            return Response(
                content={"code": 400, "msg": obj.aggregation_note or "聚合结果不可核算，请先修复采样数据。"},
                status_code=400,
            )
        if not _scope2_snapshot_ready(obj):
            return Response(content={"code": 400, "msg": "当前聚合记录尚未形成有效核算结果"}, status_code=400)
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await scope2_meter_aggregate_service.update(
            item_id=record_id, data={"status": STATUS_APPROVED, "approved_at": now}, auto_commit=True
        )
        await self._create_audit_log(
            audit_log_service,
            {
                "record_type": "Scope2MeterAggregate",
                "record_id": record_id,
                "action": AUDIT_ACTION_APPROVE,
                "comment": "审核通过",
            },
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
        await scope2_meter_aggregate_service.update(
            item_id=record_id, data={"status": STATUS_REJECTED, "reject_reason": reason}, auto_commit=True
        )
        await self._create_audit_log(
            audit_log_service,
            {
                "record_type": "Scope2MeterAggregate",
                "record_id": record_id,
                "action": AUDIT_ACTION_REJECT,
                "comment": reason,
            },
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
                        select(func.count())
                        .select_from(m.Scope2ElectricityBill)
                        .where(*(manual_conditions or [text("1=1")]))
                    )
                ).scalar_one()
            )
            manual_rows = await scope2_bill_service.list(
                *(manual_conditions or []), LimitOffset(limit + offset, 0), OrderBy(m.Scope2ElectricityBill.id, "desc")
            )
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
                        select(func.count())
                        .select_from(m.Scope2MeterAggregate)
                        .where(*(aggregate_conditions or [text("1=1")]))
                    )
                ).scalar_one()
            )
            aggregate_rows = await scope2_meter_aggregate_service.list(
                *(aggregate_conditions or []),
                LimitOffset(limit + offset, 0),
                OrderBy(m.Scope2MeterAggregate.id, "desc"),
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
                        **await _serialize_scope_record(
                            row, scope2_bill_service.repository.session, source_kind="manual_bill"
                        ),
                    }
                )
        for row in aggregate_rows:
            records.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    **await _serialize_scope_record(
                        row, scope2_meter_aggregate_service.repository.session, source_kind="meter_aggregate"
                    ),
                }
            )
        records.sort(
            key=lambda item: (str(item.get("billing_month") or ""), int(item.get("record_id") or 0)), reverse=True
        )
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
            select(func.coalesce(func.sum(m.Scope2ElectricityBill.total_kwh), 0)).where(
                m.Scope2ElectricityBill.billing_month == billing_month
            )
        )
        meter_total = await db_session.scalar(
            select(func.coalesce(func.sum(m.Scope2MeterAggregate.total_kwh), 0)).where(
                m.Scope2MeterAggregate.billing_month == billing_month,
                m.Scope2MeterAggregate.calc_status == "ready",
            )
        )
        missing_count = await db_session.scalar(
            select(func.count())
            .select_from(m.Scope2MeterAggregate)
            .where(
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
