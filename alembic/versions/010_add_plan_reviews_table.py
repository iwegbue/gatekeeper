"""Add plan_reviews table.

Revision ID: 010
Revises: 009
Create Date: 2026-03-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plan_reviews_plan_id", "plan_reviews", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_reviews_plan_id", table_name="plan_reviews")
    op.drop_table("plan_reviews")
