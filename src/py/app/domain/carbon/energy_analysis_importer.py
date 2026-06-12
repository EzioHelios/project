from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

GENERATED_INTERVAL_SOURCES = ("meter_hourly", "meter_daily")
GENERATED_WORKLOAD_SOURCE = "meter_run_hours"
DEFAULT_TARIFF_CODE = "default_electricity_tou"


@dataclass(slots=True)
class EnergyAnalysisSeedResult:
    """Result summary for generated energy analysis sample data."""

    use_systems: int = 0
    use_system_bindings: int = 0
    tariff_plans: int = 0
    tariff_segments: int = 0
    hourly_facts: int = 0
    daily_facts: int = 0
    workload_facts: int = 0


async def seed_energy_analysis_data(session: AsyncSession) -> EnergyAnalysisSeedResult:
    """Seed reusable analysis-domain data from existing equipment and meter readings."""

    await session.execute(text("select set_config('app.tenant_bypass', 'true', true)"))
    await _upsert_use_systems(session)
    await _upsert_use_system_bindings(session)
    await _upsert_default_tariff(session)
    await _rebuild_energy_interval_facts(session)
    await _rebuild_equipment_workload_facts(session)
    await session.commit()
    return await _collect_result(session)


async def _upsert_use_systems(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            insert into dataapp_energyusesystem (
                team_id, code, name, system_type, parent_code, is_enabled, remark, created_at, updated_at
            )
            select t.id, v.code, v.name, v.system_type, null, true, v.remark, now(), now()
            from team t
            cross join (
                values
                    ('handling', '仓储搬运系统', 'material_handling', 'AGV、叉车、堆垛机、行吊等仓储作业设备。'),
                    ('lighting', '照明系统', 'lighting', '仓库、办公区等照明用能。'),
                    ('charging', '充电系统', 'charging', '充电桩、充电区和相关设备。'),
                    ('storage', '仓储设施系统', 'storage', '无人平库、仓库和存储设施。'),
                    ('pv', '光伏发电系统', 'renewable_generation', '光伏逆变器和发电监测设备。'),
                    ('office', '办公及公共系统', 'office', '办公区、公共区域和综合用能。'),
                    ('other', '其他用能系统', 'other', '暂未细分的用能对象。')
            ) as v(code, name, system_type, remark)
            on conflict (team_id, code) do update set
                name = excluded.name,
                system_type = excluded.system_type,
                remark = excluded.remark,
                is_enabled = true,
                updated_at = now()
            """
        )
    )


async def _upsert_use_system_bindings(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            insert into dataapp_energyusesystembinding (
                team_id, system_code, equipment_id, equipment_code, equipment_name, sector_id, area_id, area_name,
                valid_from, valid_to, confidence_level, is_primary, remark, created_at, updated_at
            )
            select
                e.team_id,
                case
                    when coalesce(e.name, '') like '%充电%' or coalesce(s.name, '') like '%充电%' then 'charging'
                    when coalesce(e.name, '') like '%照明%' or coalesce(s.name, '') like '%照明%' then 'lighting'
                    when coalesce(e.name, '') like '%AGV%' or coalesce(s.name, '') like '%AGV%'
                      or coalesce(e.name, '') like '%叉车%' or coalesce(s.name, '') like '%叉车%'
                      or coalesce(e.name, '') like '%堆垛%' or coalesce(s.name, '') like '%堆垛%'
                      or coalesce(e.name, '') like '%行吊%' or coalesce(s.name, '') like '%行吊%'
                      or coalesce(e.name, '') like '%取缆%' or coalesce(s.name, '') like '%取缆%' then 'handling'
                    when e.category = 1 or coalesce(e.name, '') like '%光伏%' or coalesce(s.name, '') like '%光伏%' then 'pv'
                    when coalesce(e.name, '') like '%仓库%' or coalesce(s.name, '') like '%仓库%'
                      or coalesce(e.name, '') like '%平库%' or coalesce(s.name, '') like '%平库%' then 'storage'
                    when coalesce(e.name, '') like '%办公%' or coalesce(s.name, '') like '%办公%' then 'office'
                    else 'other'
                end as system_code,
                e.id,
                e.code,
                e.name,
                e.sector_id,
                coalesce(s.area_id::text, s.code, e.warehouse_code),
                coalesce(s.name, e.warehouse_name),
                null,
                null,
                'medium',
                true,
                '由设备和区域名称规则生成, 用于能源分析首版归类。',
                now(),
                now()
            from dataapp_monitorequipment e
            left join dataapp_monitorsector s on s.id = e.sector_id
            on conflict (team_id, system_code, equipment_id) do update set
                equipment_code = excluded.equipment_code,
                equipment_name = excluded.equipment_name,
                sector_id = excluded.sector_id,
                area_id = excluded.area_id,
                area_name = excluded.area_name,
                confidence_level = excluded.confidence_level,
                is_primary = true,
                remark = excluded.remark,
                updated_at = now()
            """
        )
    )


