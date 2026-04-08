"""Unit tests for payment allocation logic."""

from datetime import date
from decimal import Decimal

from app.domain.repayment import apply_payment


def test_standard_payment_waterfall():
    """Fees → interest → principal allocation order."""
    allocation = apply_payment(
        outstanding_balance=Decimal("900"),
        accrued_interest=Decimal("10"),
        outstanding_fees=Decimal("5"),
        payment_amount=Decimal("100"),
        payment_date=date(2026, 2, 1),
    )
    assert allocation.fees_applied == Decimal("5.00")
    assert allocation.interest_applied == Decimal("10.00")
    assert allocation.principal_applied == Decimal("85.00")
    assert allocation.remaining == Decimal("0.00")


def test_overpayment_returns_surplus():
    allocation = apply_payment(
        outstanding_balance=Decimal("50"),
        accrued_interest=Decimal("0"),
        outstanding_fees=Decimal("0"),
        payment_amount=Decimal("75"),
        payment_date=date(2026, 2, 1),
    )
    assert allocation.principal_applied == Decimal("50.00")
    assert allocation.remaining == Decimal("25.00")


def test_partial_payment_covers_fees_and_interest_only():
    allocation = apply_payment(
        outstanding_balance=Decimal("500"),
        accrued_interest=Decimal("20"),
        outstanding_fees=Decimal("10"),
        payment_amount=Decimal("25"),
        payment_date=date(2026, 2, 1),
    )
    assert allocation.fees_applied == Decimal("10.00")
    assert allocation.interest_applied == Decimal("15.00")
    assert allocation.principal_applied == Decimal("0.00")
    assert allocation.remaining == Decimal("0.00")


def test_zero_fees_and_interest():
    allocation = apply_payment(
        outstanding_balance=Decimal("200"),
        accrued_interest=Decimal("0"),
        outstanding_fees=Decimal("0"),
        payment_amount=Decimal("200"),
        payment_date=date(2026, 2, 1),
    )
    assert allocation.principal_applied == Decimal("200.00")
    assert allocation.remaining == Decimal("0.00")
