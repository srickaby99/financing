import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.types import DialectJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class WebhookStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    principal_applied: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    interest_applied: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    fees_applied: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Reference ID from the external payment processor notification
    external_reference_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentStatus.PENDING)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    loan: Mapped["Loan"] = relationship(back_populates="payments")  # noqa: F821


class InboundWebhookEvent(Base):
    """Append-only log of all inbound payment notifications.

    The external_event_id uniqueness constraint enforces idempotency —
    duplicate deliveries from the processor are rejected before processing.
    """

    __tablename__ = "inbound_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source: Mapped[str] = mapped_column(String(60), nullable=False)  # processor slug
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    payload: Mapped[dict] = mapped_column(DialectJSON, nullable=False)
    raw_headers: Mapped[str | None] = mapped_column(Text)  # for signature verification later

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WebhookStatus.RECEIVED)

    # Set after successful processing
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id")
    )

    # Relationships
    payment: Mapped["Payment | None"] = relationship()
