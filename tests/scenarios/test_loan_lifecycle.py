"""
Full loan lifecycle scenario test.

Walks through all four phases from the README end-to-end, making HTTP
requests exactly as a real client would. At each step the complete
expected system state is asserted — not just that something changed,
but that every relevant field has the right value.

    Phase 1 — Admin sets up a product and partner
    Phase 2 — Partner onboards a borrower
    Phase 3 — Borrower applies, system decisions instantly
    Phase 4 — Payments applied, loan reaches PAID_OFF

Run with:
    python -m pytest tests/scenarios/test_loan_lifecycle.py -v
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.scenarios.conftest import make_credit_mock

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

PRODUCT = {
    "name": "12-Month Device Financing",
    "product_type": "DEVICE",
    "interest_rate_model": "FIXED",
    "min_term_months": 3,
    "max_term_months": 24,
    "min_amount": "200.00",
    "max_amount": "2000.00",
    "default_interest_rate": "0.0999",
    "origination_fee": "0.00",
    "late_fee_rules": {},
    "eligibility_rules": {"min_credit_score": 600, "max_dti": 0.45},
}

BORROWER = {
    "first_name": "Alex",
    "last_name": "Johnson",
    "date_of_birth": "1990-03-15",
    "ssn": "123456789",
    "email": "alex.johnson@example.com",
    "phone": "512-555-0100",
    "address_line1": "100 Main St",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
}

PAYMENT_METHOD = {
    "type": "CARD",
    "processor_token": "tok_stripe_test_abc123",
    "last4": "4242",
    "brand": "Visa",
    "is_default": True,
}

APPLICATION = {
    "requested_amount": "1000.00",
    "requested_term_months": 12,
}


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_loan_lifecycle(client):
    """
    End-to-end loan lifecycle: admin setup → borrower onboarding →
    application approval → first payment → full payoff.
    """

    # =========================================================================
    # PHASE 1 — Admin Setup
    # =========================================================================

    # --- Step 1: Create a product -----------------------------------------------
    r = await client.post("/api/v1/products", json=PRODUCT)

    assert r.status_code == 201, r.text
    product = r.json()

    assert product["id"] is not None
    assert product["name"] == "12-Month Device Financing"
    assert product["product_type"] == "DEVICE"
    assert product["interest_rate_model"] == "FIXED"
    assert Decimal(product["min_amount"]) == Decimal("200.00")
    assert Decimal(product["max_amount"]) == Decimal("2000.00")
    assert Decimal(product["default_interest_rate"]) == Decimal("0.0999")
    assert Decimal(product["origination_fee"]) == Decimal("0.00")
    assert product["eligibility_rules"] == {"min_credit_score": 600, "max_dti": 0.45}
    assert product["is_active"] is True

    product_id = product["id"]

    # --- Step 2: Create a partner -----------------------------------------------
    slug = f"acme-electronics-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/v1/partners", json={"name": "Acme Electronics", "slug": slug})

    assert r.status_code == 201, r.text
    partner_response = r.json()

    partner = partner_response["partner"]
    api_key = partner_response["api_key"]

    assert partner["id"] is not None
    assert partner["name"] == "Acme Electronics"
    assert partner["slug"] == slug
    assert partner["status"] == "ACTIVE"
    # API key must be returned once and only once at creation
    assert isinstance(api_key, str)
    assert len(api_key) > 20

    partner_id = partner["id"]
    partner_headers = {"X-API-Key": api_key}

    # --- Step 3: Assign the product to the partner ------------------------------
    r = await client.post(
        f"/api/v1/partners/{partner_id}/products",
        json={"product_id": product_id},
    )

    assert r.status_code == 201, r.text
    assignment = r.json()

    assert assignment["partner_id"] == partner_id
    assert assignment["product_id"] == product_id
    assert assignment["is_active"] is True
    # No overrides set — partner uses product defaults
    assert assignment["rate_override"] is None
    assert assignment["origination_fee_override"] is None

    # =========================================================================
    # PHASE 2 — Borrower Onboarding
    # =========================================================================

    # --- Step 4: Create a borrower ----------------------------------------------
    borrower_payload = {**BORROWER, "email": f"alex.{uuid.uuid4().hex[:6]}@example.com"}
    r = await client.post("/api/v1/borrowers", json=borrower_payload)

    assert r.status_code == 201, r.text
    borrower = r.json()

    assert borrower["id"] is not None
    assert borrower["first_name"] == "Alex"
    assert borrower["last_name"] == "Johnson"
    assert borrower["ssn_last4"] == "6789"
    assert borrower["state"] == "TX"
    assert borrower["city"] == "Austin"
    assert borrower["address_line1"] == "100 Main St"
    assert borrower["zip_code"] == "78701"
    # Full SSN must never appear in the response
    assert "ssn" not in borrower
    assert "123456789" not in str(borrower)

    borrower_id = borrower["id"]

    # --- Step 5: Add a tokenized payment method ---------------------------------
    r = await client.post(f"/api/v1/borrowers/{borrower_id}/payment-methods", json=PAYMENT_METHOD)

    assert r.status_code == 201, r.text
    pm = r.json()

    assert pm["id"] is not None
    assert pm["borrower_id"] == borrower_id
    assert pm["type"] == "CARD"
    assert pm["last4"] == "4242"
    assert pm["brand"] == "Visa"
    assert pm["is_default"] is True
    assert pm["status"] == "ACTIVE"
    # Raw processor token must never appear in the response
    assert "tok_stripe_test_abc123" not in str(pm)

    # =========================================================================
    # PHASE 3 — Application and Decisioning
    # =========================================================================

    # --- Step 6: Submit a loan application --------------------------------------
    # Credit score 720 with $5,000/month income and $400/month debt → DTI 0.08
    # Both pass the product rules (min_credit_score=600, max_dti=0.45) → APPROVED

    application_payload = {
        **APPLICATION,
        "borrower_id": borrower_id,
        "product_id": product_id,
    }

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_factory.return_value = make_credit_mock(
            credit_score=720,
            monthly_income="5000.00",
            monthly_debt="400.00",
        )
        r = await client.post("/api/v1/applications", json=application_payload, headers=partner_headers)

    assert r.status_code == 201, r.text
    application = r.json()

    # Application-level state
    assert application["id"] is not None
    assert application["borrower_id"] == borrower_id
    assert application["product_id"] == product_id
    assert application["partner_id"] == partner_id
    assert Decimal(application["requested_amount"]) == Decimal("1000.00")
    assert application["requested_term_months"] == 12
    assert application["status"] == "APPROVED"
    assert application["decided_at"] is not None
    assert application["loan_id"] is not None  # loan was originated

    # Underwriting result — every field checked
    uw = application["underwriting_result"]
    assert uw["approved"] is True
    assert uw["credit_score"] == 720
    assert Decimal(str(uw["dti"])) == Decimal("0.08")   # 400/5000
    assert Decimal(uw["approved_amount"]) == Decimal("1000.00")
    assert Decimal(uw["approved_rate"]) == Decimal("0.0999")
    assert uw["approved_term_months"] == 12
    assert Decimal(uw["monthly_payment"]) > Decimal("0")
    assert uw["decline_reasons"] == []

    loan_id = application["loan_id"]
    monthly_payment = uw["monthly_payment"]  # carry forward for payment steps

    # --- Step 7: Verify the originated loan's full state ------------------------
    r = await client.get(f"/api/v1/loans/{loan_id}", headers=partner_headers)

    assert r.status_code == 200, r.text
    loan = r.json()

    assert loan["id"] == loan_id
    assert loan["application_id"] == application["id"]
    assert loan["borrower_id"] == borrower_id
    assert loan["product_id"] == product_id
    assert loan["status"] == "ACTIVE"
    assert Decimal(loan["principal"]) == Decimal("1000.00")
    assert Decimal(loan["outstanding_balance"]) == Decimal("1000.00")  # no payments yet
    assert Decimal(loan["interest_rate"]) == Decimal("0.0999")
    assert loan["term_months"] == 12
    assert Decimal(loan["origination_fee"]) == Decimal("0.00")
    assert loan["origination_date"] is not None
    assert loan["maturity_date"] is not None
    assert loan["next_due_date"] is not None

    # --- Step 8: Verify the amortization schedule -------------------------------
    r = await client.get(f"/api/v1/loans/{loan_id}/schedule", headers=partner_headers)

    assert r.status_code == 200, r.text
    schedule = r.json()

    # One entry per month of the term
    assert len(schedule) == 12

    # Periods are numbered 1 through 12 in order
    assert [e["period"] for e in schedule] == list(range(1, 13))

    # Every period has a positive principal and interest component
    for entry in schedule:
        assert Decimal(entry["principal_due"]) > Decimal("0")
        assert Decimal(entry["interest_due"]) > Decimal("0")
        assert Decimal(entry["balance_after"]) >= Decimal("0")

    # Final period amortizes completely to zero
    assert Decimal(schedule[-1]["balance_after"]) == Decimal("0.00")

    # Due dates advance month-by-month
    from datetime import date
    due_dates = [date.fromisoformat(e["due_date"]) for e in schedule]
    for i in range(1, len(due_dates)):
        assert due_dates[i] > due_dates[i - 1]

    # No payments recorded yet
    r = await client.get(f"/api/v1/loans/{loan_id}/payments", headers=partner_headers)
    assert r.status_code == 200
    assert r.json() == []

    # =========================================================================
    # PHASE 4 — Loan Servicing and Payoff
    # =========================================================================

    # --- Step 9: First payment --------------------------------------------------
    # The processor sends a settlement notification for one monthly payment.
    # Current implementation applies all payment directly to principal
    # (accrued_interest=0 in payment_processing.py — interest accrual is
    # tracked on the schedule but not yet deducted at payment time).

    r = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": "payment.settled",
            "loan_id": loan_id,
            "amount": monthly_payment,
            "payment_date": "2026-05-01",
            "external_reference_id": f"txn-{uuid.uuid4().hex[:8]}",
        },
        headers={"X-Payment-Source": "stripe"},
    )

    assert r.status_code == 200, r.text
    event = r.json()

    # Webhook event state
    assert event["id"] is not None
    assert event["status"] == "PROCESSED"
    assert event["payment_id"] is not None
    assert event["processed_at"] is not None

    # Loan balance reduced by the full payment amount (all goes to principal)
    r = await client.get(f"/api/v1/loans/{loan_id}", headers=partner_headers)
    loan = r.json()

    expected_balance = (Decimal("1000.00") - Decimal(monthly_payment)).quantize(Decimal("0.01"))
    assert Decimal(loan["outstanding_balance"]) == expected_balance
    assert loan["status"] == "ACTIVE"  # not paid off yet

    # Payment record — complete state check
    r = await client.get(f"/api/v1/loans/{loan_id}/payments", headers=partner_headers)
    payments = r.json()

    assert len(payments) == 1
    p = payments[0]
    assert p["loan_id"] == loan_id
    assert Decimal(p["amount"]) == Decimal(monthly_payment)
    assert Decimal(p["principal_applied"]) == Decimal(monthly_payment)  # all to principal
    assert Decimal(p["interest_applied"]) == Decimal("0.00")
    assert Decimal(p["fees_applied"]) == Decimal("0.00")
    assert p["status"] == "SETTLED"
    assert p["payment_date"] == "2026-05-01"

    # --- Step 10: Idempotency check — duplicate event is safely ignored ---------
    duplicate_event_id = f"evt-dedup-{uuid.uuid4().hex}"

    r1 = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "event_id": duplicate_event_id,
            "event_type": "payment.settled",
            "loan_id": loan_id,
            "amount": monthly_payment,
            "payment_date": "2026-05-15",
            "external_reference_id": f"txn-{uuid.uuid4().hex[:8]}",
        },
    )
    r2 = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "event_id": duplicate_event_id,  # same event_id
            "event_type": "payment.settled",
            "loan_id": loan_id,
            "amount": monthly_payment,
            "payment_date": "2026-05-15",
            "external_reference_id": f"txn-{uuid.uuid4().hex[:8]}",
        },
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same event returned both times
    assert r1.json()["id"] == r2.json()["id"]

    # Only one additional payment record created (not two)
    r = await client.get(f"/api/v1/loans/{loan_id}/payments", headers=partner_headers)
    assert len(r.json()) == 2  # original + one from dedup test (not two)

    # --- Step 11: Full payoff ---------------------------------------------------
    # Fetch current balance and send a payment for the exact remaining amount.

    r = await client.get(f"/api/v1/loans/{loan_id}", headers=partner_headers)
    remaining_balance = r.json()["outstanding_balance"]

    r = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": "payment.settled",
            "loan_id": loan_id,
            "amount": remaining_balance,
            "payment_date": "2026-06-01",
            "external_reference_id": f"txn-{uuid.uuid4().hex[:8]}",
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PROCESSED"

    # Final loan state — all fields checked
    r = await client.get(f"/api/v1/loans/{loan_id}", headers=partner_headers)
    loan = r.json()

    assert loan["status"] == "PAID_OFF"
    assert Decimal(loan["outstanding_balance"]) == Decimal("0.00")
    assert loan["next_due_date"] is None
