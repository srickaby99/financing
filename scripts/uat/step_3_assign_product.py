"""
UAT Step 3 — Assign Product to Partner

Authorizes the partner to offer the device financing product.
Until this step, the partner cannot submit applications for this product.

After running, inspect the result:
    SELECT pp.id, pa.name as partner, pr.name as product, pp.is_active,
           pp.rate_override, pp.origination_fee_override
    FROM partner_products pp
    JOIN partners pa ON pa.id = pp.partner_id
    JOIN products pr ON pr.id = pp.product_id
    WHERE pa.slug = 'uat-partner';
"""

import asyncio
import uuid

from _shared import field, header, make_engine, make_session_factory, require_state, save_state, sql_hint

from app.schemas.partner import PartnerProductAssign
from app.services import partner_service


async def main():
    header("STEP 3 — Assign Product to Partner")

    state = require_state("partner_id", "product_id")
    partner_id = uuid.UUID(state["partner_id"])
    product_id = uuid.UUID(state["product_id"])

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        print(f"  Assigning product to partner...")
        print()
        print(f"  Partner ID:  {partner_id}")
        print(f"  Product ID:  {product_id}")
        print()

        data = PartnerProductAssign(
            product_id=product_id,
            rate_override=None,           # use product defaults
            origination_fee_override=None,
        )

        assignment = await partner_service.assign_product(partner_id, data, db)

    print("  Assignment created successfully!")
    print()
    field("Assignment ID:",           str(assignment.id))
    field("Partner ID:",              str(assignment.partner_id))
    field("Product ID:",              str(assignment.product_id))
    field("Active:",                  "Yes" if assignment.is_active else "No")
    field("Rate Override:",           str(assignment.rate_override) if assignment.rate_override else "None (uses product default)")
    field("Fee Override:",            str(assignment.origination_fee_override) if assignment.origination_fee_override else "None (uses product default)")

    save_state({"partner_product_id": str(assignment.id)})

    sql_hint(
        f"SELECT pp.id, pa.name AS partner, pr.name AS product, pp.is_active "
        f"FROM partner_products pp "
        f"JOIN partners pa ON pa.id = pp.partner_id "
        f"JOIN products pr ON pr.id = pp.product_id "
        f"WHERE pp.id = '{assignment.id}';"
    )

    print("  State saved.  Run step_4_create_borrower.py next.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
