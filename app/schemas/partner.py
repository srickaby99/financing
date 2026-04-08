import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.partner import PartnerStatus


class PartnerCreate(BaseModel):
    name: str = Field(max_length=120)
    slug: str = Field(max_length=60, pattern=r"^[a-z0-9-]+$")


class PartnerRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    slug: str
    status: PartnerStatus


class ApiKeyResponse(BaseModel):
    """Returned once at partner creation. The raw key is never stored."""
    partner: PartnerRead
    api_key: str


class PartnerProductAssign(BaseModel):
    product_id: uuid.UUID
    rate_override: Decimal | None = Field(None, ge=0, le=1, decimal_places=4)
    origination_fee_override: Decimal | None = Field(None, ge=0, decimal_places=2)


class PartnerProductRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    partner_id: uuid.UUID
    product_id: uuid.UUID
    is_active: bool
    rate_override: Decimal | None
    origination_fee_override: Decimal | None
