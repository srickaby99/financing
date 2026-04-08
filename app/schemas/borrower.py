import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.models.borrower import PaymentMethodStatus, PaymentMethodType


class BorrowerCreate(BaseModel):
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    date_of_birth: date
    ssn: str = Field(min_length=9, max_length=9, pattern=r"^\d{9}$")  # full SSN — hashed before storage
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    address_line1: str = Field(max_length=120)
    address_line2: str | None = Field(None, max_length=120)
    city: str = Field(max_length=80)
    state: str = Field(min_length=2, max_length=2)
    zip_code: str = Field(max_length=10)


class BorrowerRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    ssn_last4: str
    email: str
    phone: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    zip_code: str


class PaymentMethodCreate(BaseModel):
    type: PaymentMethodType
    processor_token: str = Field(max_length=255)
    last4: str = Field(min_length=4, max_length=4)
    brand: str | None = Field(None, max_length=40)
    is_default: bool = False


class PaymentMethodRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    borrower_id: uuid.UUID
    type: PaymentMethodType
    last4: str
    brand: str | None
    is_default: bool
    status: PaymentMethodStatus
