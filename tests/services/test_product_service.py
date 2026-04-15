"""Tests for product_service — CRUD and effective terms resolution."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.partner import PartnerProduct
from app.schemas.product import ProductCreate, ProductUpdate
from app.services import product_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_payload(**overrides) -> ProductCreate:
    defaults = dict(
        name="Personal Loan",
        product_type="PERSONAL",
        interest_rate_model="FIXED",
        min_term_months=6,
        max_term_months=36,
        min_amount=Decimal("200.00"),
        max_amount=Decimal("5000.00"),
        default_interest_rate=Decimal("0.1199"),
        origination_fee=Decimal("0.00"),
        eligibility_rules={},
    )
    defaults.update(overrides)
    return ProductCreate(**defaults)


# ---------------------------------------------------------------------------
# create_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_product_returns_product(db):
    """(+) Created product is persisted and returned with an ID."""
    product = await product_service.create_product(_create_payload(), db)
    assert product.id is not None
    assert product.name == "Personal Loan"
    assert product.is_active is True


@pytest.mark.asyncio
async def test_create_product_stores_eligibility_rules(db):
    """(+) JSONB eligibility_rules are stored correctly."""
    rules = {"min_credit_score": 620, "max_dti": 0.40}
    product = await product_service.create_product(_create_payload(eligibility_rules=rules), db)
    assert product.eligibility_rules["min_credit_score"] == 620


@pytest.mark.asyncio
async def test_create_product_defaults_active(db):
    """(+) New products are active by default."""
    product = await product_service.create_product(_create_payload(), db)
    assert product.is_active is True


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_product_returns_existing(db, product):
    """(+) Retrieves a product by its ID."""
    fetched = await product_service.get_product(product.id, db)
    assert fetched.id == product.id


@pytest.mark.asyncio
async def test_get_product_raises_404_for_unknown_id(db):
    """(-) Unknown product ID raises 404."""
    with pytest.raises(HTTPException) as exc:
        await product_service.get_product(uuid.uuid4(), db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# list_products
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_products_returns_active(db, product):
    """(+) list_products returns active products."""
    products = await product_service.list_products(db, active_only=True)
    ids = [p.id for p in products]
    assert product.id in ids


@pytest.mark.asyncio
async def test_list_products_excludes_inactive(db, product):
    """(+) Inactive products are excluded from active-only listing."""
    await product_service.update_product(product.id, ProductUpdate(is_active=False), db)
    products = await product_service.list_products(db, active_only=True)
    assert product.id not in [p.id for p in products]


@pytest.mark.asyncio
async def test_list_products_includes_inactive_when_flag_off(db, product):
    """(+) active_only=False returns inactive products too."""
    await product_service.update_product(product.id, ProductUpdate(is_active=False), db)
    products = await product_service.list_products(db, active_only=False)
    assert product.id in [p.id for p in products]


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_product_changes_name(db, product):
    """(+) Name update is persisted."""
    updated = await product_service.update_product(product.id, ProductUpdate(name="Updated Name"), db)
    assert updated.name == "Updated Name"


@pytest.mark.asyncio
async def test_update_product_changes_rate(db, product):
    """(+) Interest rate update is persisted."""
    updated = await product_service.update_product(
        product.id, ProductUpdate(default_interest_rate=Decimal("0.0799")), db
    )
    assert Decimal(str(updated.default_interest_rate)) == Decimal("0.0799")


@pytest.mark.asyncio
async def test_update_product_raises_404_for_unknown_id(db):
    """(-) Updating a non-existent product raises 404."""
    with pytest.raises(HTTPException) as exc:
        await product_service.update_product(uuid.uuid4(), ProductUpdate(name="X"), db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_effective_terms
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_effective_terms_uses_product_defaults(db, partner, product, partner_product):
    """(+) Returns product defaults when PartnerProduct has no overrides."""
    p, _ = partner
    rate, fee = await product_service.resolve_effective_terms(p.id, product.id, db)
    assert rate == Decimal(str(product.default_interest_rate))
    assert fee == Decimal(str(product.origination_fee))


@pytest.mark.asyncio
async def test_resolve_effective_terms_uses_rate_override(db, partner, product, partner_product):
    """(+) PartnerProduct rate_override supersedes the product default."""
    p, _ = partner
    partner_product.rate_override = Decimal("0.0599")
    await db.commit()

    rate, _ = await product_service.resolve_effective_terms(p.id, product.id, db)
    assert rate == Decimal("0.0599")


@pytest.mark.asyncio
async def test_resolve_effective_terms_uses_fee_override(db, partner, product, partner_product):
    """(+) PartnerProduct origination_fee_override supersedes the product default."""
    p, _ = partner
    partner_product.origination_fee_override = Decimal("25.00")
    await db.commit()

    _, fee = await product_service.resolve_effective_terms(p.id, product.id, db)
    assert fee == Decimal("25.00")


@pytest.mark.asyncio
async def test_resolve_effective_terms_raises_403_when_not_assigned(db, partner, product):
    """(-) Partner not assigned to product raises 403."""
    p, _ = partner
    with pytest.raises(HTTPException) as exc:
        await product_service.resolve_effective_terms(p.id, product.id, db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_effective_terms_raises_403_when_inactive(db, partner, product, partner_product):
    """(-) Inactive PartnerProduct raises 403."""
    p, _ = partner
    partner_product.is_active = False
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await product_service.resolve_effective_terms(p.id, product.id, db)
    assert exc.value.status_code == 403
