"""Report-subject editing uses existing tenant-owned enterprise records."""

import pytest

from app.db import models as m
from app.domain.master_data.enterprise_profile import EnterpriseProfileUpdate, update_enterprise_profile
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_profile_edit_is_tenant_isolated_even_with_cached_objects(session):
    a = m.Team(name="Profile A", slug="report-profile-a")
    b = m.Team(name="Profile B", slug="report-profile-b")
    session.add_all([a, b])
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    own = m.EnterpriseInfo(team_id=a.id, name="Own", other_info={"scene": "preserve"})
    other = m.EnterpriseInfo(team_id=b.id, name="Other")
    session.add_all([own, other])
    await session.commit()
    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = a.id
    updated = await update_enterprise_profile(
        session, own.id, EnterpriseProfileUpdate(name="Updated", registered_address="Address")
    )
    assert updated.other_info == {"scene": "preserve", "registered_address": "Address"}
    with pytest.raises(ValueError, match="不存在"):
        await update_enterprise_profile(session, other.id, EnterpriseProfileUpdate(name="Overwritten"))
    assert other.name == "Other"
