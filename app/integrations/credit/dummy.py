"""Dummy credit bureau client for development and testing.

Generates deterministic credit reports based on borrower data so that
the same borrower always receives the same score — making test scenarios
reproducible without a real bureau integration.

Score generation rules:
- Base score derived from a hash of the borrower's SSN hash (stable per borrower)
- Score range: 580–800
- Monthly income: configurable default (DEFAULT_MONTHLY_INCOME)
- Monthly debt: configurable default (DEFAULT_MONTHLY_DEBT)

To simulate specific scenarios in tests, override the defaults by
instantiating DummyCreditBureauClient with explicit values.
"""

import hashlib
from decimal import Decimal

from app.integrations.credit.base import CreditBureauClient
from app.integrations.credit.models import CreditReport
from app.models.borrower import Borrower

DEFAULT_MONTHLY_INCOME = Decimal("4000.00")
DEFAULT_MONTHLY_DEBT = Decimal("500.00")

_SCORE_MIN = 580
_SCORE_RANGE = 221  # 580–800 inclusive


class DummyCreditBureauClient(CreditBureauClient):
    def __init__(
        self,
        monthly_income: Decimal = DEFAULT_MONTHLY_INCOME,
        monthly_debt: Decimal = DEFAULT_MONTHLY_DEBT,
        score_override: int | None = None,
    ) -> None:
        self._monthly_income = monthly_income
        self._monthly_debt = monthly_debt
        self._score_override = score_override

    async def pull_credit_report(self, borrower: Borrower) -> CreditReport:
        score = self._score_override if self._score_override is not None else self._derive_score(borrower)
        return CreditReport(
            borrower_id=borrower.id,
            credit_score=score,
            monthly_income=self._monthly_income,
            monthly_debt_obligations=self._monthly_debt,
        )

    @staticmethod
    def _derive_score(borrower: Borrower) -> int:
        """Deterministic score from borrower's SSN hash.

        Same borrower → same score across restarts and test runs.
        """
        digest = hashlib.sha256(borrower.ssn_hash.encode()).digest()
        # Use first 2 bytes as a 0–65535 integer, map to score range
        raw = int.from_bytes(digest[:2], "big")
        return _SCORE_MIN + (raw % _SCORE_RANGE)