async def _upsert_default_tariff(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            insert into dataapp_energytariffplan (
                team_id, code, name, energy_type_code, currency, effective_from, effective_to, is_enabled,
                remark, created_at, updated_at
            )
            select
                t.id,
                :code,
                '默认外购电力分时电价',
                'purchased_electricity',
                'CNY',
                date '2023-01-01',
                null,
                true,
                '样本电价方案, 用于能源分析成本测算; 上线时应替换为企业真实尖峰平谷价格。',
                now(),
                now()
            from team t
            on conflict (team_id, code) do update set
                name = excluded.name,
                energy_type_code = excluded.energy_type_code,
                currency = excluded.currency,
                effective_from = excluded.effective_from,
                effective_to = excluded.effective_to,
                is_enabled = true,
                remark = excluded.remark,
                updated_at = now()
            """
        ),
        {"code": DEFAULT_TARIFF_CODE},
    )
    await session.execute(
        text(
            """
            delete from dataapp_energytariffsegment s
            using dataapp_energytariffplan p
            where s.plan_id = p.id and p.code = :code
            """
        ),
        {"code": DEFAULT_TARIFF_CODE},
    )
    await session.execute(
        text(
            """
            insert into dataapp_energytariffsegment (
                team_id, plan_id, segment_type, start_time, end_time, price, unit, sort_index, remark,
                created_at, updated_at
            )
            select
                p.team_id,
                p.id,
                v.segment_type,
                v.start_time::time,
                v.end_time::time,
                v.price,
                'CNY/kWh',
                v.sort_index,
                '样本分时电价段。',
                now(),
                now()
            from dataapp_energytariffplan p
            cross join (
                values
                    ('valley', '00:00', '08:00', 0.350000::numeric, 1),
                    ('flat', '08:00', '10:00', 0.800000::numeric, 2),
                    ('peak', '10:00', '15:00', 1.200000::numeric, 3),
                    ('flat', '15:00', '18:00', 0.800000::numeric, 4),
                    ('peak', '18:00', '21:00', 1.200000::numeric, 5),
                    ('flat', '21:00', '23:59:59', 0.800000::numeric, 6)
            ) as v(segment_type, start_time, end_time, price, sort_index)
            where p.code = :code
            """
        ),
        {"code": DEFAULT_TARIFF_CODE},
    )


async def _rebuild_energy_interval_facts(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            delete from dataapp_energyintervalfact
            where source_system in ('meter_hourly', 'meter_daily')
            """
        )
    )
    await session.execute(
        text(
            """
            with readings as (
                select
                    v.team_id,
                    v.equipment_id,
                    v.ammeter_id,
                    v.ammeter_name,
                    v.area_id,
                    v.area_name,
                    v.reading_time,
                    v.zygdnsz,
                    lag(v.zygdnsz) over (partition by v.team_id, v.equipment_id order by v.reading_time) as prev_value
                from dataapp_ammeterindexvalue v
                where v.reading_time is not null and v.zygdnsz is not null and v.equipment_id is not null
            ),
            deltas as (
                select
                    team_id,
                    equipment_id,
                    ammeter_id,
                    ammeter_name,
                    area_id,
                    area_name,
                    reading_time,
                    zygdnsz - prev_value as delta_kwh
                from readings
                where prev_value is not null and zygdnsz - prev_value > 0 and zygdnsz - prev_value < 100000
            ),
            hourly as (
                select
                    d.team_id,
                    d.equipment_id,
                    date_trunc('hour', d.reading_time) as period_start,
                    max(d.ammeter_id) as ammeter_id,
                    max(d.ammeter_name) as ammeter_name,
                    max(d.area_id) as meter_area_id,
                    max(d.area_name) as meter_area_name,
                    sum(d.delta_kwh)::numeric(18, 6) as amount,
                    count(*)::int as reading_count
                from deltas d
                group by d.team_id, d.equipment_id, date_trunc('hour', d.reading_time)
            ),
            priced as (
                select
                    h.*,
                    e.code as equipment_code,
                    coalesce(e.name, h.ammeter_name) as equipment_name,
                    coalesce(b.area_id, h.meter_area_id) as area_id,
                    coalesce(b.area_name, h.meter_area_name) as area_name,
                    b.system_code as use_system_code,
                    s.name as use_system_name,
                    case
                        when extract(hour from h.period_start) < 8 then 'valley'
                        when extract(hour from h.period_start) in (10, 11, 12, 13, 14, 18, 19, 20) then 'peak'
                        else 'flat'
                    end as segment_type
                from hourly h
                left join dataapp_monitorequipment e on e.id = h.equipment_id
                left join dataapp_energyusesystembinding b on b.team_id = h.team_id and b.equipment_id = h.equipment_id and b.is_primary
                left join dataapp_energyusesystem s on s.team_id = h.team_id and s.code = b.system_code
            )
            insert into dataapp_energyintervalfact (
                team_id, source_system, source_record_id, energy_type_code, equipment_id, equipment_code,
                equipment_name, area_id, area_name, use_system_code, use_system_name, granularity, period_start,
                period_end, amount, unit, cost_cny, tariff_segment_type, reading_count, data_quality, remark,
                created_at, updated_at
            )
            select
                p.team_id,
                'meter_hourly',
                'meter_hourly:' || p.equipment_id || ':' || to_char(p.period_start, 'YYYYMMDDHH24'),
                'purchased_electricity',
                p.equipment_id,
                p.equipment_code,
                p.equipment_name,
                p.area_id,
                p.area_name,
                p.use_system_code,
                p.use_system_name,
                'hour',
                p.period_start,
                p.period_start + interval '1 hour',
                p.amount,
                'kWh',
                case p.segment_type when 'peak' then p.amount * 1.2 when 'valley' then p.amount * 0.35 else p.amount * 0.8 end,
                p.segment_type,
                p.reading_count,
                'measured',
                '由电表累计示值差分生成。',
                now(),
                now()
            from priced p
            """
        )
    )
    await session.execute(
        text(
            """
            insert into dataapp_energyintervalfact (
                team_id, source_system, source_record_id, energy_type_code, equipment_id, equipment_code,
                equipment_name, area_id, area_name, use_system_code, use_system_name, granularity, period_start,
                period_end, amount, unit, cost_cny, tariff_segment_type, reading_count, data_quality, remark,
                created_at, updated_at
            )
            select
                team_id,
                'meter_daily',
                'meter_daily:' || equipment_id || ':' || to_char(date_trunc('day', period_start), 'YYYYMMDD'),
                energy_type_code,
                equipment_id,
                max(equipment_code),
                max(equipment_name),
                max(area_id),
                max(area_name),
                max(use_system_code),
                max(use_system_name),
                'day',
                date_trunc('day', period_start),
                date_trunc('day', period_start) + interval '1 day',
                sum(amount),
                'kWh',
                sum(cost_cny),
                null,
                sum(reading_count),
                'measured',
                '由小时电量事实聚合生成。',
                now(),
                now()
            from dataapp_energyintervalfact
            where source_system = 'meter_hourly'
            group by team_id, equipment_id, energy_type_code, date_trunc('day', period_start)
            """
        )
    )


