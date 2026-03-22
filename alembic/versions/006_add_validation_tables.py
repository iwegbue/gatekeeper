"""add validation tables (compiled_plans, validation_runs)

Revision ID: 006
Revises: 005
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compiled_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plan_snapshot", JSONB, nullable=False),
        sa.Column("compiled_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("interpretability_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("coherence_warnings", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "validation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("compiled_plan_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="INTERPRETABILITY"),
        sa.Column("settings", JSONB, nullable=True),
        sa.Column("summary_metrics", JSONB, nullable=True),
        sa.Column("feedback", JSONB, nullable=True),
        sa.Column("data_snapshot_id", UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("validation_runs")
    op.drop_table("compiled_plans")
