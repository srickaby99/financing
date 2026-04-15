import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import DialectJSON


class ProductType(StrEnum):
    DEVICE = "DEVICE"
    PERSONAL = "PERSONAL"
    PURCHASE = "PURCHASE"
    AUTO = "AUTO"


class InterestRateModel(StrEnum):
    FIXED = "FIXED"
    VARIABLE = "VARIABLE"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    product_type: Mapped[str] = mapped_column(String(40), nullable=False)
    interest_rate_model: Mapped[str] = mapped_column(String(20), nullable=False, default=InterestRateModel.FIXED)

    # Term limits (months)
    min_term_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_term_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Amount limits
    min_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Default rate (annual, e.g. 0.0799 = 7.99%). Can be overridden per PartnerProduct.
    default_interest_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)

    # Fees
    origination_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    late_fee_rules: Mapped[dict] = mapped_column(DialectJSON, nullable=False, default=dict)

    collateral_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Flexible per-product underwriting rules evaluated by the rules engine
    # e.g. {"min_credit_score": 600, "max_dti": 0.45, "allowed_states": ["CA", "TX"]}
    eligibility_rules: Mapped[dict] = mapped_column(DialectJSON, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    partner_products: Mapped[list["PartnerProduct"]] = relationship(back_populates="product")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Product {self.name} ({self.product_type})>"
