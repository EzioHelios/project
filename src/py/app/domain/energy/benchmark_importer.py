from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.lib.demo_tenancy import require_demo_tenant
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

WAREHOUSE_BENCHMARK_PROFILE_NAME = "仓储行业标杆库-示例"
WAREHOUSE_BENCHMARK_SOURCE = "仓储行业标杆样本"


@dataclass(slots=True)
class EnergyBenchmarkSeedResult:
    """Result summary for warehouse benchmark sample data."""

    profiles_deleted: int = 0
    profiles_inserted: int = 0
    items_inserted: int = 0


async def seed_warehouse_energy_benchmark_data(session: AsyncSession) -> EnergyBenchmarkSeedResult:
    """Seed a reusable warehouse scenario benchmark library for the energy benchmark page."""

    await require_demo_tenant(session)
    result = EnergyBenchmarkSeedResult()
    result.profiles_deleted = await _delete_existing_warehouse_profiles(session)
    result.profiles_inserted = await _insert_warehouse_profiles(session)
    result.items_inserted = await _insert_warehouse_items(session)
    await session.commit()
    return result


async def _delete_existing_warehouse_profiles(session: AsyncSession) -> int:
    team_id = require_session_tenant_id(session)
    deleted = await session.execute(
        text(
            """
            delete from dataapp_energybenchmarkprofile
            where team_id = :team_id and name = :profile_name and source_name = :source_name
            """
        ),
        {
            "team_id": str(team_id),
            "profile_name": WAREHOUSE_BENCHMARK_PROFILE_NAME,
            "source_name": WAREHOUSE_BENCHMARK_SOURCE,
        },
    )
    return int(deleted.rowcount or 0)


async def _insert_warehouse_profiles(session: AsyncSession) -> int:
    team_id = require_session_tenant_id(session)
    inserted = await session.execute(
        text(
            """
            insert into dataapp_energybenchmarkprofile (
                team_id, name, industry_name, scenario, source_name, valid_from, valid_to,
                is_enabled, remark, created_at, updated_at
            )
            select
                t.id,
                :profile_name,
                '仓储物流',
                '仓储园区/常温仓/自动化立体库',
                :source_name,
                date '2026-01-01',
                date '2026-12-31',
                true,
                '仓储场景行业标杆样本, 用于能效对标模块演示和项目初始化。',
                now(),
                now()
            from team t
            where t.id = :team_id
            """
        ),
        {
            "team_id": str(team_id),
            "profile_name": WAREHOUSE_BENCHMARK_PROFILE_NAME,
            "source_name": WAREHOUSE_BENCHMARK_SOURCE,
        },
    )
    return int(inserted.rowcount or 0)


