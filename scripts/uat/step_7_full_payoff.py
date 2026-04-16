"""
UAT Step 7 — Full Loan Payoff

Sends a final payment for the exact remaining balance.
The loan status transitions to PAID_OFF and next_due_date is cleared.

After running, inspect the final state:
    -- Loan should be PAID_OFF with zero balance
    SELECT id, status, outstanding_balance, next_due_date
    FROM loans WHERE id = '<loan_id>';

    -- All payments on this loan
    SELECT id, amount, principal_applied, status, payment_date
    FROM payments WHERE loan_id = '<loan_id>' ORDER BY payment_date;

    -- Complete ledger history
    SELECT entry_type, debit_account, credit_account, amount, created_at
    FROM ledger_entries WHERE loan_id = '<loan_id>' ORDER BY created_at;

    -- Full audit trail
    SELECT action, actor_type, before, after, created_at
    FROM audit_log WHERE entity_id = '<loan_id>' ORDER BY created_at;
"""

import asyncio
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from _shared import field, header, make_engine, make_session_factory, require_state, sql_hint

from app.models.loan import Loan
from app.schemas.payment import InboundPaymentWebhook
from app.services import payment_service


async def main():
    header("STEP 7 — Full Loan Payoff")

    state = require_state("loan_id")
    loan_id = uuid.UUID(state["loan_id"])

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        # Fetch current outstanding balance
        result = await db.execute(select(Loan).where(Loan.id == loan_id))
        loan = result.scalar_one()

        remaining = Decimal(str(loan.outstanding_balance))

        if remaining == Decimal("0"):
            print("  Loan is already fully paid off. Nothing to do.")
            await engine.dispose()
            return

        print(f"  Loan ID:             {loan_id}")
        print(f"  Remaining balance:   ${remaining:,.2f}")
        print()
        print("  Sending final payment to clear the balance...")
        print()

        event_id = f"uat-payoff-{uuid.uuid4().hex[:12]}"
        ref_id   = f"uat-txn-{uuid.uuid4().hex[:8]}"

        data = InboundPaymentWebhook(
            event_id=event_id,
            event_type="payment.settled",
            loan_id=loan_id,
            amount=remaining,
            payment_date=date.today(),
            external_reference_id=ref_id,
        )

        event = await payment_service.receive_payment_webhook(data, source="uat-processor", db=db)

        await db.refresh(loan)

    print("  Final payment processed!")
    print()

    print("  Final Loan State")
    print("  " + "-" * 40)
    field("Loan ID:",            str(loan.id))
    field("Status:",             loan.status)
    field("Outstanding Balance:", f"${Decimal(str(loan.outstanding_balance)):,.2f}")
    field("Next Due Date:",      str(loan.next_due_date) if loan.next_due_date else "None (loan closed)")
    field("Origination Date:",   str(loan.origination_date))
    field("Maturity Date:",      str(loan.maturity_date))
    print()

    if loan.status == "PAID_OFF":
        print("  Loan is PAID_OFF.")
    else:
        print(f"  WARNING: Expected PAID_OFF but got {loan.status}.")
    print()

    sql_hint(f"SELECT id, status, outstanding_balance, next_due_date FROM loans WHERE id = '{loan_id}';")

    print(f"  Full payment history:")
    print(f"    SELECT id, amount, principal_applied, status, payment_date")
    print(f"    FROM payments WHERE loan_id = '{loan_id}' ORDER BY payment_date;")
    print()
    print(f"  Complete ledger:")
    print(f"    SELECT entry_type, debit_account, credit_account, amount, created_at")
    print(f"    FROM ledger_entries WHERE loan_id = '{loan_id}' ORDER BY created_at;")
    print()
    print(f"  Audit trail:")
    print(f"    SELECT action, actor_type, before, after, created_at")
    print(f"    FROM audit_log WHERE entity_id = '{loan_id}' ORDER BY created_at;")
    print()

    print("  UAT complete! Run cleanup.py when you are ready to reset.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
