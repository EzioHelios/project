"""Migrate legacy verification evidence and remove retired storage tables.

Revision ID: 8c9d0e1f2a3b
Revises: 7b8c9d0e1f2a
Create Date: 2026-08-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8c9d0e1f2a3b"
down_revision = "7b8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Move attachment metadata to canonical evidence tables, then retire legacy storage."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("select set_config('app.tenant_bypass', 'true', true)"))

    op.execute(
        sa.text(
            """
            with candidates as (
                select
                    attachment.*,
                    project.project_no,
                    row_number() over (order by attachment.id) as row_no
                from carbon_verification_attachment attachment
                left join carbon_verification_project project on project.id = attachment.project_id
                where not exists (
                    select 1
                    from ghg_evidence_file evidence
                    where evidence.team_id = attachment.team_id
                      and evidence.evidence_code = left('LEGACY-' || attachment.attachment_no, 96)
                )
            ), id_base as (
                select coalesce(max(id), 0) as max_id from ghg_evidence_file
            )
            insert into ghg_evidence_file (
                id,
                evidence_code,
                file_name,
                document_type,
                document_no,
                issuer,
                storage_key,
                sha256,
                confidentiality,
                verification_status,
                team_id,
                created_at,
                updated_at
            )
            select
                id_base.max_id + candidates.row_no,
                left('LEGACY-' || candidates.attachment_no, 96),
                coalesce(candidates.file_name, candidates.title, candidates.attachment_no),
                coalesce(candidates.attachment_type, 'supporting_document'),
                candidates.attachment_no,
                candidates.source_name,
                coalesce(candidates.file_path, 'legacy-metadata://' || candidates.attachment_no),
                coalesce(candidates.sha256, md5(candidates.attachment_no || candidates.id::text)),
                'internal',
                case
                    when candidates.status in ('approved', 'ready') then 'approved'
                    when candidates.status = 'rejected' then 'rejected'
                    else 'pending'
                end,
                candidates.team_id,
                candidates.created_at,
                candidates.updated_at
            from candidates
            cross join id_base
            """
        )
    )
    op.execute(
        sa.text(
            """
            with candidates as (
                select
                    attachment.*,
                    project.project_no,
                    evidence.id as evidence_id,
                    row_number() over (order by attachment.id) as row_no
                from carbon_verification_attachment attachment
                join ghg_evidence_file evidence
                  on evidence.team_id = attachment.team_id
                 and evidence.evidence_code = left('LEGACY-' || attachment.attachment_no, 96)
                left join carbon_verification_project project on project.id = attachment.project_id
                where not exists (
                    select 1
                    from ghg_evidence_link link
                    where link.team_id = attachment.team_id
                      and link.link_code = left('LEGACY-LINK-' || attachment.attachment_no, 96)
                )
            ), id_base as (
                select coalesce(max(id), 0) as max_id from ghg_evidence_link
            )
            insert into ghg_evidence_link (
                id,
                link_code,
                record_type,
                record_code,
                evidence_id,
                evidence_role,
                review_status,
                reviewer,
                reviewed_at,
                team_id,
                created_at,
                updated_at
            )
            select
                id_base.max_id + candidates.row_no,
                left('LEGACY-LINK-' || candidates.attachment_no, 96),
                case when candidates.project_no is not null then 'verification_project' else 'legacy_record' end,
                coalesce(candidates.project_no, candidates.attachment_no),
                candidates.evidence_id,
                case when candidates.project_no is not null then 'verification_scope' else 'activity_evidence' end,
                case
                    when candidates.status in ('approved', 'ready') then 'approved'
                    when candidates.status = 'rejected' then 'rejected'
                    else 'pending'
                end,
                coalesce(candidates.reviewed_by, candidates.uploaded_by),
                candidates.reviewed_at,
                candidates.team_id,
                candidates.created_at,
                candidates.updated_at
            from candidates
            cross join id_base
            """
        )
    )

    op.drop_table("carbon_verification_attachment")
    op.drop_table("dataapp_carbonauditlog")


def downgrade() -> None:
    """The retired verification storage contract is intentionally not restorable."""
    msg = "Legacy verification storage cannot be restored after canonical evidence migration."
    raise RuntimeError(msg)
