"""
UAT Cleanup

Removes all data created by the UAT steps from the database.
Deletes in reverse dependency order to respect foreign key constraints.

After running, the database is clean and the UAT can be re-run from step 1.
"""

import asyncio
import uuid

from sqlalchemy import delete, select

from _shared import clear_state, header, load_state, make_engine, make_session_factory

from app.models.audit import AuditLog
from app.models.ledger import LedgerEntry
from app.models.loan import Loan, RepaymentScheduleEntry
from app.models.application import LoanApplication
from app.models.payment import InboundWebhookEvent, Payment
from app.models.borrower import Borrower, PaymentMethod
from app.models.partner import Partner, PartnerProduct
from app.models.product import Product


async def main():
    header("UAT Cleanup")

    state = load_state()

    if not state:
        print("  Nothing to clean up — uat_state.json is empty or missing.")
        print()
        return

    print("  IDs to clean up:")
    for key, val in state.items():
        print(f"    {key}: {val}")
    print()

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:

        # --- Audit log (no FK — just string entity_id references) ---
        if "loan_id" in state:
            n = await _delete(db, AuditLog, AuditLog.entity_id == state["loan_id"])
            print(f"  Deleted {n} audit_log rows for loan")

        if "application_id" in state:
            n = await _delete(db, AuditLog, AuditLog.entity_id == state["application_id"])
            print(f"  Deleted {n} audit_log rows for application")

        # --- Ledger entries ---
        if "loan_id" in state:
            loan_id = uuid.UUID(state["loan_id"])
            n = await _delete(db, LedgerEntry, LedgerEntry.loan_id == loan_id)
            print(f"  Deleted {n} ledger_entries")

        # --- Inbound webhook events ---
        if "payment_id" in state:
            payment_id = uuid.UUID(state["payment_id"])
            n = await _delete(db, InboundWebhookEvent, InboundWebhookEvent.payment_id == payment_id)
            print(f"  Deleted {n} inbound_webhook_events (first payment)")

        # Also clean up any other events for this loan (payoff payment etc.)
        if "loan_id" in state:
            loan_uuid = uuid.UUID(state["loan_id"])
            # Find all payment IDs for this loan
            result = await db.execute(select(Payment.id).where(Payment.loan_id == loan_uuid))
            payment_ids = [row[0] for row in result.all()]
            if payment_ids:
                for pid in payment_ids:
                    n = await _delete(db, InboundWebhookEvent, InboundWebhookEvent.payment_id == pid)
                    if n:
                        print(f"  Deleted {n} inbound_webhook_events for payment {pid}")

        # --- Payments ---
        if "loan_id" in state:
            n = await _delete(db, Payment, Payment.loan_id == uuid.UUID(state["loan_id"]))
            print(f"  Deleted {n} payments")

        # --- Repayment schedule ---
        if "loan_id" in state:
            n = await _delete(db, RepaymentScheduleEntry, RepaymentScheduleEntry.loan_id == uuid.UUID(state["loan_id"]))
            print(f"  Deleted {n} repayment_schedule_entries")

        # --- Loan ---
        if "loan_id" in state:
            n = await _delete(db, Loan, Loan.id == uuid.UUID(state["loan_id"]))
            print(f"  Deleted {n} loan")

        # --- Loan application ---
        if "application_id" in state:
            n = await _delete(db, LoanApplication, LoanApplication.id == uuid.UUID(state["application_id"]))
            print(f"  Deleted {n} loan_application")

        # --- Payment methods ---
        if "borrower_id" in state:
            n = await _delete(db, PaymentMethod, PaymentMethod.borrower_id == uuid.UUID(state["borrower_id"]))
            print(f"  Deleted {n} payment_methods")

        # --- Borrower ---
        if "borrower_id" in state:
            n = await _delete(db, Borrower, Borrower.id == uuid.UUID(state["borrower_id"]))
            print(f"  Deleted {n} borrower")

        # --- Partner products ---
        if "partner_product_id" in state:
            n = await _delete(db, PartnerProduct, PartnerProduct.id == uuid.UUID(state["partner_product_id"]))
            print(f"  Deleted {n} partner_product")

        # --- Partner ---
        if "partner_id" in state:
            n = await _delete(db, Partner, Partner.id == uuid.UUID(state["partner_id"]))
            print(f"  Deleted {n} partner")

        # --- Product ---
        if "product_id" in state:
            n = await _delete(db, Product, Product.id == uuid.UUID(state["product_id"]))
            print(f"  Deleted {n} product")

        await db.commit()

    clear_state()

    print()
    print("  Database clean. State file cleared.")
    print("  You can now re-run the UAT from step_1_create_product.py.")
    print()

    await engine.dispose()


async def _delete(db, model, condition) -> int:
    result = await db.execute(delete(model).where(condition))
    return result.rowcount


if __name__ == "__main__":
    asyncio.run(main())
