"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # trading_plans
    op.create_table(
        "trading_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # plan_rules
    op.create_table(
        "plan_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trading_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("rule_type", sa.String(20), nullable=False, server_default="REQUIRED"),
        sa.Column("weight", sa.Integer, nullable=False, server_default="1"),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("parameters", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_plan_rules_plan_id", "plan_rules", ["plan_id"])
    op.create_index("ix_plan_rules_layer", "plan_rules", ["layer"])

    # instruments
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(30), nullable=False, unique=True),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False, server_default="FX"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # settings
    op.create_table(
        "settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ai_provider", sa.String(20), nullable=False, server_default="anthropic"),
        sa.Column("anthropic_api_key", sa.String, nullable=False, server_default=""),
        sa.Column("openai_api_key", sa.String, nullable=False, server_default=""),
        sa.Column("ollama_base_url", sa.String, nullable=False, server_default=""),
        sa.Column("ai_model", sa.String(100), nullable=False, server_default=""),
        sa.Column("notifications_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("entry_window_hours", sa.Integer, nullable=False, server_default="4"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ideas
    op.create_table(
        "ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument", sa.String, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False, server_default="WATCHING"),
        sa.Column("checklist_score", sa.Integer, nullable=True),
        sa.Column("grade", sa.String, nullable=True),
        sa.Column("risk_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("entry_window_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # idea_rule_checks
    op.create_table(
        "idea_rule_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_idea_rule_checks_idea_id", "idea_rule_checks", ["idea_id"])
    op.create_index("ix_idea_rule_checks_rule_id", "idea_rule_checks", ["rule_id"])

    # state_transitions
    op.create_table(
        "state_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String, nullable=False),
        sa.Column("to_state", sa.String, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_state_transitions_idea_id", "state_transitions", ["idea_id"])

    # trades
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument", sa.String, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(15, 5), nullable=False),
        sa.Column("sl_price", sa.Numeric(15, 5), nullable=False),
        sa.Column("initial_sl_price", sa.Numeric(15, 5), nullable=True),
        sa.Column("tp_price", sa.Numeric(15, 5), nullable=True),
        sa.Column("risk_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("lot_size", sa.Numeric(10, 2), nullable=True),
        sa.Column("grade", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False, server_default="OPEN"),
        sa.Column("be_locked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("partials_taken", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(15, 5), nullable=True),
        sa.Column("r_multiple", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # journal_tags
    op.create_table(
        "journal_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # journal_entries
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trade_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="DRAFT"),
        sa.Column("trade_summary", postgresql.JSONB, nullable=True),
        sa.Column("plan_adherence_pct", sa.Integer, nullable=True),
        sa.Column("rule_violations", postgresql.JSONB, nullable=True),
        sa.Column("what_went_well", sa.Text, nullable=True),
        sa.Column("what_went_wrong", sa.Text, nullable=True),
        sa.Column("lessons_learned", sa.Text, nullable=True),
        sa.Column("emotions", sa.Text, nullable=True),
        sa.Column("would_take_again", sa.Boolean, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # journal_entry_tags (association)
    op.create_table(
        "journal_entry_tags",
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_tags.id", ondelete="CASCADE"), primary_key=True),
    )

    # ai_analyses
    op.create_table(
        "ai_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("instrument", sa.String, nullable=True),
        sa.Column("trigger", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="PENDING"),
        sa.Column("raw_response", postgresql.JSONB, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_analyses")
    op.drop_table("journal_entry_tags")
    op.drop_table("journal_entries")
    op.drop_table("journal_tags")
    op.drop_table("trades")
    op.drop_index("ix_state_transitions_idea_id", "state_transitions")
    op.drop_table("state_transitions")
    op.drop_index("ix_idea_rule_checks_rule_id", "idea_rule_checks")
    op.drop_index("ix_idea_rule_checks_idea_id", "idea_rule_checks")
    op.drop_table("idea_rule_checks")
    op.drop_table("ideas")
    op.drop_table("settings")
    op.drop_table("instruments")
    op.drop_index("ix_plan_rules_layer", "plan_rules")
    op.drop_index("ix_plan_rules_plan_id", "plan_rules")
    op.drop_table("plan_rules")
    op.drop_table("trading_plans")
