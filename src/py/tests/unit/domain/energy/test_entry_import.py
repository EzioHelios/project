from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from litestar.exceptions import ClientException

from app.domain.energy.usecases.imports import EnergyDatasetImportUseCase
from app.domain.energy.usecases.interval_facts import _data_quality, _decimal_or_none
from app.lib.tenancy import TENANT_ID_SESSION_KEY


def test_numeric_values_reject_nonfinite_and_keep_zero() -> None:
    assert _decimal_or_none("0") == 0
    assert _decimal_or_none("") is None
    for value in ("NaN", "Infinity", "-Infinity", "not-a-number"):
        with pytest.raises(ClientException):
            _decimal_or_none(value)


@pytest.fixture
def entry_session(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    session = MagicMock()
    session.info = {TENANT_ID_SESSION_KEY: uuid4()}
    session.scalar = AsyncMock(return_value=None)
    session.saved = SimpleNamespace(
        id=73,
        source_system="manual_csv",
        source_record_id="august",
        energy_type_code="natural_gas",
        period_start="2026-08-01",
        period_end="2026-08-31",
        amount=0,
        unit="m3",
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    @asynccontextmanager
    async def nested():
        yield

    session.begin_nested = nested
    payload = {
        "source_system": "manual_csv",
        "source_record_id": "august",
        "energy_type_code": "natural_gas",
        "period_start": datetime(2026, 8, 1),  # noqa: DTZ001 - energy facts store local naive timestamps
        "period_end": datetime(2026, 8, 31),  # noqa: DTZ001 - energy facts store local naive timestamps
        "amount": 0,
        "unit": "m3",
    }
    monkeypatch.setattr(
        "app.domain.energy.usecases.imports._normalize_energy_interval_fact_data", AsyncMock(return_value=payload)
    )
    return session


@pytest.mark.anyio
async def test_preview_is_read_only_and_reports_in_file_duplicate(entry_session: MagicMock) -> None:
    result = await EnergyDatasetImportUseCase(entry_session).import_rows(
        dataset="energy_interval_facts",
        rows=[{"source_record_id": "august"}] * 2,
        preview=True,
    )
    assert result.imported_count == 0
    assert result.imported_ids == []
    assert result.records[0]["status"] == "ready"
    assert result.skipped_count == 1
    assert "未覆盖" in result.errors[0]["message"]
    entry_session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_duplicate_import_never_updates_existing_record(entry_session: MagicMock) -> None:
    entry_session.scalar.return_value = 42
    result = await EnergyDatasetImportUseCase(entry_session).import_rows(
        dataset="energy_interval_facts",
        rows=[{"source_record_id": "august"}],
    )
    assert result.imported_count == 0
    assert result.skipped_count == 1
    assert result.imported_ids == []
    assert entry_session.scalar.await_count == 1
    entry_session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_insert_returns_actual_id_and_handles_concurrent_conflict(entry_session: MagicMock) -> None:
    entry_session.scalar.side_effect = [None, entry_session.saved]
    result = await EnergyDatasetImportUseCase(entry_session).import_rows(
        dataset="energy_interval_facts",
        rows=[{"source_record_id": "august"}],
    )
    assert result.imported_ids == [73]
    assert result.records[0]["amount"] == 0
    assert result.imported_count == 1
    statement = str(entry_session.scalar.call_args.args[0])
    assert "DO NOTHING" in statement
    assert "DO UPDATE" not in statement
    entry_session.scalar.side_effect = [None, None]
    conflict = await EnergyDatasetImportUseCase(entry_session).import_rows(
        dataset="energy_interval_facts",
        rows=[{"source_record_id": "august"}],
    )
    assert conflict.imported_count == 0
    assert conflict.skipped_count == 1


def test_legacy_quality_is_preserved_when_editing_existing_records() -> None:
    assert _data_quality("generated") == "generated"
    assert _data_quality("provisional") == "provisional"
    with pytest.raises(ClientException):
        _data_quality("invalid")
