"""Add rules_modified_at to trading_plans.

NULL means the plan's rules have never been manually edited since creation
(either freshly loaded from a template or never had any rules added).
Set to the current timestamp whenever a rule is created, updated, or deleted.
Cleared back to NULL when the plan is reset (all rules wiped).

Used by Pro to decide whether to serve a pre-built seed backtest EA (NULL)
or generate a custom one via AI (non-NULL).

Revision ID: 012
Revises: 011
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trading_plans",
        sa.Column("rules_modified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trading_plans", "rules_modified_at")
