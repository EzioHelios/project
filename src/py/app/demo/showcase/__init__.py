"""Deterministic, self-contained demonstration tenant."""

from app.demo.showcase.builder import (
    SHOWCASE_PACKAGE_CODE,
    SHOWCASE_TENANT_SLUG,
    ShowcaseCoverage,
    ShowcaseDemoBuilder,
    ShowcaseDemoResult,
    ensure_showcase_team,
)

__all__ = (
    "SHOWCASE_PACKAGE_CODE",
    "SHOWCASE_TENANT_SLUG",
    "ShowcaseCoverage",
    "ShowcaseDemoBuilder",
    "ShowcaseDemoResult",
    "ensure_showcase_team",
)
