import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.partner import ApiKeyResponse, PartnerCreate, PartnerProductAssign, PartnerProductRead, PartnerRead
from app.services import partner_service

router = APIRouter(prefix="/partners", tags=["partners"])


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_partner(data: PartnerCreate, db: AsyncSession = Depends(get_db)):
    partner, raw_key = await partner_service.create_partner(data, db)
    return ApiKeyResponse(partner=PartnerRead.model_validate(partner), api_key=raw_key)


@router.get("/{partner_id}", response_model=PartnerRead)
async def get_partner(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await partner_service.get_partner(partner_id, db)


@router.post("/{partner_id}/products", response_model=PartnerProductRead, status_code=201)
async def assign_product(
    partner_id: uuid.UUID,
    data: PartnerProductAssign,
    db: AsyncSession = Depends(get_db),
):
    return await partner_service.assign_product(partner_id, data, db)


@router.get("/{partner_id}/products", response_model=list[PartnerProductRead])
async def list_partner_products(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await partner_service.list_partner_products(partner_id, db)