async def _rebuild_equipment_workload_facts(session: AsyncSession) -> None:
    await session.execute(text("delete from dataapp_equipmentworkloadfact where source_system = 'meter_run_hours'"))
    await session.execute(
        text(
            """
            insert into dataapp_equipmentworkloadfact (
                team_id, source_system, source_record_id, equipment_id, equipment_code, equipment_name, area_id,
                area_name, use_system_code, workload_type, period_start, period_end, workload_amount, workload_unit,
                run_hours, record_status, remark, created_at, updated_at
            )
            select
                team_id,
                'meter_run_hours',
                'meter_run_hours:' || equipment_id || ':' || to_char(date_trunc('day', period_start), 'YYYYMMDD'),
                equipment_id,
                max(equipment_code),
                max(equipment_name),
                max(area_id),
                max(area_name),
                max(use_system_code),
                'run_hours',
                date_trunc('day', period_start),
                date_trunc('day', period_start) + interval '1 day',
                count(*)::numeric,
                'h',
                count(*)::numeric,
                'confirmed',
                '由小时电量大于 0 的区间派生运行小时。',
                now(),
                now()
            from dataapp_energyintervalfact
            where source_system = 'meter_hourly' and amount > 0
            group by team_id, equipment_id, date_trunc('day', period_start)
            """
        )
    )


async def _collect_result(session: AsyncSession) -> EnergyAnalysisSeedResult:
    result = EnergyAnalysisSeedResult()
    result.use_systems = int((await session.execute(text("select count(*) from dataapp_energyusesystem"))).scalar_one() or 0)
    result.use_system_bindings = int((await session.execute(text("select count(*) from dataapp_energyusesystembinding"))).scalar_one() or 0)
    result.tariff_plans = int((await session.execute(text("select count(*) from dataapp_energytariffplan"))).scalar_one() or 0)
    result.tariff_segments = int((await session.execute(text("select count(*) from dataapp_energytariffsegment"))).scalar_one() or 0)
    result.hourly_facts = int(
        (
            await session.execute(
                text("select count(*) from dataapp_energyintervalfact where source_system = 'meter_hourly'")
            )
        ).scalar_one()
        or 0
    )
    result.daily_facts = int(
        (
            await session.execute(
                text("select count(*) from dataapp_energyintervalfact where source_system = 'meter_daily'")
            )
        ).scalar_one()
        or 0
    )
    result.workload_facts = int((await session.execute(text("select count(*) from dataapp_equipmentworkloadfact"))).scalar_one() or 0)
    return result
