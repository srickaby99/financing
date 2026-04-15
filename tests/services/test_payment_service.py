"""Tests for payment_service — inbound webhook handling and idempotency."""

import uuid
from decimal import Decimal
from datetime import date

import pytest
from sqlalchemy import select

from app.models.payment import InboundWebhookEvent, Payment, WebhookStatus
from app.schemas.payment import InboundPaymentWebhook
from app.services import payment_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _webhook(loan_id, event_id: str = None, amount="100.00") -> InboundPaymentWebhook:
    return InboundPaymentWebhook(
        event_id=event_id or f"evt-{uuid.uuid4().hex}",
        event_type="payment.settled",
        loan_id=loan_id,
        amount=Decimal(amount),
        payment_date=date(2026, 5, 1),
        external_reference_id=f"txn-{uuid.uuid4().hex[:8]}",
    )


# ---------------------------------------------------------------------------
# receive_payment_webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_creates_event_record(db, approved_application):
    """(+) Inbound webhook creates an InboundWebhookEvent record."""
    event = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id),
        source="test-processor",
        db=db,
    )
    assert event.id is not None
    assert event.source == "test-processor"


@pytest.mark.asyncio
async def test_webhook_records_event_type(db, approved_application):
    """(+) event_type is stored on the webhook event."""
    event = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id),
        source="processor",
        db=db,
    )
    assert event.event_type == "payment.settled"


@pytest.mark.asyncio
async def test_webhook_applies_payment_to_loan(db, approved_application):
    """(+) Payment is applied and loan balance is reduced."""
    from app.models.loan import Loan

    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    balance_before = Decimal(str(loan.outstanding_balance))

    await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id, amount="100.00"),
        source="processor",
        db=db,
    )

    await db.refresh(loan)
    balance_after = Decimal(str(loan.outstanding_balance))
    assert balance_after < balance_before


@pytest.mark.asyncio
async def test_webhook_creates_payment_record(db, approved_application):
    """(+) A Payment record is created after processing."""
    event = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id, amount="88.85"),
        source="processor",
        db=db,
    )
    result = await db.execute(
        select(Payment).where(Payment.loan_id == approved_application.loan_id)
    )
    payments = result.scalars().all()
    assert len(payments) == 1
    assert Decimal(str(payments[0].amount)) == Decimal("88.85")


@pytest.mark.asyncio
async def test_webhook_marks_event_processed(db, approved_application):
    """(+) Event status is PROCESSED after successful payment application."""
    event = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id),
        source="processor",
        db=db,
    )
    await db.refresh(event)
    assert event.status == WebhookStatus.PROCESSED


@pytest.mark.asyncio
async def test_webhook_idempotent_on_duplicate_event_id(db, approved_application):
    """(-) Sending the same event_id twice returns the same event, no duplicate payment."""
    event_id = f"evt-dedup-{uuid.uuid4().hex}"

    e1 = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id, event_id=event_id),
        source="processor",
        db=db,
    )
    e2 = await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id, event_id=event_id),
        source="processor",
        db=db,
    )

    assert e1.id == e2.id

    result = await db.execute(
        select(Payment).where(Payment.loan_id == approved_application.loan_id)
    )
    payments = result.scalars().all()
    assert len(payments) == 1


@pytest.mark.asyncio
async def test_full_payoff_marks_loan_paid_off(db, approved_application):
    """(+) Paying the full outstanding balance marks the loan as PAID_OFF."""
    from app.models.loan import Loan, LoanStatus

    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    full_balance = str(loan.outstanding_balance)

    await payment_service.receive_payment_webhook(
        _webhook(approved_application.loan_id, amount=full_balance),
        source="processor",
        db=db,
    )

    await db.refresh(loan)
    assert loan.status == LoanStatus.PAID_OFF
    assert loan.next_due_date is None
