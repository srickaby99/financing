import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, verify_api_key
from app.models.partner import Partner, PartnerProduct, PartnerStatus
from app.schemas.partner import PartnerCreate, PartnerProductAssign


async def create_partner(data: PartnerCreate, db: AsyncSession) -> tuple[Partner, str]:
    """Create a partner and return (partner, raw_api_key).

    The raw key is returned once and never stored — only its hash is persisted.
    """
    # Check slug uniqueness
    existing = await db.execute(select(Partner).where(Partner.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Partner slug '{data.slug}' is already taken",
        )

    raw_key, key_hash = generate_api_key()
    partner = Partner(name=data.name, slug=data.slug, api_key_hash=key_hash)
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return partner, raw_key


async def get_partner(partner_id: uuid.UUID, db: AsyncSession) -> Partner:
    result = await db.execute(select(Partner).where(Partner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return partner


async def authenticate_partner(api_key: str, db: AsyncSession) -> Partner:
    """Resolve a Partner from a raw API key. Raises 401 if invalid or suspended."""
    from app.core.security import _hash_api_key
    key_hash = _hash_api_key(api_key)
    result = await db.execute(select(Partner).where(Partner.api_key_hash == key_hash))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if partner.status == PartnerStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Partner account suspended")
    return partner


async def assign_product(
    partner_id: uuid.UUID,
    data: PartnerProductAssign,
    db: AsyncSession,
) -> PartnerProduct:
    # Prevent duplicates
    result = await db.execute(
        select(PartnerProduct).where(
            PartnerProduct.partner_id == partner_id,
            PartnerProduct.product_id == data.product_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Re-activate and update overrides if already exists
        existing.is_active = True
        existing.rate_override = data.rate_override
        existing.origination_fee_override = data.origination_fee_override
        await db.commit()
        await db.refresh(existing)
        return existing

    pp = PartnerProduct(
        partner_id=partner_id,
        product_id=data.product_id,
        rate_override=data.rate_override,
        origination_fee_override=data.origination_fee_override,
    )
    db.add(pp)
    await db.commit()
    await db.refresh(pp)
    return pp


async def list_partner_products(partner_id: uuid.UUID, db: AsyncSession) -> list[PartnerProduct]:
    result = await db.execute(
        select(PartnerProduct).where(
            PartnerProduct.partner_id == partner_id,
            PartnerProduct.is_active.is_(True),
        )
    )
    return list(result.scalars().all())
