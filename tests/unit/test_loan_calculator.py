"""Unit tests for pure loan calculation functions."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.loan_calculator import (
    calculate_monthly_payment,
    calculate_payoff_amount,
    generate_amortization_schedule,
)


def test_monthly_payment_standard():
    """$1,000 at 12% annual over 12 months ≈ $88.85."""
    payment = calculate_monthly_payment(
        principal=Decimal("1000"),
        annual_rate=Decimal("0.12"),
        term_months=12,
    )
    assert payment == Decimal("88.85")


def test_monthly_payment_zero_interest():
    """Zero-interest: payment = principal / term."""
    payment = calculate_monthly_payment(
        principal=Decimal("600"),
        annual_rate=Decimal("0"),
        term_months=12,
    )
    assert payment == Decimal("50.00")


def test_amortization_schedule_length():
    schedule = generate_amortization_schedule(
        principal=Decimal("1000"),
        annual_rate=Decimal("0.12"),
        term_months=12,
        start_date=date(2026, 1, 1),
    )
    assert len(schedule) == 12


def test_amortization_schedule_final_balance_zero():
    """Final balance must be zero (or negligible rounding)."""
    schedule = generate_amortization_schedule(
        principal=Decimal("1200"),
        annual_rate=Decimal("0.09"),
        term_months=24,
        start_date=date(2026, 1, 1),
    )
    assert schedule[-1].balance_after == Decimal("0.00")


def test_amortization_schedule_periods_are_sequential():
    schedule = generate_amortization_schedule(
        principal=Decimal("500"),
        annual_rate=Decimal("0.10"),
        term_months=6,
        start_date=date(2026, 1, 1),
    )
    assert [row.period for row in schedule] == list(range(1, 7))


def test_amortization_interest_decreases_over_time():
    """Each period's interest_due should be <= prior period (declining balance)."""
    schedule = generate_amortization_schedule(
        principal=Decimal("2000"),
        annual_rate=Decimal("0.15"),
        term_months=12,
        start_date=date(2026, 1, 1),
    )
    interests = [row.interest_due for row in schedule]
    assert interests == sorted(interests, reverse=True)


def test_payoff_amount_no_days():
    """Zero days elapsed — payoff equals outstanding balance."""
    payoff = calculate_payoff_amount(
        outstanding_balance=Decimal("500"),
        annual_rate=Decimal("0.12"),
        days_since_last_payment=0,
    )
    assert payoff == Decimal("500.00")


def test_payoff_amount_accrues_interest():
    """30 days of interest on $1200 at 12% annual ≈ $11.84."""
    payoff = calculate_payoff_amount(
        outstanding_balance=Decimal("1200"),
        annual_rate=Decimal("0.12"),
        days_since_last_payment=30,
    )
    assert payoff > Decimal("1200")
