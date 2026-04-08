"""Payment allocation logic.

Determines how an incoming payment amount is split across
interest, principal, and fees for a given loan.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


@dataclass
class PaymentAllocation:
    interest_applied: Decimal
    principal_applied: Decimal
    fees_applied: Decimal
    remaining: Decimal  # unallocated surplus (overpayment)


def apply_payment(
    outstanding_balance: Decimal,
    accrued_interest: Decimal,
    outstanding_fees: Decimal,
    payment_amount: Decimal,
    payment_date: date,  # reserved for future per-diem interest accrual
) -> PaymentAllocation:
    """Allocate a payment using standard waterfall order: fees → interest → principal.

    Returns a PaymentAllocation describing how the amount was applied.
    Any surplus beyond the full payoff is returned as `remaining`.
    """
    remaining = payment_amount

    # 1. Fees first
    fees_applied = min(outstanding_fees, remaining).quantize(CENTS, ROUND_HALF_UP)
    remaining -= fees_applied

    # 2. Accrued interest
    interest_applied = min(accrued_interest, remaining).quantize(CENTS, ROUND_HALF_UP)
    remaining -= interest_applied

    # 3. Principal
    principal_applied = min(outstanding_balance, remaining).quantize(CENTS, ROUND_HALF_UP)
    remaining -= principal_applied

    return PaymentAllocation(
        interest_applied=interest_applied,
        principal_applied=principal_applied,
        fees_applied=fees_applied,
        remaining=remaining.quantize(CENTS, ROUND_HALF_UP),
    )
