"""add_plan_builder_session

Revision ID: 007
Revises: 006
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_builder_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_key", sa.Text(), nullable=False, unique=True),
        sa.Column("conversation", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_plan_builder_sessions_session_key",
        "plan_builder_sessions",
        ["session_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_plan_builder_sessions_session_key", table_name="plan_builder_sessions")
    op.drop_table("plan_builder_sessions")
