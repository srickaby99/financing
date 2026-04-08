"""Tests for the dummy credit bureau client."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.integrations.credit.dummy import DummyCreditBureauClient


def _make_borrower(ssn_hash: str = "abc123") -> MagicMock:
    borrower = MagicMock()
    borrower.id = uuid.uuid4()
    borrower.ssn_hash = ssn_hash
    return borrower


@pytest.mark.asyncio
async def test_returns_credit_report():
    client = DummyCreditBureauClient()
    borrower = _make_borrower()
    report = await client.pull_credit_report(borrower)
    assert report.borrower_id == borrower.id
    assert 580 <= report.credit_score <= 800


@pytest.mark.asyncio
async def test_score_is_deterministic():
    """Same borrower always gets the same score."""
    client = DummyCreditBureauClient()
    borrower = _make_borrower(ssn_hash="fixed-hash-value")
    r1 = await client.pull_credit_report(borrower)
    r2 = await client.pull_credit_report(borrower)
    assert r1.credit_score == r2.credit_score


@pytest.mark.asyncio
async def test_score_override():
    client = DummyCreditBureauClient(score_override=720)
    report = await client.pull_credit_report(_make_borrower())
    assert report.credit_score == 720


@pytest.mark.asyncio
async def test_custom_income_and_debt():
    client = DummyCreditBureauClient(
        monthly_income=Decimal("5000"),
        monthly_debt=Decimal("800"),
    )
    report = await client.pull_credit_report(_make_borrower())
    assert report.monthly_income == Decimal("5000")
    assert report.monthly_debt_obligations == Decimal("800")


@pytest.mark.asyncio
async def test_dti_computed_correctly():
    client = DummyCreditBureauClient(
        monthly_income=Decimal("4000"),
        monthly_debt=Decimal("1000"),
    )
    report = await client.pull_credit_report(_make_borrower())
    assert report.dti == Decimal("0.25")
