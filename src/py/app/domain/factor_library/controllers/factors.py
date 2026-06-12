# ruff: noqa: E712
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import func, or_, select

from app.db import models as m
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.controllers import _augment_raw_factor_record_dict, _list_page, model_to_dict
from app.domain.carbon.deps import provide_emission_factor_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorLibraryController(Controller):
    tags = ["Factor Library"]
    dependencies = {"emission_factor_service": provide_emission_factor_service}

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
