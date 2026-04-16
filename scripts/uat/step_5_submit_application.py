"""
UAT Step 5 — Submit Loan Application

Submits a loan application on behalf of the borrower.
The system runs underwriting immediately and returns an instant decision.

If approved, a Loan is originated and a full repayment schedule is generated.

After running, inspect the results:
    -- Application
    SELECT id, status, requested_amount, decided_at
    FROM loan_applications WHERE id = '<id>';

    -- Loan
    SELECT id, status, principal, outstanding_balance, interest_rate, next_due_date
    FROM loans WHERE id = '<loan_id>';

    -- Repayment schedule (first 3 periods)
    SELECT period, due_date, principal_due, interest_due, balance_after
    FROM repayment_schedule_entries WHERE loan_id = '<loan_id>'
    ORDER BY period LIMIT 3;
"""

import asyncio
import uuid
from decimal import Decimal

from _shared import field, header, make_engine, make_session_factory, require_state, save_state, sql_hint

from app.schemas.application import ApplicationCreate
from app.services import application_service


async def main():
    header("STEP 5 — Submit Loan Application")

    state = require_state("borrower_id", "product_id", "partner_id")
    borrower_id = uuid.UUID(state["borrower_id"])
    product_id  = uuid.UUID(state["product_id"])
    partner_id  = uuid.UUID(state["partner_id"])

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        print(f"  Borrower:   {borrower_id}")
        print(f"  Product:    {product_id}")
        print(f"  Partner:    {partner_id}")
        print(f"  Amount:     $800.00  |  Term: 12 months")
        print()
        print("  Running underwriting (credit pull + rules engine)...")
        print()

        data = ApplicationCreate(
            borrower_id=borrower_id,
            product_id=product_id,
            requested_amount=Decimal("800.00"),
            requested_term_months=12,
        )

        result = await application_service.submit_application(data, partner_id, db)

    uw = result.underwriting_result

    print(f"  Decision: {'APPROVED' if uw.approved else 'DECLINED'}")
    print()

    # Application details
    print("  Application")
    print("  " + "-" * 40)
    field("ID:",                   str(result.id))
    field("Status:",               result.status)
    field("Requested Amount:",     f"${result.requested_amount:,.2f}")
    field("Requested Term:",       f"{result.requested_term_months} months")
    field("Decided At:",           str(result.decided_at))
    print()

    # Underwriting result
    print("  Underwriting Result")
    print("  " + "-" * 40)
    field("Approved:",             str(uw.approved))
    field("Credit Score:",         str(uw.credit_score))
    field("DTI:",                  f"{float(uw.dti):.2%}" if uw.dti else "—")
    if uw.approved:
        field("Approved Amount:",  f"${uw.approved_amount:,.2f}")
        field("Approved Rate:",    f"{float(uw.approved_rate) * 100:.2f}%")
        field("Approved Term:",    f"{uw.approved_term_months} months")
        field("Monthly Payment:",  f"${uw.monthly_payment:,.2f}")
    else:
        field("Decline Reasons:",  ", ".join(uw.decline_reasons))
    print()

    state_update = {"application_id": str(result.id)}

    if result.loan_id:
        state_update["loan_id"] = str(result.loan_id)
        print("  Loan originated successfully!")
        print()
        field("Loan ID:", str(result.loan_id))
        print()

        sql_hint(
            f"SELECT id, status, principal, outstanding_balance, interest_rate, next_due_date "
            f"FROM loans WHERE id = '{result.loan_id}';"
        )
        print(f"  Repayment schedule (first 3 periods):")
        print(
            f"    SELECT period, due_date, principal_due, interest_due, balance_after "
            f"FROM repayment_schedule_entries "
            f"WHERE loan_id = '{result.loan_id}' ORDER BY period LIMIT 3;"
        )
        print()
    else:
        print("  No loan was originated (application was declined).")
        print()
        sql_hint(
            f"SELECT id, status, underwriting_result "
            f"FROM loan_applications WHERE id = '{result.id}';"
        )

    save_state(state_update)

    print("  State saved.  Run step_6_make_payment.py next.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
