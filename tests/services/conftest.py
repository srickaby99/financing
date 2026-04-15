"""Shared fixtures for service-level tests."""

import hashlib
import uuid
from datetime import date
from decimal import Decimal

import pytest_asyncio

from app.core.security import generate_api_key
from app.models.application import ApplicationStatus, LoanApplication
from app.models.borrower import Borrower
from app.models.loan import Loan, LoanStatus
from app.models.partner import Partner, PartnerProduct
from app.models.product import InterestRateModel, Product, ProductType


@pytest_asyncio.fixture
async def product(db):
    p = Product(
        name="Device Financing",
        product_type=ProductType.DEVICE,
        interest_rate_model=InterestRateModel.FIXED,
        min_term_months=3,
        max_term_months=24,
        min_amount=Decimal("100.00"),
        max_amount=Decimal("2000.00"),
        default_interest_rate=Decimal("0.0999"),
        origination_fee=Decimal("0.00"),
        late_fee_rules={},
        eligibility_rules={"min_credit_score": 580, "max_dti": 0.45},
        is_active=True,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest_asyncio.fixture
async def partner(db):
    raw_key, key_hash = generate_api_key()
    p = Partner(
        name="Test Partner",
        slug=f"test-partner-{uuid.uuid4().hex[:8]}",
        api_key_hash=key_hash,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p, raw_key


@pytest_asyncio.fixture
async def partner_product(db, partner, product):
    p, _ = partner
    pp = PartnerProduct(partner_id=p.id, product_id=product.id, is_active=True)
    db.add(pp)
    await db.commit()
    await db.refresh(pp)
    return pp


@pytest_asyncio.fixture
async def borrower(db):
    ssn = "999887777"
    b = Borrower(
        first_name="Jane",
        last_name="Smith",
        date_of_birth=date(1988, 6, 15),
        ssn_last4=ssn[-4:],
        ssn_hash=hashlib.sha256(ssn.encode()).hexdigest(),
        email=f"jane.smith.{uuid.uuid4().hex[:6]}@example.com",
        address_line1="456 Oak Ave",
        city="Austin",
        state="TX",
        zip_code="78701",
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b


@pytest_asyncio.fixture
async def approved_application(db, borrower, product, partner, partner_product):
    """A fully submitted + approved LoanApplication with an associated Loan."""
    from unittest.mock import AsyncMock, patch

    from app.integrations.credit.models import CreditReport
    from app.schemas.application import ApplicationCreate
    from app.services.application_service import submit_application

    p, _ = partner
    credit_report = CreditReport(
        borrower_id=borrower.id,
        credit_score=720,
        monthly_income=Decimal("4000"),
        monthly_debt_obligations=Decimal("500"),
    )

    with patch("app.services.application_service.get_credit_client") as mock_factory:
        mock_client = AsyncMock()
        mock_client.pull_credit_report.return_value = credit_report
        mock_factory.return_value = mock_client

        result = await submit_application(
            data=ApplicationCreate(
                borrower_id=borrower.id,
                product_id=product.id,
                requested_amount=Decimal("800.00"),
                requested_term_months=12,
            ),
            partner_id=p.id,
            db=db,
        )
    return result
