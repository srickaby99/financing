"""Integration tests for inbound payment webhook handling."""

import pytest
import pytest_asyncio


WEBHOOK_PAYLOAD = {
    "event_id": "evt_001",
    "event_type": "payment.settled",
    "loan_id": None,  # filled in per test
    "amount": "88.85",
    "payment_date": "2026-02-01",
    "external_reference_id": "txn_abc123",
}


@pytest.mark.asyncio
async def test_webhook_accepted_and_logged(client, approved_loan):
    loan_id, api_key = approved_loan
    payload = {**WEBHOOK_PAYLOAD, "loan_id": str(loan_id), "event_id": "evt_unique_001"}

    resp = await client.post(
        "/api/v1/webhooks/payments",
        json=payload,
        headers={"X-Payment-Source": "test-processor"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RECEIVED"
    assert data["external_event_id"] == "evt_unique_001"


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(client, approved_loan):
    """Sending the same event_id twice must not create duplicate records."""
    loan_id, api_key = approved_loan
    payload = {**WEBHOOK_PAYLOAD, "loan_id": str(loan_id), "event_id": "evt_duplicate_test"}

    r1 = await client.post("/api/v1/webhooks/payments", json=payload)
    r2 = await client.post("/api/v1/webhooks/payments", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    # Both responses refer to the same event
    assert r1.json()["id"] == r2.json()["id"]


@pytest_asyncio.fixture
async def approved_loan(client):
    """Create a full partner → product → borrower → approved application → loan."""
    p_resp = await client.post("/api/v1/partners", json={"name": "Pay Corp", "slug": "pay-corp"})
    partner = p_resp.json()["partner"]
    api_key = p_resp.json()["api_key"]

    prod_resp = await client.post("/api/v1/products", json={
        "name": "Personal Loan",
        "product_type": "PERSONAL",
        "interest_rate_model": "FIXED",
        "min_term_months": 6,
        "max_term_months": 36,
        "min_amount": "100.00",
        "max_amount": "5000.00",
        "default_interest_rate": "0.1199",
        "eligibility_rules": {},
    })
    product = prod_resp.json()

    await client.post(
        f"/api/v1/partners/{partner['id']}/products",
        json={"product_id": product["id"]},
    )

    b_resp = await client.post("/api/v1/borrowers", json={
        "first_name": "Bob",
        "last_name": "Smith",
        "date_of_birth": "1985-03-20",
        "ssn": "111223333",
        "email": "bob@example.com",
        "address_line1": "456 Oak Ave",
        "city": "Dallas",
        "state": "TX",
        "zip_code": "75201",
    })
    borrower = b_resp.json()

    app_resp = await client.post(
        "/api/v1/applications",
        json={
            "borrower_id": borrower["id"],
            "product_id": product["id"],
            "requested_amount": "1000.00",
            "requested_term_months": 12,
        },
        headers={"X-API-Key": api_key},
    )
    loan_id = app_resp.json()["loan_id"]
    return loan_id, api_key
