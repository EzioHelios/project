"""Register resource permissions and migrate existing role grants to explicit RBAC."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f151115b002"
down_revision = "f151115a001"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("energy.consumption.view", "能源数据与查询查看", "energy"),
    ("energy.consumption.manage", "能源数据与查询维护", "energy"),
    ("energy.intensity.view", "能源消费量与强度查看", "energy"),
    ("energy.intensity.manage", "能源消费量与强度维护", "energy"),
    ("energy.analysis.view", "用能分析查看", "energy"),
    ("energy.analysis.manage", "用能分析维护", "energy"),
    ("energy.benchmark.view", "能效对标查看", "energy"),
    ("energy.benchmark.manage", "能效对标维护", "energy"),
    ("energy.flow.view", "能流分析查看", "energy"),
    ("energy.flow.manage", "能流分析维护", "energy"),
    ("energy.balance.view", "能量平衡查看", "energy"),
    ("energy.balance.manage", "能量平衡维护", "energy"),
    ("energy.budget.view", "能碳预算查看", "energy"),
    ("energy.budget.manage", "能碳预算维护", "energy"),
    ("master_data.view", "组织区域与设备查看", "master_data"),
    ("master_data.manage", "组织区域与设备维护", "master_data"),
    ("production.view", "经营与生产数据查看", "production"),
    ("production.manage", "经营与生产数据维护", "production"),
    ("factor_library.view", "排放因子查看", "factor_library"),
    ("factor_library.manage", "排放因子维护", "factor_library"),
    ("bigscreen.view", "态势大屏查看", "bigscreen"),
    ("bigscreen.manage", "态势大屏维护", "bigscreen"),
    ("monitor.view", "监测告警查看", "monitor"),
    ("monitor.manage", "监测告警维护", "monitor"),
    ("iot.view", "采集接入查看", "iot"),
    ("iot.manage", "采集接入维护", "iot"),
    ("vision.view", "视觉识别查看", "vision"),
    ("vision.manage", "视觉识别维护", "vision"),
    ("product_footprint.view", "产品碳足迹查看", "product_footprint"),
    ("material_allocation.view", "物资作业分摊查看", "material_allocation"),
    ("system.tasks.view", "平台任务查看", "system"),
    ("energy.dictionary.manage", "全局能源字典维护", "energy"),
)


def upgrade() -> None:
    """Add grants without changing users, memberships, passwords or customer data."""
    conn = op.get_bind()
    roles = list(conn.execute(sa.text("SELECT id, slug FROM role")).mappings())
    managers = set(
        conn.execute(
            sa.text(
                "SELECT DISTINCT rp.role_id FROM role_permission rp JOIN permission p ON p.id=rp.permission_id WHERE p.code='carbon.config.manage'"
            )
        ).scalars()
    )
    for code, name, module in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permission (id,code,name,module,created_at,updated_at) VALUES (:id,:code,:name,:module,now(),now()) ON CONFLICT (code) DO NOTHING"
            ),
            {"id": uuid4(), "code": code, "name": name, "module": module},
        )
        # These reads previously had no business guard. Preserve existing users' access
        # explicitly once; newly created roles start with no grants.
        for role in roles:
            allow_read = (
                (
                    role["slug"] in {"application-access", "warehouse-customer-viewer", "woheng-demo-operator"}
                    or role["id"] in managers
                )
                and code.endswith(".view")
                and code != "system.tasks.view"
            )
            allow_write = (
                code != "energy.dictionary.manage"
                and code.endswith(".manage")
                and role["id"] in managers
                and module in {"energy", "master_data", "production", "factor_library"}
            )
            allow_write = allow_write or (
                code == "monitor.manage" and role["slug"] in {"application-access", "woheng-demo-operator"}
            )
            if not (allow_read or allow_write):
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (id,role_id,permission_id,created_at,updated_at) SELECT :id,:role_id,id,now(),now() FROM permission WHERE code=:code ON CONFLICT (role_id,permission_id) DO NOTHING"
                ),
                {"id": uuid4(), "role_id": role["id"], "code": code},
            )


def downgrade() -> None:
    """Remove only the resource permissions introduced by this revision."""
    for code, _, _ in PERMISSIONS:
        op.get_bind().execute(sa.text("DELETE FROM permission WHERE code=:code"), {"code": code})
