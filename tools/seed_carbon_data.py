"""Apply the reusable canonical energy-carbon demo package.

Legacy random Scope-table seeding was removed together with those tables. This
compatibility command now delegates to the versioned demo package so generated
inventory, evidence, verification and disclosure data stay reproducible.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "py"))

from app.config import alchemy
from app.demo import ApplyDemoPackage
from app.domain.metering.legacy_migration import resolve_team_id
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

logger = logging.getLogger(__name__)


async def run(*, team_slug: str, package_code: str, profile_code: str) -> None:
    """Apply one traceable and idempotent package to the selected tenant."""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        team_id = await resolve_team_id(session, team_slug)
        await session.commit()
        session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        session.info[TENANT_ID_SESSION_KEY] = team_id
        result = await ApplyDemoPackage(session).execute(package_code=package_code, profile_code=profile_code)
    logger.info(
        "Demo package applied: package=%s profile=%s team=%s activities=%s runs=%s",
        result.package_code,
        result.profile_code,
        result.team_id,
        result.inventory_activities,
        result.inventory_runs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a canonical reusable carbon demo package")
    parser.add_argument("--team", required=True, help="Target tenant team slug")
    parser.add_argument("--package", choices=["xiangtai"], default="xiangtai")
    parser.add_argument("--profile", choices=["foundation", "transition", "leadership"], default="transition")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(run(team_slug=args.team, package_code=args.package, profile_code=args.profile))


if __name__ == "__main__":
    main()
