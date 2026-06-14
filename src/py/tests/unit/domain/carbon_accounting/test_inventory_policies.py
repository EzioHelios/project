from __future__ import annotations

from app.domain.carbon_accounting.domain.policies import inventory_lock_block_reason, inventory_status


def test_inventory_status_is_empty_when_no_included_records() -> None:
    assert inventory_status(included_record_count=0, missing_result_count=0) == "empty"


def test_inventory_status_has_issues_when_included_records_have_missing_results() -> None:
    assert inventory_status(included_record_count=3, missing_result_count=1) == "issues"


def test_inventory_status_is_ready_when_included_records_are_complete() -> None:
    assert inventory_status(included_record_count=3, missing_result_count=0) == "ready"


def test_inventory_lock_is_blocked_when_no_included_records() -> None:
    assert inventory_lock_block_reason(included_record_count=0, missing_result_count=0) == "核算批次尚未生成清单"


def test_inventory_lock_is_blocked_when_results_are_missing() -> None:
    assert inventory_lock_block_reason(included_record_count=3, missing_result_count=1) == "核算批次存在缺失计算结果"


def test_inventory_lock_is_allowed_when_inventory_is_complete() -> None:
    assert inventory_lock_block_reason(included_record_count=3, missing_result_count=0) is None
