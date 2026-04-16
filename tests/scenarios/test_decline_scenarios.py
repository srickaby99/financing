"""
Decline and error scenario tests.

Verifies that the system correctly rejects applications and requests
that violate business rules or authorization requirements.

Each test asserts:
  - The correct HTTP status code
  - The correct error detail or decline reason
  - That no loan was created when an application is declined

Run with:
    python -m pytest tests/scenarios/test_decline_scenarios.py -v
"""

import uuid
from unittest.mock import patch

import pytest

from tests.scenarios.conftest import make_credit_mock


# ---------------------------------------------------------------------------
# Shared setup — product, partner, borrower created fresh per test
# ---------------------------------------------------------------------------

async def _create_product(client) -> dict:
    r = await client.post("/api/v1/products", json={
        "name": "Test Product",
        "product_type": "PERSONAL",
        "interest_rate_model": "FIXED",
        "min_term_months": 6,
        "max_term_months": 36,
        "min_amount": "500.00",
        "max_amount": "10000.00",
        "default_interest_rate": "0.1199",
        "origination_fee": "0.00",
        "late_fee_rules": {},
        "eligibility_rules": {
            "min_credit_score": 640,
            "max_dti": 0.40,
        },
    })
    assert r.status_code == 201
    return r.json()


async def _create_partner(client) -> tuple[dict, str]:
    slug = f"test-partner-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/v1/partners", json={"name": "Test Partner", "slug": slug})
    assert r.status_code == 201
    body = r.json()
    return body["partner"], body["api_key"]


async def _assign(client, partner_id: str, product_id: str) -> None:
    r = await client.post(
        f"/api/v1/partners/{partner_id}/products",
        json={"product_id": product_id},
    )
    assert r.status_code == 201


async def _create_borrower(client) -> str:
    r = await client.post("/api/v1/borrowers", json={
        "first_name": "Test",
        "last_name": "Borrower",
        "date_of_birth": "1985-01-01",
        "ssn": f"9{uuid.uuid4().int % 100000000:08d}",
        "email": f"test.{uuid.uuid4().hex[:8]}@example.com",
        "address_line1": "1 Test St",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
    })
    assert r.status_code == 201
    return r.json()["id"]


async def _setup(client):
    """Create product, partner, assignment, and borrower. Returns (product, partner, api_key, borrower_id)."""
    product = await _create_product(client)
    partner, api_key = await _create_partner(client)
    await _assign(client, partner["id"], product["id"])
    borrower_id = await _create_borrower(client)
    return product, partner, api_key, borrower_id


# ---------------------------------------------------------------------------
# Decline: credit score below minimum
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_declined_low_credit_score(client):
    """
    Application with credit score below product minimum (640) is DECLINED.

    System state after:
      - application.status = DECLINED
      - application.loan_id = None (no loan created)
      - underwriting_result contains the specific decline reason
    """
    product, partner, api_key, borrower_id = await _setup(client)

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(
            credit_score=580,           # below min_credit_score=640
            monthly_income="5000.00",
            monthly_debt="500.00",
        )
        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product["id"],
                "requested_amount": "2000.00",
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert r.status_code == 201, r.text
    application = r.json()

    assert application["status"] == "DECLINED"
    assert application["loan_id"] is None  # no loan originated

    uw = application["underwriting_result"]
    assert uw["approved"] is False
    assert uw["credit_score"] == 580
    assert len(uw["decline_reasons"]) >= 1
    assert any("credit_score" in reason for reason in uw["decline_reasons"])
    assert uw["approved_amount"] is None
    assert uw["monthly_payment"] is None


# ---------------------------------------------------------------------------
# Decline: DTI above maximum
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_declined_high_dti(client):
    """
    Application with DTI above product maximum (0.40) is DECLINED.

    $3,000 debt / $5,000 income = 0.60 DTI > 0.40 max.

    System state after:
      - application.status = DECLINED
      - application.loan_id = None
      - decline reason references DTI
    """
    product, partner, api_key, borrower_id = await _setup(client)

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(
            credit_score=700,           # passes credit check
            monthly_income="5000.00",
            monthly_debt="3000.00",     # DTI = 0.60 — fails max_dti=0.40
        )
        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product["id"],
                "requested_amount": "2000.00",
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert r.status_code == 201, r.text
    application = r.json()

    assert application["status"] == "DECLINED"
    assert application["loan_id"] is None

    uw = application["underwriting_result"]
    assert uw["approved"] is False
    assert len(uw["decline_reasons"]) >= 1
    assert any("dti" in reason for reason in uw["decline_reasons"])


