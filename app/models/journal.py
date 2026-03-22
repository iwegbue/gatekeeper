import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

journal_entry_tags = Table(
    "journal_entry_tags",
    Base.metadata,
    Column(
        "journal_entry_id", UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("journal_tags.id", ondelete="CASCADE"), primary_key=True),
)


class JournalTag(Base):
    __tablename__ = "journal_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    entries: Mapped[list["JournalEntry"]] = relationship(
        secondary=journal_entry_tags,
        back_populates="tags",
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    idea_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, default="DRAFT")  # JournalStatus enum

    # Auto-populated trade audit
    trade_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Plan adherence (computed from idea_rule_checks)
    plan_adherence_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_violations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Structured review
    what_went_well: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_went_wrong: Mapped[str | None] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotions: Mapped[str | None] = mapped_column(Text, nullable=True)
    would_take_again: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tags: Mapped[list[JournalTag]] = relationship(
        secondary=journal_entry_tags,
        back_populates="entries",
        lazy="selectin",
    )
