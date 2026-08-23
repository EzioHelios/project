"""Internal organization-inventory report lifecycle."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.domain.ghg_inventory.models import (
    GhgActivityRecord,
    GhgCalculationRun,
    GhgEvidenceLink,
    GhgInventoryReport,
    GhgInventoryReportReview,
)
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def build_inventory_evidence_snapshot(session: AsyncSession, inventory_code: str) -> dict[str, int | str]:
    """Build the report evidence snapshot from the current inventory evidence links."""
    activity_codes = set(
        (
            await session.scalars(
                select(GhgActivityRecord.record_code).where(GhgActivityRecord.inventory_code == inventory_code)
            )
        ).all()
    )
    evidence_count = int(
        await session.scalar(
            select(func.count())
            .select_from(GhgEvidenceLink)
            .where(
                GhgEvidenceLink.record_type == "activity",
                GhgEvidenceLink.record_code.in_(activity_codes),
            )
        )
        or 0
    )
    linked_record_count = int(
        await session.scalar(
            select(func.count(func.distinct(GhgEvidenceLink.record_code))).where(
                GhgEvidenceLink.record_type == "activity",
                GhgEvidenceLink.record_code.in_(activity_codes),
            )
        )
        or 0
    )
    coverage_pct = (
        (Decimal(linked_record_count) * Decimal(100) / Decimal(len(activity_codes))).quantize(Decimal("0.01"))
        if activity_codes
        else Decimal(0)
    )
    return {
        "activityCount": len(activity_codes),
        "linkedActivityCount": linked_record_count,
        "evidenceLinkCount": evidence_count,
        "coveragePct": str(coverage_pct),
    }


class CreateInventoryReport:
    """Freeze a completed calculation run into a new internal report version."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, run_code: str, title: str, change_summary: str | None) -> GhgInventoryReport:
        require_session_tenant_id(self.session)
        run = await self.session.scalar(select(GhgCalculationRun).where(GhgCalculationRun.run_code == run_code))
        if run is None:
            msg = "核算运行不存在"
            raise ValueError(msg)
        if run.status != "completed":
            msg = "只有已完成的核算运行才能生成盘查报告"
            raise ValueError(msg)
        if not all((run.reporting_org_id, run.reporting_period_id, run.organization_boundary_id)):
            msg = "核算运行缺少报告组织、报告期间或组织边界"
            raise ValueError(msg)
        report_code = f"RPT-{run.reporting_org_id}-{run.reporting_period_id}"
        latest_version = int(
            await self.session.scalar(
                select(func.max(GhgInventoryReport.version)).where(GhgInventoryReport.report_code == report_code)
            )
            or 0
        )
        evidence_snapshot = await build_inventory_evidence_snapshot(self.session, run.inventory_code)
        report = GhgInventoryReport(
            report_code=report_code,
            version=latest_version + 1,
            title=title,
            inventory_code=run.inventory_code,
            run_id=run.id,
            reporting_org_id=run.reporting_org_id,
            reporting_period_id=run.reporting_period_id,
            organization_boundary_id=run.organization_boundary_id,
            reporting_profile_id=run.reporting_profile_id,
            status="draft",
            content_snapshot={
                "runCode": run.run_code,
                "inputSnapshot": run.input_snapshot,
                "qualitySnapshot": run.quality_snapshot,
            },
            metrics_snapshot=run.summary_snapshot,
            evidence_snapshot=evidence_snapshot,
            change_summary=change_summary,
        )
        self.session.add(report)
        await self.session.commit()
        return report


class TransitionInventoryReport:
    """Apply one auditable internal report status transition."""

    TRANSITIONS = {
        "submit": ("draft", "submitted"),
        "resubmit": ("rejected", "submitted"),
        "approve": ("submitted", "approved"),
        "reject": ("submitted", "rejected"),
        "publish": ("approved", "published"),
        "archive": ("published", "archived"),
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        report_code: str,
        version: int,
        action: str,
        actor: str,
        comment: str | None,
    ) -> GhgInventoryReport:
        require_session_tenant_id(self.session)
        transition = self.TRANSITIONS.get(action)
        if transition is None:
            msg = "不支持的报告操作"
            raise ValueError(msg)
        report = await self.session.scalar(
            select(GhgInventoryReport).where(
                GhgInventoryReport.report_code == report_code,
                GhgInventoryReport.version == version,
            )
        )
        if report is None:
            msg = "盘查报告不存在"
            raise ValueError(msg)
        expected_status, target_status = transition
        if report.status != expected_status:
            msg = f"报告当前状态为{report.status}; 不能执行{action}"
            raise ValueError(msg)
        if action == "reject" and not (comment or "").strip():
            msg = "退回报告时必须填写审核意见"
            raise ValueError(msg)
        now = datetime.now().astimezone()
        original_status = report.status
        report.status = target_status
        if action in {"submit", "resubmit"}:
            report.submitted_by = actor
            report.submitted_at = now
        elif action == "approve":
            report.approved_by = actor
            report.approved_at = now
        elif action == "publish":
            report.published_at = now
        self.session.add(
            GhgInventoryReportReview(
                report_id=report.id,
                action=action,
                from_status=original_status,
                to_status=target_status,
                actor=actor,
                comment=comment,
                acted_at=now,
            )
        )
        await self.session.commit()
        return report