# ---------------------------------------------------------------------------
# Decline: requested amount above product maximum
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rejected_amount_above_maximum(client):
    """
    Requesting more than the product maximum ($10,000) returns 422 immediately.
    No application is created — validation happens before underwriting.
    """
    product, partner, api_key, borrower_id = await _setup(client)

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(credit_score=750)

        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product["id"],
                "requested_amount": "15000.00",  # above max_amount=10000
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Decline: requested amount below product minimum
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rejected_amount_below_minimum(client):
    """
    Requesting less than the product minimum ($500) returns 422 immediately.
    """
    product, partner, api_key, borrower_id = await _setup(client)

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(credit_score=750)

        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product["id"],
                "requested_amount": "100.00",   # below min_amount=500
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Auth: missing API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client):
    """
    Submitting an application without an X-API-Key header returns 401.
    """
    product, partner, api_key, borrower_id = await _setup(client)

    r = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower_id,
            "product_id": product["id"],
            "requested_amount": "2000.00",
            "requested_term_months": 12,
        },
        # no headers — no API key
    )

    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Auth: invalid API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(client):
    """
    Submitting an application with a wrong API key returns 401.
    """
    product, partner, api_key, borrower_id = await _setup(client)

    r = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower_id,
            "product_id": product["id"],
            "requested_amount": "2000.00",
            "requested_term_months": 12,
        },
        headers={"X-API-Key": "invalid-key-that-does-not-exist"},
    )

    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Auth: partner not authorized for product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partner_not_authorized_for_product_returns_403(client):
    """
    A partner cannot submit an application for a product they haven't been assigned.

    Setup: two products — partner is assigned product_a only.
    Attempting to apply using product_b raises 403.
    """
    # Create two products
    product_a = await _create_product(client)
    product_b = await _create_product(client)

    # Partner is assigned only product_a
    partner, api_key = await _create_partner(client)
    await _assign(client, partner["id"], product_a["id"])

    borrower_id = await _create_borrower(client)

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(credit_score=750)

        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product_b["id"],   # partner not assigned to this
                "requested_amount": "2000.00",
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Duplicate webhook: idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_webhook_is_ignored(client):
    """
    Sending the same event_id twice results in exactly one payment applied.

    The second call returns 200 (not an error) but the same event record,
    and the loan balance is only reduced once.
    """
    product, partner, api_key, borrower_id = await _setup(client)

    # Get an approved loan first
    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(credit_score=700)
        r = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower_id,
                "product_id": product["id"],
                "requested_amount": "1000.00",
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )
    assert r.status_code == 201
    loan_id = r.json()["loan_id"]
    assert loan_id is not None

    # Send the same webhook twice
    duplicate_event_id = f"evt-dup-{uuid.uuid4().hex}"
    webhook_payload = {
        "event_id": duplicate_event_id,
        "event_type": "payment.settled",
        "loan_id": loan_id,
        "amount": "100.00",
        "payment_date": "2026-05-01",
        "external_reference_id": f"txn-{uuid.uuid4().hex[:8]}",
    }

    r1 = await client.post("/api/v1/webhooks/payments", json=webhook_payload)
    r2 = await client.post("/api/v1/webhooks/payments", json=webhook_payload)

    assert r1.status_code == 200
    assert r2.status_code == 200

    # Same event record returned
    assert r1.json()["id"] == r2.json()["id"]

    # Only one payment applied — balance reduced by $100 exactly once
    r = await client.get(f"/api/v1/loans/{loan_id}", headers={"X-API-Key": api_key})
    from decimal import Decimal
    assert Decimal(r.json()["outstanding_balance"]) == Decimal("900.00")
