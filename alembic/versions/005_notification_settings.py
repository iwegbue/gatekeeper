"""add SMTP and Telegram notification settings

Revision ID: 005
Revises: 004
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Email / SMTP
    op.add_column("settings", sa.Column("email_notifications_enabled", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("settings", sa.Column("smtp_host", sa.String, nullable=False, server_default=""))
    op.add_column("settings", sa.Column("smtp_port", sa.Integer, nullable=False, server_default="587"))
    op.add_column("settings", sa.Column("smtp_username", sa.String, nullable=False, server_default=""))
    op.add_column("settings", sa.Column("smtp_password", sa.String, nullable=False, server_default=""))
    op.add_column("settings", sa.Column("smtp_from_email", sa.String, nullable=False, server_default=""))
    op.add_column("settings", sa.Column("smtp_tls", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("settings", sa.Column("notify_email_to", sa.String, nullable=False, server_default=""))
    # Telegram
    op.add_column("settings", sa.Column("telegram_notifications_enabled", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("settings", sa.Column("telegram_bot_token", sa.String, nullable=False, server_default=""))
    op.add_column("settings", sa.Column("telegram_chat_id", sa.String, nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("settings", "telegram_chat_id")
    op.drop_column("settings", "telegram_bot_token")
    op.drop_column("settings", "telegram_notifications_enabled")
    op.drop_column("settings", "notify_email_to")
    op.drop_column("settings", "smtp_tls")
    op.drop_column("settings", "smtp_from_email")
    op.drop_column("settings", "smtp_password")
    op.drop_column("settings", "smtp_username")
    op.drop_column("settings", "smtp_port")
    op.drop_column("settings", "smtp_host")
    op.drop_column("settings", "email_notifications_enabled")
