"""Deterministic standards-rule coverage for climate governance."""

from decimal import Decimal

import pytest

from app.domain.climate_governance.domain import (
    assess_cdp_readiness,
    assess_re100_progress,
    assess_sbti_progress,
    evaluate_renewable_claim,
)

pytestmark = pytest.mark.unit


def test_sbti_scope3_threshold_and_coverage() -> None:
    result = assess_sbti_progress(
        reporting_year=2026,
        scope1_tco2e=Decimal(100),
        scope2_tco2e=Decimal(100),
        scope3_tco2e=Decimal(800),
        baseline_year=2024,
        baseline_tco2e=Decimal(1200),
        target_year=2030,
        reduction_pct=Decimal(42),
        scope12_coverage_pct=Decimal(95),
        scope3_coverage_pct=Decimal(60),
    )

    assert result["scope3TargetRequired"] is True
    assert result["status"] == "needs_attention"
    assert next(check for check in result["checks"] if check["code"] == "scope3_coverage")["passed"] is False


def test_sbti_internal_target_path_is_reproducible() -> None:
    result = assess_sbti_progress(
        reporting_year=2027,
        scope1_tco2e=Decimal(300),
        scope2_tco2e=Decimal(300),
        scope3_tco2e=Decimal(300),
        baseline_year=2025,
        baseline_tco2e=Decimal(1000),
        target_year=2030,
        reduction_pct=Decimal(50),
        scope12_coverage_pct=Decimal(100),
        scope3_coverage_pct=Decimal(67),
    )

    assert result["targetPathTco2e"] == 800.0
    assert result["gapTco2e"] == 100.0
    assert result["trajectoryKind"] == "internal_linear_tracking"


def test_cdp_result_is_internal_readiness() -> None:
    result = assess_cdp_readiness(
        reporting_year=2026,
        domains={
            "governance": True,
            "risks": False,
            "strategy": True,
            "inventory": True,
            "energy": True,
            "targets": True,
            "actions": True,
            "verification": False,
        },
    )

    assert result["readinessPct"] == 75.0
    assert result["resultKind"] == "internal_readiness"


def test_renewable_claim_requires_market_vintage_retirement_and_evidence() -> None:
    status, reasons = evaluate_renewable_claim(
        quantity_mwh=Decimal(100),
        reporting_year=2026,
        generation_country="CN",
        consumption_country="CN",
        vintage_year=2025,
        ownership_status="held",
        evidence_reference=None,
    )

    assert status == "needs_review"
    assert len(reasons) == 3


def test_re100_progress_never_exceeds_total_electricity() -> None:
    result = assess_re100_progress(
        reporting_year=2026,
        total_electricity_mwh=Decimal(100),
        eligible_mwh=Decimal(120),
        pending_mwh=Decimal(10),
        target_pct=Decimal(100),
    )

    assert result["eligibleRenewableMwh"] == 100.0
    assert result["progressPct"] == 100.0
    assert result["gapMwh"] == 0.0
