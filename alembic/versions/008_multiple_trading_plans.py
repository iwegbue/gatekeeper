"""Add support for multiple trading plans.

Adds is_active flag to trading_plans and plan_id FK to ideas.
Backfills existing data: marks the first plan as active, sets all
existing ideas' plan_id to that plan.

Revision ID: 008
Revises: 007
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_active column to trading_plans (default False so new plans start inactive)
    op.add_column(
        "trading_plans",
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
    )

    # 2. Mark the first existing plan as active (if any exist)
    op.execute(
        """
        UPDATE trading_plans SET is_active = true
        WHERE id = (SELECT id FROM trading_plans ORDER BY created_at ASC LIMIT 1)
        """
    )

    # 3. Add plan_id column to ideas (nullable initially for backfill)
    op.add_column(
        "ideas",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 4. Backfill: set all existing ideas' plan_id to the active plan
    op.execute(
        """
        UPDATE ideas SET plan_id = (
            SELECT id FROM trading_plans WHERE is_active = true LIMIT 1
        )
        WHERE plan_id IS NULL
        """
    )

    # 5. Add FK constraint and index
    op.create_foreign_key(
        "fk_ideas_plan_id",
        "ideas",
        "trading_plans",
        ["plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ideas_plan_id", "ideas", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_ideas_plan_id", "ideas")
    op.drop_constraint("fk_ideas_plan_id", "ideas", type_="foreignkey")
    op.drop_column("ideas", "plan_id")
    op.drop_column("trading_plans", "is_active")
