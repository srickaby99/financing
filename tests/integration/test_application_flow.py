"""Integration tests for the full application → approval → origination flow."""

import pytest
import pytest_asyncio


PRODUCT_PAYLOAD = {
    "name": "Device Financing",
    "description": "Point-of-sale device financing",
    "product_type": "DEVICE",
    "interest_rate_model": "FIXED",
    "min_term_months": 3,
    "max_term_months": 24,
    "min_amount": "100.00",
    "max_amount": "2000.00",
    "default_interest_rate": "0.0999",
    "origination_fee": "0.00",
    "eligibility_rules": {"min_credit_score": 580},
}

BORROWER_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1990-05-15",
    "ssn": "123456789",
    "email": "jane.doe@example.com",
    "address_line1": "123 Main St",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
}


@pytest_asyncio.fixture
async def partner_and_key(client):
    resp = await client.post("/api/v1/partners", json={"name": "Acme Electronics", "slug": "acme"})
    assert resp.status_code == 201
    data = resp.json()
    return data["partner"], data["api_key"]


@pytest_asyncio.fixture
async def product(client):
    resp = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def partner_with_product(client, partner_and_key, product):
    partner, api_key = partner_and_key
    resp = await client.post(
        f"/api/v1/partners/{partner['id']}/products",
        json={"product_id": product["id"]},
    )
    assert resp.status_code == 201
    return partner, api_key, product


@pytest_asyncio.fixture
async def borrower(client):
    resp = await client.post("/api/v1/borrowers", json=BORROWER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_full_approval_flow(client, partner_with_product, borrower):
    partner, api_key, product = partner_with_product

    resp = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower["id"],
            "product_id": product["id"],
            "requested_amount": "800.00",
            "requested_term_months": 12,
        },
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "APPROVED"
    assert data["loan_id"] is not None
    assert data["underwriting_result"]["approved"] is True
    assert data["underwriting_result"]["monthly_payment"] is not None


@pytest.mark.asyncio
async def test_declined_low_credit_score(client, partner_with_product, db):
    """Override dummy client to return a very low score."""
    from unittest.mock import AsyncMock, patch
    from decimal import Decimal
    from app.integrations.credit.models import CreditReport
    import uuid

    partner, api_key, product = partner_with_product

    # Create a borrower with a different SSN to avoid dedup conflict
    resp = await client.post("/api/v1/borrowers", json={**BORROWER_PAYLOAD, "ssn": "987654321", "email": "other@example.com"})
    borrower = resp.json()

    low_score_report = CreditReport(
        borrower_id=uuid.UUID(borrower["id"]),
        credit_score=400,
        monthly_income=Decimal("4000"),
        monthly_debt_obligations=Decimal("500"),
    )

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_client = AsyncMock()
        mock_client.pull_credit_report.return_value = low_score_report
        mock_factory.return_value = mock_client

        resp = await client.post(
            "/api/v1/applications",
            json={
                "borrower_id": borrower["id"],
                "product_id": product["id"],
                "requested_amount": "800.00",
                "requested_term_months": 12,
            },
            headers={"X-API-Key": api_key},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "DECLINED"
    assert data["loan_id"] is None
    assert len(data["underwriting_result"]["decline_reasons"]) > 0


@pytest.mark.asyncio
async def test_approved_loan_has_schedule(client, partner_with_product, borrower):
    partner, api_key, product = partner_with_product

    app_resp = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower["id"],
            "product_id": product["id"],
            "requested_amount": "600.00",
            "requested_term_months": 6,
        },
        headers={"X-API-Key": api_key},
    )
    loan_id = app_resp.json()["loan_id"]

    schedule_resp = await client.get(
        f"/api/v1/loans/{loan_id}/schedule",
        headers={"X-API-Key": api_key},
    )
    assert schedule_resp.status_code == 200
    schedule = schedule_resp.json()
    assert len(schedule) == 6
    assert schedule[-1]["balance_after"] == "0.00"


@pytest.mark.asyncio
async def test_unauthorized_without_api_key(client, product, borrower):
    resp = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower["id"],
            "product_id": product["id"],
            "requested_amount": "500.00",
            "requested_term_months": 12,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_partner_cannot_use_unassigned_product(client, partner_and_key, product, borrower):
    """Partner that hasn't been assigned the product should get 403."""
    # Create a second partner without assigning the product
    resp = await client.post("/api/v1/partners", json={"name": "Other Corp", "slug": "other-corp"})
    other_api_key = resp.json()["api_key"]

    resp = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower["id"],
            "product_id": product["id"],
            "requested_amount": "500.00",
            "requested_term_months": 12,
        },
        headers={"X-API-Key": other_api_key},
    )
    assert resp.status_code == 403
