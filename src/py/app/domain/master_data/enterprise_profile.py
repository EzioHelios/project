"""Tenant enterprise profile editing, without a second reporting ledger."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.lib.tenancy import require_session_tenant_id


class EnterpriseProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    unify_code: Annotated[str | None, Field(max_length=30)] = None
    belong_unit: Annotated[str | None, Field(max_length=100)] = None
    industry: Annotated[str | None, Field(max_length=30)] = None
    location: Annotated[str | None, Field(max_length=50)] = None
    people_count: Annotated[int | None, Field(ge=0)] = None
    park_area: Annotated[float | None, Field(ge=0, allow_inf_nan=False)] = None
    store_area: Annotated[float | None, Field(ge=0, allow_inf_nan=False)] = None
    green_area: Annotated[float | None, Field(ge=0, allow_inf_nan=False)] = None
    registered_address: Annotated[str | None, Field(max_length=500)] = None
    legal_representative: Annotated[str | None, Field(max_length=100)] = None
    contact_name: Annotated[str | None, Field(max_length=100)] = None
    contact_details: Annotated[str | None, Field(max_length=300)] = None
    organization_description: Annotated[str | None, Field(max_length=10000)] = None
    process_description: Annotated[str | None, Field(max_length=10000)] = None


PROFILE_DETAIL_FIELDS = {
    "registered_address",
    "legal_representative",
    "contact_name",
    "contact_details",
    "organization_description",
    "process_description",
}


async def update_enterprise_profile(
    session: AsyncSession,
    enterprise_id: int,
    data: EnterpriseProfileUpdate,
) -> m.EnterpriseInfo:
    team_id = require_session_tenant_id(session)
    row = await session.scalar(
        select(m.EnterpriseInfo).where(
            m.EnterpriseInfo.id == enterprise_id,
            m.EnterpriseInfo.team_id == team_id,
        )
    )
    if row is None:
        msg = "企业档案不存在"
        raise ValueError(msg)
    details = dict(row.other_info or {})
    for key, value in data.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        if key == "name" and not value:
            msg = "企业名称不能为空"
            raise ValueError(msg)
        if key in PROFILE_DETAIL_FIELDS:
            details[key] = value
        else:
            setattr(row, key, value)
    row.other_info = details
    await session.commit()
    return row
