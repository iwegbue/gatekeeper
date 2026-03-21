import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instrument: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # Direction enum
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(15, 5), nullable=False)
    sl_price: Mapped[float] = mapped_column(Numeric(15, 5), nullable=False)
    initial_sl_price: Mapped[float | None] = mapped_column(Numeric(15, 5), nullable=True)
    tp_price: Mapped[float | None] = mapped_column(Numeric(15, 5), nullable=True)
    risk_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    lot_size: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    grade: Mapped[str] = mapped_column(String, nullable=False)  # SetupGrade enum
    state: Mapped[str] = mapped_column(String, default="OPEN")  # TradeState enum
    be_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    partials_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(15, 5), nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc)
    )
