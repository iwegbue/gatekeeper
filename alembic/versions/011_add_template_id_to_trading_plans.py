"""Add template_id to trading_plans.

Records which starter template (if any) was used to create this plan.
NULL means the plan was created from scratch or via the Plan Builder.

Revision ID: 011
Revises: 010
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trading_plans",
        sa.Column("template_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trading_plans", "template_id")
