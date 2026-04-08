# Re-export all models so Alembic autogenerate can detect them
from app.models.audit import ActorType, AuditLog
from app.models.application import ApplicationStatus, LoanApplication
from app.models.borrower import Borrower, PaymentMethod, PaymentMethodStatus, PaymentMethodType
from app.models.ledger import EntryType, LedgerEntry
from app.models.loan import Loan, LoanStatus, RepaymentScheduleEntry
from app.models.partner import Partner, PartnerProduct, PartnerStatus
from app.models.payment import InboundWebhookEvent, Payment, PaymentStatus, WebhookStatus
from app.models.product import InterestRateModel, Product, ProductType

__all__ = [
    "AuditLog",
    "ActorType",
    "Product",
    "ProductType",
    "InterestRateModel",
    "Partner",
    "PartnerStatus",
    "PartnerProduct",
    "Borrower",
    "PaymentMethod",
    "PaymentMethodType",
    "PaymentMethodStatus",
    "LoanApplication",
    "ApplicationStatus",
    "Loan",
    "LoanStatus",
    "RepaymentScheduleEntry",
    "Payment",
    "PaymentStatus",
    "InboundWebhookEvent",
    "WebhookStatus",
    "LedgerEntry",
    "EntryType",
]
