"""Versioned, deterministic rules for the lightweight climate-governance workbench."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


class ClimateGovernanceError(ValueError):
    """Raised when a climate-governance command violates a business invariant."""


@dataclass(frozen=True)
class RuleSet:
    """Immutable code-owned rule set frozen into every assessment run."""

    code: str
    version: str
    effective_from: str
    source_name: str
    source_url: str

    def snapshot(self) -> dict[str, str]:
        return asdict(self)


SBTI_RULESET = RuleSet(
    code="SBTI_CORPORATE",
    version="NZS-1.3.1+NTC-5.3.1",
    effective_from="2026-04",
    source_name="SBTi Corporate Net-Zero Standard and Near-Term Criteria",
    source_url="https://sciencebasedtargets.org/corporate-net-zero",
)
CDP_RULESET = RuleSet(
    code="CDP_CORPORATE_CLIMATE",
    version="2026",
    effective_from="2026",
    source_name="CDP Full Corporate Questionnaire 2026",
    source_url="https://www.cdp.net/en/disclose/how-to-disclose",
)
RE100_RULESET = RuleSet(
    code="RE100_CORPORATE_ELECTRICITY",
    version="TECH-2025-03+REPORTING-2026-07",
    effective_from="2026-07",
    source_name="RE100 Technical Criteria and Reporting Guidance",
    source_url="https://www.theclimategroup.org/re100/technical-guidance",
)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal(0)
    return (numerator / denominator * Decimal(100)).quantize(Decimal("0.01"))


def _check(
    code: str, label: str, passed: bool, *, value: Any = None, threshold: Any = None, severity: str = "blocking"
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "passed": passed,
        "value": value,
        "threshold": threshold,
        "severity": severity,
    }


def assess_sbti_progress(
    *,
    reporting_year: int,
    scope1_tco2e: Decimal,
    scope2_tco2e: Decimal,
    scope3_tco2e: Decimal,
    baseline_year: int | None,
    baseline_tco2e: Decimal | None,
    target_year: int | None,
    reduction_pct: Decimal | None,
    scope12_coverage_pct: Decimal,
    scope3_coverage_pct: Decimal,
) -> dict[str, Any]:
    """Assess current SBTi readiness and an internal linear management trajectory."""

    current = scope1_tco2e + scope2_tco2e + scope3_tco2e
    scope3_share = _pct(scope3_tco2e, current)
    scope3_required = scope3_share >= Decimal(40)
    target_configured = all(value is not None for value in (baseline_year, baseline_tco2e, target_year, reduction_pct))
    years_valid = bool(target_configured and baseline_year < target_year)  # type: ignore[operator]
    checks = [
        _check("inventory_available", "组织温室气体盘查已形成", current > 0, value=float(current)),
        _check(
            "scope12_coverage",
            "Scope 1和Scope 2目标覆盖率",
            scope12_coverage_pct >= Decimal(95),
            value=float(scope12_coverage_pct),
            threshold=95,
        ),
        _check(
            "scope3_materiality",
            "Scope 3重要性判定",
            True,
            value=float(scope3_share),
            threshold=40,
            severity="information",
        ),
        _check(
            "scope3_coverage",
            "Scope 3目标覆盖率",
            (not scope3_required) or scope3_coverage_pct >= Decimal(67),
            value=float(scope3_coverage_pct),
            threshold=67 if scope3_required else None,
        ),
        _check("target_configured", "基准年和目标已配置", target_configured),
        _check("target_period", "基准年早于目标年", years_valid),
    ]

    target_path: Decimal | None = None
    target_end: Decimal | None = None
    gap: Decimal | None = None
    target_completion_pct: Decimal | None = None
    if target_configured and years_valid and baseline_tco2e is not None and reduction_pct is not None:
        duration = Decimal(target_year - baseline_year)  # type: ignore[operator]
        elapsed = Decimal(max(0, min(reporting_year - baseline_year, target_year - baseline_year)))  # type: ignore[operator]
        target_end = baseline_tco2e * (Decimal(1) - reduction_pct / Decimal(100))
        target_path = baseline_tco2e - (baseline_tco2e - target_end) * elapsed / duration
        gap = current - target_path
        reduction_required = baseline_tco2e - target_end
        if reduction_required > 0:
            target_completion_pct = min(
                Decimal(100),
                max(Decimal(0), _pct(baseline_tco2e - current, reduction_required)),
            )

    blocking = [item for item in checks if item["severity"] == "blocking" and not item["passed"]]
    return {
        "framework": "sbti",
        "status": "ready" if not blocking else "needs_attention",
        "reportingYear": reporting_year,
        "actualTco2e": float(current),
        "scope1Tco2e": float(scope1_tco2e),
        "scope2Tco2e": float(scope2_tco2e),
        "scope3Tco2e": float(scope3_tco2e),
        "scope3SharePct": float(scope3_share),
        "scope3TargetRequired": scope3_required,
        "targetPathTco2e": float(target_path) if target_path is not None else None,
        "targetEndTco2e": float(target_end) if target_end is not None else None,
        "gapTco2e": float(gap) if gap is not None else None,
        "targetCompletionPct": float(target_completion_pct) if target_completion_pct is not None else None,
        "readinessPct": float(_pct(Decimal(len(checks) - len(blocking)), Decimal(len(checks)))),
        "trajectoryKind": "internal_linear_tracking",
        "checks": checks,
    }


def assess_cdp_readiness(*, reporting_year: int, domains: dict[str, bool]) -> dict[str, Any]:
    """Build an internal CDP climate-disclosure readiness result, never an official score."""

    labels = {
        "governance": "治理责任",
        "risks": "气候风险与机遇",
        "strategy": "战略与转型计划",
        "inventory": "温室气体盘查",
        "energy": "能源与电力数据",
        "targets": "气候目标",
        "actions": "减排措施",
        "verification": "核查与证据",
    }
    checks = [
        _check(
            f"cdp_{code}",
            label,
            bool(domains.get(code)),
            severity="blocking" if code in {"inventory", "energy", "targets"} else "warning",
        )
        for code, label in labels.items()
    ]
    completed = sum(item["passed"] for item in checks)
    blocking = [item for item in checks if item["severity"] == "blocking" and not item["passed"]]
    return {
        "framework": "cdp",
        "status": "ready" if not blocking and completed == len(checks) else "needs_attention",
        "reportingYear": reporting_year,
        "readinessPct": float(_pct(Decimal(completed), Decimal(len(checks)))),
        "completedDomains": completed,
        "totalDomains": len(checks),
        "checks": checks,
        "resultKind": "internal_readiness",
    }


def evaluate_renewable_claim(
    *,
    quantity_mwh: Decimal,
    reporting_year: int,
    generation_country: str | None,
    consumption_country: str | None,
    vintage_year: int | None,
    ownership_status: str,
    evidence_reference: str | None,
) -> tuple[str, list[str]]:
    """Apply conservative claim-quality checks shared by RE100 and Scope 2 claims."""

    reasons: list[str] = []
    if quantity_mwh <= 0:
        reasons.append("电量必须大于0")
    if not generation_country or not consumption_country or generation_country != consumption_country:
        reasons.append("发电与用电市场边界不一致")
    if vintage_year != reporting_year:
        reasons.append("电力属性年份与报告年度不一致")
    if ownership_status not in {"retired", "allocated"}:
        reasons.append("电力属性尚未完成注销或唯一归属")
    if not evidence_reference:
        reasons.append("缺少合同、证书或注销凭证")
    return ("eligible" if not reasons else "needs_review", reasons)


def assess_re100_progress(
    *,
    reporting_year: int,
    total_electricity_mwh: Decimal,
    eligible_mwh: Decimal,
    pending_mwh: Decimal,
    target_pct: Decimal,
) -> dict[str, Any]:
    """Calculate renewable-electricity progress without conflating credits and electricity."""

    eligible = min(max(eligible_mwh, Decimal(0)), max(total_electricity_mwh, Decimal(0)))
    progress = _pct(eligible, total_electricity_mwh)
    self_reported = _pct(min(eligible + max(pending_mwh, Decimal(0)), total_electricity_mwh), total_electricity_mwh)
    target_mwh = total_electricity_mwh * target_pct / Decimal(100)
    gap = max(Decimal(0), target_mwh - eligible)
    checks = [
        _check(
            "electricity_denominator",
            "组织用电边界已形成",
            total_electricity_mwh > 0,
            value=float(total_electricity_mwh),
        ),
        _check(
            "eligible_claims", "可再生电力属性已完成资格校验", eligible > 0, value=float(eligible), severity="warning"
        ),
        _check(
            "target_progress",
            "达到年度可再生电力目标",
            progress >= target_pct,
            value=float(progress),
            threshold=float(target_pct),
            severity="warning",
        ),
    ]
    return {
        "framework": "re100",
        "status": "on_track" if progress >= target_pct and total_electricity_mwh > 0 else "needs_attention",
        "reportingYear": reporting_year,
        "totalElectricityMwh": float(total_electricity_mwh),
        "eligibleRenewableMwh": float(eligible),
        "pendingRenewableMwh": float(pending_mwh),
        "progressPct": float(progress),
        "selfReportedPct": float(self_reported),
        "targetPct": float(target_pct),
        "gapMwh": float(gap),
        "checks": checks,
    }
