import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaymentMethodType(StrEnum):
    ACH = "ACH"
    CARD = "CARD"


class PaymentMethodStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REMOVED = "REMOVED"


class Borrower(Base):
    __tablename__ = "borrowers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    date_of_birth: Mapped[object] = mapped_column(Date, nullable=False)
    ssn_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    ssn_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of full SSN

    # Contact / billing
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    address_line1: Mapped[str] = mapped_column(String(120), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # Relationships
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(back_populates="borrower")

    def __repr__(self) -> str:
        return f"<Borrower {self.first_name} {self.last_name}>"


class PaymentMethod(Base):
    """Tokenized payment method. Raw card/bank details never stored here."""

    __tablename__ = "payment_methods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    borrower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)

    # Opaque token from payment processor (e.g. Stripe, Braintree)
    processor_token: Mapped[str] = mapped_column(String(255), nullable=False)

    # Display metadata only — not usable for charging
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(40))  # card brand or bank name

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentMethodStatus.ACTIVE)

    # Relationships
    borrower: Mapped["Borrower"] = relationship(back_populates="payment_methods")
