import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_partner
from app.db.session import get_db
from app.models.partner import Partner
from app.schemas.loan import LoanRead, RepaymentScheduleEntryRead
from app.schemas.payment import PaymentRead
from app.services import loan_service

router = APIRouter(prefix="/loans", tags=["loans"])


@router.get("/{loan_id}", response_model=LoanRead)
async def get_loan(
    loan_id: uuid.UUID,
    partner: Annotated[Partner, Depends(get_current_partner)],
    db: AsyncSession = Depends(get_db),
):
    return await loan_service.get_loan(loan_id, db)


@router.get("/{loan_id}/schedule", response_model=list[RepaymentScheduleEntryRead])
async def get_loan_schedule(
    loan_id: uuid.UUID,
    partner: Annotated[Partner, Depends(get_current_partner)],
    db: AsyncSession = Depends(get_db),
):
    return await loan_service.get_loan_schedule(loan_id, db)


@router.get("/{loan_id}/payments", response_model=list[PaymentRead])
async def get_loan_payments(
    loan_id: uuid.UUID,
    partner: Annotated[Partner, Depends(get_current_partner)],
    db: AsyncSession = Depends(get_db),
):
    return await loan_service.get_loan_payments(loan_id, db)
