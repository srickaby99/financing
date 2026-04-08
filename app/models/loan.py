import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class LoanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAID_OFF = "PAID_OFF"
    DEFAULTED = "DEFAULTED"
    CHARGED_OFF = "CHARGED_OFF"


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_applications.id"), nullable=False, unique=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    borrower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False
    )

    principal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # annual rate
    term_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    origination_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    origination_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LoanStatus.ACTIVE)

    outstanding_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    next_due_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    application: Mapped["LoanApplication"] = relationship(back_populates="loan")  # noqa: F821
    product: Mapped["Product"] = relationship()  # noqa: F821
    borrower: Mapped["Borrower"] = relationship()  # noqa: F821
    schedule: Mapped[list["RepaymentScheduleEntry"]] = relationship(
        back_populates="loan", order_by="RepaymentScheduleEntry.period"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="loan")  # noqa: F821
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="loan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Loan {self.id} [{self.status}]>"


class RepaymentScheduleEntry(Base):
    __tablename__ = "repayment_schedule_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False
    )
    period: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1-based month number
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    loan: Mapped["Loan"] = relationship(back_populates="schedule")
