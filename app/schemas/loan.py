import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.loan import LoanStatus


class RepaymentScheduleEntryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    loan_id: uuid.UUID
    period: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    balance_after: Decimal


class LoanRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID
    product_id: uuid.UUID
    borrower_id: uuid.UUID
    principal: Decimal
    interest_rate: Decimal
    term_months: int
    origination_fee: Decimal
    origination_date: date
    maturity_date: date
    status: LoanStatus
    outstanding_balance: Decimal
    next_due_date: date | None
    created_at: datetime
