"""Registry-backed orchestrator for reusable demo packages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.demo.ops.contracts import DemoAction, DemoExecutionContext, DemoPackage, DemoRunResult
from app.demo.ops.woheng import WOHENG_NAMESPACE, WohengShowcasePackage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DemoOpsError(ValueError):
    """Raised when a demo package operation is not valid."""


class DemoOpsOrchestrator:
    """Resolve and execute versioned demo packages."""

    def __init__(self, session: AsyncSession) -> None:
        self._packages: dict[str, DemoPackage] = {
            WohengShowcasePackage.key: WohengShowcasePackage(session),
        }

    def list_packages(self) -> list[DemoPackage]:
        """Return registered packages."""
        return list(self._packages.values())

    async def execute(
        self,
        *,
        package_key: str,
        namespace: str,
        profile: str,
        action: DemoAction,
        apply: bool,
    ) -> DemoRunResult:
        """Execute one package action."""
        package = self._packages.get(package_key)
        if package is None:
            msg = f"Unknown demo package: {package_key}"
            raise DemoOpsError(msg)
        if namespace != WOHENG_NAMESPACE:
            msg = "The Woheng showcase package requires namespace 'woheng'."
            raise DemoOpsError(msg)
        if profile not in package.supported_profiles:
            msg = f"Profile {profile!r} is not supported by {package_key!r}."
            raise DemoOpsError(msg)
        context = DemoExecutionContext(package_key=package_key, namespace=namespace, profile=profile, apply=apply)
        return await package.execute(context, action)
