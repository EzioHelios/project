"""normalize organization boundary selections and demo carbon budget units

Revision ID: 0a1b2c3d4e5f
Revises: f5a6b7c8d9e
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op

revision = "0a1b2c3d4e5f"
down_revision = "f5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE carbon_organization_boundary
        SET operational_boundary = (COALESCE(operational_boundary, '{}'::json)::jsonb || jsonb_build_object(
            'schemaVersion', 'organization-boundary-v1',
            'scopes', to_jsonb(array_remove(ARRAY[
                CASE WHEN COALESCE((operational_boundary ->> 'scope1')::boolean, false)
                          OR COALESCE(operational_boundary -> 'isoCategories', '[]'::json)::jsonb ? '1'
                     THEN 'scope1' END,
                CASE WHEN COALESCE((operational_boundary ->> 'scope2')::boolean, false)
                          OR COALESCE(operational_boundary -> 'isoCategories', '[]'::json)::jsonb ? '2'
                     THEN 'scope2' END,
                CASE WHEN COALESCE(json_array_length(COALESCE(operational_boundary -> 'scope3_categories', '[]'::json)), 0) > 0
                          OR COALESCE(operational_boundary -> 'isoCategories', '[]'::json)::jsonb ?| ARRAY['3', '4', '5', '6']
                     THEN 'scope3' END
            ]::text[], NULL)),
            'scope2Methods', CASE
                WHEN COALESCE((operational_boundary ->> 'scope2')::boolean, false)
                     OR COALESCE(operational_boundary -> 'isoCategories', '[]'::json)::jsonb ? '2'
                THEN '["location", "market"]'::jsonb
                ELSE '[]'::jsonb
            END,
            'isoCategories', COALESCE(operational_boundary -> 'isoCategories', '["1", "2", "3", "4", "5", "6"]'::json),
            'scope3Categories', '[]'::jsonb
        ))::json
        WHERE NOT COALESCE(operational_boundary, '{}'::json)::jsonb ? 'scopes'
        """
    )
    op.execute(
        """
        UPDATE dataapp_energycarbonbudgetplan
        SET carbon_budget_co2e = carbon_budget_co2e / 1000,
            carbon_intensity_budget = carbon_intensity_budget / 1000
        WHERE code = 'MVP-ECB-2026' AND carbon_budget_co2e >= 10000
        """
    )
    op.execute(
        """
        UPDATE dataapp_energycarbonbudgetallocation AS allocation
        SET carbon_budget_co2e = allocation.carbon_budget_co2e / 1000,
            carbon_intensity_budget = allocation.carbon_intensity_budget / 1000
        FROM dataapp_energycarbonbudgetplan AS plan
        WHERE allocation.plan_id = plan.id
          AND plan.code = 'MVP-ECB-2026'
          AND allocation.carbon_budget_co2e >= 1000
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE dataapp_energycarbonbudgetplan
        SET carbon_budget_co2e = carbon_budget_co2e * 1000,
            carbon_intensity_budget = carbon_intensity_budget * 1000
        WHERE code = 'MVP-ECB-2026' AND carbon_budget_co2e < 10000
        """
    )
    op.execute(
        """
        UPDATE dataapp_energycarbonbudgetallocation AS allocation
        SET carbon_budget_co2e = allocation.carbon_budget_co2e * 1000,
            carbon_intensity_budget = allocation.carbon_intensity_budget * 1000
        FROM dataapp_energycarbonbudgetplan AS plan
        WHERE allocation.plan_id = plan.id
          AND plan.code = 'MVP-ECB-2026'
          AND allocation.carbon_budget_co2e < 1000
        """
    )
