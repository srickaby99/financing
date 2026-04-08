"""Shared data models for credit bureau responses.

These dataclasses are the contract between the CreditBureauClient
implementations and the underwriting service. All implementations
must populate these fields.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class CreditReport:
    borrower_id: uuid.UUID
    credit_score: int
    monthly_income: Decimal
    monthly_debt_obligations: Decimal

    # Optional trade-line detail — not used by the rules engine today
    # but available for logging / future scoring models
    open_accounts: int = 0
    derogatory_marks: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def dti(self) -> Decimal:
        """Debt-to-income ratio."""
        if self.monthly_income <= 0:
            return Decimal("999")
        return self.monthly_debt_obligations / self.monthly_income
