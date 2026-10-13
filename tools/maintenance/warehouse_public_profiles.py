"""Apply reviewed public descriptions to the two warehouse tenant profiles.

Run with the application environment: python warehouse_public_profiles.py [--apply].
Only public_profile/bigscreen metadata is replaced; existing enterprise facts stay intact.
"""

# ruff: noqa: RUF001, T201 - reviewed Chinese public copy and CLI audit output.

import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

PROFILES = [
    {
        "team_id": "00000000-0000-7000-8000-000000000001",
        "name": "祥泰仓库",
        "bigscreen": {"overview_focus": "business", "monitor_focus": "safety", "carbon_focus": "commute"},
        "public_profile": {
            "title": "祥泰仓库 · 绿色数智仓储",
            "summary": "国网泰州供电公司祥泰仓库开展数智、绿色化改造，将智能仓储作业、电动搬运与绿色能源设施结合，服务电力物资仓储与配送。",
            "features": [
                {"label": "智能作业", "value": "应用仓储机器人、无人视觉平库等设施，推进物资仓储作业数字化。"},
                {"label": "电动搬运", "value": "采用电动叉车开展仓储作业，以电动配送车辆支持绿色物流。"},
                {"label": "绿色能源", "value": "配套分布式光伏及光储充一体化设施；2023年公开报道光伏装机552.42kW。"},
            ],
            "source_name": "泰州日报 / 中国江苏网",
            "source_url": "https://jsnews.jschina.com.cn/tz/a/202306/t20230625_3237602.shtml",
            "published_on": "2023-06-25",
        },
    },
    {
        "team_id": "00000000-0000-7000-8000-000000000002",
        "name": "安方中心库",
        "bigscreen": {"overview_focus": "sampling", "monitor_focus": "sampling", "carbon_focus": "inventory"},
        "public_profile": {
            "title": "江苏安方电力科技有限公司",
            "summary": "公司围绕仓储运营、物资检测与物流配送提供电力智慧供应链服务，推进仓储数字化和绿色循环包装应用。",
            "features": [
                {"label": "仓储运营", "value": "通过数字化仓储平台组织物资管理，开展仓储运营服务。"},
                {"label": "物资检测", "value": "围绕电力物资开展检测服务，推进移动快检与现场服务。"},
                {"label": "物流配送", "value": "开展智能配载、运输配送与绿色循环包装业务。"},
            ],
            "source_name": "人民日报海外版 · 企业供稿",
            "source_url": "https://paper.people.com.cn/rmrbhwb/pc/content/202605/20/content_30157919.html",
            "published_on": "2026-05-20",
        },
    },
]


async def main(apply: bool) -> None:
    for item in PROFILES:
        async with provide_services(provide_users_service) as (users,):
            session = users.repository.session
            team_id = UUID(item["team_id"])
            session.info.update({TENANT_ID_SESSION_KEY: team_id, TENANT_BYPASS_SESSION_KEY: False})
            team = await session.get(m.Team, team_id)
            if team is None or team.name != item["name"]:
                raise ValueError(f"Tenant identity mismatch: {item['name']}")
            enterprise = await session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
            before = dict(enterprise.other_info or {}) if enterprise else {}
            after = {**before, "public_profile": item["public_profile"], "bigscreen": item["bigscreen"]}
            print(
                json.dumps(
                    {
                        "tenant": item["name"],
                        "apply": apply,
                        "created": enterprise is None,
                        "before": before,
                        "after": after,
                    },
                    ensure_ascii=False,
                )
            )
            if apply:
                if enterprise is None:
                    enterprise = m.EnterpriseInfo(team_id=team_id, name=item["name"])
                    session.add(enterprise)
                enterprise.other_info = after
                await session.commit()
            else:
                await session.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
