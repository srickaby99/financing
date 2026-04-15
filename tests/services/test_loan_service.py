"""Tests for loan_service — origination, retrieval, schedule, and payments."""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.loan import Loan, LoanStatus, RepaymentScheduleEntry
from app.models.ledger import EntryType, LedgerEntry
from app.services import loan_service


# ---------------------------------------------------------------------------
# get_loan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_loan_returns_existing(db, approved_application):
    """(+) Retrieves a loan by ID."""
    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()

    fetched = await loan_service.get_loan(loan.id, db)
    assert fetched.id == loan.id


@pytest.mark.asyncio
async def test_get_loan_raises_404_for_unknown_id(db):
    """(-) Unknown loan ID raises 404."""
    with pytest.raises(HTTPException) as exc:
        await loan_service.get_loan(uuid.uuid4(), db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Loan origination (via approved_application fixture)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_originated_loan_has_correct_principal(db, approved_application):
    """(+) Loan principal matches the approved amount."""
    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    assert Decimal(str(loan.principal)) == Decimal("800.00")


@pytest.mark.asyncio
async def test_originated_loan_status_is_active(db, approved_application):
    """(+) Newly originated loans are ACTIVE."""
    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    assert loan.status == LoanStatus.ACTIVE


@pytest.mark.asyncio
async def test_originated_loan_outstanding_balance_equals_principal(db, approved_application):
    """(+) Initial outstanding balance equals the principal."""
    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    assert Decimal(str(loan.outstanding_balance)) == Decimal(str(loan.principal))


@pytest.mark.asyncio
async def test_originated_loan_has_next_due_date(db, approved_application):
    """(+) Loan has a next_due_date set after origination."""
    result = await db.execute(select(Loan).where(Loan.id == approved_application.loan_id))
    loan = result.scalar_one()
    assert loan.next_due_date is not None


@pytest.mark.asyncio
async def test_originated_loan_creates_disbursement_ledger_entry(db, approved_application):
    """(+) A DISBURSEMENT ledger entry is created at origination."""
    result = await db.execute(
        select(LedgerEntry).where(
            LedgerEntry.loan_id == approved_application.loan_id,
            LedgerEntry.entry_type == EntryType.DISBURSEMENT,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert Decimal(str(entry.amount)) == Decimal("800.00")


# ---------------------------------------------------------------------------
# get_loan_schedule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_loan_schedule_returns_correct_number_of_entries(db, approved_application):
    """(+) Schedule has one entry per month of the loan term."""
    schedule = await loan_service.get_loan_schedule(approved_application.loan_id, db)
    assert len(schedule) == 12


@pytest.mark.asyncio
async def test_get_loan_schedule_periods_are_sequential(db, approved_application):
    """(+) Schedule periods are numbered 1 through term_months."""
    schedule = await loan_service.get_loan_schedule(approved_application.loan_id, db)
    assert [e.period for e in schedule] == list(range(1, 13))


@pytest.mark.asyncio
async def test_get_loan_schedule_final_balance_is_zero(db, approved_application):
    """(+) Final schedule entry balance_after is zero."""
    schedule = await loan_service.get_loan_schedule(approved_application.loan_id, db)
    assert Decimal(str(schedule[-1].balance_after)) == Decimal("0.00")


@pytest.mark.asyncio
async def test_get_loan_schedule_returns_empty_for_unknown_loan(db):
    """(+) Non-existent loan ID returns empty schedule (no 404)."""
    schedule = await loan_service.get_loan_schedule(uuid.uuid4(), db)
    assert schedule == []


# ---------------------------------------------------------------------------
# get_loan_payments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_loan_payments_empty_before_any_payment(db, approved_application):
    """(+) No payments recorded before any webhook is received."""
    payments = await loan_service.get_loan_payments(approved_application.loan_id, db)
    assert payments == []


@pytest.mark.asyncio
async def test_get_loan_payments_returns_empty_for_unknown_loan(db):
    """(+) Non-existent loan ID returns empty list (no 404)."""
    payments = await loan_service.get_loan_payments(uuid.uuid4(), db)
    assert payments == []
