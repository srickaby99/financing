"""Abstract credit bureau client interface.

To add a real bureau integration:
1. Create a new module (e.g. app/integrations/credit/experian.py)
2. Subclass CreditBureauClient and implement pull_credit_report()
3. Register the new impl in app/integrations/__init__.py get_credit_client()
"""

from abc import ABC, abstractmethod

from app.integrations.credit.models import CreditReport
from app.models.borrower import Borrower


class CreditBureauClient(ABC):
    @abstractmethod
    async def pull_credit_report(self, borrower: Borrower) -> CreditReport:
        """Fetch or generate a credit report for the given borrower.

        Implementations must never raise on a valid borrower — they should
        return a report with conservative defaults if the bureau is unavailable,
        or raise a clearly typed exception that the service layer can handle.
        """
        ...
