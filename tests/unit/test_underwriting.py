"""Unit tests for the underwriting rules engine."""

from decimal import Decimal

import pytest

from app.domain.underwriting import evaluate_application


BASE_ARGS = dict(
    credit_score=700,
    monthly_income=Decimal("4000"),
    monthly_debt_obligations=Decimal("500"),
    requested_amount=Decimal("800"),
    requested_term_months=12,
    borrower_state="CA",
    eligibility_rules={
        "min_credit_score": 600,
        "max_dti": 0.45,
        "min_monthly_income": 1500,
    },
    effective_rate=Decimal("0.0999"),
    effective_origination_fee=Decimal("0"),
)


def test_approved_when_all_rules_pass():
    decision = evaluate_application(**BASE_ARGS)
    assert decision.approved is True
    assert decision.decline_reasons == []
    assert decision.approved_amount == Decimal("800")
    assert decision.monthly_payment is not None


def test_declined_low_credit_score():
    args = {**BASE_ARGS, "credit_score": 550}
    decision = evaluate_application(**args)
    assert decision.approved is False
    assert any("credit_score" in r for r in decision.decline_reasons)


def test_declined_high_dti():
    args = {**BASE_ARGS, "monthly_debt_obligations": Decimal("2000")}
    decision = evaluate_application(**args)
    assert decision.approved is False
    assert any("dti" in r for r in decision.decline_reasons)


def test_declined_low_income():
    args = {**BASE_ARGS, "monthly_income": Decimal("1000")}
    decision = evaluate_application(**args)
    assert decision.approved is False
    assert any("income" in r for r in decision.decline_reasons)


def test_declined_state_not_allowed():
    args = {**BASE_ARGS, "eligibility_rules": {**BASE_ARGS["eligibility_rules"], "allowed_states": ["TX"]}}
    decision = evaluate_application(**args)
    assert decision.approved is False
    assert any("state" in r for r in decision.decline_reasons)


def test_multiple_decline_reasons():
    args = {
        **BASE_ARGS,
        "credit_score": 500,
        "monthly_debt_obligations": Decimal("3000"),
    }
    decision = evaluate_application(**args)
    assert decision.approved is False
    assert len(decision.decline_reasons) >= 2


def test_no_eligibility_rules_approves_all():
    """Empty rules dict means no restrictions — any application passes."""
    args = {**BASE_ARGS, "eligibility_rules": {}}
    decision = evaluate_application(**args)
    assert decision.approved is True


def test_approved_decision_includes_metrics():
    decision = evaluate_application(**BASE_ARGS)
    assert decision.credit_score == 700
    assert decision.dti is not None
