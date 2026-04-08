import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class EntryType(StrEnum):
    DISBURSEMENT = "DISBURSEMENT"
    PAYMENT = "PAYMENT"
    FEE = "FEE"
    ADJUSTMENT = "ADJUSTMENT"
    WRITEOFF = "WRITEOFF"


class LedgerEntry(Base):
    """Double-entry ledger. Append-only — never update or delete rows.
    Corrections are made by posting a reversal entry.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id")
    )

    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    debit_account: Mapped[str] = mapped_column(String(60), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(60), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # No updated_at — this table is append-only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    loan: Mapped["Loan"] = relationship(back_populates="ledger_entries")  # noqa: F821
    payment: Mapped["Payment | None"] = relationship()
