"""
UAT Step 2 — Create Partner

Creates a partner (a business that will offer the product to customers).
The API key is displayed ONCE here — it is never stored in plain text.

After running, inspect the result:
    SELECT id, name, slug, status FROM partners WHERE slug = 'uat-partner';
"""

import asyncio

from _shared import field, header, load_state, make_engine, make_session_factory, save_state, sql_hint

from app.schemas.partner import PartnerCreate
from app.services import partner_service


async def main():
    header("STEP 2 — Create Partner")

    # Warn if a partner was already created in a previous run
    existing = load_state()
    if "partner_id" in existing:
        print(f"  WARNING: A partner was already created in a previous UAT run.")
        print(f"  partner_id = {existing['partner_id']}")
        print(f"  Run cleanup.py first if you want to start fresh.")
        print()

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        print("  Creating partner: UAT Partner...")
        print()

        data = PartnerCreate(
            name="UAT Partner",
            slug="uat-partner",
        )

        partner, raw_api_key = await partner_service.create_partner(data, db)

    print("  Partner created successfully!")
    print()
    field("ID:",       str(partner.id))
    field("Name:",     partner.name)
    field("Slug:",     partner.slug)
    field("Status:",   partner.status)
    print()
    print("  API Key (shown once — not stored in plain text):")
    print(f"    {raw_api_key}")
    print()
    print("  NOTE: Save this key — it cannot be retrieved again.")

    save_state({
        "partner_id": str(partner.id),
        "api_key": raw_api_key,
    })

    sql_hint(f"SELECT id, name, slug, status FROM partners WHERE id = '{partner.id}';")

    print("  State saved.  Run step_3_assign_product.py next.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
