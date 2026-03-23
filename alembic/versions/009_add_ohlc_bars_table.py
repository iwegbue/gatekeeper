"""Add ohlc_bars table for replay engine market data snapshots.

Revision ID: 009
Revises: 008
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ohlc_bars",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 4), nullable=True),
        sa.Column("data_snapshot_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "symbol",
            "timeframe",
            "ts",
            "data_snapshot_id",
            name="uq_ohlc_bars_symbol_timeframe_ts_snapshot",
        ),
    )
    op.create_index("ix_ohlc_bars_data_snapshot_id", "ohlc_bars", ["data_snapshot_id"])
    op.create_index("ix_ohlc_bars_symbol_timeframe", "ohlc_bars", ["symbol", "timeframe"])


def downgrade() -> None:
    op.drop_index("ix_ohlc_bars_symbol_timeframe", table_name="ohlc_bars")
    op.drop_index("ix_ohlc_bars_data_snapshot_id", table_name="ohlc_bars")
    op.drop_table("ohlc_bars")
