"""Tests for borrower_service — borrower creation and payment method management."""

import hashlib
import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.borrower import PaymentMethodStatus, PaymentMethodType
from app.schemas.borrower import BorrowerCreate, PaymentMethodCreate
from app.services import borrower_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _borrower_payload(ssn: str = "111223333", email_suffix: str = "") -> BorrowerCreate:
    suffix = email_suffix or uuid.uuid4().hex[:6]
    return BorrowerCreate(
        first_name="Test",
        last_name="User",
        date_of_birth=date(1990, 3, 20),
        ssn=ssn,
        email=f"test.{suffix}@example.com",
        address_line1="789 Pine St",
        city="Houston",
        state="TX",
        zip_code="77001",
    )


# ---------------------------------------------------------------------------
# create_borrower
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_borrower_returns_borrower(db):
    """(+) Creates and returns a borrower record."""
    borrower = await borrower_service.create_borrower(_borrower_payload(), db)
    assert borrower.id is not None
    assert borrower.first_name == "Test"


@pytest.mark.asyncio
async def test_create_borrower_stores_only_last4(db):
    """(+) Full SSN is not stored — only last 4 digits."""
    borrower = await borrower_service.create_borrower(_borrower_payload(ssn="222334444"), db)
    assert borrower.ssn_last4 == "4444"


@pytest.mark.asyncio
async def test_create_borrower_stores_ssn_hash(db):
    """(+) SSN hash is stored for deduplication."""
    ssn = "333445555"
    borrower = await borrower_service.create_borrower(_borrower_payload(ssn=ssn), db)
    expected_hash = hashlib.sha256(ssn.encode()).hexdigest()
    assert borrower.ssn_hash == expected_hash


@pytest.mark.asyncio
async def test_create_borrower_raises_409_for_duplicate_ssn(db):
    """(-) Creating a second borrower with the same SSN raises 409."""
    ssn = "444556666"
    await borrower_service.create_borrower(_borrower_payload(ssn=ssn), db)

    with pytest.raises(HTTPException) as exc:
        await borrower_service.create_borrower(_borrower_payload(ssn=ssn), db)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# get_borrower
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_borrower_returns_existing(db, borrower):
    """(+) Retrieves a borrower by ID."""
    fetched = await borrower_service.get_borrower(borrower.id, db)
    assert fetched.id == borrower.id


@pytest.mark.asyncio
async def test_get_borrower_raises_404_for_unknown_id(db):
    """(-) Unknown borrower ID raises 404."""
    with pytest.raises(HTTPException) as exc:
        await borrower_service.get_borrower(uuid.uuid4(), db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# add_payment_method
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_payment_method_creates_record(db, borrower):
    """(+) Adds a payment method to the borrower."""
    pm = await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.CARD,
            processor_token="tok_test_001",
            last4="4242",
            brand="Visa",
            is_default=False,
        ),
        db,
    )
    assert pm.id is not None
    assert pm.borrower_id == borrower.id
    assert pm.last4 == "4242"


@pytest.mark.asyncio
async def test_add_payment_method_status_active(db, borrower):
    """(+) New payment methods are ACTIVE by default."""
    pm = await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.ACH,
            processor_token="tok_ach_001",
            last4="6789",
            is_default=False,
        ),
        db,
    )
    assert pm.status == PaymentMethodStatus.ACTIVE


@pytest.mark.asyncio
async def test_add_default_payment_method_clears_previous_default(db, borrower):
    """(+) Setting a new default clears the previous default flag."""
    first = await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.CARD,
            processor_token="tok_first",
            last4="1111",
            is_default=True,
        ),
        db,
    )
    assert first.is_default is True

    second = await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.CARD,
            processor_token="tok_second",
            last4="2222",
            is_default=True,
        ),
        db,
    )

    # Refresh first from DB
    await db.refresh(first)
    assert first.is_default is False
    assert second.is_default is True


@pytest.mark.asyncio
async def test_add_non_default_payment_method_does_not_affect_existing_default(db, borrower):
    """(+) Adding a non-default method leaves existing default unchanged."""
    default = await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.CARD,
            processor_token="tok_default",
            last4="9999",
            is_default=True,
        ),
        db,
    )

    await borrower_service.add_payment_method(
        borrower.id,
        PaymentMethodCreate(
            type=PaymentMethodType.CARD,
            processor_token="tok_other",
            last4="8888",
            is_default=False,
        ),
        db,
    )

    await db.refresh(default)
    assert default.is_default is True
