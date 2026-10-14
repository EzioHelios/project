from __future__ import annotations

import pytest

from app.demo.ops import DemoAction, DemoOpsError, DemoOpsOrchestrator, DemoStepStatus


@pytest.mark.anyio
async def test_woheng_package_install_plan_is_non_mutating() -> None:
    orchestrator = DemoOpsOrchestrator(session=object())  # type: ignore[arg-type]

    result = await orchestrator.execute(
        package_key="woheng-showcase",
        namespace="woheng",
        profile="full",
        action=DemoAction.INSTALL,
        apply=False,
    )

    assert result.status == DemoStepStatus.PLANNED
    assert result.applied is False
    assert [step.module_key for step in result.steps] == ["energy-types", "tenant", "dataset", "mqtt"]


def test_woheng_package_is_registered() -> None:
    orchestrator = DemoOpsOrchestrator(session=object())  # type: ignore[arg-type]

    packages = {package.key: package for package in orchestrator.list_packages()}

    assert packages["woheng-showcase"].supported_profiles == ("full",)


@pytest.mark.anyio
async def test_unknown_woheng_profile_is_rejected() -> None:
    orchestrator = DemoOpsOrchestrator(session=object())  # type: ignore[arg-type]

    with pytest.raises(DemoOpsError):
        await orchestrator.execute(
            package_key="woheng-showcase",
            namespace="woheng",
            profile="legacy-customer",
            action=DemoAction.INSTALL,
            apply=False,
        )


@pytest.mark.anyio
async def test_customer_namespace_is_rejected_before_package_execution() -> None:
    orchestrator = DemoOpsOrchestrator(session=object())  # type: ignore[arg-type]
    with pytest.raises(DemoOpsError, match="namespace"):
        await orchestrator.execute(
            package_key="woheng-showcase",
            namespace="xiangtai",
            profile="full",
            action=DemoAction.INSTALL,
            apply=True,
        )
