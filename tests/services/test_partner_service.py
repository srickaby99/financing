"""Tests for partner_service — partner management, auth, and product assignment."""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.partner import PartnerStatus
from app.schemas.partner import PartnerCreate, PartnerProductAssign
from app.services import partner_service


# ---------------------------------------------------------------------------
# create_partner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_partner_returns_partner_and_key(db):
    """(+) Returns partner record and a non-empty raw API key."""
    partner, raw_key = await partner_service.create_partner(
        PartnerCreate(name="Acme Corp", slug="acme-corp"), db
    )
    assert partner.id is not None
    assert partner.name == "Acme Corp"
    assert raw_key is not None and len(raw_key) > 0


@pytest.mark.asyncio
async def test_create_partner_stores_key_hash_not_raw(db):
    """(+) Raw API key is not stored — only its hash."""
    partner, raw_key = await partner_service.create_partner(
        PartnerCreate(name="Hash Test", slug=f"hash-test-{uuid.uuid4().hex[:6]}"), db
    )
    assert partner.api_key_hash != raw_key


@pytest.mark.asyncio
async def test_create_partner_default_status_active(db):
    """(+) New partners are ACTIVE by default."""
    partner, _ = await partner_service.create_partner(
        PartnerCreate(name="Active Co", slug=f"active-co-{uuid.uuid4().hex[:6]}"), db
    )
    assert partner.status == PartnerStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_partner_raises_409_for_duplicate_slug(db):
    """(-) Creating a second partner with the same slug raises 409."""
    slug = f"unique-slug-{uuid.uuid4().hex[:6]}"
    await partner_service.create_partner(PartnerCreate(name="First", slug=slug), db)

    with pytest.raises(HTTPException) as exc:
        await partner_service.create_partner(PartnerCreate(name="Second", slug=slug), db)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# get_partner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_partner_returns_existing(db, partner):
    """(+) Retrieves a partner by its ID."""
    p, _ = partner
    fetched = await partner_service.get_partner(p.id, db)
    assert fetched.id == p.id


@pytest.mark.asyncio
async def test_get_partner_raises_404_for_unknown_id(db):
    """(-) Unknown partner ID raises 404."""
    with pytest.raises(HTTPException) as exc:
        await partner_service.get_partner(uuid.uuid4(), db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# authenticate_partner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_partner_returns_partner_for_valid_key(db, partner):
    """(+) Valid API key resolves to the correct partner."""
    p, raw_key = partner
    result = await partner_service.authenticate_partner(raw_key, db)
    assert result.id == p.id


@pytest.mark.asyncio
async def test_authenticate_partner_raises_401_for_invalid_key(db):
    """(-) Invalid API key raises 401."""
    with pytest.raises(HTTPException) as exc:
        await partner_service.authenticate_partner("not-a-valid-key", db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_partner_raises_403_for_suspended_partner(db, partner):
    """(-) Suspended partner raises 403 even with a valid key."""
    p, raw_key = partner
    p.status = PartnerStatus.SUSPENDED
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await partner_service.authenticate_partner(raw_key, db)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# assign_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assign_product_creates_partner_product(db, partner, product):
    """(+) Assigning a product creates a PartnerProduct record."""
    p, _ = partner
    pp = await partner_service.assign_product(
        p.id, PartnerProductAssign(product_id=product.id), db
    )
    assert pp.partner_id == p.id
    assert pp.product_id == product.id
    assert pp.is_active is True


@pytest.mark.asyncio
async def test_assign_product_stores_rate_override(db, partner, product):
    """(+) Rate override is stored on the PartnerProduct."""
    p, _ = partner
    pp = await partner_service.assign_product(
        p.id,
        PartnerProductAssign(product_id=product.id, rate_override=Decimal("0.0599")),
        db,
    )
    assert Decimal(str(pp.rate_override)) == Decimal("0.0599")


@pytest.mark.asyncio
async def test_assign_product_reactivates_existing(db, partner, product):
    """(+) Assigning a product that was previously deactivated reactivates it."""
    p, _ = partner
    pp = await partner_service.assign_product(
        p.id, PartnerProductAssign(product_id=product.id), db
    )
    pp.is_active = False
    await db.commit()

    pp_updated = await partner_service.assign_product(
        p.id, PartnerProductAssign(product_id=product.id), db
    )
    assert pp_updated.is_active is True
    assert pp_updated.id == pp.id  # same record, not a new one


# ---------------------------------------------------------------------------
# list_partner_products
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_partner_products_returns_assigned(db, partner, product, partner_product):
    """(+) Lists active products assigned to a partner."""
    p, _ = partner
    results = await partner_service.list_partner_products(p.id, db)
    assert any(pp.product_id == product.id for pp in results)


@pytest.mark.asyncio
async def test_list_partner_products_excludes_inactive(db, partner, product, partner_product):
    """(+) Inactive PartnerProduct entries are excluded."""
    p, _ = partner
    partner_product.is_active = False
    await db.commit()

    results = await partner_service.list_partner_products(p.id, db)
    assert not any(pp.product_id == product.id for pp in results)


@pytest.mark.asyncio
async def test_list_partner_products_empty_for_unassigned_partner(db, partner):
    """(+) Partner with no products returns empty list."""
    p, _ = partner
    results = await partner_service.list_partner_products(p.id, db)
    assert results == []
