import hashlib
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.borrower import Borrower, PaymentMethod
from app.schemas.borrower import BorrowerCreate, PaymentMethodCreate


def _hash_ssn(ssn: str) -> str:
    return hashlib.sha256(ssn.encode()).hexdigest()


async def create_borrower(data: BorrowerCreate, db: AsyncSession) -> Borrower:
    ssn_hash = _hash_ssn(data.ssn)

    # Deduplicate by SSN hash
    result = await db.execute(select(Borrower).where(Borrower.ssn_hash == ssn_hash))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A borrower with this SSN already exists",
        )

    borrower = Borrower(
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        ssn_last4=data.ssn[-4:],
        ssn_hash=ssn_hash,
        email=data.email,
        phone=data.phone,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
    )
    db.add(borrower)
    await db.commit()
    await db.refresh(borrower)
    return borrower


async def get_borrower(borrower_id: uuid.UUID, db: AsyncSession) -> Borrower:
    result = await db.execute(select(Borrower).where(Borrower.id == borrower_id))
    borrower = result.scalar_one_or_none()
    if not borrower:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower not found")
    return borrower


async def add_payment_method(
    borrower_id: uuid.UUID,
    data: PaymentMethodCreate,
    db: AsyncSession,
) -> PaymentMethod:
    # If new method is default, clear existing defaults
    if data.is_default:
        result = await db.execute(
            select(PaymentMethod).where(
                PaymentMethod.borrower_id == borrower_id,
                PaymentMethod.is_default.is_(True),
            )
        )
        for pm in result.scalars().all():
            pm.is_default = False

    pm = PaymentMethod(
        borrower_id=borrower_id,
        type=data.type,
        processor_token=data.processor_token,
        last4=data.last4,
        brand=data.brand,
        is_default=data.is_default,
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    return pm
