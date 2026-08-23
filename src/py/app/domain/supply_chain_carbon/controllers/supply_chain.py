from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get, patch, post
from litestar.params import Body
from litestar.response import Response

from app.domain.accounts.guards import requires_permission
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.supply_chain_carbon.queries.supply_chain import (
    SupplyChainCarbonQuery,
    SupplyChainCarbonQueryService,
)
from app.domain.supply_chain_carbon.usecases.supply_chain import SupplyChainCarbonUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


SUPPLY_CHAIN_BODY = Body()


class SupplyChainCarbonController(Controller):
    tags = ["Supply Chain Carbon"]
    guards = [requires_permission("carbon.inventory.view")]

    @get("/api/carbon/supply-chain/summary", operation_id="SupplyChainCarbonGetSummary")
    async def get_summary(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/carbon/supply-chain/source-readiness", operation_id="SupplyChainCarbonGetSourceReadiness")
    async def get_source_readiness(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).source_readiness()
        return Response(content=ok_data(data))

    @get("/api/carbon/supply-chain/analysis", operation_id="SupplyChainCarbonGetAnalysis")
    async def get_analysis(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).analysis()
        return Response(content=ok_data(data))

    @get("/api/carbon/supply-chain/suppliers", operation_id="SupplyChainCarbonListSuppliers")
    async def list_suppliers(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).suppliers(
            _query(status=status, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/suppliers",
        operation_id="SupplyChainCarbonCreateSupplier",
        guards=[requires_permission("carbon.record.create")],
    )
    async def create_supplier(
        self, db_session: AsyncSession, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_supplier(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/supply-chain/suppliers/{supplier_id:int}",
        operation_id="SupplyChainCarbonUpdateSupplier",
        guards=[requires_permission("carbon.record.update")],
    )
    async def update_supplier(
        self, db_session: AsyncSession, supplier_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).update_supplier(supplier_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/supply-chain/sites", operation_id="SupplyChainCarbonListSites")
    async def list_sites(
        self,
        db_session: AsyncSession,
        supplier_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).sites(
            _query(supplier_id=supplier_id, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/sites",
        operation_id="SupplyChainCarbonCreateSite",
        guards=[requires_permission("carbon.record.create")],
    )
    async def create_site(
        self, db_session: AsyncSession, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_site(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/supply-chain/sites/{site_id:int}",
        operation_id="SupplyChainCarbonUpdateSite",
        guards=[requires_permission("carbon.record.update")],
    )
    async def update_site(
        self, db_session: AsyncSession, site_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).update_site(site_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/supply-chain/tasks", operation_id="SupplyChainCarbonListTasks")
    async def list_tasks(
        self,
        db_session: AsyncSession,
        supplier_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).tasks(
            _query(
                supplier_id=supplier_id, status=status, task_type=task_type, keyword=keyword, limit=limit, offset=offset
            )
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/tasks",
        operation_id="SupplyChainCarbonCreateTask",
        guards=[requires_permission("carbon.record.create")],
    )
    async def create_task(
        self, db_session: AsyncSession, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_task(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/supply-chain/tasks/{task_id:int}",
        operation_id="SupplyChainCarbonUpdateTask",
        guards=[requires_permission("carbon.record.update")],
    )
    async def update_task(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).update_task(task_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/submit",
        operation_id="SupplyChainCarbonSubmitTask",
        guards=[requires_permission("carbon.record.submit")],
    )
    async def submit_task(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).decide_task(task_id, "submit", data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/approve",
        operation_id="SupplyChainCarbonApproveTask",
        guards=[requires_permission("carbon.record.approve")],
    )
    async def approve_task(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).decide_task(task_id, "approve", data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/reject",
        operation_id="SupplyChainCarbonRejectTask",
        guards=[requires_permission("carbon.record.reject")],
    )
    async def reject_task(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).decide_task(task_id, "reject", data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/request-revision",
        operation_id="SupplyChainCarbonRequestRevision",
        guards=[requires_permission("carbon.record.reject")],
    )
    async def request_revision(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).decide_task(task_id, "request_revision", data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/supply-chain/tasks/{task_id:int}/data", operation_id="SupplyChainCarbonListTaskData")
    async def list_task_data(
        self, db_session: AsyncSession, task_id: int, limit: int = 50, offset: int = 0
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).data_items(
            _query(task_id=task_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/data",
        operation_id="SupplyChainCarbonCreateTaskData",
        guards=[requires_permission("carbon.record.create")],
    )
    async def create_task_data(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_carbon_data(task_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/supply-chain/data/{data_id:int}",
        operation_id="SupplyChainCarbonUpdateTaskData",
        guards=[requires_permission("carbon.record.update")],
    )
    async def update_task_data(
        self, db_session: AsyncSession, data_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).update_carbon_data(data_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get(
        "/api/carbon/supply-chain/tasks/{task_id:int}/evidence",
        operation_id="SupplyChainCarbonListTaskEvidence",
    )
    async def list_task_evidence(
        self, db_session: AsyncSession, task_id: int, limit: int = 50, offset: int = 0
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).evidence_items(
            _query(task_id=task_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/evidence",
        operation_id="SupplyChainCarbonCreateTaskEvidence",
        guards=[requires_permission("carbon.record.create")],
    )
    async def create_task_evidence(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_evidence(task_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get(
        "/api/carbon/supply-chain/tasks/{task_id:int}/reviews",
        operation_id="SupplyChainCarbonListTaskReviews",
    )
    async def list_task_reviews(
        self, db_session: AsyncSession, task_id: int, limit: int = 50, offset: int = 0
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).review_decisions(
            _query(task_id=task_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/supply-chain/releases", operation_id="SupplyChainCarbonListReleases")
    async def list_releases(
        self,
        db_session: AsyncSession,
        task_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        data = await SupplyChainCarbonQueryService(db_session).releases(
            _query(task_id=task_id, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/supply-chain/tasks/{task_id:int}/releases",
        operation_id="SupplyChainCarbonCreateRelease",
        guards=[requires_permission("carbon.inventory.export")],
    )
    async def create_release(
        self, db_session: AsyncSession, task_id: int, data: dict[str, Any] = SUPPLY_CHAIN_BODY
    ) -> Response[dict[str, Any]]:
        try:
            obj = await SupplyChainCarbonUseCase(db_session).create_release(task_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))


def _query(
    *,
    supplier_id: int | None = None,
    task_id: int | None = None,
    status: str | None = None,
    task_type: str | None = None,
    data_type: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SupplyChainCarbonQuery:
    return SupplyChainCarbonQuery(
        supplier_id=supplier_id,
        task_id=task_id,
        status=status,
        task_type=task_type,
        data_type=data_type,
        keyword=keyword,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


def _error(exc: ValueError) -> Response[dict[str, Any]]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message}, status_code=status_code)
