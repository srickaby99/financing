"""
UAT Step 4 — Create Borrower

Registers the customer who will apply for the loan.
Note: the full SSN is hashed before storage — only the last 4 digits
and a SHA-256 hash are persisted. The raw SSN never touches the database.

After running, inspect the result:
    SELECT id, first_name, last_name, email, ssn_last4, state, city
    FROM borrowers WHERE id = '<id>';
"""

import asyncio
from datetime import date

from _shared import field, header, make_engine, make_session_factory, save_state, sql_hint

from app.schemas.borrower import BorrowerCreate
from app.services import borrower_service


async def main():
    header("STEP 4 — Create Borrower")

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        print("  Creating borrower: Jane UAT Smith...")
        print()

        data = BorrowerCreate(
            first_name="Jane",
            last_name="Smith",
            date_of_birth=date(1988, 6, 15),
            ssn="987654321",           # hashed before storage — last 4 stored as "4321"
            email="jane.smith.uat@example.com",
            phone="512-555-0199",
            address_line1="42 Oak Avenue",
            address_line2=None,
            city="Austin",
            state="TX",
            zip_code="78701",
        )

        borrower = await borrower_service.create_borrower(data, db)

    print("  Borrower created successfully!")
    print()
    field("ID:",           str(borrower.id))
    field("Name:",         f"{borrower.first_name} {borrower.last_name}")
    field("Date of Birth:", str(borrower.date_of_birth))
    field("SSN Last 4:",   borrower.ssn_last4)
    field("SSN Hash:",     f"{borrower.ssn_hash[:16]}...  (full SSN never stored)")
    field("Email:",        borrower.email)
    field("Phone:",        borrower.phone or "—")
    field("Address:",      borrower.address_line1)
    field("City/State:",   f"{borrower.city}, {borrower.state} {borrower.zip_code}")

    save_state({"borrower_id": str(borrower.id)})

    sql_hint(f"SELECT id, first_name, last_name, email, ssn_last4, state, city FROM borrowers WHERE id = '{borrower.id}';")

    print("  State saved.  Run step_5_submit_application.py next.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
