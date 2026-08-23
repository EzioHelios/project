"""Versioned, reusable demo packages for the energy-carbon platform."""

from app.demo.catalog import (
    DemoPackageManifest,
    DemoProfile,
    DemoVerificationSpec,
    load_demo_manifest,
    load_demo_profile,
    load_demo_verification,
)
from app.demo.orchestrator import ApplyDemoPackage, DemoApplyResult, DemoPackageError

__all__ = (
    "ApplyDemoPackage",
    "DemoApplyResult",
    "DemoPackageError",
    "DemoPackageManifest",
    "DemoProfile",
    "DemoVerificationSpec",
    "load_demo_manifest",
    "load_demo_profile",
    "load_demo_verification",
)
