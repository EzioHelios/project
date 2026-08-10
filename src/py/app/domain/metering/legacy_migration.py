"""Resumable, non-destructive migration from the legacy meter table."""

from __future__ import annotations

# ruff: noqa: S608
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from app.db import models as m

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


LEGACY_TABLE = "dataapp_ammeterindexvalue"
FACT_TABLE = "metering_meter_reading_fact"
MAX_BATCH_SIZE = 50_000


@dataclass(frozen=True, slots=True)
class LegacyMigrationResult:
    run_code: str
    source_high_watermark: int
    source_rows: int
    expected_facts: int
    inserted_facts: int
    duplicate_facts: int
    dry_run: bool


class LegacyMeterReadingMigration:
    """Expand legacy meter rows into canonical facts while preserving the source table."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        team_id: UUID,
        from_time: datetime,
        to_time: datetime | None = None,
        batch_size: int = 10_000,
    ) -> None:
        if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
            msg = "batch_size must be between 1 and 50000"
            raise ValueError(msg)
        self.session = session
        self.team_id = team_id
        self.from_time = from_time
        self.to_time = to_time
        self.batch_size = batch_size

    async def execute(self, *, dry_run: bool = False) -> LegacyMigrationResult:
        high_watermark = await self._source_high_watermark()
        source_rows, expected_facts = await self._source_counts(high_watermark)
        run_code = f"legacy-meter:{self.from_time.date().isoformat()}:{high_watermark}"
        if dry_run:
            return LegacyMigrationResult(
                run_code=run_code,
                source_high_watermark=high_watermark,
                source_rows=source_rows,
                expected_facts=expected_facts,
                inserted_facts=0,
                duplicate_facts=0,
                dry_run=True,
            )

        run = await self.session.scalar(select(m.DataMigrationRun).where(m.DataMigrationRun.run_code == run_code))
        if run is None:
            run = m.DataMigrationRun(
                team_id=self.team_id,
                run_code=run_code,
                migration_type="legacy_meter_reading",
                source_table=LEGACY_TABLE,
                target_table=FACT_TABLE,
                from_time=self.from_time,
                to_time=self.to_time,
                source_high_watermark=str(high_watermark),
                last_source_id=0,
                status="running",
                source_rows=source_rows,
                target_rows=0,
                skipped_rows=0,
                started_at=datetime.now(UTC).replace(tzinfo=None),
                run_config={"batch_size": self.batch_size, "skip_linked_mqtt": True},
            )
            self.session.add(run)
            await self.session.commit()
        elif run.status == "completed":
            return LegacyMigrationResult(
                run_code=run.run_code,
                source_high_watermark=high_watermark,
                source_rows=run.source_rows,
                expected_facts=run.target_rows,
                inserted_facts=max(run.target_rows - run.skipped_rows, 0),
                duplicate_facts=run.skipped_rows,
                dry_run=False,
            )
        else:
            run.status = "running"
            run.error_detail = None
            await self.session.commit()

        inserted_total = max(run.target_rows - run.skipped_rows, 0)
        duplicate_total = run.skipped_rows
        try:
            while (run.last_source_id or 0) < high_watermark:
                checkpoint, expanded, inserted = await self._migrate_batch(
                    last_source_id=run.last_source_id or 0,
                    high_watermark=high_watermark,
                )
                if checkpoint is None:
                    break
                inserted_total += inserted
                duplicate_total += expanded - inserted
                run.last_source_id = checkpoint
                run.target_rows = inserted_total + duplicate_total
                run.skipped_rows = duplicate_total
                await self.session.commit()
            run.status = "completed"
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            run.last_source_id = high_watermark
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            run = await self.session.scalar(select(m.DataMigrationRun).where(m.DataMigrationRun.run_code == run_code))
            if run is not None:
                run.status = "failed"
                run.error_detail = str(exc)[:4000]
                await self.session.commit()
            raise

        return LegacyMigrationResult(
            run_code=run_code,
            source_high_watermark=high_watermark,
            source_rows=source_rows,
            expected_facts=expected_facts,
            inserted_facts=inserted_total,
            duplicate_facts=duplicate_total,
            dry_run=False,
        )

    async def _source_high_watermark(self) -> int:
        result = await self.session.scalar(
            text(
                f"""
                select coalesce(max(id), 0)
                from {LEGACY_TABLE}
                where team_id = :team_id
                  and source_message_id is null
                  and equipment_id is not null
                  and coalesce(reading_time, end_time, start_time, add_time) >= :from_time
                  and (
                      cast(:to_time as timestamp) is null
                      or coalesce(reading_time, end_time, start_time, add_time) < cast(:to_time as timestamp)
                  )
                """
            ),
            {"team_id": self.team_id, "from_time": self.from_time, "to_time": self.to_time},
        )
        return int(result or 0)

    async def _source_counts(self, high_watermark: int) -> tuple[int, int]:
        row = (
            await self.session.execute(
                text(
                    f"""
                    select
                        count(*) as source_rows,
                        coalesce(sum(
                            (zygdn is not null)::int + (fygdn is not null)::int +
                            (zwgdn is not null)::int + (fwgdn is not null)::int +
                            (zygdnsz is not null)::int + (fygdnsz is not null)::int +
                            (zwgdnsz is not null)::int + (fwgdnsz is not null)::int
                        ), 0) as expected_facts
                    from {LEGACY_TABLE}
                    where team_id = :team_id
                      and id <= :high_watermark
                      and source_message_id is null
                      and equipment_id is not null
                      and coalesce(reading_time, end_time, start_time, add_time) >= :from_time
                      and (
                          cast(:to_time as timestamp) is null
                          or coalesce(reading_time, end_time, start_time, add_time) < cast(:to_time as timestamp)
                      )
                    """
                ),
                {
                    "team_id": self.team_id,
                    "high_watermark": high_watermark,
                    "from_time": self.from_time,
                    "to_time": self.to_time,
                },
            )
        ).one()
        return int(row.source_rows), int(row.expected_facts)

    async def _migrate_batch(self, *, last_source_id: int, high_watermark: int) -> tuple[int | None, int, int]:
        row = (
            await self.session.execute(
                text(
                    f"""
                    with source as (
                        select *
                        from {LEGACY_TABLE}
                        where team_id = :team_id
                          and id > :last_source_id
                          and id <= :high_watermark
                          and source_message_id is null
                          and equipment_id is not null
                          and coalesce(reading_time, end_time, start_time, add_time) >= :from_time
                          and (
                              cast(:to_time as timestamp) is null
                              or coalesce(reading_time, end_time, start_time, add_time) < cast(:to_time as timestamp)
                          )
                        order by id
                        limit :batch_size
                    ), expanded as (
                        select
                            source.id as legacy_id,
                            source.team_id,
                            source.equipment_id,
                            source.data_source,
                            coalesce(source.reading_time, source.end_time, source.start_time, source.add_time) as reading_time,
                            point.source_code,
                            point.point_code,
                            point.point_name,
                            point.direction,
                            point.energy_kind,
                            point.value_kind,
                            point.unit,
                            point.value
                        from source
                        cross join lateral (values
                            ('ZYGDN', 'forward_active_total', '正向有功总电能', 'forward', 'active', 'legacy_quantity', 'kWh', source.zygdn::numeric),
                            ('FYGDN', 'reverse_active_total', '反向有功总电能', 'reverse', 'active', 'legacy_quantity', 'kWh', source.fygdn::numeric),
                            ('ZWGDN', 'forward_reactive_total', '正向无功总电能', 'forward', 'reactive', 'legacy_quantity', 'kvarh', source.zwgdn::numeric),
                            ('FWGDN', 'reverse_reactive_total', '反向无功总电能', 'reverse', 'reactive', 'legacy_quantity', 'kvarh', source.fwgdn::numeric),
                            ('ZYGDNSZ', 'forward_active_total', '正向有功总电能', 'forward', 'active', 'register_index', 'kWh', source.zygdnsz::numeric),
                            ('FYGDNSZ', 'reverse_active_total', '反向有功总电能', 'reverse', 'active', 'register_index', 'kWh', source.fygdnsz::numeric),
                            ('ZWGDNSZ', 'forward_reactive_total', '正向无功总电能', 'forward', 'reactive', 'register_index', 'kvarh', source.zwgdnsz::numeric),
                            ('FWGDNSZ', 'reverse_reactive_total', '反向无功总电能', 'reverse', 'reactive', 'register_index', 'kvarh', source.fwgdnsz::numeric)
                        ) as point(source_code, point_code, point_name, direction, energy_kind, value_kind, unit, value)
                        where point.value is not null
                    ), inserted as (
                        insert into {FACT_TABLE} (
                            team_id, source_system, source_record_id, source_message_id, binding_id,
                            equipment_id, source_point_code, source_point_name, point_code, point_name,
                            energy_direction, energy_kind, tou_period, value_kind, raw_value,
                            normalized_value, unit, quality_status, source_type, reading_time, mapping_version
                        )
                        select
                            team_id,
                            case data_source
                                when 0 then 'yunji_legacy'
                                when 1 then 'infrared_hw_legacy'
                                else 'legacy_meter'
                            end,
                            'legacy:' || legacy_id::text || ':' || lower(source_code),
                            null,
                            null,
                            equipment_id,
                            source_code,
                            source_code,
                            point_code,
                            point_name,
                            direction,
                            energy_kind,
                            'total',
                            value_kind,
                            value::text,
                            value,
                            unit,
                            'valid',
                            data_source,
                            reading_time,
                            'legacy_migration_v1'
                        from expanded
                        on conflict on constraint uq_metering_fact_source_record_point do nothing
                        returning 1
                    )
                    select
                        (select max(id) from source) as checkpoint,
                        (select count(*) from expanded) as expanded_count,
                        (select count(*) from inserted) as inserted_count
                    """
                ),
                {
                    "team_id": self.team_id,
                    "last_source_id": last_source_id,
                    "high_watermark": high_watermark,
                    "from_time": self.from_time,
                    "to_time": self.to_time,
                    "batch_size": self.batch_size,
                },
            )
        ).one()
        checkpoint = int(row.checkpoint) if row.checkpoint is not None else None
        return checkpoint, int(row.expanded_count), int(row.inserted_count)


async def resolve_team_id(session: AsyncSession, team_slug: str) -> UUID:
    team_id = await session.scalar(select(m.Team.id).where(func.lower(m.Team.slug) == team_slug.strip().lower()))
    if team_id is None:
        msg = f"Unknown team slug: {team_slug}"
        raise ValueError(msg)
    return team_id
