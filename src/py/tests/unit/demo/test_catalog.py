"""Demo package catalog validation."""

from __future__ import annotations

import pytest

from app.demo.catalog import load_demo_manifest, load_demo_profile, load_demo_verification


@pytest.mark.unit
@pytest.mark.parametrize("profile_code", ["foundation", "transition", "leadership"])
def test_xiangtai_profiles_are_declared_and_bounded(profile_code: str) -> None:
    manifest = load_demo_manifest("xiangtai")
    profile = load_demo_profile("xiangtai", profile_code)

    assert profile.code == profile_code
    assert profile_code in manifest.climate_profiles
    assert sum(claim.share_pct for claim in profile.re100.claims) <= 100
    assert profile.re100.electricity_data_year == manifest.source_data_year
    assert 0 <= profile.sbti.scope12_coverage_pct <= 100
    assert 0 <= profile.sbti.scope3_coverage_pct <= 100
    assert all(project.code.startswith("DEMO-XT-") for project in manifest.reduction_projects)


@pytest.mark.unit
def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="not declared"):
        load_demo_profile("xiangtai", "unknown")


@pytest.mark.unit
def test_xiangtai_verification_covers_all_inventory_categories() -> None:
    verification = load_demo_verification("xiangtai")
    covered = {
        category
        for evidence in verification.evidence
        if evidence.target_kind == "activity"
        for category in evidence.iso_category_codes
    }

    assert covered == {"1.1", "1.2", "1.4", "2.1", "2.2", "3.1", "4.4"}
    assert {item.review_status for item in verification.evidence} == {"approved", "pending"}
    assert {item.status for item in verification.findings} == {"open", "closed"}
