import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import PartnerProduct
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


async def create_product(data: ProductCreate, db: AsyncSession) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_product(product_id: uuid.UUID, db: AsyncSession) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def list_products(db: AsyncSession, active_only: bool = True) -> list[Product]:
    query = select(Product)
    if active_only:
        query = query.where(Product.is_active.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_product(product_id: uuid.UUID, data: ProductUpdate, db: AsyncSession) -> Product:
    product = await get_product(product_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


async def resolve_effective_terms(
    partner_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Decimal, Decimal]:
    """Return (effective_rate, effective_origination_fee) for a partner+product pair.

    Checks PartnerProduct for overrides; falls back to Product defaults.
    The service layer always routes through here so per-partner pricing
    is applied consistently without changes to calling code.
    """
    result = await db.execute(
        select(PartnerProduct).where(
            PartnerProduct.partner_id == partner_id,
            PartnerProduct.product_id == product_id,
            PartnerProduct.is_active.is_(True),
        )
    )
    pp = result.scalar_one_or_none()
    if not pp:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This partner is not authorized to offer this product",
        )

    product = await get_product(product_id, db)
    effective_rate = Decimal(str(pp.rate_override)) if pp.rate_override is not None else Decimal(str(product.default_interest_rate))
    effective_fee = Decimal(str(pp.origination_fee_override)) if pp.origination_fee_override is not None else Decimal(str(product.origination_fee))
    return effective_rate, effective_fee
