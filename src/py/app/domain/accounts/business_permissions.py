"""Business permission catalogue for the existing role/permission tables."""

from __future__ import annotations

RESOURCE_NAMES = {
    "energy.consumption": "能源数据与查询",
    "energy.intensity": "能源消费量与强度",
    "energy.analysis": "用能分析",
    "energy.benchmark": "能效对标",
    "energy.flow": "能流分析",
    "energy.balance": "能量平衡",
    "energy.budget": "能碳预算",
    "master_data": "组织区域与设备",
    "production": "经营与生产数据",
    "factor_library": "排放因子",
    "bigscreen": "态势大屏",
    "monitor": "监测告警",
    "iot": "采集接入",
    "vision": "视觉识别",
}
BUSINESS_PERMISSION_SPECS = (
    *(
        (f"{resource}.{action}", f"{label}{verb}", resource.split(".")[0])
        for resource, label in RESOURCE_NAMES.items()
        for action, verb in (("view", "查看"), ("manage", "维护"))
    ),
    ("product_footprint.view", "产品碳足迹查看", "product_footprint"),
    ("material_allocation.view", "物资作业分摊查看", "material_allocation"),
    ("system.tasks.view", "平台任务查看", "system"),
    ("energy.dictionary.manage", "全局能源字典维护", "energy"),
)

# A role template, not a runtime account-name exception. All access uses ordinary RBAC.
CUSTOMER_DEMO_ROLE = "energy-carbon-customer-demo"
CUSTOMER_DEMO_PERMISSIONS = frozenset(
    f"{resource}.{action}"
    for resource in RESOURCE_NAMES
    if resource not in {"bigscreen", "monitor", "iot", "vision"}
    for action in ("view", "manage")
) | frozenset(
    {
        "product_footprint.view",
        "product_footprint:write",
        "material_allocation.view",
        "material_operations:write",
        "material_allocation:calculate",
        "carbon.inventory.view",
        "carbon.inventory.import",
        "carbon.inventory.calculate",
        "carbon.inventory.export",
        "carbon.inventory.report.manage",
        "carbon.record.create",
        "carbon.record.update",
        "carbon.record.delete",
        "carbon.record.submit",
        "carbon.verification.view",
        "carbon.verification.manage",
        "carbon.verification.export",
        "carbon.verification.evidence.manage",
        "carbon.assets.view",
        "carbon.assets.configure",
        "carbon.assets.ledger.post",
        "carbon.assets.compliance.manage",
        "carbon.assets.cost.run",
    }
)
