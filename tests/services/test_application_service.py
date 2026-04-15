"""Tests for application_service — the core loan origination flow."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.integrations.credit.models import CreditReport
from app.models.application import ApplicationStatus
from app.schemas.application import ApplicationCreate
from app.services import application_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_credit_report(borrower_id, score=720, income=Decimal("4000"), debt=Decimal("500")):
    return CreditReport(
        borrower_id=borrower_id,
        credit_score=score,
        monthly_income=income,
        monthly_debt_obligations=debt,
    )


def _patch_credit_client(report: CreditReport):
    mock_client = AsyncMock()
    mock_client.pull_credit_report.return_value = report
    mock_factory = patch("app.services.application_service.get_credit_client", return_value=mock_client)
    return mock_factory


def _app_data(borrower_id, product_id, amount="800.00", term=12) -> ApplicationCreate:
    return ApplicationCreate(
        borrower_id=borrower_id,
        product_id=product_id,
        requested_amount=Decimal(amount),
        requested_term_months=term,
    )


# ---------------------------------------------------------------------------
# submit_application — approved path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_application_approved(db, borrower, product, partner, partner_product):
    """(+) Good credit score + valid product returns APPROVED with a loan_id."""
    p, _ = partner
    report = _mock_credit_report(borrower.id)

    with _patch_credit_client(report):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.status == ApplicationStatus.APPROVED
    assert result.loan_id is not None


@pytest.mark.asyncio
async def test_submit_application_approved_returns_monthly_payment(db, borrower, product, partner, partner_product):
    """(+) Approved response includes monthly_payment in underwriting_result."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id)):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.underwriting_result.monthly_payment is not None
    assert result.underwriting_result.monthly_payment > 0


@pytest.mark.asyncio
async def test_submit_application_approved_records_credit_score(db, borrower, product, partner, partner_product):
    """(+) Underwriting result captures credit score."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id, score=710)):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.underwriting_result.credit_score == 710


# ---------------------------------------------------------------------------
# submit_application — declined path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_application_declined_low_credit(db, borrower, product, partner, partner_product):
    """(-) Credit score below minimum returns DECLINED with a reason."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id, score=400)):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.status == ApplicationStatus.DECLINED
    assert result.loan_id is None
    assert len(result.underwriting_result.decline_reasons) > 0


@pytest.mark.asyncio
async def test_submit_application_declined_high_dti(db, borrower, product, partner, partner_product):
    """(-) Debt-to-income ratio above max returns DECLINED."""
    p, _ = partner
    report = _mock_credit_report(borrower.id, income=Decimal("2000"), debt=Decimal("1500"))

    with _patch_credit_client(report):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.status == ApplicationStatus.DECLINED
    assert any("dti" in r for r in result.underwriting_result.decline_reasons)


@pytest.mark.asyncio
async def test_submit_application_declined_has_no_loan(db, borrower, product, partner, partner_product):
    """(-) Declined applications do not originate a loan."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id, score=300)):
        result = await application_service.submit_application(
            _app_data(borrower.id, product.id), p.id, db
        )

    assert result.loan_id is None


# ---------------------------------------------------------------------------
# submit_application — validation failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_application_raises_422_amount_too_high(db, borrower, product, partner, partner_product):
    """(-) Requested amount above product maximum raises 422."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id)):
        with pytest.raises(HTTPException) as exc:
            await application_service.submit_application(
                _app_data(borrower.id, product.id, amount="99999.00"), p.id, db
            )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_submit_application_raises_422_amount_too_low(db, borrower, product, partner, partner_product):
    """(-) Requested amount below product minimum raises 422."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id)):
        with pytest.raises(HTTPException) as exc:
            await application_service.submit_application(
                _app_data(borrower.id, product.id, amount="0.01"), p.id, db
            )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_submit_application_raises_404_for_unknown_borrower(db, product, partner, partner_product):
    """(-) Unknown borrower ID raises 404."""
    p, _ = partner
    with _patch_credit_client(CreditReport(
        borrower_id=uuid.uuid4(), credit_score=720,
        monthly_income=Decimal("4000"), monthly_debt_obligations=Decimal("500")
    )):
        with pytest.raises(HTTPException) as exc:
            await application_service.submit_application(
                _app_data(uuid.uuid4(), product.id), p.id, db
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_application_raises_403_partner_not_authorized(db, borrower, product, partner):
    """(-) Partner not assigned to product raises 403 (no partner_product fixture)."""
    p, _ = partner
    with _patch_credit_client(_mock_credit_report(borrower.id)):
        with pytest.raises(HTTPException) as exc:
            await application_service.submit_application(
                _app_data(borrower.id, product.id), p.id, db
            )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# get_application
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_application_returns_existing(db, approved_application):
    """(+) Retrieves an existing application by ID."""
    from sqlalchemy import select
    from app.models.application import LoanApplication

    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == approved_application.id)
    )
    app = result.scalar_one()
    fetched = await application_service.get_application(app.id, db)
    assert fetched.id == app.id


@pytest.mark.asyncio
async def test_get_application_raises_404_for_unknown_id(db):
    """(-) Unknown application ID raises 404."""
    with pytest.raises(HTTPException) as exc:
        await application_service.get_application(uuid.uuid4(), db)
    assert exc.value.status_code == 404
