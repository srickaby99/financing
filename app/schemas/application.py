import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    borrower_id: uuid.UUID
    product_id: uuid.UUID
    requested_amount: Decimal = Field(gt=0, decimal_places=2)
    requested_term_months: int = Field(ge=1)


class UnderwritingResult(BaseModel):
    """Embedded in ApplicationRead when a decision has been made."""
    approved: bool
    credit_score: int | None = None
    dti: Decimal | None = None
    approved_amount: Decimal | None = None
    approved_rate: Decimal | None = None
    approved_term_months: int | None = None
    monthly_payment: Decimal | None = None
    decline_reasons: list[str] = Field(default_factory=list)


class ApplicationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    borrower_id: uuid.UUID
    product_id: uuid.UUID
    partner_id: uuid.UUID
    requested_amount: Decimal
    requested_term_months: int
    status: ApplicationStatus
    underwriting_result: UnderwritingResult | None = None
    created_at: datetime
    decided_at: datetime | None = None

    # Populated on APPROVED — shortcut so callers don't need a second request
    loan_id: uuid.UUID | None = None
