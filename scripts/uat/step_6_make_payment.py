"""
UAT Step 6 — Make a Payment

Simulates the external payment processor sending a settlement notification.
The system applies the payment to the loan and reduces the outstanding balance.

This is one monthly payment — the loan will remain ACTIVE after this step.

After running, inspect the results:
    -- Loan balance after payment
    SELECT id, status, outstanding_balance, next_due_date
    FROM loans WHERE id = '<loan_id>';

    -- Payment record
    SELECT id, amount, principal_applied, interest_applied, fees_applied, status
    FROM payments WHERE loan_id = '<loan_id>';

    -- Webhook event log
    SELECT id, source, event_type, status, processed_at
    FROM inbound_webhook_events WHERE payment_id = '<payment_id>';

    -- Ledger entry
    SELECT entry_type, debit_account, credit_account, amount
    FROM ledger_entries WHERE loan_id = '<loan_id>';

    -- Audit log
    SELECT entity_type, action, before, after, created_at
    FROM audit_log WHERE entity_id = '<loan_id>' ORDER BY created_at;
"""

import asyncio
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from _shared import field, header, make_engine, make_session_factory, require_state, save_state, sql_hint

from app.models.loan import Loan
from app.schemas.payment import InboundPaymentWebhook
from app.services import payment_service


async def main():
    header("STEP 6 — Make a Payment")

    state = require_state("loan_id")
    loan_id = uuid.UUID(state["loan_id"])

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        # Fetch current loan state before payment
        result = await db.execute(select(Loan).where(Loan.id == loan_id))
        loan = result.scalar_one()

        balance_before = Decimal(str(loan.outstanding_balance))
        rate = Decimal(str(loan.interest_rate))

        # Calculate one monthly payment using the same PMT formula as the system
        from app.domain.loan_calculator import calculate_monthly_payment
        monthly_payment = calculate_monthly_payment(
            principal=Decimal(str(loan.principal)),
            annual_rate=rate,
            term_months=loan.term_months,
        )

        print(f"  Loan ID:           {loan_id}")
        print(f"  Balance before:    ${balance_before:,.2f}")
        print(f"  Payment amount:    ${monthly_payment:,.2f}  (one monthly payment)")
        print()
        print("  Sending payment notification from processor...")
        print()

        event_id = f"uat-evt-{uuid.uuid4().hex[:12]}"
        ref_id   = f"uat-txn-{uuid.uuid4().hex[:8]}"

        data = InboundPaymentWebhook(
            event_id=event_id,
            event_type="payment.settled",
            loan_id=loan_id,
            amount=monthly_payment,
            payment_date=date.today(),
            external_reference_id=ref_id,
        )

        event = await payment_service.receive_payment_webhook(data, source="uat-processor", db=db)

        # Re-fetch loan to get updated balance
        await db.refresh(loan)
        balance_after = Decimal(str(loan.outstanding_balance))

    print("  Payment processed successfully!")
    print()

    print("  Webhook Event")
    print("  " + "-" * 40)
    field("Event ID:",           str(event.id))
    field("External Event ID:",  event.external_event_id)
    field("Source:",             event.source)
    field("Event Type:",         event.event_type)
    field("Status:",             event.status)
    field("Processed At:",       str(event.processed_at))
    field("Payment ID:",         str(event.payment_id))
    print()

    print("  Loan Balance")
    print("  " + "-" * 40)
    field("Balance Before:",     f"${balance_before:,.2f}")
    field("Payment Applied:",    f"${monthly_payment:,.2f}")
    field("Balance After:",      f"${balance_after:,.2f}")
    field("Reduction:",          f"${balance_before - balance_after:,.2f}")
    field("Loan Status:",        loan.status)
    print()

    save_state({
        "payment_event_id": str(event.id),
        "payment_id": str(event.payment_id),
    })

    sql_hint(
        f"SELECT id, amount, principal_applied, interest_applied, fees_applied, status "
        f"FROM payments WHERE loan_id = '{loan_id}';"
    )
    print(f"  Ledger entries:")
    print(f"    SELECT entry_type, debit_account, credit_account, amount")
    print(f"    FROM ledger_entries WHERE loan_id = '{loan_id}' ORDER BY created_at;")
    print()
    print(f"  Audit log:")
    print(f"    SELECT action, before, after, created_at")
    print(f"    FROM audit_log WHERE entity_id = '{loan_id}' ORDER BY created_at;")
    print()

    print("  State saved.  Run step_7_full_payoff.py to pay off the loan.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
