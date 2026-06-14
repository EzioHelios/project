from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get, post
from litestar.exceptions import ClientException
from litestar.response import Response

from app.domain.accounts.guards import requires_superuser
from app.domain.carbon.real_company_package_importer import (
    import_real_company_package,
    list_real_company_package_summaries,
    resolve_real_company_package_dir,
    summarize_real_company_package,
)
from app.domain.carbon.services._bigscreen import (
    BigscreenCarbonService,
    BigscreenIntroService,
    BigscreenMetaService,
    BigscreenOverviewService,
    BigscreenPowerService,
)
from app.domain.carbon.services._huayi_bigscreen import HuayiBigscreenMetaService, HuayiBigscreenOverviewService
from app.domain.energy.controllers._utils import ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.lib.settings import AppSettings


class BigscreenController(Controller):
    path = "/api/bigscreen"
    tags = ["Bigscreen"]

    @get("/meta")
    async def get_meta(self, settings: AppSettings) -> Response[dict]:
        payload = BigscreenMetaService(
            title=settings.DISPLAY_NAME,
            short_name=settings.SHORT_NAME,
            description=settings.DESCRIPTION,
        ).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/intro")
    async def get_intro(self, db_session: AsyncSession, settings: AppSettings) -> Response[dict]:
        meta = BigscreenMetaService(
            title=settings.DISPLAY_NAME,
            short_name=settings.SHORT_NAME,
            description=settings.DESCRIPTION,
        )
        payload = await BigscreenIntroService(session=db_session, meta=meta).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/overview")
    async def get_overview(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenOverviewService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/power")
    async def get_power(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenPowerService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/carbon")
    async def get_carbon(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenCarbonService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})


class HuayiBigscreenController(Controller):
    path = "/api/bigscreen/huayi"
    tags = ["Bigscreen"]

    @get("/meta")
    async def get_meta(self) -> Response[dict]:
        payload = HuayiBigscreenMetaService().build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/overview")
    async def get_overview(self) -> Response[dict]:
        payload = HuayiBigscreenOverviewService().build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})


class RealCompanyPackageImportController(Controller):
    tags = ["Carbon"]

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
