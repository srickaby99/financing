"""Payment processing — applies a settled payment to its loan."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repayment import apply_payment
from app.models.ledger import EntryType, LedgerEntry
from app.models.loan import Loan, LoanStatus
from app.models.payment import InboundWebhookEvent, Payment, PaymentStatus, WebhookStatus

logger = logging.getLogger(__name__)


async def apply_payment_to_loan(webhook_event_id: uuid.UUID, db: AsyncSession) -> None:
    """Apply an inbound webhook payment to its loan and write the ledger entry."""
    result = await db.execute(
        select(InboundWebhookEvent).where(InboundWebhookEvent.id == webhook_event_id)
    )
    event = result.scalar_one_or_none()
    if not event or event.status == WebhookStatus.PROCESSED:
        return

    payload = event.payload
    loan_id = uuid.UUID(str(payload["loan_id"]))
    amount = Decimal(str(payload["amount"]))
    external_ref = payload["external_reference_id"]

    from datetime import date
    payment_date = date.fromisoformat(payload["payment_date"])

    loan_result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = loan_result.scalar_one_or_none()
    if not loan:
        logger.error("Loan %s not found for webhook event %s", loan_id, webhook_event_id)
        event.status = WebhookStatus.FAILED
        await db.commit()
        return

    allocation = apply_payment(
        outstanding_balance=Decimal(str(loan.outstanding_balance)),
        accrued_interest=Decimal("0"),
        outstanding_fees=Decimal("0"),
        payment_amount=amount,
        payment_date=payment_date,
    )

    payment = Payment(
        loan_id=loan.id,
        amount=amount,
        payment_date=payment_date,
        principal_applied=allocation.principal_applied,
        interest_applied=allocation.interest_applied,
        fees_applied=allocation.fees_applied,
        external_reference_id=external_ref,
        status=PaymentStatus.SETTLED,
    )
    db.add(payment)
    await db.flush()

    db.add(LedgerEntry(
        loan_id=loan.id,
        payment_id=payment.id,
        entry_type=EntryType.PAYMENT,
        debit_account="cash",
        credit_account="loans_receivable",
        amount=amount,
    ))

    new_balance = Decimal(str(loan.outstanding_balance)) - allocation.principal_applied
    loan.outstanding_balance = max(new_balance, Decimal("0"))
    if loan.outstanding_balance == 0:
        loan.status = LoanStatus.PAID_OFF
        loan.next_due_date = None

    event.status = WebhookStatus.PROCESSED
    event.processed_at = datetime.now(UTC)
    event.payment_id = payment.id

    from app.services.audit_service import audit
    await audit(
        db,
        entity_type="Loan",
        entity_id=loan.id,
        action="payment_applied",
        before={"outstanding_balance": str(Decimal(str(loan.outstanding_balance)) + allocation.principal_applied)},
        after={"outstanding_balance": str(loan.outstanding_balance), "status": loan.status},
        note=f"Payment {payment.id} — external ref {external_ref}",
    )

    await db.commit()
    logger.info("Payment %s applied to loan %s", payment.id, loan.id)

    from app.tasks.notifications import send_payment_confirmation
    await send_payment_confirmation(str(payment.id))
