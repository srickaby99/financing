import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PartnerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PartnerStatus.ACTIVE)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Relationships
    partner_products: Mapped[list["PartnerProduct"]] = relationship(back_populates="partner")

    def __repr__(self) -> str:
        return f"<Partner {self.slug}>"


class PartnerProduct(Base):
    """Controls which products a partner may offer.

    The nullable override columns are the extensibility seam for future
    per-partner pricing: if set they supersede the Product defaults.
    The service layer always resolves effective terms through this table.
    """

    __tablename__ = "partner_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Per-partner overrides — nullable means "use product default"
    rate_override: Mapped[float | None] = mapped_column(Numeric(6, 4))
    origination_fee_override: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Relationships
    partner: Mapped["Partner"] = relationship(back_populates="partner_products")
    product: Mapped["Product"] = relationship(back_populates="partner_products")  # noqa: F821
