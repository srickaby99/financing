"""Pure financial calculation functions.

All functions operate on plain Python Decimals and return plain values.
No database access, no side effects.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class ScheduleRow:
    period: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    balance_after: Decimal


CENTS = Decimal("0.01")


def calculate_monthly_payment(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
) -> Decimal:
    """Standard amortizing monthly payment (PMT formula).

    For zero-interest products returns a simple principal / term_months.
    """
    if annual_rate == 0:
        return (principal / term_months).quantize(CENTS, ROUND_HALF_UP)

    monthly_rate = annual_rate / 12
    # PMT = P * r / (1 - (1 + r)^-n)
    factor = (1 + monthly_rate) ** term_months
    payment = principal * monthly_rate * factor / (factor - 1)
    return payment.quantize(CENTS, ROUND_HALF_UP)


def generate_amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date,
) -> list[ScheduleRow]:
    """Generate a full amortization schedule.

    The first payment is due one month after start_date.
    The final payment is adjusted to zero out any rounding residual.
    """
    from dateutil.relativedelta import relativedelta  # optional dep — add to pyproject if needed

    monthly_payment = calculate_monthly_payment(principal, annual_rate, term_months)
    monthly_rate = annual_rate / 12
    balance = principal
    rows: list[ScheduleRow] = []

    for period in range(1, term_months + 1):
        due_date = start_date + relativedelta(months=period)
        interest_due = (balance * monthly_rate).quantize(CENTS, ROUND_HALF_UP)
        principal_due = monthly_payment - interest_due

        # Last period: clear any rounding residual
        if period == term_months:
            principal_due = balance

        balance_after = (balance - principal_due).quantize(CENTS, ROUND_HALF_UP)
        # Guard against floating-point drift going slightly negative
        balance_after = max(balance_after, Decimal("0"))

        rows.append(
            ScheduleRow(
                period=period,
                due_date=due_date,
                principal_due=principal_due.quantize(CENTS, ROUND_HALF_UP),
                interest_due=interest_due,
                balance_after=balance_after,
            )
        )
        balance = balance_after

    return rows


def calculate_apr(
    principal: Decimal,
    monthly_payment: Decimal,
    term_months: int,
    origination_fee: Decimal,
) -> Decimal:
    """Approximate APR using the Newton-Raphson method on the IRR.

    APR = monthly IRR * 12, where IRR solves:
        principal - origination_fee = sum(monthly_payment / (1 + r)^t for t in 1..n)
    """
    net_proceeds = principal - origination_fee
    if net_proceeds <= 0:
        raise ValueError("Net proceeds must be positive")

    # Initial guess: nominal annual rate
    r = Decimal("0.01")  # 1% monthly starting guess
    for _ in range(100):
        pv = sum(monthly_payment / (1 + r) ** t for t in range(1, term_months + 1))
        # Derivative of PV with respect to r
        dpv = sum(-t * monthly_payment / (1 + r) ** (t + 1) for t in range(1, term_months + 1))
        delta = (pv - net_proceeds) / dpv
        r -= delta
        if abs(delta) < Decimal("1e-8"):
            break

    apr = (r * 12).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    return apr


def calculate_payoff_amount(
    outstanding_balance: Decimal,
    annual_rate: Decimal,
    days_since_last_payment: int,
) -> Decimal:
    """Calculate the total amount needed to pay off a loan today,
    including accrued interest since the last payment.
    """
    daily_rate = annual_rate / 365
    accrued_interest = (outstanding_balance * daily_rate * days_since_last_payment).quantize(
        CENTS, ROUND_HALF_UP
    )
    return outstanding_balance + accrued_interest
