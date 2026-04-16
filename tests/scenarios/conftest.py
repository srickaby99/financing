"""Shared helpers for scenario tests."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

from app.integrations.credit.models import CreditReport


def make_credit_mock(
    credit_score: int = 720,
    monthly_income: str = "5000.00",
    monthly_debt: str = "400.00",
) -> AsyncMock:
    """Return a configured mock credit bureau client.

    Usage:
        with patch("app.services.application_service.get_credit_client") as mock_factory:
            mock_factory.return_value = make_credit_mock(credit_score=720)
            r = await client.post("/api/v1/applications", ...)
    """
    mock = AsyncMock()
    mock.pull_credit_report.return_value = CreditReport(
        borrower_id=uuid.uuid4(),
        credit_score=credit_score,
        monthly_income=Decimal(monthly_income),
        monthly_debt_obligations=Decimal(monthly_debt),
    )
    return mock
