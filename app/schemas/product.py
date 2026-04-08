import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.product import InterestRateModel, ProductType


class ProductCreate(BaseModel):
    name: str = Field(max_length=120)
    description: str | None = None
    product_type: ProductType
    interest_rate_model: InterestRateModel = InterestRateModel.FIXED
    min_term_months: int = Field(ge=1)
    max_term_months: int = Field(ge=1)
    min_amount: Decimal = Field(ge=0, decimal_places=2)
    max_amount: Decimal = Field(ge=0, decimal_places=2)
    default_interest_rate: Decimal = Field(ge=0, le=1, decimal_places=4)
    origination_fee: Decimal = Field(ge=0, decimal_places=2, default=Decimal("0"))
    late_fee_rules: dict = Field(default_factory=dict)
    collateral_required: bool = False
    eligibility_rules: dict = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    description: str | None = None
    is_active: bool | None = None
    default_interest_rate: Decimal | None = Field(None, ge=0, le=1)
    origination_fee: Decimal | None = Field(None, ge=0)
    late_fee_rules: dict | None = None
    eligibility_rules: dict | None = None
    min_term_months: int | None = Field(None, ge=1)
    max_term_months: int | None = Field(None, ge=1)
    min_amount: Decimal | None = Field(None, ge=0)
    max_amount: Decimal | None = Field(None, ge=0)


class ProductRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    product_type: ProductType
    interest_rate_model: InterestRateModel
    min_term_months: int
    max_term_months: int
    min_amount: Decimal
    max_amount: Decimal
    default_interest_rate: Decimal
    origination_fee: Decimal
    late_fee_rules: dict
    collateral_required: bool
    eligibility_rules: dict
    is_active: bool
