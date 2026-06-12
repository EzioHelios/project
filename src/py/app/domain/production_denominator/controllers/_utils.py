from __future__ import annotations

from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter

from app.domain.energy.controllers._utils import model_to_dict


def paged_payload(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


async def list_page(
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
    return paged_payload([model_to_dict(row) for row in rows], total, limit_clamped, offset_clamped)


async def log_admin_data_event(
    audit_service: Any,
    request: Any,
    *,
    action: str,
    target_type: str,
    target_id: int | str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    payload = dict(details or {})
    payload.setdefault("target_type", target_type)
    if target_id is not None:
        payload.setdefault("target_id", target_id)
    await audit_service.log_action(
        action=action,
        actor_id=request.user.id,
        actor_email=request.user.email,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        target_label=target_label,
        details=payload,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
