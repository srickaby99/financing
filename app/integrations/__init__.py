"""Integration factory functions.

Swap implementations by changing CREDIT_BUREAU_IMPL in .env.
"""

from functools import lru_cache

from app.core.config import settings
from app.integrations.credit.base import CreditBureauClient


@lru_cache(maxsize=1)
def get_credit_client() -> CreditBureauClient:
    impl = settings.CREDIT_BUREAU_IMPL.lower()
    if impl == "dummy":
        from app.integrations.credit.dummy import DummyCreditBureauClient
        return DummyCreditBureauClient()
    raise ValueError(f"Unknown CREDIT_BUREAU_IMPL: {impl!r}. Valid options: 'dummy'")
