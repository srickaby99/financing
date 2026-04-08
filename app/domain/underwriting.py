"""Underwriting rules engine.

Pure functions — no I/O. Evaluates a credit report and application
against a product's eligibility_rules JSONB and returns a decision.

eligibility_rules schema (all keys optional):
    {
        "min_credit_score": int,        # e.g. 600
        "max_dti": float,               # e.g. 0.45 (45%)
        "min_monthly_income": float,    # e.g. 1500.00
        "allowed_states": [str],        # e.g. ["CA", "TX", "NY"]
        "max_amount": float,            # product-level cap (also enforced by Product model)
    }
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class UnderwritingDecision:
    approved: bool
    decline_reasons: list[str] = field(default_factory=list)

    # Populated on approval
    approved_amount: Decimal | None = None
    approved_rate: Decimal | None = None
    approved_term_months: int | None = None
    monthly_payment: Decimal | None = None

    # Metrics included for audit / record-keeping
    credit_score: int | None = None
    dti: Decimal | None = None


def evaluate_application(
    credit_score: int,
    monthly_income: Decimal,
    monthly_debt_obligations: Decimal,
    requested_amount: Decimal,
    requested_term_months: int,
    borrower_state: str,
    eligibility_rules: dict,
    effective_rate: Decimal,
    effective_origination_fee: Decimal,
) -> UnderwritingDecision:
    """Evaluate a loan application against product eligibility rules.

    Args:
        credit_score: Borrower credit score from credit bureau.
        monthly_income: Borrower gross monthly income.
        monthly_debt_obligations: Borrower existing monthly debt payments.
        requested_amount: Amount the borrower is requesting.
        requested_term_months: Term length in months.
        borrower_state: Two-letter state code from the borrower's address.
        eligibility_rules: Product.eligibility_rules JSONB dict.
        effective_rate: Annual interest rate (may be overridden by PartnerProduct).
        effective_origination_fee: Origination fee (may be overridden by PartnerProduct).

    Returns:
        UnderwritingDecision with approved=True/False and details.
    """
    from app.domain.loan_calculator import calculate_monthly_payment

    decline_reasons: list[str] = []
    dti = (
        (monthly_debt_obligations / monthly_income)
        if monthly_income > 0
        else Decimal("999")
    )

    # --- Rule evaluation ---

    min_score = eligibility_rules.get("min_credit_score")
    if min_score is not None and credit_score < min_score:
        decline_reasons.append(f"credit_score_below_minimum ({credit_score} < {min_score})")

    max_dti = eligibility_rules.get("max_dti")
    if max_dti is not None and dti > Decimal(str(max_dti)):
        decline_reasons.append(f"dti_exceeds_maximum ({dti:.2f} > {max_dti})")

    min_income = eligibility_rules.get("min_monthly_income")
    if min_income is not None and monthly_income < Decimal(str(min_income)):
        decline_reasons.append(f"monthly_income_below_minimum ({monthly_income} < {min_income})")

    allowed_states = eligibility_rules.get("allowed_states")
    if allowed_states and borrower_state not in allowed_states:
        decline_reasons.append(f"state_not_eligible ({borrower_state})")

    rule_max_amount = eligibility_rules.get("max_amount")
    if rule_max_amount is not None and requested_amount > Decimal(str(rule_max_amount)):
        decline_reasons.append(
            f"requested_amount_exceeds_maximum ({requested_amount} > {rule_max_amount})"
        )

    if decline_reasons:
        return UnderwritingDecision(
            approved=False,
            decline_reasons=decline_reasons,
            credit_score=credit_score,
            dti=dti,
        )

    # --- Approved ---
    monthly_payment = calculate_monthly_payment(requested_amount, effective_rate, requested_term_months)

    return UnderwritingDecision(
        approved=True,
        approved_amount=requested_amount,
        approved_rate=effective_rate,
        approved_term_months=requested_term_months,
        monthly_payment=monthly_payment,
        credit_score=credit_score,
        dti=dti,
    )
