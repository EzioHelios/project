"""Woheng automotive unified showcase demo package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, or_, select, text

from app.db import models as m
from app.db.models import Team, TeamMember, TeamRoles, User
from app.demo.ops.contracts import DemoAction, DemoExecutionContext, DemoPlanStep, DemoRunResult, DemoStepStatus
from app.demo.showcase import ShowcaseDemoBuilder
from app.domain.carbon.energy_analysis_importer import (
    _rebuild_energy_interval_facts,
    _rebuild_equipment_workload_facts,
    seed_energy_analysis_data,
)
from app.domain.energy.policy_benchmark_sync import sync_policy_benchmark_library
from app.domain.energy.usecases.energy_types import (
    diagnose_energy_type_data,
    ensure_standard_energy_types,
    repair_energy_type_data,
)
from app.lib import constants
from app.lib.crypt import get_password_hash
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


WOHENG_PACKAGE_KEY = "woheng-showcase"
WOHENG_NAMESPACE = "woheng"
WOHENG_PROFILE = "full"
WOHENG_BRAND_NAME = "沃衡汽车能碳管理平台"
WOHENG_ENGLISH_BRAND_NAME = "Voryntis Mobility"
WOHENG_COMPANY_NAME = "沃衡汽车有限公司"
WOHENG_COMPANY_ADDRESS = "安徽省芜湖市智能网联新能源汽车示范园区"
WOHENG_COMPANY_CREDIT_CODE = "91310000VORYNTIS2026"
WOHENG_COMPANY_EMAIL = "carbon@voryntis-auto.example.com"
WOHENG_COMPANY_WEBSITE = "https://www.voryntis-auto.example.com"
WOHENG_COMPANY_CONTACT = "林启航"
WOHENG_COMPANY_CONTACT_EMAIL = "lin.qihang@voryntis-auto.example.com"
WOHENG_SOURCE_NAME = "沃衡汽车统一演示包V1"
WOHENG_DEMO_PERMISSION_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("carbon.inventory.view", "查看温室气体盘查", "查看规范化活动、参数、证据和核算结果", "carbon"),
    ("carbon.inventory.import", "导入温室气体活动", "下载分类模板、预检并导入盘查数据", "carbon"),
    ("carbon.inventory.calculate", "执行温室气体核算", "按已发布方法和报告配置生成核算快照", "carbon"),
    ("carbon.inventory.report.manage", "编制温室气体盘查报告", "根据正式核算运行编制盘查报告", "carbon"),
    ("carbon.inventory.report.review", "审核温室气体盘查报告", "提交、审核或退回盘查报告", "carbon"),
    ("carbon.inventory.report.publish", "发布温室气体盘查报告", "发布已批准的盘查报告", "carbon"),
    ("carbon.inventory.export", "导出温室气体盘查成果", "导出盘查结果、证据索引和报告", "carbon"),
    ("microgrid.view", "查看微电网", "查看微电网运行、预测和优化结果", "microgrid"),
    ("microgrid.configure", "配置微电网", "维护微电网站点、资源、测点绑定和灵活性参数", "microgrid"),
    ("microgrid.forecast.run", "执行微电网预测", "发起微电网负荷与新能源出力预测", "microgrid"),
    ("microgrid.optimize.run", "执行微电网优化", "发起微电网优化调度计算", "microgrid"),
    ("microgrid.dispatch.simulate", "模拟微电网调度", "生成并查看微电网调度下发和回执", "microgrid"),
)
MIN_EQUIPMENT_COUNT = 19
MIN_ACTIVITY_COUNT = 400
MIN_REPORT_COUNT = 5
MIN_MQTT_MAPPING_COUNT = 12
MIN_METER_READING_COUNT = 240
MIN_SCOPE2_AGGREGATE_COUNT = 48
MIN_ENERGY_INTERVAL_COUNT = 180
MIN_WORKLOAD_COUNT = 6
MIN_BENCHMARK_ITEM_COUNT = 10
MIN_POLICY_BENCHMARK_PROFILE_COUNT = 2
MIN_EQUIPMENT_EFFICIENCY_ITEM_COUNT = 8
MIN_EQUIPMENT_EFFICIENCY_DEVICE_COUNT = 6
MIN_MEASUREMENT_BOUNDARY_COUNT = 4
MIN_MEASUREMENT_BOUNDARY_MEMBER_COUNT = 5
MIN_BOUNDARY_BOUND_ENERGY_FACT_COUNT = 120
MIN_OPERATION_LEDGER_COUNT = 6
MIN_PRODUCTION_DATA_COUNT = 3
MIN_PRODUCT_FOOTPRINT_STUDY_COUNT = 1
MIN_SUPPLY_CHAIN_SUPPLIER_COUNT = 2
MIN_REDUCTION_PROJECT_COUNT = 5
MIN_ALARM_EVENT_COUNT = 1
MIN_VIDEO_ALARM_EVENT_COUNT = 1
REQUIRED_ENERGY_INTERVAL_TYPES: tuple[str, ...] = (
    "purchased_electricity",
    "natural_gas",
    "diesel",
    "purchased_steam",
    "refrigerant",
)
MIN_INTERVAL_ROWS_PER_REQUIRED_TYPE = 24
LEGACY_RESIDUE_SAMPLE_LIMIT = 5
LEGACY_SHOWCASE_MARKERS = (
    "DEMO-PARK",
    "demo-park",
    "华东综合能源示范园区",
    "DEMO91320000PARK2026X",
    "奇瑞",
    "中汽信科",
    "华东绿色仓储",
    "绿色仓储能碳平台",
)

EQUIPMENT_EFFICIENCY_SPECS: dict[str, tuple[int, str]] = {
    "TRANSFORMER-01": (1, "GB 20052-2020 电力变压器能效限定值及能效等级"),
    "PV-INVERTER-01": (1, "T/CPIA 0050-2023 光伏并网逆变器效率要求"),
    "PV-INVERTER-02": (2, "T/CPIA 0050-2023 光伏并网逆变器效率要求"),
    "BOILER-01": (2, "GB 24500-2020 工业锅炉能效限定值及能效等级"),
    "CHILLER-01": (2, "GB 19577-2015 冷水机组能效限定值及能效等级"),
    "CHILLER-02": (3, "GB 19577-2015 冷水机组能效限定值及能效等级"),
    "CONVEYOR-01": (3, "GB 18613-2020 电动机能效限定值及能效等级"),
    "AIR-COMPRESSOR-01": (2, "GB 19153-2019 容积式空气压缩机能效限定值及能效等级"),
    "EVSE-GROUP-01": (2, "T/CECA-G 0208-2022 电动汽车充电设备能效要求"),
    "HVAC-01": (2, "GB 21454-2021 多联式空调机组能效限定值及能效等级"),
}


@dataclass(frozen=True, slots=True)
class WohengAccountSpec:
    email: str
    env_key: str
    default_secret: tuple[str, ...]
    name: str
    username: str
    is_superuser: bool
    team_scope: str
    is_owner: bool


@dataclass(frozen=True, slots=True)
class WohengTenantSpec:
    slug: str
    name: str
    city_code: str
    role: str
    enterprise_name: str
    enterprise_code: str
    location: str
    load_profile: str
    peak_power_kw: Decimal


TENANTS: tuple[WohengTenantSpec, ...] = (
    WohengTenantSpec(
        slug="woheng-taizhou-production-base",
        name="沃衡汽车泰州生产基地",
        city_code="TZ",
        role="整车装配、厂内物流、电表接入、分区分项用能监测和告警闭环样板",
        enterprise_name=f"{WOHENG_COMPANY_NAME}(泰州生产基地)",
        enterprise_code=WOHENG_COMPANY_CREDIT_CODE,
        location="江苏省泰州市新能源汽车产业园沃衡汽车泰州生产基地",
        load_profile="metering-intensive",
        peak_power_kw=Decimal("1026.4"),
    ),
    WohengTenantSpec(
        slug="woheng-huzhou-production-base",
        name="沃衡汽车湖州生产基地",
        city_code="HZ",
        role="零部件制造、经营活动台账、非电数据导入、组织碳核算、报告导出和减排绩效样板",
        enterprise_name=f"{WOHENG_COMPANY_NAME}(湖州生产基地)",
        enterprise_code=WOHENG_COMPANY_CREDIT_CODE,
        location="浙江省湖州市新能源汽车零部件产业园沃衡汽车湖州生产基地",
        load_profile="operation-intensive",
        peak_power_kw=Decimal("988.6"),
    ),
)

STANDARD_ACCOUNTS: tuple[WohengAccountSpec, ...] = (
    WohengAccountSpec(
        email="admin@example.com",
        env_key="WOHENG_DEMO_ADMIN_SECRET",
        default_secret=("Admin", "123", "!"),
        name="系统管理员",
        username="admin",
        is_superuser=True,
        team_scope="all",
        is_owner=True,
    ),
    WohengAccountSpec(
        email="codex.e2e@local.test",
        env_key="WOHENG_DEMO_E2E_SECRET",
        default_secret=("Codex", "E2E", "123", "!"),
        name="自动化验证员",
        username="codex_e2e",
        is_superuser=False,
        team_scope="woheng",
        is_owner=False,
    ),
    WohengAccountSpec(
        email="woheng.mobile@local.test",
        env_key="WOHENG_DEMO_MOBILE_SECRET",
        default_secret=("Woheng", "Mobile", "123", "!"),
        name="演示运营员",
        username="woheng_mobile",
        is_superuser=False,
        team_scope="woheng",
        is_owner=False,
    ),
)


class WohengShowcasePackage:
    """Install and validate the single-brand Woheng showcase package."""

    key = WOHENG_PACKAGE_KEY
    version = "1.0.0"
    description = "Single-brand Woheng automotive energy-carbon showcase with Taizhou and Huzhou production tenants."
    supported_profiles = (WOHENG_PROFILE,)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def _standard_account_emails(self) -> tuple[str, ...]:
        return tuple(account.email for account in STANDARD_ACCOUNTS)

    def _account_password(self, account: WohengAccountSpec) -> str:
        return os.getenv(account.env_key) or "".join(account.default_secret)

    async def execute(self, context: DemoExecutionContext, action: DemoAction) -> DemoRunResult:
        """Plan or execute one Woheng package action."""
        if action == DemoAction.PREFLIGHT:
            return await self._preflight(context)
        if action == DemoAction.INSTALL:
            return await self._install(context)
        if action == DemoAction.VALIDATE:
            return await self._validate(context)
        if action == DemoAction.CLEANUP:
            return await self._cleanup(context)
        msg = f"Unsupported demo action: {action}"
        raise ValueError(msg)

    async def _preflight(self, context: DemoExecutionContext) -> DemoRunResult:
        standard_account_count = int(
            await self._session.scalar(select(func.count(User.id)).where(User.email.in_(self._standard_account_emails)))
            or 0
        )
        admin_exists = bool(await self._session.scalar(select(User.id).where(User.email == "admin@example.com")))
        status = DemoStepStatus.COMPLETED if admin_exists else DemoStepStatus.FAILED
        return self._result(
            context,
            DemoAction.PREFLIGHT,
            False,
            status,
            [
                DemoPlanStep(
                    module_key="identity",
                    action=DemoAction.PREFLIGHT,
                    status=status,
                    summary="检查沃衡汽车演示标准账号",
                    details={
                        "standard_account_count": standard_account_count,
                        "required_accounts": list(self._standard_account_emails),
                    },
                ),
                DemoPlanStep(
                    module_key="brand",
                    action=DemoAction.PREFLIGHT,
                    status=DemoStepStatus.COMPLETED,
                    summary="演示品牌固定为沃衡汽车能碳管理平台",
                    details={
                        "brand": WOHENG_BRAND_NAME,
                        "english_brand": WOHENG_ENGLISH_BRAND_NAME,
                        "company": WOHENG_COMPANY_NAME,
                        "credit_code": WOHENG_COMPANY_CREDIT_CODE,
                    },
                ),
            ],
        )

    async def _install(self, context: DemoExecutionContext) -> DemoRunResult:
        planned = self._install_steps(DemoStepStatus.PLANNED)
        if not context.apply:
            return self._result(context, DemoAction.INSTALL, False, DemoStepStatus.PLANNED, planned)

        steps: list[DemoPlanStep] = []
        init_result = await ensure_standard_energy_types(self._session, apply=True)
        steps.append(
            DemoPlanStep(
                module_key="energy-types",
                action=DemoAction.INSTALL,
                status=DemoStepStatus.COMPLETED,
                summary="初始化标准能源品种与单位换算字典",
                details={
                    "energy_types_created": init_result.energy_types_created,
                    "energy_types_updated": init_result.energy_types_updated,
                    "unit_conversions_created": init_result.conversions_created,
                    "unit_conversions_updated": init_result.conversions_updated,
                },
            )
        )
        await self._ensure_standard_accounts()
        for tenant in TENANTS:
            team = await self._ensure_team(tenant)
            self._session.info[TENANT_ID_SESSION_KEY] = team.id
            self._session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
            await self._synchronize_bigint_sequences()
            existing_counts = await self._tenant_counts()
            if self._has_base_showcase_dataset(existing_counts):
                result_summary = {
                    "activities": existing_counts["activities"],
                    "reports": existing_counts["reports"],
                    "equipment": existing_counts["equipment"],
                    "microgrid_meter_bindings": existing_counts["microgrid_meter_bindings"],
                    "coverage_passed": True,
                    "builder": "skipped-existing-base-dataset",
                }
            else:
                result = await ShowcaseDemoBuilder(self._session).execute(climate_profile="transition")
                result_summary = {
                    "activities": result.activities,
                    "reports": result.reports,
                    "equipment": result.equipment,
                    "microgrid_meter_bindings": result.microgrid_meter_bindings,
                    "coverage_passed": result.coverage.passed,
                    "builder": "ShowcaseDemoBuilder",
                }
            legacy_repair_summary = await self._specialize_tenant(tenant, team_id=team.id)
            repair_result = await repair_energy_type_data(self._session, team_slug=tenant.slug, apply=True)
            await self._record_manifest(
                context,
                module_key="tenant",
                object_type="team",
                object_key=tenant.slug,
                object_id=str(team.id),
                team_id=team.id,
                details={
                    "name": tenant.name,
                    "role": tenant.role,
                    "brand": WOHENG_BRAND_NAME,
                    "english_brand": WOHENG_ENGLISH_BRAND_NAME,
                    "company": WOHENG_COMPANY_NAME,
                },
            )
            await self._record_manifest(
                context,
                module_key="dataset",
                object_type="showcase-result",
                object_key=f"{tenant.slug}:summary",
                object_id=str(team.id),
                team_id=team.id,
                details=result_summary,
            )
            await self._session.commit()
            steps.append(
                DemoPlanStep(
                    module_key="tenant",
                    action=DemoAction.INSTALL,
                    status=DemoStepStatus.COMPLETED,
                    summary=f"安装并差异化演示租户: {tenant.name}",
                    details={
                        "slug": tenant.slug,
                        "team_id": str(team.id),
                        "activities": result_summary["activities"],
                        "reports": result_summary["reports"],
                        "equipment": result_summary["equipment"],
                        "builder": result_summary["builder"],
                        "energy_interval_facts_repaired": repair_result.interval_facts_updated,
                        "equipment_energy_types_repaired": repair_result.equipment_updated,
                        "ghg_activities_repaired": repair_result.ghg_activities_updated,
                        "legacy_showcase_fields_repaired": legacy_repair_summary["fields_repaired"],
                        "legacy_showcase_rows_repaired": legacy_repair_summary["rows_repaired"],
                    },
                )
            )
        await self._ensure_standard_account_memberships()
        steps.append(
            DemoPlanStep(
                module_key="identity",
                action=DemoAction.INSTALL,
                status=DemoStepStatus.COMPLETED,
                summary="安装并校准标准演示账号",
                details={
                    "accounts": list(self._standard_account_emails),
                    "admin_scope": "all-teams",
                    "demo_scope": [tenant.slug for tenant in TENANTS],
                },
            )
        )
        validation = await self._validate(context)
        steps.extend(validation.steps)
        status = DemoStepStatus.COMPLETED if validation.status == DemoStepStatus.COMPLETED else DemoStepStatus.FAILED
        return self._result(context, DemoAction.INSTALL, True, status, steps)

    async def _validate(self, context: DemoExecutionContext) -> DemoRunResult:
        steps: list[DemoPlanStep] = []
        for tenant in TENANTS:
            await self._session.commit()
            self._session.info[TENANT_BYPASS_SESSION_KEY] = True
            team = await self._find_team(tenant.slug)
            await self._session.commit()
            if team is None:
                steps.append(
                    DemoPlanStep(
                        module_key="tenant",
                        action=DemoAction.VALIDATE,
                        status=DemoStepStatus.FAILED,
                        summary=f"沃衡汽车演示租户不存在: {tenant.name}",
                        details={"slug": tenant.slug},
                    )
                )
                continue
            self._session.info[TENANT_ID_SESSION_KEY] = team.id
            self._session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
            counts = await self._tenant_counts()
            energy_interval_type_counts = await self._energy_interval_type_counts()
            energy_type_diagnostics = await diagnose_energy_type_data(self._session, team_slug=tenant.slug)
            legacy_residue_summary = await self._legacy_residue_summary()
            required_energy_types_ready = all(
                energy_interval_type_counts.get(energy_type_code, 0) >= MIN_INTERVAL_ROWS_PER_REQUIRED_TYPE
                for energy_type_code in REQUIRED_ENERGY_INTERVAL_TYPES
            )
            passed = (
                counts["equipment"] >= MIN_EQUIPMENT_COUNT
                and counts["activities"] >= MIN_ACTIVITY_COUNT
                and counts["reports"] >= MIN_REPORT_COUNT
                and counts["mqtt_mappings"] >= MIN_MQTT_MAPPING_COUNT
                and counts["meter_readings"] >= MIN_METER_READING_COUNT
                and counts["scope2_aggregates"] >= MIN_SCOPE2_AGGREGATE_COUNT
                and counts["energy_interval_facts"] >= MIN_ENERGY_INTERVAL_COUNT
                and counts["workload_facts"] >= MIN_WORKLOAD_COUNT
                and counts["benchmark_items"] >= MIN_BENCHMARK_ITEM_COUNT
                and counts["policy_benchmark_profiles"] >= MIN_POLICY_BENCHMARK_PROFILE_COUNT
                and counts["equipment_efficiency_items"] >= MIN_EQUIPMENT_EFFICIENCY_ITEM_COUNT
                and counts["equipment_efficiency_devices"] >= MIN_EQUIPMENT_EFFICIENCY_DEVICE_COUNT
                and counts["measurement_boundaries"] >= MIN_MEASUREMENT_BOUNDARY_COUNT
                and counts["measurement_boundary_members"] >= MIN_MEASUREMENT_BOUNDARY_MEMBER_COUNT
                and counts["boundary_bound_energy_facts"] >= MIN_BOUNDARY_BOUND_ENERGY_FACT_COUNT
                and counts["in_money"] >= MIN_OPERATION_LEDGER_COUNT
                and counts["out_money"] >= MIN_OPERATION_LEDGER_COUNT
                and counts["employee_commute"] >= MIN_OPERATION_LEDGER_COUNT
                and counts["production_products"] >= MIN_PRODUCTION_DATA_COUNT
                and counts["product_prices"] >= MIN_PRODUCTION_DATA_COUNT
                and counts["production_outputs"] >= MIN_PRODUCTION_DATA_COUNT
                and counts["production_resource_bindings"] >= MIN_PRODUCTION_DATA_COUNT
                and counts["product_footprint_studies"] >= MIN_PRODUCT_FOOTPRINT_STUDY_COUNT
                and counts["supply_chain_suppliers"] >= MIN_SUPPLY_CHAIN_SUPPLIER_COUNT
                and counts["supplier_disclosure_tasks"] >= MIN_SUPPLY_CHAIN_SUPPLIER_COUNT
                and counts["category_51_activities"] >= 1
                and counts["reduction_projects"] >= MIN_REDUCTION_PROJECT_COUNT
                and counts["alarm_events"] >= MIN_ALARM_EVENT_COUNT
                and counts["video_alarm_events"] >= MIN_VIDEO_ALARM_EVENT_COUNT
                and required_energy_types_ready
                and energy_type_diagnostics.issue_count == 0
                and legacy_residue_summary["rows_with_residue"] == 0
            )
            steps.append(
                DemoPlanStep(
                    module_key="tenant-dataset",
                    action=DemoAction.VALIDATE,
                    status=DemoStepStatus.COMPLETED if passed else DemoStepStatus.FAILED,
                    summary=f"校验沃衡汽车演示租户数据闭环: {tenant.name}",
                    details={
                        "slug": tenant.slug,
                        "required_equipment": MIN_EQUIPMENT_COUNT,
                        "required_activities": MIN_ACTIVITY_COUNT,
                        "required_reports": MIN_REPORT_COUNT,
                        "required_mqtt_mappings": MIN_MQTT_MAPPING_COUNT,
                        "required_meter_readings": MIN_METER_READING_COUNT,
                        "required_scope2_aggregates": MIN_SCOPE2_AGGREGATE_COUNT,
                        "required_energy_interval_facts": MIN_ENERGY_INTERVAL_COUNT,
                        "required_energy_interval_types": list(REQUIRED_ENERGY_INTERVAL_TYPES),
                        "energy_interval_type_counts": energy_interval_type_counts,
                        "required_workload_facts": MIN_WORKLOAD_COUNT,
                        "required_benchmark_items": MIN_BENCHMARK_ITEM_COUNT,
                        "required_policy_benchmark_profiles": MIN_POLICY_BENCHMARK_PROFILE_COUNT,
                        "required_equipment_efficiency_items": MIN_EQUIPMENT_EFFICIENCY_ITEM_COUNT,
                        "required_equipment_efficiency_devices": MIN_EQUIPMENT_EFFICIENCY_DEVICE_COUNT,
                        "required_measurement_boundaries": MIN_MEASUREMENT_BOUNDARY_COUNT,
                        "required_measurement_boundary_members": MIN_MEASUREMENT_BOUNDARY_MEMBER_COUNT,
                        "required_boundary_bound_energy_facts": MIN_BOUNDARY_BOUND_ENERGY_FACT_COUNT,
                        "required_operation_ledger_rows": MIN_OPERATION_LEDGER_COUNT,
                        "required_production_data_rows": MIN_PRODUCTION_DATA_COUNT,
                        "required_product_footprint_studies": MIN_PRODUCT_FOOTPRINT_STUDY_COUNT,
                        "required_supply_chain_suppliers": MIN_SUPPLY_CHAIN_SUPPLIER_COUNT,
                        "required_reduction_projects": MIN_REDUCTION_PROJECT_COUNT,
                        "required_alarm_events": MIN_ALARM_EVENT_COUNT,
                        "required_video_alarm_events": MIN_VIDEO_ALARM_EVENT_COUNT,
                        "energy_type_issues": energy_type_diagnostics.issue_count,
                        "legacy_residue_rows": legacy_residue_summary["rows_with_residue"],
                        "legacy_residue_samples": legacy_residue_summary["samples"],
                        **counts,
                    },
                )
            )
        status = (
            DemoStepStatus.COMPLETED
            if all(step.status == DemoStepStatus.COMPLETED for step in steps)
            else DemoStepStatus.FAILED
        )
        return self._result(context, DemoAction.VALIDATE, False, status, steps)

    async def _cleanup(self, context: DemoExecutionContext) -> DemoRunResult:
        planned = [
            DemoPlanStep(
                module_key="tenant",
                action=DemoAction.CLEANUP,
                status=DemoStepStatus.PLANNED,
                summary="删除 manifest 登记的沃衡汽车演示租户及其级联业务数据",
                details={"namespace": context.namespace, "tenants": [tenant.slug for tenant in TENANTS]},
            )
        ]
        if not context.apply:
            return self._result(context, DemoAction.CLEANUP, False, DemoStepStatus.PLANNED, planned)

        rows = list(
            (
                await self._session.scalars(
                    select(m.DemoManifest).where(
                        m.DemoManifest.namespace == context.namespace,
                        m.DemoManifest.package_key == context.package_key,
                        m.DemoManifest.object_type == "team",
                    )
                )
            ).all()
        )
        deleted = 0
        self._session.info[TENANT_BYPASS_SESSION_KEY] = True
        for row in rows:
            if row.object_id is None:
                continue
            team = await self._session.get(Team, row.object_id)
            if team is not None:
                await self._session.delete(team)
                deleted += 1
        await self._session.execute(
            delete(m.DemoManifest).where(
                m.DemoManifest.namespace == context.namespace,
                m.DemoManifest.package_key == context.package_key,
            )
        )
        await self._session.commit()
        self._session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        return self._result(
            context,
            DemoAction.CLEANUP,
            True,
            DemoStepStatus.COMPLETED,
            [
                DemoPlanStep(
                    module_key="tenant",
                    action=DemoAction.CLEANUP,
                    status=DemoStepStatus.COMPLETED,
                    summary="已清理 manifest 登记的沃衡汽车演示租户",
                    details={"deleted_teams": deleted},
                )
            ],
        )

    def _install_steps(self, status: DemoStepStatus) -> list[DemoPlanStep]:
        return [
            DemoPlanStep(
                module_key="energy-types",
                action=DemoAction.INSTALL,
                status=status,
                summary="初始化标准能源品种与单位换算字典",
                details={"dictionary": "dataapp_energytype"},
            ),
            DemoPlanStep(
                module_key="tenant",
                action=DemoAction.INSTALL,
                status=status,
                summary="创建两个沃衡汽车演示子租户并授权标准演示账号访问",
                details={"tenants": [tenant.slug for tenant in TENANTS], "brand": WOHENG_BRAND_NAME},
            ),
            DemoPlanStep(
                module_key="dataset",
                action=DemoAction.INSTALL,
                status=status,
                summary="安装组织碳、能源、监测告警、减排、碳价模拟和报告演示数据",
                details={"source": "ShowcaseDemoBuilder", "profile": "transition"},
            ),
            DemoPlanStep(
                module_key="mqtt",
                action=DemoAction.INSTALL,
                status=status,
                summary="为泰州和湖州写入完整且差异化的 MQTT 数据源、订阅、设备绑定和点位映射",
                details={"taizhou": "full", "huzhou": "full"},
            ),
        ]

    async def _ensure_standard_accounts(self) -> dict[str, User]:
        self._session.info[TENANT_BYPASS_SESSION_KEY] = True
        users: dict[str, User] = {}
        verified_at = datetime.now(UTC).date()
        for account in STANDARD_ACCOUNTS:
            user = await self._session.scalar(select(User).where(User.email == account.email))
            if user is None:
                user = User(email=account.email)
                self._session.add(user)
                await self._session.flush()

            conflicting_username_user = await self._session.scalar(
                select(User).where(User.username == account.username, User.email != account.email)
            )
            if conflicting_username_user is not None:
                conflicting_username_user.username = None

            user.name = account.name
            user.username = account.username
            user.hashed_password = await get_password_hash(self._account_password(account))
            user.is_active = True
            user.is_verified = True
            user.verified_at = verified_at
            user.is_superuser = account.is_superuser
            user.is_two_factor_enabled = False
            user.totp_secret = None
            user.backup_codes = None
            users[account.email] = user
        await self._ensure_default_user_role(users.values())
        await self._session.commit()
        return users

    async def _ensure_default_user_role(self, users: Sequence[User]) -> None:
        role = await self._session.scalar(
            select(m.Role).where(or_(m.Role.slug == "application-access", m.Role.name == constants.DEFAULT_ACCESS_ROLE))
        )
        if role is None:
            return
        await self._ensure_demo_role_permissions(role)
        for user in users:
            has_role = await self._session.scalar(
                select(m.UserRole.id).where(m.UserRole.user_id == user.id, m.UserRole.role_id == role.id)
            )
            if has_role is None:
                self._session.add(m.UserRole(user_id=user.id, role_id=role.id))

    async def _ensure_demo_role_permissions(self, role: m.Role) -> None:
        for code, name, description, module in WOHENG_DEMO_PERMISSION_SPECS:
            permission = await self._session.scalar(select(m.Permission).where(m.Permission.code == code))
            if permission is None:
                permission = m.Permission(code=code, name=name, description=description, module=module)
                self._session.add(permission)
                await self._session.flush()
            has_permission = await self._session.scalar(
                select(m.RolePermission.id).where(
                    m.RolePermission.role_id == role.id,
                    m.RolePermission.permission_id == permission.id,
                )
            )
            if has_permission is None:
                self._session.add(m.RolePermission(role_id=role.id, permission_id=permission.id))

    async def _ensure_standard_account_memberships(self) -> None:
        self._session.info[TENANT_BYPASS_SESSION_KEY] = True
        teams = list((await self._session.scalars(select(Team).order_by(Team.name))).all())
        teams_by_slug = {team.slug: team for team in teams}
        woheng_slugs = {tenant.slug for tenant in TENANTS}
        users_by_email = {
            user.email: user
            for user in (
                await self._session.scalars(select(User).where(User.email.in_(self._standard_account_emails)))
            ).all()
        }

        for account in STANDARD_ACCOUNTS:
            user = users_by_email.get(account.email)
            if user is None:
                continue
            desired_teams = teams if account.team_scope == "all" else [teams_by_slug[slug] for slug in woheng_slugs]
            desired_team_ids = {team.id for team in desired_teams}
            await self._session.execute(
                delete(TeamMember).where(TeamMember.user_id == user.id, TeamMember.team_id.not_in(desired_team_ids))
            )
            existing_memberships = list(
                (await self._session.scalars(select(TeamMember).where(TeamMember.user_id == user.id))).all()
            )
            existing_by_team_id = {membership.team_id: membership for membership in existing_memberships}
            for team in desired_teams:
                membership = existing_by_team_id.get(team.id)
                if membership is None:
                    membership = TeamMember(team_id=team.id, user_id=user.id)
                    self._session.add(membership)
                membership.role = TeamRoles.ADMIN
                membership.is_owner = account.is_owner
        await self._session.commit()

    async def _ensure_team(self, tenant: WohengTenantSpec) -> Team:
        self._session.info[TENANT_BYPASS_SESSION_KEY] = True
        team = await self._find_team(tenant.slug)
        if team is None:
            team = Team(
                slug=tenant.slug,
                name=tenant.name,
                description=f"{WOHENG_SOURCE_NAME}; {tenant.role}。",
                is_active=True,
            )
            self._session.add(team)
            await self._session.flush()
        else:
            team.name = tenant.name
            team.description = f"{WOHENG_SOURCE_NAME}; {tenant.role}。"
            team.is_active = True
        admin = await self._session.scalar(select(User).where(User.email == "admin@example.com"))
        if admin is not None:
            membership = await self._session.scalar(
                select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == admin.id)
            )
            if membership is None:
                self._session.add(TeamMember(team_id=team.id, user_id=admin.id, role=TeamRoles.ADMIN, is_owner=True))
        await self._session.commit()
        return team

    def _has_base_showcase_dataset(self, counts: dict[str, int]) -> bool:
        return (
            counts["equipment"] >= MIN_EQUIPMENT_COUNT
            and counts["activities"] >= MIN_ACTIVITY_COUNT
            and counts["reports"] >= MIN_REPORT_COUNT
        )

    def _inventory_code_for_year(self, tenant: WohengTenantSpec, year: int) -> str:
        return f"WOHENG-{tenant.city_code}-INV-{year}"

    async def _synchronize_bigint_sequences(self) -> None:
        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        await self._session.execute(
            text(
                """
                do $$
                declare
                    seq record;
                begin
                    perform set_config('app.tenant_bypass', 'true', true);
                    for seq in
                        select distinct
                            discovered.table_schema,
                            discovered.table_name,
                            discovered.sequence_name
                        from (
                            select
                                table_ns.nspname as table_schema,
                                table_cls.relname as table_name,
                                format('%I.%I', sequence_ns.nspname, sequence_cls.relname) as sequence_name
                            from pg_class sequence_cls
                            join pg_namespace sequence_ns on sequence_ns.oid = sequence_cls.relnamespace
                            join pg_depend dep on dep.objid = sequence_cls.oid and dep.deptype = 'a'
                            join pg_class table_cls on table_cls.oid = dep.refobjid
                            join pg_namespace table_ns on table_ns.oid = table_cls.relnamespace
                            join pg_attribute attr on attr.attrelid = table_cls.oid and attr.attnum = dep.refobjsubid
                            where sequence_cls.relkind = 'S'
                              and table_ns.nspname = 'public'
                              and attr.attname = 'id'
                            union all
                            select
                                table_columns.table_schema,
                                table_columns.table_name,
                                format('%I.%I', sequence_ns.nspname, sequence_cls.relname) as sequence_name
                            from information_schema.columns table_columns
                            join pg_namespace sequence_ns on sequence_ns.nspname = table_columns.table_schema
                            join pg_class sequence_cls
                              on sequence_cls.relnamespace = sequence_ns.oid
                             and sequence_cls.relkind = 'S'
                             and sequence_cls.relname = table_columns.table_name || '_id_seq'
                            where table_columns.table_schema = 'public'
                              and table_columns.column_name = 'id'
                        ) discovered
                    loop
                        execute format(
                            'select setval(%L, greatest((select coalesce(max(id), 0) from %I.%I), 1), true)',
                            seq.sequence_name,
                            seq.table_schema,
                            seq.table_name
                        );
                    end loop;
                    perform set_config('app.tenant_bypass', 'false', true);
                end $$;
                """
            )
        )

    async def _find_team(self, slug: str) -> Team | None:
        return await self._session.scalar(select(Team).where(Team.slug == slug))

    async def _specialize_tenant(self, tenant: WohengTenantSpec, *, team_id: UUID) -> dict[str, int]:
        enterprise = await self._session.scalar(
            select(m.EnterpriseInfo).where(m.EnterpriseInfo.unify_code == "DEMO91320000PARK2026X")
        )
        if enterprise is not None:
            enterprise.name = tenant.enterprise_name
            enterprise.belong_unit = WOHENG_COMPANY_NAME
            enterprise.unify_code = tenant.enterprise_code
            enterprise.location = tenant.location
            enterprise.industry = "汽车整车及零部件制造"
            enterprise.other_info = {
                **dict(enterprise.other_info or {}),
                "demoPackage": WOHENG_PACKAGE_KEY,
                "namespace": WOHENG_NAMESPACE,
                "tenantRole": tenant.role,
                "brand": WOHENG_BRAND_NAME,
                "englishBrand": WOHENG_ENGLISH_BRAND_NAME,
                "companyAddress": WOHENG_COMPANY_ADDRESS,
                "enterpriseEmail": WOHENG_COMPANY_EMAIL,
                "enterpriseWebsite": WOHENG_COMPANY_WEBSITE,
                "contactName": WOHENG_COMPANY_CONTACT,
                "contactEmail": WOHENG_COMPANY_CONTACT_EMAIL,
            }

        await self._specialize_inventory_identity(tenant, enterprise)
        initial_legacy_repair_summary = await self._normalize_legacy_showcase_residue(tenant)

        root = await self._session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == "ROOT"))
        if root is not None:
            root.name = tenant.name
            root.location_desc = tenant.location
            root.remark = WOHENG_SOURCE_NAME

        equipment_rows = list((await self._session.scalars(select(m.MonitorEquipment))).all())
        for equipment in equipment_rows:
            equipment.owner_unit = tenant.enterprise_name
            equipment.location = tenant.location if equipment.code == "PCC-METER-01" else equipment.location
            if equipment.energy_type in {"electricity", "purchased_electricity"}:
                equipment.protocol = "mqtt"
                equipment.data_acquisition_method = "MQTT电表接入"
                equipment.external_device_id = f"WH-{tenant.city_code}-{equipment.code}"
                equipment.network_env = "MQTT专线网关"

        await self._ensure_equipment_efficiency_master_data()
        await self._ensure_mqtt_config(tenant)
        await self._ensure_metering_data(tenant)
        await seed_energy_analysis_data(self._session)
        await _rebuild_energy_interval_facts(self._session)
        await self._cleanup_energy_activity_residue(tenant)
        await self._ensure_non_meter_energy_interval_facts(tenant)
        await _rebuild_equipment_workload_facts(self._session)
        await self._ensure_energy_balance_boundaries(tenant)
        await self._ensure_energy_benchmark(tenant)
        await sync_policy_benchmark_library(
            self._session,
            ["ndrc-2023", "ndrc-equipment-2024"],
            apply=True,
        )
        await self._ensure_operational_ledgers(tenant)
        await self._ensure_production_denominators(tenant)
        await self._ensure_supply_chain_and_product_footprint(tenant)
        await self._ensure_category_51_activity(tenant)
        await self._ensure_warning_events(tenant)
        await self._ensure_video_alarm_events(tenant)
        legacy_repair_summary = await self._normalize_legacy_showcase_residue(tenant)
        legacy_repair_summary = {
            "rows_repaired": initial_legacy_repair_summary["rows_repaired"] + legacy_repair_summary["rows_repaired"],
            "fields_repaired": initial_legacy_repair_summary["fields_repaired"]
            + legacy_repair_summary["fields_repaired"],
        }
        await self._session.commit()
        await self._record_manifest(
            DemoExecutionContext(
                package_key=WOHENG_PACKAGE_KEY,
                namespace=WOHENG_NAMESPACE,
                profile=WOHENG_PROFILE,
                apply=True,
            ),
            module_key="tenant-specialization",
            object_type="tenant-profile",
            object_key=tenant.slug,
            object_id=str(team_id),
            team_id=team_id,
            details={
                "load_profile": tenant.load_profile,
                "enterprise": tenant.enterprise_name,
                "legacy_showcase_repair": legacy_repair_summary,
            },
        )
        return legacy_repair_summary

    async def _specialize_inventory_identity(
        self, tenant: WohengTenantSpec, enterprise: m.EnterpriseInfo | None
    ) -> None:
        organizations = list((await self._session.scalars(select(m.ReportingOrganization))).all())
        for organization in organizations:
            organization.code = str(self._replace_legacy_brand_text(organization.code, tenant))
            organization.name = tenant.enterprise_name
            organization.enterprise_id = enterprise.id if enterprise is not None else organization.enterprise_id
            organization.legal_entity_code = tenant.enterprise_code
            organization.source_name = WOHENG_SOURCE_NAME
            organization.remark = f"{tenant.name}组织温室气体盘查主体。"

        periods = list((await self._session.scalars(select(m.ReportingPeriod))).all())
        period_year_by_id: dict[int, int] = {}
        for period in periods:
            year = period.period_start.year
            period_year_by_id[period.id] = year
            period.code = str(self._replace_legacy_brand_text(period.code, tenant))
            period.name = f"{tenant.name}{year}年度组织温室气体盘查期"
            period.source_name = WOHENG_SOURCE_NAME
            period.standard_code = "ISO 14064-1"
            period.remark = f"{tenant.name}年度组织碳核算与报告期。"

        boundaries = list((await self._session.scalars(select(m.OrganizationBoundary))).all())
        for boundary in boundaries:
            year = period_year_by_id.get(boundary.period_id, 2026)
            boundary.boundary_no = str(self._replace_legacy_brand_text(boundary.boundary_no, tenant))
            boundary.boundary_name = f"{tenant.name}{year}年度组织边界"
            boundary.source_name = WOHENG_SOURCE_NAME
            boundary.standard_code = "ISO 14064-1"
            boundary.remark = f"{tenant.name}运营控制法组织边界。"
            boundary.operational_boundary = self._replace_legacy_brand_text(boundary.operational_boundary, tenant)

        reports = list((await self._session.scalars(select(m.GhgInventoryReport))).all())
        for report in reports:
            report.inventory_code = str(self._replace_legacy_brand_text(report.inventory_code, tenant))
            report.title = str(self._replace_legacy_brand_text(report.title, tenant))
            if "华东" in report.title or "示范园区" in report.title or "盘查期组织温室气体盘查报告" in report.title:
                year = period_year_by_id.get(report.reporting_period_id, 2026)
                report.title = f"{tenant.name}{year}年度组织温室气体盘查报告"
            elif "组织温室气体盘查报告" in report.title and not report.title.startswith(tenant.name):
                report.title = f"{tenant.name}{report.title}"
            report.content_snapshot = self._replace_legacy_brand_text(report.content_snapshot, tenant)
            report.metrics_snapshot = self._replace_legacy_brand_text(report.metrics_snapshot, tenant)
            report.evidence_snapshot = self._replace_legacy_brand_text(report.evidence_snapshot, tenant)
            report.change_summary = self._replace_legacy_brand_text(report.change_summary, tenant)

    def _replace_legacy_brand_text(self, value: object, tenant: WohengTenantSpec) -> object:
        prefix = f"WOHENG-{tenant.city_code}"
        replacements = {
            "DEMO-PARK": prefix,
            "demo-park": f"woheng-{tenant.city_code.lower()}",
            "2026年奇瑞绿能综合能碳管理平台采购项目": WOHENG_BRAND_NAME,
            "奇瑞绿能": WOHENG_COMPANY_NAME,
            "奇瑞": WOHENG_COMPANY_NAME,
            "中汽信科": WOHENG_COMPANY_NAME,
            "华东绿色仓储能碳平台": WOHENG_BRAND_NAME,
            "绿色仓储能碳平台": WOHENG_BRAND_NAME,
            "华东综合能源示范园区有限公司": tenant.enterprise_name,
            "华东综合能源示范园区运营主体": tenant.enterprise_name,
            "华东综合能源示范园区": tenant.name,
            "华东地区": tenant.location,
            "DEMO91320000PARK2026X": tenant.enterprise_code,
            "综合能碳标准演示数据包V1": WOHENG_SOURCE_NAME,
        }
        if isinstance(value, str):
            result = value
            for source, target in replacements.items():
                result = result.replace(source, target)
            return result
        if isinstance(value, dict):
            return {
                self._replace_legacy_brand_text(key, tenant): self._replace_legacy_brand_text(item, tenant)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._replace_legacy_brand_text(item, tenant) for item in value]
        return value

    def _replace_legacy_inventory_code(self, value: object, tenant: WohengTenantSpec) -> object:
        normalized = self._replace_legacy_brand_text(value, tenant)
        if not isinstance(normalized, str):
            return normalized
        prefix = f"WOHENG-{tenant.city_code}"
        if normalized.startswith(f"{prefix}-RP-"):
            return normalized.replace(f"{prefix}-RP-", f"{prefix}-INV-", 1)
        return normalized

    def _showcase_residue_fields(self) -> tuple[tuple[type[Any], str, tuple[str, ...]], ...]:
        return (
            (
                m.ReportingOrganization,
                "reporting_organization",
                ("code", "name", "legal_entity_code", "source_name", "remark"),
            ),
            (m.ReportingPeriod, "reporting_period", ("code", "name", "source_name", "remark")),
            (
                m.OrganizationBoundary,
                "organization_boundary",
                ("boundary_no", "boundary_name", "operational_boundary", "source_name", "remark"),
            ),
            (
                m.GhgEmissionSource,
                "ghg_emission_source",
                (
                    "inventory_code",
                    "organization_code",
                    "facility_code",
                    "source_code",
                    "source_name",
                    "external_facility_code",
                    "external_facility_name",
                    "source_system",
                    "source_payload",
                ),
            ),
            (
                m.GhgActivityRecord,
                "ghg_activity_record",
                (
                    "record_code",
                    "inventory_code",
                    "organization_code",
                    "facility_code",
                    "source_code",
                    "activity_code",
                    "activity_name",
                    "parameter_set_code",
                    "source_payload",
                    "remarks",
                    "source_system",
                ),
            ),
            (
                m.GhgActivityAllocation,
                "ghg_activity_allocation",
                (
                    "allocation_code",
                    "external_facility_code",
                    "external_facility_name",
                    "area_code_snapshot",
                    "area_name_snapshot",
                    "area_path_snapshot",
                    "equipment_code_snapshot",
                    "equipment_name_snapshot",
                    "source_kind",
                ),
            ),
            (
                m.GhgParameterValue,
                "ghg_parameter_value",
                ("value_code", "source_name", "evidence_code", "measurement_method", "laboratory"),
            ),
            (
                m.GhgParameterAssignment,
                "ghg_parameter_assignment",
                ("source_name", "selection_rule", "snapshot"),
            ),
            (
                m.GhgEvidenceFile,
                "ghg_evidence_file",
                ("evidence_code", "file_name", "document_no", "issuer", "storage_key"),
            ),
            (
                m.GhgEvidenceLink,
                "ghg_evidence_link",
                ("link_code", "record_code", "page_or_cell_reference", "reviewer"),
            ),
            (
                m.GhgImportBatch,
                "ghg_import_batch",
                ("batch_code", "inventory_code", "organization_code", "facility_code", "file_name", "context_snapshot"),
            ),
            (m.GhgImportIssue, "ghg_import_issue", ("field_code", "message", "current_value", "suggestion")),
            (
                m.GhgCalculationRun,
                "ghg_calculation_run",
                ("run_code", "inventory_code", "input_snapshot", "summary_snapshot", "quality_snapshot"),
            ),
            (m.GhgCalculationResult, "ghg_calculation_result", ("formula_snapshot",)),
            (
                m.GhgInventoryReport,
                "ghg_inventory_report",
                (
                    "report_code",
                    "title",
                    "inventory_code",
                    "content_snapshot",
                    "metrics_snapshot",
                    "evidence_snapshot",
                    "change_summary",
                ),
            ),
            (
                m.CarbonVerificationProject,
                "carbon_verification_project",
                (
                    "project_no",
                    "project_name",
                    "verification_basis",
                    "sampling_strategy",
                    "scope_description",
                    "finding_summary",
                    "conclusion",
                    "source_name",
                    "remark",
                ),
            ),
            (
                m.CarbonVerificationFinding,
                "carbon_verification_finding",
                (
                    "finding_no",
                    "record_code",
                    "title",
                    "description",
                    "action_required",
                    "display_name",
                    "correction_evidence",
                    "source_payload",
                    "source_name",
                    "remark",
                ),
            ),
            (
                m.CarbonVerificationTemplateVersion,
                "carbon_verification_template_version",
                ("template_code", "template_name", "template_path", "applicable_scope", "source_name", "remark"),
            ),
            (
                m.CarbonVerificationExportJob,
                "carbon_verification_export_job",
                ("job_no", "export_type", "source_name", "error_message"),
            ),
            (
                m.CarbonVerificationExportFile,
                "carbon_verification_export_file",
                ("file_name", "file_path", "source_name"),
            ),
            (
                m.ReductionTarget,
                "decarbonization_target",
                ("code", "name", "trajectory", "source_name"),
            ),
            (
                m.ReductionProject,
                "decarbonization_project",
                (
                    "code",
                    "name",
                    "objective",
                    "implementation_plan",
                    "evaluation_summary",
                    "source_name",
                ),
            ),
            (
                m.ReductionProjectResourceLink,
                "decarbonization_project_resource_link",
                ("resource_key", "resource_snapshot"),
            ),
            (
                m.ReductionProjectBoundary,
                "decarbonization_project_boundary",
                ("physical_boundary", "ghg_sources_sinks", "exclusions", "organization_snapshot"),
            ),
            (
                m.ReductionBaselineScenario,
                "decarbonization_baseline_scenario",
                ("name", "model_parameters", "factor_snapshot", "inventory_reference"),
            ),
            (
                m.ReductionApplicabilityAssessment,
                "decarbonization_applicability_assessment",
                ("answers", "checks", "blocking_reasons", "methodology_snapshot"),
            ),
            (
                m.ReductionMonitoringPlan,
                "decarbonization_monitoring_plan",
                ("parameters", "quality_controls", "evidence_requirements"),
            ),
            (
                m.ReductionCalculationRun,
                "decarbonization_calculation_run",
                (
                    "idempotency_key",
                    "input_snapshot",
                    "methodology_snapshot",
                    "baseline_snapshot",
                    "factor_snapshot",
                    "components",
                    "diagnostics",
                    "error_message",
                ),
            ),
            (
                m.ReductionProjectReview,
                "decarbonization_project_review",
                ("reviewer_name", "organization_name", "findings", "conclusion"),
            ),
            (
                m.CcerDossier,
                "decarbonization_ccer_dossier",
                (
                    "project_design_document_no",
                    "validation_body",
                    "verification_body",
                    "registration_no",
                    "issuance_no",
                    "material_checklist",
                    "milestones",
                ),
            ),
            (
                m.ReductionAuditEvent,
                "decarbonization_audit_event",
                ("actor_name", "before_snapshot", "after_snapshot", "reason"),
            ),
            (
                m.ClimateProgram,
                "climate_governance_program",
                ("code", "name", "configuration", "source_name"),
            ),
            (m.ClimateTarget, "climate_governance_target", ("scope_coverage", "source_name")),
            (
                m.ClimateDisclosureCycle,
                "climate_governance_disclosure_cycle",
                ("owner_name", "domain_statuses", "response_snapshot", "evidence_snapshot"),
            ),
            (
                m.RenewableElectricityClaim,
                "climate_governance_renewable_claim",
                ("claim_no", "certificate_no", "eligibility_reasons", "evidence_reference", "source_name", "remark"),
            ),
            (
                m.ClimateAssessmentRun,
                "climate_governance_assessment_run",
                ("idempotency_key", "input_snapshot", "rule_snapshot", "metrics_snapshot", "checks"),
            ),
            (
                m.CarbonAssetInstrument,
                "carbon_asset_instrument",
                ("code", "name", "registry", "source_name", "source_url"),
            ),
            (
                m.CarbonAssetAccount,
                "carbon_asset_account",
                ("account_code", "account_name", "registry_account_no", "owner_name", "source_name", "remark"),
            ),
            (
                m.CarbonAssetLot,
                "carbon_asset_lot",
                (
                    "lot_no",
                    "registry_serial_no",
                    "project_code",
                    "project_name",
                    "attributes",
                    "source_name",
                    "evidence_ref",
                    "remark",
                ),
            ),
            (
                m.CarbonAssetMovement,
                "carbon_asset_movement",
                ("movement_no", "counterparty", "source_name", "evidence_ref", "remark"),
            ),
            (
                m.CarbonComplianceRuleVersion,
                "carbon_compliance_rule_version",
                ("rule_code", "rule_name", "parameters", "source_name", "source_url"),
            ),
            (
                m.CarbonComplianceCycle,
                "carbon_compliance_cycle",
                (
                    "cycle_code",
                    "cycle_name",
                    "obligation_source",
                    "obligation_snapshot",
                    "source_name",
                    "evidence_ref",
                    "remark",
                ),
            ),
            (
                m.CarbonComplianceSettlement,
                "carbon_compliance_settlement",
                ("settlement_no", "rule_snapshot", "source_name", "evidence_ref", "remark"),
            ),
            (
                m.EnvironmentalAssetUsage,
                "carbon_environmental_asset_usage",
                ("usage_no", "reporting_period", "evidence_ref", "remark"),
            ),
            (
                m.CarbonCostScenario,
                "carbon_cost_scenario",
                ("scenario_code", "scenario_name", "parameters", "source_name", "remark"),
            ),
            (
                m.CarbonCostRun,
                "carbon_cost_run",
                ("run_no", "input_snapshot", "quote_snapshot", "balance_snapshot", "result_summary", "period_results"),
            ),
        )

    def _has_legacy_showcase_marker(self, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return any(marker in value for marker in LEGACY_SHOWCASE_MARKERS)
        if isinstance(value, dict):
            return any(
                self._has_legacy_showcase_marker(key) or self._has_legacy_showcase_marker(item)
                for key, item in value.items()
            )
        if isinstance(value, list | tuple):
            return any(self._has_legacy_showcase_marker(item) for item in value)
        return False

    async def _normalize_legacy_showcase_residue(self, tenant: WohengTenantSpec) -> dict[str, int]:
        rows_repaired = 0
        fields_repaired = 0
        for model, _label, fields in self._showcase_residue_fields():
            rows = list((await self._session.scalars(select(model))).all())
            for row in rows:
                row_changed = False
                for field in fields:
                    if not hasattr(row, field):
                        continue
                    current = getattr(row, field)
                    if not self._has_legacy_showcase_marker(current):
                        continue
                    if field == "inventory_code":
                        normalized = self._replace_legacy_inventory_code(current, tenant)
                    else:
                        normalized = self._replace_legacy_brand_text(current, tenant)
                    if normalized != current:
                        setattr(row, field, normalized)
                        fields_repaired += 1
                        row_changed = True
                if row_changed:
                    rows_repaired += 1
        return {"rows_repaired": rows_repaired, "fields_repaired": fields_repaired}

    async def _legacy_residue_summary(self) -> dict[str, Any]:
        rows_with_residue = 0
        samples: dict[str, list[str]] = {}
        for model, label, fields in self._showcase_residue_fields():
            rows = list((await self._session.scalars(select(model))).all())
            model_samples: list[str] = []
            for row in rows:
                dirty_fields = [
                    field
                    for field in fields
                    if hasattr(row, field) and self._has_legacy_showcase_marker(getattr(row, field))
                ]
                if not dirty_fields:
                    continue
                rows_with_residue += 1
                if len(model_samples) < LEGACY_RESIDUE_SAMPLE_LIMIT:
                    row_id = getattr(row, "id", "unknown")
                    model_samples.append(f"{row_id}:{','.join(dirty_fields)}")
            if model_samples:
                samples[label] = model_samples
        return {"rows_with_residue": rows_with_residue, "samples": samples}

    async def _ensure_mqtt_config(self, tenant: WohengTenantSpec) -> None:
        source_code = f"WH-MQTT-{tenant.slug.upper().replace('-', '_')}"
        source = await self._session.scalar(select(m.MqttDataSource).where(m.MqttDataSource.code == source_code))
        if source is None:
            source = m.MqttDataSource(
                code=source_code,
                name=f"{tenant.name} MQTT采集网关",
                broker_host="mqtt.woheng-demo.local",
                broker_port=1883,
                username_env="WOHENG_DEMO_MQTT_USERNAME",
                password_env="WOHENG_DEMO_MQTT_PASSWORD",  # noqa: S106 - stores an environment variable name.
                client_id=f"{tenant.slug}-collector",
                tls_enabled=False,
                enabled=True,
            )
            self._session.add(source)
            await self._session.flush()

        subscription = await self._session.scalar(
            select(m.MqttSubscription).where(
                m.MqttSubscription.source_id == source.id,
                m.MqttSubscription.topic_filter == f"woheng/{tenant.slug}/meters/+/telemetry",
            )
        )
        if subscription is None:
            subscription = m.MqttSubscription(
                source_id=source.id,
                topic_filter=f"woheng/{tenant.slug}/meters/+/telemetry",
                parser_code="szscada_scada_v1",
                contract_version="v1",
                qos=1,
                expected_interval_seconds=300,
                enabled=True,
            )
            self._session.add(subscription)
            await self._session.flush()

        equipment_codes = ["PCC-METER-01", "LIGHTING-01", "CHILLER-01", "CONVEYOR-01", "ASRS-01", "EVSE-GROUP-01"]
        equipment_rows = {
            row.code: row
            for row in (
                await self._session.scalars(
                    select(m.MonitorEquipment).where(m.MonitorEquipment.code.in_(equipment_codes))
                )
            ).all()
        }
        for index, code in enumerate(equipment_codes, start=1):
            equipment = equipment_rows.get(code)
            if equipment is None:
                continue
            meter_key = f"m{index:03d}"
            binding = await self._session.scalar(
                select(m.MqttDeviceBinding).where(
                    m.MqttDeviceBinding.subscription_id == subscription.id,
                    m.MqttDeviceBinding.gateway_key == "WH-GW-01",
                    m.MqttDeviceBinding.meter_key == meter_key,
                )
            )
            if binding is None:
                binding = await self._session.scalar(
                    select(m.MqttDeviceBinding).where(
                        m.MqttDeviceBinding.subscription_id == subscription.id,
                        m.MqttDeviceBinding.gateway_key == "WH-GW-01",
                        m.MqttDeviceBinding.equipment_id == equipment.id,
                    )
                )
            if binding is None:
                binding = m.MqttDeviceBinding(
                    subscription_id=subscription.id,
                    gateway_key="WH-GW-01",
                    meter_key=meter_key,
                    selector_name_pattern=f"{equipment.name or code}*",
                    equipment_id=equipment.id,
                    external_device_id=equipment.external_device_id or f"WH-{code}",
                    temporary_address=f"{index:03d}",
                    identity_status="confirmed",
                    scaling_mode="upstream_scaled",
                    multiplier=Decimal(1),
                )
                self._session.add(binding)
                await self._session.flush()
            else:
                binding.meter_key = meter_key
                binding.selector_name_pattern = f"{equipment.name or code}*"
                binding.equipment_id = equipment.id
                binding.external_device_id = equipment.external_device_id or f"WH-{code}"
                binding.temporary_address = f"{index:03d}"
                binding.identity_status = "confirmed"
                binding.scaling_mode = "upstream_scaled"
                binding.multiplier = Decimal(1)
            await self._ensure_mqtt_points(equipment, binding)

    async def _ensure_mqtt_points(self, equipment: m.MonitorEquipment, binding: m.MqttDeviceBinding) -> None:
        for source_tag, point_code, point_name, unit in (
            ("EPI", "forward_active_total", "正向有功总电能", "kWh"),
            ("P", "active_power", "有功功率", "kW"),
        ):
            mapping = await self._session.scalar(
                select(m.MqttPointMapping).where(
                    m.MqttPointMapping.binding_id == binding.id,
                    m.MqttPointMapping.source_tag == source_tag,
                    m.MqttPointMapping.mapping_version == "v1",
                )
            )
            if mapping is None:
                mapping = m.MqttPointMapping(
                    binding_id=binding.id,
                    source_tag=source_tag,
                    source_name_suffix=point_name,
                    point_code=point_code,
                    point_name=point_name,
                    unit=unit,
                    multiplier=Decimal(1),
                    mapping_version="v1",
                    enabled=True,
                )
                self._session.add(mapping)
            else:
                mapping.source_name_suffix = point_name
                mapping.point_code = point_code
                mapping.point_name = point_name
                mapping.unit = unit
                mapping.multiplier = Decimal(1)
                mapping.enabled = True

            device_point = await self._session.scalar(
                select(m.DevicePoint).where(
                    m.DevicePoint.device_id == equipment.id,
                    m.DevicePoint.point_code == point_code,
                )
            )
            if device_point is None:
                device_point = m.DevicePoint(
                    device_id=equipment.id,
                    point_code=point_code,
                    point_name=point_name,
                    unit=unit,
                    value_type="float",
                    source_field=source_tag,
                    sampling_interval_seconds=300,
                    is_enabled=True,
                    is_alarm_enabled=source_tag == "P",
                )
                self._session.add(device_point)
            else:
                device_point.point_name = point_name
                device_point.unit = unit
                device_point.value_type = "float"
                device_point.source_field = source_tag
                device_point.sampling_interval_seconds = 300
                device_point.is_enabled = True
                if source_tag == "P":
                    device_point.is_alarm_enabled = True

    async def _ensure_metering_data(self, tenant: WohengTenantSpec) -> None:
        bindings = list((await self._session.scalars(select(m.MqttDeviceBinding))).all())
        if not bindings:
            return
        equipment_rows = {
            row.id: row
            for row in (
                await self._session.scalars(
                    select(m.MonitorEquipment).where(
                        m.MonitorEquipment.id.in_(
                            [binding.equipment_id for binding in bindings if binding.equipment_id]
                        )
                    )
                )
            ).all()
        }
        sector_ids = [equipment.sector_id for equipment in equipment_rows.values() if equipment.sector_id is not None]
        sectors = {
            row.id: row
            for row in (
                await self._session.scalars(select(m.MonitorSector).where(m.MonitorSector.id.in_(sector_ids)))
            ).all()
        }
        city_factor = Decimal("1.08") if tenant.city_code == "TZ" else Decimal("0.96")
        recent_start = datetime.now(UTC).replace(tzinfo=None, minute=0, second=0, microsecond=0) - timedelta(hours=23)
        fixed_day_start = datetime(2026, 7, 10, tzinfo=UTC).replace(tzinfo=None)
        windows = (fixed_day_start, recent_start)
        aggregate_months = [f"2026-{month:02d}" for month in range(1, 9)]

        for binding_index, binding in enumerate(bindings, start=1):
            equipment = equipment_rows.get(binding.equipment_id or 0)
            if equipment is None:
                continue
            sector = sectors.get(equipment.sector_id)
            base_index = Decimal(12000) + Decimal(binding_index * 850)
            hourly_delta = (Decimal(72) + Decimal(binding_index * 9)) * city_factor
            for window_start in windows:
                for hour in range(24):
                    start_time = window_start + timedelta(hours=hour)
                    end_time = start_time + timedelta(minutes=30)
                    start_value = base_index + Decimal(hour) * hourly_delta
                    end_value = start_value + hourly_delta
                    await self._upsert_meter_reading(
                        tenant=tenant,
                        binding=binding,
                        equipment_id=equipment.id,
                        reading_time=start_time,
                        source_tag="EPI",
                        point_code="forward_active_total",
                        point_name="正向有功总电能",
                        value_kind="register_index",
                        value=start_value,
                        unit="kWh",
                    )
                    await self._upsert_meter_reading(
                        tenant=tenant,
                        binding=binding,
                        equipment_id=equipment.id,
                        reading_time=end_time,
                        source_tag="EPI",
                        point_code="forward_active_total",
                        point_name="正向有功总电能",
                        value_kind="register_index",
                        value=end_value,
                        unit="kWh",
                    )
                    await self._upsert_meter_reading(
                        tenant=tenant,
                        binding=binding,
                        equipment_id=equipment.id,
                        reading_time=start_time + timedelta(minutes=15),
                        source_tag="P",
                        point_code="active_power",
                        point_name="有功功率",
                        value_kind="instantaneous",
                        value=(tenant.peak_power_kw / Decimal(max(len(bindings), 1)))
                        + Decimal(hour % 6) * Decimal("3.2"),
                        unit="kW",
                    )

            for month_index, billing_month in enumerate(aggregate_months, start=1):
                monthly_total = hourly_delta * Decimal(24 + month_index * 5)
                start_total = base_index + Decimal(month_index * 1200)
                await self._upsert_scope2_aggregate(
                    tenant=tenant,
                    equipment=equipment,
                    sector=sector,
                    billing_month=billing_month,
                    start_total=start_total,
                    total_kwh=monthly_total,
                )

    async def _upsert_meter_reading(
        self,
        *,
        tenant: WohengTenantSpec,
        binding: m.MqttDeviceBinding,
        equipment_id: int,
        reading_time: datetime,
        source_tag: str,
        point_code: str,
        point_name: str,
        value_kind: str,
        value: Decimal,
        unit: str,
    ) -> None:
        source_record_id = f"{tenant.slug}:{binding.meter_key}:{source_tag}:{reading_time:%Y%m%d%H%M}"
        reading = await self._session.scalar(
            select(m.MeterReadingFact).where(
                m.MeterReadingFact.source_system == "mqtt_szscada",
                m.MeterReadingFact.source_record_id == source_record_id,
                m.MeterReadingFact.equipment_id == equipment_id,
                m.MeterReadingFact.point_code == point_code,
                m.MeterReadingFact.value_kind == value_kind,
            )
        )
        if reading is None:
            reading = m.MeterReadingFact(
                source_system="mqtt_szscada",
                source_record_id=source_record_id,
                binding_id=binding.id,
                equipment_id=equipment_id,
                source_point_code=source_tag,
                source_point_name=point_name,
                point_code=point_code,
                point_name=point_name,
                energy_direction="import",
                energy_kind="electricity",
                tou_period="flat",
                value_kind=value_kind,
                raw_value=str(round(value, 4)),
                normalized_value=value,
                unit=unit,
                quality_status="valid",
                source_type=1,
                reading_time=reading_time,
                mapping_version="v1",
            )
            self._session.add(reading)
        else:
            reading.binding_id = binding.id
            reading.source_point_code = source_tag
            reading.source_point_name = point_name
            reading.point_name = point_name
            reading.raw_value = str(round(value, 4))
            reading.normalized_value = value
            reading.unit = unit
            reading.quality_status = "valid"
            reading.reading_time = reading_time

    async def _upsert_scope2_aggregate(
        self,
        *,
        tenant: WohengTenantSpec,
        equipment: m.MonitorEquipment,
        sector: m.MonitorSector | None,
        billing_month: str,
        start_total: Decimal,
        total_kwh: Decimal,
    ) -> None:
        aggregate = await self._session.scalar(
            select(m.Scope2MeterAggregate).where(
                m.Scope2MeterAggregate.ammeter_id == equipment.code,
                m.Scope2MeterAggregate.billing_month == billing_month,
                m.Scope2MeterAggregate.is_current.is_(True),
            )
        )
        end_total = start_total + total_kwh
        if aggregate is None:
            aggregate = m.Scope2MeterAggregate(
                source_kind="meter_aggregate",
                ammeter_id=equipment.code,
                ammeter_name=equipment.name,
                area_id=str(sector.id) if sector is not None else None,
                area_name=sector.name if sector is not None else None,
                billing_month=billing_month,
                first_reading_time=datetime.fromisoformat(f"{billing_month}-01T00:00:00"),
                last_reading_time=datetime.fromisoformat(f"{billing_month}-28T23:59:59"),
                start_total_energy=start_total,
                end_total_energy=end_total,
                total_kwh=total_kwh,
                status="approved",
                approved_at=datetime.fromisoformat(f"{billing_month}-28T23:59:59"),
                calc_status="ready",
                factor_source=WOHENG_SOURCE_NAME,
                factor_year=2026,
                factor_unit="kgCO2e/kWh",
                activity_amount=total_kwh,
                activity_unit="kWh",
                computed_co2e=total_kwh * Decimal("0.5703"),
                computation_note="演示包按电表月度差值形成Scope 2用电活动量。",
                aggregation_note=f"{tenant.name}演示月度电量汇总。",
                revision_no=1,
                is_current=True,
                source_snapshot={
                    "demoPackage": WOHENG_PACKAGE_KEY,
                    "tenantSlug": tenant.slug,
                    "source": "MQTT电表读数演示事实",
                },
            )
            self._session.add(aggregate)
        else:
            aggregate.ammeter_name = equipment.name
            aggregate.area_id = str(sector.id) if sector is not None else None
            aggregate.area_name = sector.name if sector is not None else None
            aggregate.start_total_energy = start_total
            aggregate.end_total_energy = end_total
            aggregate.total_kwh = total_kwh
            aggregate.status = "approved"
            aggregate.calc_status = "ready"
            aggregate.activity_amount = total_kwh
            aggregate.computed_co2e = total_kwh * Decimal("0.5703")
            aggregate.source_snapshot = {
                "demoPackage": WOHENG_PACKAGE_KEY,
                "tenantSlug": tenant.slug,
                "source": "MQTT电表读数演示事实",
            }

    async def _cleanup_energy_activity_residue(self, tenant: WohengTenantSpec) -> None:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return
        await self._session.execute(
            text(
                """
                delete from ghg_activity_allocation
                where team_id = :team_id
                  and activity_id in (
                    select id
                    from ghg_activity_record
                    where team_id = :team_id
                      and (
                        record_code like 'MANUAL-GHG-%'
                        or record_code like 'GEN-WOHENG-%'
                        or activity_code in ('manual-activity', 'energy_interval_fact')
                      )
                  )
                """
            ),
            {"team_id": str(team_id)},
        )
        await self._session.execute(
            text(
                """
                delete from ghg_activity_record
                where team_id = :team_id
                  and (
                    record_code like 'MANUAL-GHG-%'
                    or record_code like 'GEN-WOHENG-%'
                    or activity_code in ('manual-activity', 'energy_interval_fact')
                  )
                """
            ),
            {"team_id": str(team_id)},
        )
        await self._session.execute(
            text(
                """
                delete from ghg_emission_source
                where team_id = :team_id
                  and source_code like 'MANUAL-GHG-SRC-%'
                """
            ),
            {"team_id": str(team_id)},
        )

    async def _ensure_non_meter_energy_interval_facts(self, tenant: WohengTenantSpec) -> None:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return
        await self._session.execute(
            text(
                """
                delete from dataapp_energyintervalfact
                where team_id = :team_id
                  and source_system in ('scope2_meter_monthly', 'demo_ghg_activity_monthly', 'demo_ghg_activity_daily', 'demo_showcase')
                """
            ),
            {"team_id": str(team_id)},
        )
        await self._session.execute(
            text(
                """
                insert into dataapp_energyintervalfact (
                    team_id,
                    source_system,
                    source_record_id,
                    energy_type_code,
                    equipment_id,
                    equipment_code,
                    equipment_name,
                    area_id,
                    area_name,
                    use_system_code,
                    use_system_name,
                    granularity,
                    period_start,
                    period_end,
                    amount,
                    unit,
                    cost_cny,
                    tariff_segment_type,
                    reading_count,
                    data_quality,
                    remark,
                    revision_no,
                    is_current,
                    source_snapshot,
                    created_at,
                    updated_at
                )
                select
                    aggregate.team_id,
                    'scope2_meter_monthly',
                    'scope2_meter_aggregate:' || aggregate.id::text,
                    'purchased_electricity',
                    equipment.id,
                    aggregate.ammeter_id,
                    aggregate.ammeter_name,
                    aggregate.area_id,
                    aggregate.area_name,
                    binding.system_code,
                    system.name,
                    'month',
                    aggregate.first_reading_time,
                    aggregate.last_reading_time,
                    aggregate.total_kwh,
                    'kWh',
                    (aggregate.total_kwh * 0.82)::numeric(18, 6),
                    null,
                    null,
                    'measured',
                    '由电表月度汇总生成外购电力月度能源事实。',
                    1,
                    true,
                    (coalesce(aggregate.source_snapshot::jsonb, '{}'::jsonb) ||
                        jsonb_build_object(
                            'demoPackage', cast(:package_key as text),
                            'tenantSlug', cast(:tenant_slug as text),
                            'sourceName', cast(:source_name as text)
                        ))::json,
                    now(),
                    now()
                from dataapp_scope2meteraggregate aggregate
                left join dataapp_monitorequipment equipment
                  on equipment.team_id = aggregate.team_id
                 and equipment.code = aggregate.ammeter_id
                left join dataapp_energyusesystembinding binding
                  on binding.team_id = aggregate.team_id
                 and binding.equipment_id = equipment.id
                 and binding.is_primary = true
                left join dataapp_energyusesystem system
                  on system.team_id = aggregate.team_id
                 and system.code = binding.system_code
                where aggregate.team_id = :team_id
                  and aggregate.is_current = true
                  and aggregate.calc_status in ('ready', 'missing_factor')
                  and aggregate.total_kwh is not null
                """
            ),
            {
                "team_id": str(team_id),
                "package_key": WOHENG_PACKAGE_KEY,
                "tenant_slug": tenant.slug,
                "source_name": WOHENG_SOURCE_NAME,
            },
        )
        await self._session.execute(
            text(
                """
                with activity_energy as (
                    select
                        activity.*,
                        coalesce(
                            activity.source_payload ->> 'energy_type_code',
                            activity.source_payload ->> 'fuel_type',
                            case
                                when activity.ghg_scope = 'scope2'
                                 and activity.source_mechanism = 'purchased_energy'
                                then 'purchased_steam'
                                else null
                            end
                        ) as resolved_energy_type_code
                    from ghg_activity_record activity
                    where activity.team_id = :team_id
                      and activity.status = 'approved'
                      and activity.boundary_status = 'included'
                      and activity.ghg_scope in ('scope1', 'scope2')
                ),
                eligible as (
                    select
                        activity.*,
                        energy_type.name as energy_type_name,
                        coalesce(allocation.allocation_code, 'A00') as allocation_code,
                        coalesce(allocation.allocation_ratio, 1)::numeric as allocation_ratio,
                        allocation.area_id,
                        allocation.area_name_snapshot,
                        allocation.equipment_id,
                        allocation.equipment_code_snapshot,
                        allocation.equipment_name_snapshot
                    from activity_energy activity
                    join dataapp_energytype energy_type
                      on energy_type.code = activity.resolved_energy_type_code
                     and energy_type.is_enabled = true
                    left join ghg_activity_allocation allocation
                      on allocation.team_id = activity.team_id
                     and allocation.activity_id = activity.id
                     and allocation.status = 'active'
                    where activity.resolved_energy_type_code <> 'purchased_electricity'
                )
                insert into dataapp_energyintervalfact (
                    team_id,
                    source_system,
                    source_record_id,
                    energy_type_code,
                    equipment_id,
                    equipment_code,
                    equipment_name,
                    area_id,
                    area_name,
                    use_system_code,
                    use_system_name,
                    granularity,
                    period_start,
                    period_end,
                    amount,
                    unit,
                    cost_cny,
                    tariff_segment_type,
                    reading_count,
                    data_quality,
                    remark,
                    revision_no,
                    is_current,
                    source_snapshot,
                    created_at,
                    updated_at
                )
                select
                    team_id,
                    'demo_ghg_activity_monthly',
                    'ghg_activity:' || record_code || ':' || allocation_code,
                    resolved_energy_type_code,
                    equipment_id,
                    equipment_code_snapshot,
                    equipment_name_snapshot,
                    area_id::text,
                    area_name_snapshot,
                    case resolved_energy_type_code
                        when 'natural_gas' then 'thermal_power'
                        when 'diesel' then 'mobile_equipment'
                        when 'gasoline' then 'mobile_equipment'
                        when 'fuel_oil' then 'thermal_power'
                        when 'purchased_steam' then 'thermal_power'
                        when 'refrigerant' then 'cold_chain'
                        else 'other_energy'
                    end,
                    case resolved_energy_type_code
                        when 'natural_gas' then '热力动力系统'
                        when 'diesel' then '移动装备与备用电源'
                        when 'gasoline' then '移动装备与备用电源'
                        when 'fuel_oil' then '热力动力系统'
                        when 'purchased_steam' then '热力动力系统'
                        when 'refrigerant' then '冷链制冷系统'
                        else '其他用能系统'
                    end,
                    'month',
                    period_start::timestamp,
                    period_end::timestamp + interval '1 day' - interval '1 second',
                    (activity_amount * allocation_ratio)::numeric(18, 6),
                    activity_unit,
                    case resolved_energy_type_code
                        when 'natural_gas' then (activity_amount * allocation_ratio * 3.20)::numeric(18, 6)
                        when 'diesel' then (activity_amount * allocation_ratio * 7.10)::numeric(18, 6)
                        when 'gasoline' then (activity_amount * allocation_ratio * 7.40)::numeric(18, 6)
                        when 'fuel_oil' then (activity_amount * allocation_ratio * 6.30)::numeric(18, 6)
                        when 'purchased_steam' then (activity_amount * allocation_ratio * 220.00)::numeric(18, 6)
                        else null::numeric
                    end,
                    null,
                    null,
                    case
                        when data_source_type = 'system_generated' then 'generated'
                        when source_mechanism in ('metered_energy', 'purchased_energy') then 'generated'
                        else 'imported'
                    end,
                    '由组织碳活动数据同步形成非电表能源月度事实。',
                    1,
                    true,
                    jsonb_build_object(
                        'demoPackage', cast(:package_key as text),
                        'tenantSlug', cast(:tenant_slug as text),
                        'activityRecord', record_code,
                        'sourceName', cast(:source_name as text)
                    ),
                    now(),
                    now()
                from eligible
                """
            ),
            {
                "team_id": str(team_id),
                "package_key": WOHENG_PACKAGE_KEY,
                "tenant_slug": tenant.slug,
                "source_name": WOHENG_SOURCE_NAME,
            },
        )
        await self._session.execute(
            text(
                """
                with monthly as (
                    select
                        fact.*,
                        greatest((fact.period_end::date - fact.period_start::date + 1), 1)::numeric as day_count
                    from dataapp_energyintervalfact fact
                    where fact.team_id = :team_id
                      and fact.source_system = 'demo_ghg_activity_monthly'
                      and fact.granularity = 'month'
                      and fact.is_current = true
                ),
                daily as (
                    select
                        monthly.*,
                        day_bucket::timestamp as day_start
                    from monthly
                    cross join lateral generate_series(
                        monthly.period_start::date,
                        monthly.period_end::date,
                        interval '1 day'
                    ) as day_bucket
                )
                insert into dataapp_energyintervalfact (
                    team_id,
                    source_system,
                    source_record_id,
                    energy_type_code,
                    equipment_id,
                    equipment_code,
                    equipment_name,
                    area_id,
                    area_name,
                    use_system_code,
                    use_system_name,
                    granularity,
                    period_start,
                    period_end,
                    amount,
                    unit,
                    cost_cny,
                    tariff_segment_type,
                    reading_count,
                    data_quality,
                    remark,
                    revision_no,
                    is_current,
                    source_snapshot,
                    created_at,
                    updated_at
                )
                select
                    team_id,
                    'demo_ghg_activity_daily',
                    replace(source_record_id, 'ghg_activity:', 'ghg_activity_daily:') || ':' || to_char(day_start, 'YYYYMMDD'),
                    energy_type_code,
                    equipment_id,
                    equipment_code,
                    equipment_name,
                    area_id,
                    area_name,
                    use_system_code,
                    use_system_name,
                    'day',
                    day_start,
                    day_start + interval '1 day',
                    (amount / day_count)::numeric(18, 6),
                    unit,
                    case when cost_cny is null then null else (cost_cny / day_count)::numeric(18, 6) end,
                    tariff_segment_type,
                    null,
                    data_quality,
                    '由组织碳活动月度能源事实按自然日展开。',
                    1,
                    true,
                    source_snapshot,
                    now(),
                    now()
                from daily
                """
            ),
            {"team_id": str(team_id)},
        )

    async def _ensure_energy_balance_boundaries(self, tenant: WohengTenantSpec) -> None:
        equipment_codes = ["PCC-METER-01", "LIGHTING-01", "CHILLER-01", "CONVEYOR-01", "ASRS-01", "EVSE-GROUP-01"]
        equipment_rows = {
            row.code: row
            for row in (
                await self._session.scalars(
                    select(m.MonitorEquipment).where(m.MonitorEquipment.code.in_(equipment_codes))
                )
            ).all()
        }
        sector_rows = {row.code: row for row in (await self._session.scalars(select(m.MonitorSector))).all()}
        pcc = equipment_rows.get("PCC-METER-01")
        root = sector_rows.get("ROOT")
        if pcc is None or root is None:
            return

        site_boundary = await self._upsert_measurement_boundary(
            code=f"WH-{tenant.city_code}-SITE-ELECTRICITY",
            name=f"{tenant.name}外购电力计量边界",
            boundary_type="site",
            meter_equipment_id=pcc.id,
            sector_id=root.id,
            use_system_code=None,
            remark="基地外购电力总表与分项表计边界, 用于能量平衡计算。",
        )
        member_codes = ["LIGHTING-01", "CHILLER-01", "CONVEYOR-01", "ASRS-01", "EVSE-GROUP-01"]
        for code in member_codes:
            equipment = equipment_rows.get(code)
            if equipment is None:
                continue
            await self._upsert_measurement_boundary_member(
                boundary_id=site_boundary.id,
                member_code=code,
                member_type="equipment",
                equipment_id=equipment.id,
                sector_id=equipment.sector_id,
                member_role="covered",
                remark="纳入基地外购电力边界的确认分项表计。",
            )

        sub_boundary_specs = (
            ("WAREHOUSE", "仓储设施分项计量边界", "ASRS-01", "storage"),
            ("COLD", "冷链制冷分项计量边界", "CHILLER-01", "storage"),
            ("SORTING", "分拣输送分项计量边界", "CONVEYOR-01", "handling"),
            ("CHARGING", "车辆充电分项计量边界", "EVSE-GROUP-01", "charging"),
        )
        for suffix, name, equipment_code, use_system_code in sub_boundary_specs:
            equipment = equipment_rows.get(equipment_code)
            if equipment is None:
                continue
            sub_boundary = await self._upsert_measurement_boundary(
                code=f"WH-{tenant.city_code}-{suffix}-ELECTRICITY",
                name=f"{tenant.name}{name}",
                boundary_type="sub_boundary",
                meter_equipment_id=equipment.id,
                sector_id=equipment.sector_id,
                use_system_code=use_system_code,
                remark="分项计量边界, 用于从基地总边界拆分主要用能环节。",
            )
            await self._upsert_measurement_boundary_member(
                boundary_id=sub_boundary.id,
                member_code=equipment_code,
                member_type="equipment",
                equipment_id=equipment.id,
                sector_id=equipment.sector_id,
                member_role="covered",
                remark="纳入分项计量边界的确认表计。",
            )

        child_ids = [equipment_rows[code].id for code in member_codes if code in equipment_rows]
        if child_ids:
            await self._session.execute(
                text(
                    """
                    with child_totals as (
                        select granularity, period_start, period_end, sum(amount) as child_amount, sum(cost_cny) as child_cost
                        from dataapp_energyintervalfact
                        where team_id = :team_id
                          and equipment_id = any(:child_ids)
                          and is_current = true
                        group by granularity, period_start, period_end
                    )
                    update dataapp_energyintervalfact pcc_fact
                    set
                        measurement_boundary_id = :boundary_id,
                        amount = child_totals.child_amount * :input_factor,
                        cost_cny = child_totals.child_cost * :input_factor,
                        source_snapshot = (coalesce(pcc_fact.source_snapshot::jsonb, '{}'::jsonb) ||
                            jsonb_build_object(
                                'measurementBoundaryCode', cast(:boundary_code as text),
                                'balanceInputFactor', cast(:input_factor_text as text)
                            ))::json,
                        updated_at = now()
                    from child_totals
                    where pcc_fact.team_id = :team_id
                      and pcc_fact.equipment_id = :pcc_equipment_id
                      and pcc_fact.is_current = true
                      and pcc_fact.granularity = child_totals.granularity
                      and pcc_fact.period_start = child_totals.period_start
                      and pcc_fact.period_end = child_totals.period_end
                    """
                ),
                {
                    "team_id": str(site_boundary.team_id),
                    "child_ids": child_ids,
                    "boundary_id": site_boundary.id,
                    "boundary_code": site_boundary.code,
                    "pcc_equipment_id": pcc.id,
                    "input_factor": Decimal("1.012"),
                    "input_factor_text": "1.012",
                },
            )
            await self._session.execute(
                text(
                    """
                    update dataapp_energyintervalfact
                    set measurement_boundary_id = :boundary_id,
                        source_snapshot = (coalesce(source_snapshot::jsonb, '{}'::jsonb) ||
                            jsonb_build_object('measurementBoundaryCode', cast(:boundary_code as text)))::json,
                        updated_at = now()
                    where team_id = :team_id
                      and equipment_id = any(:equipment_ids)
                      and is_current = true
                    """
                ),
                {
                    "team_id": str(site_boundary.team_id),
                    "boundary_id": site_boundary.id,
                    "boundary_code": site_boundary.code,
                    "equipment_ids": child_ids,
                },
            )
            await self._session.execute(
                text(
                    """
                    update dataapp_scope2meteraggregate
                    set measurement_boundary_id = :boundary_id,
                        source_snapshot = (coalesce(source_snapshot::jsonb, '{}'::jsonb) ||
                            jsonb_build_object('measurementBoundaryCode', cast(:boundary_code as text)))::json,
                        updated_at = now()
                    where team_id = :team_id and ammeter_id = any(:equipment_codes) and is_current = true
                    """
                ),
                {
                    "team_id": str(site_boundary.team_id),
                    "boundary_id": site_boundary.id,
                    "boundary_code": site_boundary.code,
                    "equipment_codes": ["PCC-METER-01", *member_codes],
                },
            )

    async def _upsert_measurement_boundary(
        self,
        *,
        code: str,
        name: str,
        boundary_type: str,
        meter_equipment_id: int,
        sector_id: int | None,
        use_system_code: str | None,
        remark: str,
    ) -> m.MeasurementBoundary:
        boundary = await self._session.scalar(select(m.MeasurementBoundary).where(m.MeasurementBoundary.code == code))
        if boundary is None:
            boundary = m.MeasurementBoundary(code=code, name=name)
            self._session.add(boundary)
            await self._session.flush()
        boundary.name = name
        boundary.boundary_type = boundary_type
        boundary.meter_equipment_id = meter_equipment_id
        boundary.sector_id = sector_id
        boundary.use_system_code = use_system_code
        boundary.energy_direction = "import"
        boundary.include_in_scope2 = True
        boundary.valid_from = date(2026, 1, 1)
        boundary.valid_to = None
        boundary.status = "active"
        boundary.mapping_version = "woheng-v1"
        boundary.source_name = WOHENG_SOURCE_NAME
        boundary.confidence_level = "high"
        boundary.remark = remark
        await self._session.flush()
        return boundary

    async def _upsert_measurement_boundary_member(
        self,
        *,
        boundary_id: int,
        member_code: str,
        member_type: str,
        equipment_id: int | None,
        sector_id: int | None,
        member_role: str,
        remark: str,
    ) -> None:
        member = await self._session.scalar(
            select(m.MeasurementBoundaryMember).where(
                m.MeasurementBoundaryMember.boundary_id == boundary_id,
                m.MeasurementBoundaryMember.member_code == member_code,
            )
        )
        if member is None:
            member = m.MeasurementBoundaryMember(
                boundary_id=boundary_id,
                member_code=member_code,
                member_type=member_type,
            )
            self._session.add(member)
        member.member_type = member_type
        member.equipment_id = equipment_id
        member.sector_id = sector_id
        member.member_role = member_role
        member.allocation_weight = None
        member.confirmation_status = "confirmed"
        member.valid_from = date(2026, 1, 1)
        member.valid_to = None
        member.source_name = WOHENG_SOURCE_NAME
        member.remark = remark
        await self._session.flush()

    async def _ensure_energy_benchmark(self, tenant: WohengTenantSpec) -> None:
        profile_name = f"{tenant.name}能效标杆方案"
        profile = await self._session.scalar(
            select(m.EnergyBenchmarkProfile).where(
                m.EnergyBenchmarkProfile.name == profile_name,
                m.EnergyBenchmarkProfile.source_name == WOHENG_SOURCE_NAME,
            )
        )
        if profile is None:
            profile = m.EnergyBenchmarkProfile(name=profile_name, source_name=WOHENG_SOURCE_NAME)
            self._session.add(profile)
            await self._session.flush()
        profile.industry_name = "汽车整车及零部件制造"
        profile.scenario = "生产基地能源运营、物流搬运、装配线与公辅系统"
        profile.library_type = "enterprise_standard"
        profile.standard_code = "WOHENG-ENPI-2026"
        profile.version_status = "active"
        profile.valid_from = date(2026, 1, 1)
        profile.valid_to = date(2026, 12, 31)
        profile.is_enabled = True
        profile.remark = "用于沃衡汽车统一演示包的能效对标页面。"

        item_specs = (
            (
                "product",
                None,
                "生产基地产品通用标杆",
                "kgce_per_unit",
                "单位产品综合能耗",
                "0.260",
                "kgce/unit",
                "生产基地产品通用口径",
            ),
            (
                "product",
                "WH-BATT-PACK",
                "动力电池托盘总成",
                "kgce_per_unit",
                "单位产品综合能耗",
                "0.255",
                "kgce/unit",
                "动力电池托盘总成合格产量",
            ),
            (
                "product",
                "WH-DRIVE-UNIT",
                "电驱动总成",
                "kgce_per_unit",
                "单位产品综合能耗",
                "0.315",
                "kgce/unit",
                "电驱动总成合格产量",
            ),
            (
                "product",
                None,
                "生产基地产值通用标杆",
                "kgce_per_10k_value",
                "单位产值综合能耗",
                "5.800",
                "kgce/万元",
                "标准价产值口径",
            ),
            (
                "use_system",
                "handling",
                "厂内物流搬运系统",
                "kwh_per_run_hour",
                "单位运行小时用电",
                "680.000",
                "kWh/h",
                "搬运系统月度运行小时",
            ),
            (
                "use_system",
                "handling",
                "厂内物流搬运系统",
                "kwh_per_workload",
                "单位作业量用电",
                "1.450",
                "kWh/unit",
                "托盘出入库作业量",
            ),
            (
                "use_system",
                "charging",
                "充电与测试系统",
                "kwh_per_run_hour",
                "单位运行小时用电",
                "720.000",
                "kWh/h",
                "充电系统月度运行小时",
            ),
            (
                "use_system",
                "lighting",
                "照明系统",
                "kwh_per_run_hour",
                "单位运行小时用电",
                "620.000",
                "kWh/h",
                "照明系统月度运行小时",
            ),
            (
                "use_system",
                "storage",
                "仓储设施系统",
                "kwh_per_run_hour",
                "单位运行小时用电",
                "760.000",
                "kWh/h",
                "仓储设施系统月度运行小时",
            ),
            (
                "area",
                None,
                "生产基地单位面积用电标杆",
                "kwh_per_m2",
                "单位面积用电量",
                "310.000",
                "kWh/m2",
                "建筑面积年度化用电强度",
            ),
            (
                "enterprise",
                None,
                "生产基地综合面积能耗标杆",
                "tce_per_m2",
                "单位面积综合能耗",
                "0.0720",
                "tce/m2",
                "建筑面积年度化综合能耗强度",
            ),
            (
                "device_type",
                "transformer",
                "电力变压器",
                "energy_efficiency_level",
                "设备能效等级",
                "1",
                "级",
                "同能效标准分类",
            ),
            (
                "device_type",
                "ev_charger",
                "充电桩",
                "energy_efficiency_level",
                "设备能效等级",
                "1",
                "级",
                "直流/交流充电设备",
            ),
            (
                "device_type",
                "chiller",
                "冷水机组",
                "energy_efficiency_level",
                "设备能效等级",
                "1",
                "级",
                "冷水机组综合部分负荷性能系数",
            ),
            (
                "device_type",
                "pv_inverter",
                "光伏并网逆变器",
                "energy_efficiency_level",
                "设备能效等级",
                "1",
                "级",
                "平均加权效率",
            ),
        )
        for spec in item_specs:
            (
                target_type,
                target_code,
                target_name,
                metric_code,
                metric_name,
                benchmark_value,
                unit,
                applicable_condition,
            ) = spec
            item = await self._session.scalar(
                select(m.EnergyBenchmarkItem).where(
                    m.EnergyBenchmarkItem.profile_id == profile.id,
                    m.EnergyBenchmarkItem.target_type == target_type,
                    m.EnergyBenchmarkItem.target_code.is_(None)
                    if target_code is None
                    else m.EnergyBenchmarkItem.target_code == target_code,
                    m.EnergyBenchmarkItem.metric_code == metric_code,
                )
            )
            if item is None:
                item = m.EnergyBenchmarkItem(
                    profile_id=profile.id,
                    target_type=target_type,
                    target_code=target_code,
                    metric_code=metric_code,
                    metric_name=metric_name,
                    benchmark_value=Decimal(benchmark_value),
                    unit=unit,
                )
                self._session.add(item)
            item.target_name = target_name
            item.metric_name = metric_name
            item.benchmark_value = Decimal(benchmark_value)
            item.unit = unit
            item.standard_code = "WOHENG-ENPI-2026"
            item.applicable_industry = "汽车整车及零部件制造"
            item.applicable_category = target_name
            item.applicable_condition = applicable_condition
            item.metric_direction = "level_rank" if metric_code == "energy_efficiency_level" else "lower_is_better"
            item.advanced_value = Decimal(benchmark_value)
            item.saving_value = (
                Decimal(benchmark_value) * Decimal("1.08") if metric_code != "energy_efficiency_level" else Decimal(2)
            )
            item.access_value = (
                Decimal(benchmark_value) * Decimal("1.18") if metric_code != "energy_efficiency_level" else Decimal(3)
            )
            item.baseline_value = item.access_value
            item.advanced_level = "能效1级" if metric_code == "energy_efficiency_level" else "先进水平"
            item.saving_level = "能效2级" if metric_code == "energy_efficiency_level" else "节能水平"
            item.access_level = "能效3级" if metric_code == "energy_efficiency_level" else "基准水平"
            item.standard_level = "enterprise_benchmark"
            item.version_status = "active"
            item.reference_standard = "GB/T 36714-2018、GB/T 36713-2018"
            item.excellent_value = item.advanced_value
            item.warning_threshold_pct = Decimal(10)
            item.severe_threshold_pct = Decimal(25)
            item.source_name = WOHENG_SOURCE_NAME
            item.confidence_level = "medium"
            item.is_enabled = True
            item.remark = "演示标杆项, 用于展示生产基地能效对标、偏差识别和整改建议。"

    async def _ensure_equipment_efficiency_master_data(self) -> None:
        equipment_rows = list((await self._session.scalars(select(m.MonitorEquipment))).all())
        for equipment in equipment_rows:
            spec = EQUIPMENT_EFFICIENCY_SPECS.get(equipment.code)
            if spec is None:
                continue
            level, standard = spec
            equipment.energy_efficiency_level = level
            equipment.energy_efficiency_standard = standard

    async def _ensure_operational_ledgers(self, tenant: WohengTenantSpec) -> None:
        inbound_specs = (
            ("WH-RK-260701", "华东电池材料供应链", "MAT-AL-01", "电池托盘铝合金型材", "kg", 12800.0, 38.6),
            ("WH-RK-260706", "华东电子器件供应链", "MAT-BMS-02", "BMS控制板组件", "pcs", 5200.0, 126.0),
            ("WH-RK-260711", "华东包装器具循环中心", "PKG-BOX-01", "循环周转箱", "pcs", 3600.0, 42.5),
            ("WH-RK-260716", "华东电驱零部件供应链", "MAT-MTR-03", "电驱壳体半成品", "pcs", 1900.0, 218.0),
            ("WH-RK-260721", "华东热管理供应链", "MAT-HVAC-04", "热管理管路套件", "set", 2400.0, 89.0),
            ("WH-RK-260726", "华东紧固件供应链", "MAT-FAS-05", "高强度紧固件", "kg", 7600.0, 16.8),
        )
        for code, supplier, material_code, material_name, unit, quantity, unit_price in inbound_specs:
            row = await self._session.scalar(select(m.InMoney).where(m.InMoney.rkdbh == code))
            if row is None:
                row = m.InMoney(rkdbh=code)
                self._session.add(row)
            row.gysmc = supplier
            row.gysbm = supplier[:10]
            row.rkrq = "2026-07"
            row.wlbh = material_code[:15]
            row.wlms = material_name
            row.pc = f"{tenant.city_code}2607"
            row.jldw = unit
            row.shsl = quantity
            row.shdj = unit_price
            row.shje = round(quantity * unit_price, 2)
            row.ckmc = f"{tenant.name}原材料库"
            row.add_time = datetime(2026, 7, 26, 9, 0, tzinfo=UTC).replace(tzinfo=None)

        outbound_specs = (
            ("WH-CK-260702", "动力电池托盘装配", "MAT-AL-01", "电池托盘铝合金型材", "kg", 8600.0, 39.2),
            ("WH-CK-260708", "电控系统装配", "MAT-BMS-02", "BMS控制板组件", "pcs", 3100.0, 128.0),
            ("WH-CK-260713", "厂内循环包装", "PKG-BOX-01", "循环周转箱", "pcs", 2800.0, 42.5),
            ("WH-CK-260718", "电驱总成加工", "MAT-MTR-03", "电驱壳体半成品", "pcs", 1250.0, 220.0),
            ("WH-CK-260723", "热管理模块装配", "MAT-HVAC-04", "热管理管路套件", "set", 1680.0, 90.0),
            ("WH-CK-260728", "整车总装补料", "MAT-FAS-05", "高强度紧固件", "kg", 4300.0, 17.1),
        )
        for code, project, material_code, material_name, unit, quantity, unit_price in outbound_specs:
            row = await self._session.scalar(select(m.OutMoney).where(m.OutMoney.ckdbh == code))
            if row is None:
                row = m.OutMoney(ckdbh=code)
                self._session.add(row)
            row.xmmc = project
            row.xmdy = tenant.city_code
            row.wlbm = material_code[:15]
            row.wlms = material_name
            row.pc = f"{tenant.city_code}2607"
            row.jldw = unit
            row.sfsl = quantity
            row.dj = unit_price
            row.je = round(quantity * unit_price, 2)
            row.gzrq = "2026-07"
            row.gysmc = "沃衡汽车内部领用"
            row.gc = tenant.name
            row.lldh = code[-10:]
            row.ckdd = f"{tenant.name}线边库"
            row.add_time = datetime(2026, 7, 28, 17, 30, tzinfo=UTC).replace(tzinfo=None)

        commute_specs = (
            ("TZ班车一线", "班车", 1, 18.0, 10.2),
            ("TZ班车二线", "班车", 1, 22.0, 10.5),
            ("公共交通样本", "公交", 1, 14.0, 6.5),
            ("自驾汽油样本", "自驾", 1, 26.0, 7.8),
            ("自驾新能源样本", "自驾", 2, 24.0, 15.0),
            ("跨园区通勤样本", "班车", 0, 32.0, 12.0),
        )
        for name, category, power_type, mileage, consumption in commute_specs:
            employee_name = f"{tenant.city_code}{name}"[:10]
            row = await self._session.scalar(select(m.EmployeeCommute).where(m.EmployeeCommute.name == employee_name))
            if row is None:
                row = m.EmployeeCommute(name=employee_name)
                self._session.add(row)
            row.category = category
            row.car_power_type = power_type
            row.mileage = mileage
            row.unit_consumption = consumption

    async def _ensure_production_denominators(self, tenant: WohengTenantSpec) -> None:  # noqa: PLR0915
        product_specs = (
            ("WH-BATT-PACK", "动力电池托盘总成", "EV平台通用件", "电池系统", "product", "pcs", "pcs"),
            ("WH-DRIVE-UNIT", "电驱动总成", "160kW", "电驱系统", "product", "pcs", "pcs"),
            ("WH-CHASSIS-SUB", "底盘副车架总成", "轻量化", "底盘系统", "product", "pcs", "pcs"),
            ("WH-MAT-HANDLING", "入出库处理量", "托盘", "厂内物流", "material_handling", "pallet", "pallet"),
        )
        for code, name, spec, category, output_kind, default_unit, standard_unit in product_specs:
            row = await self._session.scalar(select(m.ProductionProduct).where(m.ProductionProduct.code == code))
            if row is None:
                row = m.ProductionProduct(code=code, name=name)
                self._session.add(row)
            row.name = name
            row.spec = spec
            row.category = category
            row.output_kind = output_kind
            row.default_unit = default_unit
            row.standard_unit = standard_unit
            row.is_enabled = True
            row.remark = f"{tenant.name}演示产出对象。"

        price_specs = (
            ("WH-BATT-PACK", "standard_price", "1860.00"),
            ("WH-DRIVE-UNIT", "standard_price", "4250.00"),
            ("WH-CHASSIS-SUB", "standard_price", "2380.00"),
            ("WH-MAT-HANDLING", "standard_price", "38.00"),
        )
        for product_code, price_type, price in price_specs:
            source_record_id = f"{tenant.slug}:{product_code}:{price_type}:2026"
            row = await self._session.scalar(
                select(m.ProductPrice).where(
                    m.ProductPrice.product_code == product_code,
                    m.ProductPrice.price_type == price_type,
                    m.ProductPrice.source_system == "woheng-showcase",
                    m.ProductPrice.source_record_id == source_record_id,
                )
            )
            if row is None:
                row = m.ProductPrice(product_code=product_code, price_type=price_type, price=Decimal(price))
                self._session.add(row)
            row.price = Decimal(price)
            row.currency = "CNY"
            row.tax_included = False
            row.valid_from = date(2026, 1, 1)
            row.valid_to = date(2026, 12, 31)
            row.source_system = "woheng-showcase"
            row.source_record_id = source_record_id
            row.remark = "沃衡汽车统一演示包价格口径。"

        equipment = await self._session.scalar(
            select(m.MonitorEquipment).where(m.MonitorEquipment.code == "CONVEYOR-01")
        )
        area = await self._session.scalar(select(m.MonitorSector).where(m.MonitorSector.code != "ROOT"))
        output_specs = (
            ("WH-BATT-PACK", "动力电池托盘总成", "PACK-LINE-01", "2026-07-01", "2026-07-31", "13800"),
            ("WH-DRIVE-UNIT", "电驱动总成", "EDU-LINE-01", "2026-07-01", "2026-07-31", "9200"),
            ("WH-CHASSIS-SUB", "底盘副车架总成", "CHS-LINE-01", "2026-07-01", "2026-07-31", "7600"),
            ("WH-MAT-HANDLING", "入出库处理量", "LOG-LINE-01", "2026-07-01", "2026-07-31", "48600"),
        )
        for product_code, product_name, line_code, start, end, quantity in output_specs:
            source_record_id = f"{tenant.slug}:{product_code}:{start}"
            row = await self._session.scalar(
                select(m.ProductionOutputFact).where(
                    m.ProductionOutputFact.source_system == "woheng-showcase",
                    m.ProductionOutputFact.source_record_id == source_record_id,
                )
            )
            if row is None:
                row = m.ProductionOutputFact(
                    source_system="woheng-showcase",
                    source_record_id=source_record_id,
                    product_code=product_code,
                    period_start=date.fromisoformat(start),
                    period_end=date.fromisoformat(end),
                    good_qty=Decimal(quantity),
                    unit="pcs" if product_code != "WH-MAT-HANDLING" else "pallet",
                )
                self._session.add(row)
            row.production_order_no = f"MO-{tenant.city_code}-{product_code[-4:]}-2607"
            row.batch_no = f"{tenant.city_code}-202607"
            row.product_code = product_code
            row.product_name = product_name
            row.product_spec = "沃衡汽车演示规格"
            row.output_kind = "material_handling" if product_code == "WH-MAT-HANDLING" else "product"
            row.period_start = date.fromisoformat(start)
            row.period_end = date.fromisoformat(end)
            row.good_qty = Decimal(quantity)
            row.scrap_qty = Decimal(0)
            row.rework_qty = Decimal(0)
            row.unit = "pallet" if product_code == "WH-MAT-HANDLING" else "pcs"
            row.standard_qty = Decimal(quantity)
            row.standard_unit = row.unit
            row.quality_status = "pass"
            row.record_status = "confirmed"
            row.work_center_code = "WH-AUTO-WC"
            row.line_code = line_code
            row.area_id = area.id if area is not None else None
            row.area_name = area.name if area is not None else tenant.name
            row.equipment_code = equipment.code if equipment is not None else None
            row.equipment_name = equipment.name if equipment is not None else None
            row.remark = f"{tenant.name}演示产量/作业量事实。"

        for product_code, _product_name, line_code, *_rest in output_specs:
            row = await self._session.scalar(
                select(m.ProductionResourceBinding).where(
                    m.ProductionResourceBinding.product_code == product_code,
                    m.ProductionResourceBinding.work_center_code == "WH-AUTO-WC",
                    m.ProductionResourceBinding.line_code == line_code,
                )
            )
            if row is None:
                row = m.ProductionResourceBinding(product_code=product_code, line_code=line_code)
                self._session.add(row)
            row.work_center_code = "WH-AUTO-WC"
            row.line_code = line_code
            row.area_id = area.id if area is not None else None
            row.equipment_id = equipment.id if equipment is not None else None
            row.binding_type = "primary"
            row.valid_from = date(2026, 1, 1)
            row.valid_to = None
            row.confidence_level = "high"
            row.remark = f"{tenant.name}产出对象与产线/区域/设备关联。"

    async def _ensure_category_51_activity(self, tenant: WohengTenantSpec) -> None:  # noqa: PLR0915
        period = await self._session.scalar(select(m.ReportingPeriod).order_by(m.ReportingPeriod.period_start.desc()))
        organization = await self._session.scalar(select(m.ReportingOrganization).order_by(m.ReportingOrganization.id))
        boundary = await self._session.scalar(select(m.OrganizationBoundary).order_by(m.OrganizationBoundary.id))
        area = await self._session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == "ROOT"))
        if period is None or organization is None or boundary is None or area is None:
            return
        inventory_code = self._inventory_code_for_year(tenant, period.period_start.year)
        source_code = f"WH-{tenant.city_code}-SOLD-PROCESSING"
        source = await self._session.scalar(
            select(m.GhgEmissionSource).where(
                m.GhgEmissionSource.inventory_code == inventory_code,
                m.GhgEmissionSource.source_code == source_code,
            )
        )
        if source is None:
            source = m.GhgEmissionSource(
                inventory_code=inventory_code,
                organization_code=organization.code,
                facility_code=area.code,
                source_code=source_code,
                source_name="售出零部件客户加工",
                iso_category_code="5.1",
                source_mechanism="value_chain",
                origin_kind="external",
                default_area_id=area.id,
                default_allocation_role="responsibility",
            )
            self._session.add(source)
            await self._session.flush()
        source.organization_boundary_id = boundary.id
        source.reporting_period_id = period.id
        source.organization_code = organization.code
        source.facility_code = area.code
        source.source_name = "售出零部件客户加工"
        source.iso_category_code = "5.1"
        source.source_mechanism = "value_chain"
        source.origin_kind = "external"
        source.default_area_id = area.id
        source.external_facility_code = f"{tenant.city_code}-CUSTOMER-PROCESS"
        source.external_facility_name = "客户整车装配加工环节"
        source.source_system = "woheng-showcase"
        source.source_payload = {"product_name": "动力电池托盘总成", "use_scenario": "客户装配加工"}
        source.status = "active"

        record_code = f"WH-{tenant.city_code}-CAT51-202607"
        activity = await self._session.scalar(
            select(m.GhgActivityRecord).where(
                m.GhgActivityRecord.inventory_code == inventory_code,
                m.GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            activity = m.GhgActivityRecord(
                record_code=record_code,
                inventory_code=inventory_code,
                organization_code=organization.code,
                facility_code=area.code,
                source_code=source_code,
                activity_code="sold-product-processing",
                activity_name="售出动力电池托盘客户加工",
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 31),
                iso_category_code="5.1",
                ghg_scope="scope3",
                scope3_category=10,
                source_mechanism="value_chain",
                value_chain_position="downstream",
                activity_amount=Decimal(13800),
                activity_unit="pcs",
                data_source_type="erp",
                measurement_method="销售出库记录与客户加工情景参数",
            )
            self._session.add(activity)
            await self._session.flush()
        activity.reporting_period_id = period.id
        activity.organization_boundary_id = boundary.id
        activity.emission_source_id = source.id
        activity.organization_code = organization.code
        activity.facility_code = area.code
        activity.source_code = source_code
        activity.activity_code = "sold-product-processing"
        activity.activity_name = "售出动力电池托盘客户加工"
        activity.period_start = date(2026, 7, 1)
        activity.period_end = date(2026, 7, 31)
        activity.iso_category_code = "5.1"
        activity.ghg_scope = "scope3"
        activity.scope3_category = 10
        activity.source_mechanism = "value_chain"
        activity.value_chain_position = "downstream"
        activity.boundary_status = "included"
        activity.national_source_category = "组织输出产品加工相关间接排放"
        activity.activity_amount = Decimal(13800)
        activity.activity_unit = "pcs"
        activity.data_source_type = "erp"
        activity.measurement_method = "销售出库记录与客户加工情景参数"
        activity.quality_status = "pass"
        activity.parameter_set_code = "WH-CAT51-PARAM"
        activity.source_payload = {
            "product_name": "动力电池托盘总成",
            "sales_quantity": 13800,
            "use_lifetime": "客户装配加工期",
            "use_scenario": "客户整车装配加工",
        }
        activity.remarks = f"{tenant.name}演示售出产品加工活动记录。"
        activity.status = "approved"
        activity.source_system = "woheng-showcase"
        activity.source_record_type = "OutMoney"

        allocation_code = f"{record_code}-ALLOC"
        allocation = await self._session.scalar(
            select(m.GhgActivityAllocation).where(
                m.GhgActivityAllocation.activity_id == activity.id,
                m.GhgActivityAllocation.allocation_code == allocation_code,
            )
        )
        if allocation is None:
            allocation = m.GhgActivityAllocation(
                activity_id=activity.id,
                allocation_code=allocation_code,
                area_id=area.id,
                allocation_ratio=Decimal(1),
                area_code_snapshot=area.code,
                area_name_snapshot=area.name or area.code,
            )
            self._session.add(allocation)
        allocation.emission_source_id = source.id
        allocation.area_id = area.id
        allocation.equipment_id = None
        allocation.allocation_role = "responsibility"
        allocation.allocation_ratio = Decimal(1)
        allocation.external_facility_code = source.external_facility_code
        allocation.external_facility_name = source.external_facility_name
        allocation.area_code_snapshot = area.code
        allocation.area_name_snapshot = area.name or area.code
        allocation.area_path_snapshot = area.path
        allocation.equipment_code_snapshot = None
        allocation.equipment_name_snapshot = None
        allocation.source_kind = "woheng-showcase"
        allocation.valid_from = date(2026, 1, 1)
        allocation.status = "active"

    async def _ensure_supply_chain_and_product_footprint(self, tenant: WohengTenantSpec) -> None:  # noqa: PLR0915
        product = await self._session.scalar(
            select(m.ProductionProduct).where(m.ProductionProduct.code == "WH-BATT-PACK")
        )
        product_id = product.id if product is not None else None
        supplier_specs = (
            ("WH-SUP-AL-001", "华东铝合金部件有限公司", "有色金属压延加工", "direct_material", "high"),
            ("WH-SUP-BMS-002", "华东电子控制系统有限公司", "汽车电子制造", "direct_material", "medium"),
        )
        suppliers: list[m.SupplyChainSupplier] = []
        for supplier_code, name, industry, supplier_type, risk_level in supplier_specs:
            supplier = await self._session.scalar(
                select(m.SupplyChainSupplier).where(m.SupplyChainSupplier.supplier_code == supplier_code)
            )
            if supplier is None:
                supplier = m.SupplyChainSupplier(supplier_code=supplier_code, name=name)
                self._session.add(supplier)
                await self._session.flush()
            supplier.name = name
            supplier.industry = industry
            supplier.supplier_type = supplier_type
            supplier.contact_name = "供应链协同专员"
            supplier.contact_email = f"{supplier_code.lower()}@supplier.example.com"
            supplier.country_region = "中国华东"
            supplier.status = "active"
            supplier.risk_level = risk_level
            supplier.source_name = WOHENG_SOURCE_NAME
            supplier.standard_code = "ISO 14067 / GHG Protocol Scope 3"
            supplier.remark = f"{tenant.name}供应链碳数据协同演示供应商。"
            suppliers.append(supplier)

            site = await self._session.scalar(
                select(m.SupplierSite).where(
                    m.SupplierSite.supplier_id == supplier.id,
                    m.SupplierSite.site_code == f"{supplier_code}-SITE",
                )
            )
            if site is None:
                site = m.SupplierSite(
                    supplier_id=supplier.id, site_code=f"{supplier_code}-SITE", site_name=f"{name}主生产场站"
                )
                self._session.add(site)
            site.site_name = f"{name}主生产场站"
            site.country_region = "中国华东"
            site.address = "华东新能源汽车供应链配套园"
            site.facility_scope = "原材料与零部件生产"
            site.status = "active"
            site.remark = "供应商场站范围用于供应链碳数据填报。"

            task_no = f"{tenant.city_code}-{supplier_code}-2026"
            task = await self._session.scalar(
                select(m.SupplierDisclosureTask).where(m.SupplierDisclosureTask.task_no == task_no)
            )
            if task is None:
                task = m.SupplierDisclosureTask(
                    task_no=task_no,
                    task_name=f"{name}2026年度碳数据填报",
                    supplier_id=supplier.id,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                )
                self._session.add(task)
                await self._session.flush()
            task.task_name = f"{name}2026年度碳数据填报"
            task.supplier_id = supplier.id
            task.task_type = "pcf_and_scope3"
            task.product_id = product_id
            task.product_code = "WH-BATT-PACK"
            task.product_name = "动力电池托盘总成"
            task.period_start = date(2026, 1, 1)
            task.period_end = date(2026, 12, 31)
            task.due_date = date(2026, 8, 31)
            task.status = "approved"
            task.submitted_at = datetime(2026, 8, 20, 10, 0, tzinfo=UTC).replace(tzinfo=None)
            task.approved_at = datetime(2026, 8, 23, 16, 0, tzinfo=UTC).replace(tzinfo=None)
            task.requested_by = "沃衡汽车供应链管理部"
            task.standard_code = "ISO 14067 / GHG Protocol Scope 3"
            task.source_name = WOHENG_SOURCE_NAME
            task.confidence_level = "medium"
            task.remark = "用于供应链碳数据收集、审核和披露记录演示。"

            data_no = f"{task_no}-DATA"
            carbon_data = await self._session.scalar(
                select(m.SupplierCarbonData).where(
                    m.SupplierCarbonData.task_id == task.id,
                    m.SupplierCarbonData.data_no == data_no,
                )
            )
            if carbon_data is None:
                carbon_data = m.SupplierCarbonData(task_id=task.id, supplier_id=supplier.id, data_no=data_no)
                self._session.add(carbon_data)
            carbon_data.supplier_id = supplier.id
            carbon_data.data_type = "pcf"
            carbon_data.scope_category = "purchased_goods"
            carbon_data.product_id = product_id
            carbon_data.product_code = "WH-BATT-PACK"
            carbon_data.product_name = "动力电池托盘总成"
            carbon_data.material_code = "MAT-AL-01" if "AL" in supplier_code else "MAT-BMS-02"
            carbon_data.material_name = "电池托盘铝合金型材" if "AL" in supplier_code else "BMS控制板组件"
            carbon_data.activity_amount = Decimal(12800) if "AL" in supplier_code else Decimal(5200)
            carbon_data.activity_unit = "kg" if "AL" in supplier_code else "pcs"
            carbon_data.pcf_value = Decimal("6.420000") if "AL" in supplier_code else Decimal("12.800000")
            carbon_data.pcf_unit = "kgCO2e/unit"
            carbon_data.co2e_amount = Decimal("82176.000000") if "AL" in supplier_code else Decimal("66560.000000")
            carbon_data.factor_source = "供应商经审核填报数据"
            carbon_data.boundary_type = "cradle_to_gate"
            carbon_data.data_quality = "supplier_verified"
            carbon_data.verified = True
            carbon_data.validity_start = date(2026, 1, 1)
            carbon_data.validity_end = date(2026, 12, 31)
            carbon_data.source_type = "supplier_portal"
            carbon_data.source_ref = task_no
            carbon_data.status = "approved"
            carbon_data.published_to_scope3 = True
            carbon_data.published_to_pcf = True
            carbon_data.remark = "供应商填报并审核通过的产品相关碳数据。"

            evidence_no = f"{task_no}-EVD"
            evidence = await self._session.scalar(
                select(m.SupplierEvidence).where(
                    m.SupplierEvidence.task_id == task.id,
                    m.SupplierEvidence.evidence_no == evidence_no,
                )
            )
            if evidence is None:
                evidence = m.SupplierEvidence(
                    task_id=task.id,
                    evidence_no=evidence_no,
                    evidence_type="pcf_statement",
                    file_name=f"{name}碳数据填报凭证.pdf",
                )
                self._session.add(evidence)
            evidence.evidence_type = "pcf_statement"
            evidence.file_name = f"{name}碳数据填报凭证.pdf"
            evidence.file_path = f"/demo/woheng/supply-chain/{evidence_no}.pdf"
            evidence.file_sha256 = ("a" * 64) if "AL" in supplier_code else ("b" * 64)
            evidence.file_size_bytes = 420000
            evidence.review_status = "approved"
            evidence.submitted_by = supplier.contact_name
            evidence.reviewed_at = datetime(2026, 8, 23, 16, 0, tzinfo=UTC).replace(tzinfo=None)
            evidence.remark = "供应链碳数据审核凭证。"

            release_no = f"{task_no}-REL"
            release = await self._session.scalar(
                select(m.SupplierDisclosureRelease).where(m.SupplierDisclosureRelease.release_no == release_no)
            )
            if release is None:
                release = m.SupplierDisclosureRelease(release_no=release_no, task_id=task.id)
                self._session.add(release)
            release.task_id = task.id
            release.release_type = "customer_disclosure"
            release.recipient_name = "沃衡汽车低碳供应链项目组"
            release.status = "released"
            release.released_at = datetime(2026, 8, 24, 9, 30, tzinfo=UTC).replace(tzinfo=None)
            release.payload = {
                "supplier": supplier.name,
                "taskNo": task_no,
                "productCode": "WH-BATT-PACK",
                "status": "released",
            }
            release.remark = "供应商碳数据披露记录。"

        study_code = f"WH-{tenant.city_code}-PCF-BATT-PACK-2026"
        study = await self._session.scalar(
            select(m.ProductFootprintStudy).where(m.ProductFootprintStudy.study_code == study_code)
        )
        if study is None:
            study = m.ProductFootprintStudy(
                study_code=study_code,
                study_name="动力电池托盘总成碳足迹研究",
                product_code="WH-BATT-PACK",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
            self._session.add(study)
            await self._session.flush()
        study.study_name = "动力电池托盘总成碳足迹研究"
        study.product_id = product_id
        study.product_code = "WH-BATT-PACK"
        study.product_name = "动力电池托盘总成"
        study.product_spec = "EV平台通用件"
        study.product_category = "电池系统"
        study.standard_code = "ISO 14067"
        study.standard_name = "温室气体 产品碳足迹 量化要求和指南"
        study.pcr_code = "EV-BATTERY-TRAY-DEMO"
        study.functional_unit = "1件动力电池托盘总成"
        study.declared_unit = "1 pcs"
        study.period_start = date(2026, 1, 1)
        study.period_end = date(2026, 12, 31)
        study.boundary_type = "cradle_to_gate"
        study.status = "active"
        study.result_status = "calculated"
        study.source_name = WOHENG_SOURCE_NAME
        study.confidence_level = "medium"
        study.remark = f"{tenant.name}产品碳足迹演示研究。"

        boundary = await self._session.scalar(
            select(m.ProductSystemBoundary).where(m.ProductSystemBoundary.study_id == study.id)
        )
        if boundary is None:
            boundary = m.ProductSystemBoundary(study_id=study.id)
            self._session.add(boundary)
        boundary.boundary_type = "cradle_to_gate"
        boundary.included_stages = ["raw_material", "inbound_transport", "manufacturing", "packaging"]
        boundary.excluded_stages = ["use", "end_of_life"]
        boundary.cutoff_rule = "纳入主要原材料、运输、制造电力和包装活动数据。"
        boundary.geography = "中国华东"
        boundary.technology_scope = "新能源汽车零部件生产基地"
        boundary.temporal_scope = "2026年度"
        boundary.assumption = "演示研究使用供应链审核数据与基地计量数据。"
        boundary.standard_code = "ISO 14067"
        boundary.source_name = WOHENG_SOURCE_NAME

        stage_specs = (
            ("raw_material", "原材料获取", 1, Decimal(148736)),
            ("inbound_transport", "入厂运输", 2, Decimal(18640)),
            ("manufacturing", "基地制造", 3, Decimal(42680)),
            ("packaging", "包装与交付准备", 4, Decimal(9320)),
        )
        stages_by_code: dict[str, m.ProductLifeCycleStage] = {}
        for stage_code, stage_name, sequence, _co2e in stage_specs:
            stage = await self._session.scalar(
                select(m.ProductLifeCycleStage).where(
                    m.ProductLifeCycleStage.study_id == study.id,
                    m.ProductLifeCycleStage.stage_code == stage_code,
                )
            )
            if stage is None:
                stage = m.ProductLifeCycleStage(study_id=study.id, stage_code=stage_code, stage_name=stage_name)
                self._session.add(stage)
                await self._session.flush()
            stage.stage_name = stage_name
            stage.sequence = sequence
            stage.included = True
            stage.description = f"{stage_name}阶段活动数据。"
            stages_by_code[stage_code] = stage

        inventory_specs = (
            (
                "PCF-RAW-001",
                "raw_material",
                "供应商铝合金型材碳数据",
                "material",
                "12800",
                "kg",
                "6.42",
                "kgCO2e/unit",
                "供应商经审核填报数据",
                "82176",
            ),
            (
                "PCF-RAW-002",
                "raw_material",
                "供应商BMS控制板组件碳数据",
                "material",
                "5200",
                "pcs",
                "12.80",
                "kgCO2e/unit",
                "供应商经审核填报数据",
                "66560",
            ),
            (
                "PCF-TRN-001",
                "inbound_transport",
                "入厂运输",
                "transport",
                "18640",
                "t.km",
                "1.00",
                "kgCO2e/t.km",
                "运输活动数据",
                "18640",
            ),
            (
                "PCF-MFG-001",
                "manufacturing",
                "制造电力",
                "energy",
                "74840",
                "kWh",
                "0.5703",
                "kgCO2e/kWh",
                "基地计量电量",
                "42680",
            ),
            (
                "PCF-PKG-001",
                "packaging",
                "循环包装分摊",
                "material",
                "9320",
                "pcs",
                "1.00",
                "kgCO2e/pcs",
                "包装台账",
                "9320",
            ),
        )
        for (
            item_no,
            stage_code,
            item_name,
            activity_type,
            amount,
            unit,
            factor,
            factor_unit,
            factor_source,
            co2e,
        ) in inventory_specs:
            item = await self._session.scalar(
                select(m.ProductFootprintInventoryItem).where(
                    m.ProductFootprintInventoryItem.study_id == study.id,
                    m.ProductFootprintInventoryItem.item_no == item_no,
                )
            )
            if item is None:
                item = m.ProductFootprintInventoryItem(
                    study_id=study.id,
                    item_no=item_no,
                    activity_type=activity_type,
                    item_name=item_name,
                )
                self._session.add(item)
            item.stage_id = stages_by_code[stage_code].id
            item.activity_type = activity_type
            item.item_name = item_name
            item.activity_amount = Decimal(amount)
            item.activity_unit = unit
            item.factor_value = Decimal(factor)
            item.factor_unit = factor_unit
            item.factor_source = factor_source
            item.supplier_name = (
                suppliers[0].name if "铝合金" in item_name else suppliers[1].name if "BMS" in item_name else None
            )
            item.allocation_ratio = Decimal(1)
            item.computed_co2e = Decimal(co2e)
            item.calc_status = "calculated"
            item.data_quality = "supplier_verified" if "供应商" in item_name else "measured_or_ledger"
            item.source_type = "supplier" if "供应商" in item_name else "internal_ledger"
            item.source_ref = f"{tenant.slug}:{item_no}"
            item.evidence_path = f"/demo/woheng/product-footprint/{item_no}.pdf"
            item.included = True
            item.remark = "产品碳足迹演示活动数据。"

        rule = await self._session.scalar(
            select(m.ProductFootprintAllocationRule).where(
                m.ProductFootprintAllocationRule.study_id == study.id,
                m.ProductFootprintAllocationRule.process_code == "PACK-LINE-01",
            )
        )
        if rule is None:
            rule = m.ProductFootprintAllocationRule(
                study_id=study.id, process_code="PACK-LINE-01", process_name="动力电池托盘装配线"
            )
            self._session.add(rule)
        rule.process_name = "动力电池托盘装配线"
        rule.allocation_method = "physical"
        rule.basis = "按产品件数分配"
        rule.ratio = Decimal(1)
        rule.source_name = WOHENG_SOURCE_NAME
        rule.remark = "生产线单一主产品演示分配规则。"

        result = await self._session.scalar(
            select(m.ProductFootprintResult).where(
                m.ProductFootprintResult.study_id == study.id,
                m.ProductFootprintResult.result_version == 1,
            )
        )
        stage_payload = [
            {
                "stage_code": code,
                "stage_name": name,
                "item_count": 1 if code != "raw_material" else 2,
                "kg_co2e": float(co2e),
            }
            for code, name, _sequence, co2e in stage_specs
        ]
        if result is None:
            result = m.ProductFootprintResult(study_id=study.id, result_version=1)
            self._session.add(result)
        total_co2e = Decimal(219376)
        result.total_co2e = total_co2e
        result.unit = "kgCO2e"
        result.footprint_per_declared_unit = Decimal("15.8968")
        result.result_status = "calculated"
        result.calculated_at = datetime(2026, 8, 25, 15, 0, tzinfo=UTC).replace(tzinfo=None)
        result.inventory_count = len(inventory_specs)
        result.missing_factor_count = 0
        result.stage_payload = stage_payload
        result.result_payload = {
            "declaredUnit": study.declared_unit,
            "functionalUnit": study.functional_unit,
            "totalCo2e": float(total_co2e),
            "sourceName": WOHENG_SOURCE_NAME,
        }
        result.report_status = "generated"
        result.remark = "沃衡汽车统一演示包产品碳足迹核算结果。"

    async def _ensure_warning_events(self, tenant: WohengTenantSpec) -> None:
        equipment = await self._session.scalar(
            select(m.MonitorEquipment).where(m.MonitorEquipment.code == "PCC-METER-01")
        )
        sector = await self._session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == "ROOT"))
        if equipment is None or sector is None:
            return
        rule = await self._session.scalar(select(m.WarningRule).where(m.WarningRule.alarm_code == "WH-PEAK-POWER"))
        if rule is None:
            rule = m.WarningRule(
                name="关口功率越限预警",
                description="生产与厂内物流高峰期关口功率超过策略阈值时触发。",
                range_val={"operator": ">", "threshold": 980, "unit": "kW"},
                event_type=2,
                equipment_id=equipment.id,
                sector_id=sector.id,
                point_code="active_power",
                alarm_code="WH-PEAK-POWER",
                alarm_name="关口功率越限",
                alarm_level="warning",
                is_enabled=True,
                table_name="metering_meter_reading_fact",
            )
            self._session.add(rule)
            await self._session.flush()
        event = await self._session.scalar(select(m.AlarmEvent).where(m.AlarmEvent.alarm_code == "WH-PEAK-POWER"))
        if event is None:
            self._session.add(
                m.AlarmEvent(
                    rule_id=rule.id,
                    event_type=2,
                    alarm_code="WH-PEAK-POWER",
                    alarm_name=f"{tenant.name}关口功率越限",
                    alarm_level="warning",
                    alarm_category="energy",
                    event_desc="生产线、空压站与充电负荷叠加导致关口功率接近需量控制阈值。",
                    event_time=datetime(2026, 8, 28, 14, 35, tzinfo=UTC),
                    sector_id=sector.id,
                    equipment_id=equipment.id,
                    point_code="active_power",
                    current_value=tenant.peak_power_kw,
                    threshold_value=980,
                    status="closed",
                    resolved_at=datetime(2026, 8, 28, 15, 10, tzinfo=UTC),
                    handled_by="生产基地能源运维专员",
                    handle_note="已联动充电桩错峰策略并复核功率曲线。",
                    is_handle=True,
                )
            )

    async def _ensure_video_alarm_events(self, tenant: WohengTenantSpec) -> None:
        monitor = await self._session.scalar(select(m.VideoMonitor).where(m.VideoMonitor.ip_address == "10.26.7.51"))
        if monitor is None:
            monitor = m.VideoMonitor(
                location=f"{tenant.name}装卸月台",
                f_area=tenant.city_code,
                f_area_type="生产物流",
                video_url="rtsp://video.woheng-demo.local/loading-dock",
                status=0,
                ip_address="10.26.7.51",
                install_height=4.5,
                install_method="壁装",
                vedio_type="AI识别摄像机",
                pixel="400W",
                brand="Woheng",
                b_model="WH-CAM-AI-400",
                install_time="2026-01-15",
            )
            self._session.add(monitor)
            await self._session.flush()
        event_specs = (
            (2, "装卸月台烟火识别预警", "2026-08-28T10:18:00", False),
            (4, "夜间非授权区域入侵预警", "2026-08-28T22:46:00", True),
        )
        for event_type, desc, event_time, handled in event_specs:
            event = await self._session.scalar(
                select(m.VedioAlarmEvent).where(
                    m.VedioAlarmEvent.equipment_id == monitor.id,
                    m.VedioAlarmEvent.event_desc == desc,
                )
            )
            if event is None:
                event = m.VedioAlarmEvent(event_type=event_type, event_desc=desc, equipment_id=monitor.id)
                self._session.add(event)
            event.event_type = event_type
            event.event_desc = desc
            event.event_time = datetime.fromisoformat(event_time)
            event.equipment_id = monitor.id
            event.add_time = datetime.fromisoformat(event_time)
            event.is_handle = handled

    async def _tenant_counts(self) -> dict[str, int]:
        return {
            "equipment": int(await self._session.scalar(select(func.count(m.MonitorEquipment.id))) or 0),
            "activities": int(await self._session.scalar(select(func.count(m.GhgActivityRecord.id))) or 0),
            "reports": int(await self._session.scalar(select(func.count(m.GhgInventoryReport.id))) or 0),
            "microgrid_meter_bindings": int(
                await self._session.scalar(select(func.count(m.MicrogridAssetMeterBinding.id))) or 0
            ),
            "mqtt_sources": int(await self._session.scalar(select(func.count(m.MqttDataSource.id))) or 0),
            "mqtt_mappings": int(await self._session.scalar(select(func.count(m.MqttPointMapping.id))) or 0),
            "meter_readings": int(await self._session.scalar(select(func.count(m.MeterReadingFact.id))) or 0),
            "scope2_aggregates": int(await self._session.scalar(select(func.count(m.Scope2MeterAggregate.id))) or 0),
            "energy_interval_facts": int(await self._session.scalar(select(func.count(m.EnergyIntervalFact.id))) or 0),
            "workload_facts": int(await self._session.scalar(select(func.count(m.EquipmentWorkloadFact.id))) or 0),
            "benchmark_profiles": int(await self._session.scalar(select(func.count(m.EnergyBenchmarkProfile.id))) or 0),
            "benchmark_items": int(await self._session.scalar(select(func.count(m.EnergyBenchmarkItem.id))) or 0),
            "policy_benchmark_profiles": int(
                await self._session.scalar(
                    select(func.count(m.EnergyBenchmarkProfile.id)).where(
                        m.EnergyBenchmarkProfile.library_type.in_(("policy_industry", "equipment_efficiency"))
                    )
                )
                or 0
            ),
            "equipment_efficiency_items": int(
                await self._session.scalar(
                    select(func.count(m.EnergyBenchmarkItem.id))
                    .join(m.EnergyBenchmarkProfile, m.EnergyBenchmarkProfile.id == m.EnergyBenchmarkItem.profile_id)
                    .where(m.EnergyBenchmarkProfile.library_type == "equipment_efficiency")
                    .where(m.EnergyBenchmarkItem.metric_code == "energy_efficiency_level")
                )
                or 0
            ),
            "equipment_efficiency_devices": int(
                await self._session.scalar(
                    select(func.count(m.MonitorEquipment.id)).where(
                        m.MonitorEquipment.energy_efficiency_level.is_not(None)
                    )
                )
                or 0
            ),
            "measurement_boundaries": int(
                await self._session.scalar(select(func.count(m.MeasurementBoundary.id))) or 0
            ),
            "measurement_boundary_members": int(
                await self._session.scalar(select(func.count(m.MeasurementBoundaryMember.id))) or 0
            ),
            "boundary_bound_energy_facts": int(
                await self._session.scalar(
                    select(func.count(m.EnergyIntervalFact.id)).where(
                        m.EnergyIntervalFact.measurement_boundary_id.is_not(None)
                    )
                )
                or 0
            ),
            "in_money": int(await self._session.scalar(select(func.count(m.InMoney.id))) or 0),
            "out_money": int(await self._session.scalar(select(func.count(m.OutMoney.id))) or 0),
            "employee_commute": int(await self._session.scalar(select(func.count(m.EmployeeCommute.id))) or 0),
            "production_products": int(await self._session.scalar(select(func.count(m.ProductionProduct.id))) or 0),
            "product_prices": int(await self._session.scalar(select(func.count(m.ProductPrice.id))) or 0),
            "production_outputs": int(await self._session.scalar(select(func.count(m.ProductionOutputFact.id))) or 0),
            "production_resource_bindings": int(
                await self._session.scalar(select(func.count(m.ProductionResourceBinding.id))) or 0
            ),
            "product_footprint_studies": int(
                await self._session.scalar(select(func.count(m.ProductFootprintStudy.id))) or 0
            ),
            "product_footprint_results": int(
                await self._session.scalar(select(func.count(m.ProductFootprintResult.id))) or 0
            ),
            "supply_chain_suppliers": int(
                await self._session.scalar(select(func.count(m.SupplyChainSupplier.id))) or 0
            ),
            "supplier_disclosure_tasks": int(
                await self._session.scalar(select(func.count(m.SupplierDisclosureTask.id))) or 0
            ),
            "category_51_activities": int(
                await self._session.scalar(
                    select(func.count(m.GhgActivityRecord.id)).where(m.GhgActivityRecord.iso_category_code == "5.1")
                )
                or 0
            ),
            "reduction_projects": int(await self._session.scalar(select(func.count(m.ReductionProject.id))) or 0),
            "alarm_events": int(await self._session.scalar(select(func.count(m.AlarmEvent.id))) or 0),
            "video_alarm_events": int(await self._session.scalar(select(func.count(m.VedioAlarmEvent.id))) or 0),
        }

    async def _energy_interval_type_counts(self) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(m.EnergyIntervalFact.energy_type_code, func.count(m.EnergyIntervalFact.id))
                .where(m.EnergyIntervalFact.is_current.is_(True))
                .group_by(m.EnergyIntervalFact.energy_type_code)
                .order_by(m.EnergyIntervalFact.energy_type_code)
            )
        ).all()
        return {str(energy_type_code): int(row_count or 0) for energy_type_code, row_count in rows}

    async def _record_manifest(
        self,
        context: DemoExecutionContext,
        *,
        module_key: str,
        object_type: str,
        object_key: str,
        object_id: str | None,
        team_id: UUID | None,
        details: dict[str, object],
    ) -> None:
        row = await self._session.scalar(
            select(m.DemoManifest).where(
                m.DemoManifest.namespace == context.namespace,
                m.DemoManifest.object_type == object_type,
                m.DemoManifest.object_key == object_key,
            )
        )
        if row is None:
            row = m.DemoManifest(
                namespace=context.namespace,
                profile=context.profile,
                package_key=context.package_key,
                module_key=module_key,
                object_type=object_type,
                object_key=object_key,
                object_id=object_id,
                team_id=team_id,
                details=details,
            )
            self._session.add(row)
        else:
            row.profile = context.profile
            row.package_key = context.package_key
            row.module_key = module_key
            row.object_id = object_id
            row.team_id = team_id
            row.details = details
        await self._session.commit()

    def _result(
        self,
        context: DemoExecutionContext,
        action: DemoAction,
        applied: bool,
        status: DemoStepStatus,
        steps: Sequence[DemoPlanStep],
    ) -> DemoRunResult:
        return DemoRunResult(
            package_key=context.package_key,
            namespace=context.namespace,
            profile=context.profile,
            action=action,
            applied=applied,
            status=status,
            steps=steps,
        )
