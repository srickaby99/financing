import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from app.db.types import DialectJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    borrower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False
    )

    requested_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    requested_term_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ApplicationStatus.DRAFT)

    # Stores the full underwriting decision: approved_amount, approved_rate,
    # approved_term, decline_reasons, credit_score, dti, etc.
    underwriting_result: Mapped[dict | None] = mapped_column(DialectJSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    borrower: Mapped["Borrower"] = relationship()  # noqa: F821
    product: Mapped["Product"] = relationship()  # noqa: F821
    partner: Mapped["Partner"] = relationship()  # noqa: F821
    loan: Mapped["Loan | None"] = relationship(back_populates="application")  # noqa: F821

    def __repr__(self) -> str:
        return f"<LoanApplication {self.id} [{self.status}]>"
