import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.borrower import BorrowerCreate, BorrowerRead, PaymentMethodCreate, PaymentMethodRead
from app.services import borrower_service

router = APIRouter(prefix="/borrowers", tags=["borrowers"])


@router.post("", response_model=BorrowerRead, status_code=201)
async def create_borrower(data: BorrowerCreate, db: AsyncSession = Depends(get_db)):
    return await borrower_service.create_borrower(data, db)


@router.get("/{borrower_id}", response_model=BorrowerRead)
async def get_borrower(borrower_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await borrower_service.get_borrower(borrower_id, db)


@router.post("/{borrower_id}/payment-methods", response_model=PaymentMethodRead, status_code=201)
async def add_payment_method(
    borrower_id: uuid.UUID,
    data: PaymentMethodCreate,
    db: AsyncSession = Depends(get_db),
):
    return await borrower_service.add_payment_method(borrower_id, data, db)
