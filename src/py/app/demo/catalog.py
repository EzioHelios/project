"""Typed loader for package-owned demo data."""

from __future__ import annotations

from importlib.resources import files
from typing import TypeVar

import msgspec

T = TypeVar("T")


class DemoReductionTargetSpec(msgspec.Struct, frozen=True, kw_only=True):
    code: str
    name: str
    baseline_year: int
    target_year: int
    reduction_pct: float


class DemoReductionProjectSpec(msgspec.Struct, frozen=True, kw_only=True):
    code: str
    name: str
    category: str
    status: str
    reduction_status: str
    risk_level: str
    owner_name: str
    department_name: str
    area_code: str
    planned_start: str
    planned_end: str
    progress_pct: float
    investment_cny: float
    expected_reduction_tco2e: float
    monitored_reduction_tco2e: float
    objective: str
    implementation_plan: str
    inventory_impact_kind: str


class DemoPackageManifest(msgspec.Struct, frozen=True, kw_only=True):
    schema_version: str
    code: str
    name: str
    tenant_slug: str
    reporting_year: int
    source_data_year: int
    source_name: str
    adapters: list[str]
    climate_profiles: list[str]
    reduction_target: DemoReductionTargetSpec
    reduction_projects: list[DemoReductionProjectSpec]


class DemoSbtiSpec(msgspec.Struct, frozen=True, kw_only=True):
    baseline_year: int
    baseline_multiplier: float
    target_year: int
    reduction_pct: float
    scope12_coverage_pct: float
    scope3_coverage_pct: float
    scope2_method: str


class DemoCdpSpec(msgspec.Struct, frozen=True, kw_only=True):
    status: str
    owner_name: str
    domain_statuses: dict[str, bool]


class DemoRenewableClaimSpec(msgspec.Struct, frozen=True, kw_only=True):
    source_type: str
    share_pct: float
    technology: str
    ownership_status: str
    evidence_reference: str | None = None


class DemoRe100Spec(msgspec.Struct, frozen=True, kw_only=True):
    electricity_data_year: int
    target_year: int
    target_pct: float
    claims: list[DemoRenewableClaimSpec]


class DemoProfile(msgspec.Struct, frozen=True, kw_only=True):
    schema_version: str
    code: str
    name: str
    description: str
    sbti: DemoSbtiSpec
    cdp: DemoCdpSpec
    re100: DemoRe100Spec


class DemoVerificationEvidenceSpec(msgspec.Struct, frozen=True, kw_only=True):
    code: str
    file_name: str
    document_type: str
    content_type: str
    evidence_role: str
    target_kind: str
    iso_category_codes: list[str]
    review_status: str


class DemoVerificationFindingSpec(msgspec.Struct, frozen=True, kw_only=True):
    finding_no: str
    issue_type: str
    finding_type: str
    severity: str
    title: str
    description: str
    action_required: str
    iso_category_code: str
    status: str


class DemoVerificationSpec(msgspec.Struct, frozen=True, kw_only=True):
    schema_version: str
    project_no: str
    project_name: str
    project_type: str
    assurance_level: str
    materiality_threshold_pct: float
    verification_basis: str
    sampling_strategy: str
    site_visit_required: bool
    site_visit_status: str
    conclusion_status: str
    scope_description: str
    evidence: list[DemoVerificationEvidenceSpec]
    findings: list[DemoVerificationFindingSpec]


def _read_json(package_code: str, relative_path: str, target_type: type[T]) -> T:
    if package_code not in {"xiangtai"}:
        msg = f"Unknown demo package: {package_code}"
        raise ValueError(msg)
    resource = files("app.demo").joinpath(package_code, relative_path)
    return msgspec.json.decode(resource.read_bytes(), type=target_type)


def load_demo_manifest(package_code: str) -> DemoPackageManifest:
    """Load and validate one immutable demo package manifest."""

    return _read_json(package_code, "manifest.json", DemoPackageManifest)


def load_demo_profile(package_code: str, profile_code: str) -> DemoProfile:
    """Load one named climate-disclosure profile from the package."""

    manifest = load_demo_manifest(package_code)
    if profile_code not in manifest.climate_profiles:
        msg = f"Profile {profile_code!r} is not declared by demo package {package_code!r}"
        raise ValueError(msg)
    return _read_json(package_code, f"climate/{profile_code}.json", DemoProfile)


def load_demo_verification(package_code: str) -> DemoVerificationSpec:
    """Load the package-owned organization-verification scenario."""

    return _read_json(package_code, "verification.json", DemoVerificationSpec)