async def _insert_warehouse_items(session: AsyncSession) -> int:
    team_id = require_session_tenant_id(session)
    inserted = await session.execute(
        text(
            """
            with sample_items as (
                select *
                from (
                    values
                        (
                            'device', null, '仓储设备通用运行标杆', 'kwh_per_run_hour', '单位运行小时用电',
                            3.800000::numeric, 'kWh/h', 3.300000::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于仓储搬运、照明、充电等主要用电设备的运行小时对标。'
                        ),
                        (
                            'device', null, '仓储设备通用作业标杆', 'kwh_per_workload', '单位作业量用电',
                            1.600000::numeric, 'kWh/unit', 1.300000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于以作业量、托盘量、出入库量承接的设备级对标。'
                        ),
                        (
                            'use_system', 'handling', '仓储搬运系统', 'kwh_per_run_hour', '单位运行小时用电',
                            4.200000::numeric, 'kWh/h', 3.600000::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于 AGV、叉车、堆垛机、行吊等仓储作业系统。'
                        ),
                        (
                            'use_system', 'handling', '仓储搬运系统', 'kwh_per_workload', '单位作业量用电',
                            1.450000::numeric, 'kWh/unit', 1.200000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于以出入库作业量折算的搬运系统能效对标。'
                        ),
                        (
                            'use_system', 'lighting', '照明系统', 'kwh_per_run_hour', '单位运行小时用电',
                            1.050000::numeric, 'kWh/h', 0.850000::numeric, 12.00::numeric, 28.00::numeric,
                            'high', '适用于仓库、装卸区、办公区照明回路。'
                        ),
                        (
                            'use_system', 'charging', '充电系统', 'kwh_per_run_hour', '单位运行小时用电',
                            5.600000::numeric, 'kWh/h', 4.800000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于叉车、AGV、充电桩及集中充电区域。'
                        ),
                        (
                            'use_system', 'storage', '仓储设施系统', 'kwh_per_run_hour', '单位运行小时用电',
                            2.400000::numeric, 'kWh/h', 2.000000::numeric, 12.00::numeric, 30.00::numeric,
                            'medium', '适用于自动化立体库、输送线和仓储辅助设施。'
                        ),
                        (
                            'use_system', 'office', '办公及公共系统', 'kwh_per_run_hour', '单位运行小时用电',
                            1.200000::numeric, 'kWh/h', 0.950000::numeric, 12.00::numeric, 28.00::numeric,
                            'medium', '适用于办公、公共区域和后勤用能。'
                        ),
                        (
                            'use_system', 'other', '其他用能系统', 'kwh_per_run_hour', '单位运行小时用电',
                            3.000000::numeric, 'kWh/h', 2.500000::numeric, 12.00::numeric, 30.00::numeric,
                            'medium', '适用于暂未细分的仓储用能对象。'
                        ),
                        (
                            'area', null, '仓储区域通用面积标杆', 'kwh_per_m2', '单位面积用电量',
                            68.000000::numeric, 'kWh/m2', 58.000000::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于仓储建筑、装卸区、办公辅助区域的面积强度对标。'
                        ),
                        (
                            'area', null, '仓储区域通用面积标杆', 'tce_per_m2', '单位面积综合能耗',
                            0.008400::numeric, 'tce/m2', 0.007200::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于以标准煤折算的仓储区域面积强度对标。'
                        ),
                        (
                            'enterprise', null, '仓储园区综合面积标杆', 'kwh_per_m2', '单位面积用电量',
                            72.000000::numeric, 'kWh/m2', 62.000000::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于园区级仓储物流综合用电强度。'
                        ),
                        (
                            'enterprise', null, '仓储园区综合面积标杆', 'tce_per_m2', '单位面积综合能耗',
                            0.009000::numeric, 'tce/m2', 0.007800::numeric, 10.00::numeric, 25.00::numeric,
                            'high', '适用于园区级仓储物流综合能耗强度。'
                        ),
                        (
                            'product', null, '仓储处理量通用标杆', 'kgce_per_unit', '单位产品综合能耗',
                            0.120000::numeric, 'kgce/unit', 0.095000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于以出入库件数、托盘数或订单处理量承接的单位处理量对标。'
                        ),
                        (
                            'product', null, '仓储产值通用标杆', 'kgce_per_10k_value', '单位产值综合能耗',
                            8.500000::numeric, 'kgce/万元', 7.200000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于仓储作业产值强度和高价值低周转物料场景对标。'
                        ),
                        (
                            'device_type', 'forklift_charger', '叉车充电设备', 'kwh_per_run_hour', '单位运行小时用电',
                            6.200000::numeric, 'kWh/h', 5.200000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于叉车充电机、充电桩和集中充电回路。'
                        ),
                        (
                            'device_type', 'stacker_crane', '堆垛机', 'kwh_per_run_hour', '单位运行小时用电',
                            4.800000::numeric, 'kWh/h', 4.000000::numeric, 10.00::numeric, 25.00::numeric,
                            'medium', '适用于自动化立体库堆垛设备。'
                        ),
                        (
                            'device_type', 'warehouse_lighting', '仓储照明回路', 'kwh_per_run_hour', '单位运行小时用电',
                            0.900000::numeric, 'kWh/h', 0.750000::numeric, 12.00::numeric, 28.00::numeric,
                            'medium', '适用于 LED 照明、分区照明和公共区域照明回路。'
                        )
                ) as v(
                    target_type, target_code, target_name, metric_code, metric_name, benchmark_value, unit,
                    excellent_value, warning_threshold_pct, severe_threshold_pct, confidence_level, remark
                )
            )
            insert into dataapp_energybenchmarkitem (
                team_id, profile_id, target_type, target_code, target_name, metric_code, metric_name,
                benchmark_value, unit, excellent_value, warning_threshold_pct, severe_threshold_pct,
                source_name, confidence_level, is_enabled, remark, created_at, updated_at
            )
            select
                p.team_id,
                p.id,
                s.target_type,
                s.target_code,
                s.target_name,
                s.metric_code,
                s.metric_name,
                s.benchmark_value,
                s.unit,
                s.excellent_value,
                s.warning_threshold_pct,
                s.severe_threshold_pct,
                cast(:source_name as varchar),
                s.confidence_level,
                true,
                s.remark,
                now(),
                now()
            from dataapp_energybenchmarkprofile p
            cross join sample_items s
            where p.team_id = :team_id
              and p.name = cast(:profile_name as varchar)
              and p.source_name = cast(:source_name as varchar)
            """
        ),
        {
            "team_id": str(team_id),
            "profile_name": WAREHOUSE_BENCHMARK_PROFILE_NAME,
            "source_name": WAREHOUSE_BENCHMARK_SOURCE,
        },
    )
    return int(inserted.rowcount or 0)
