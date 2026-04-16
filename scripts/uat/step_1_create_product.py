"""
UAT Step 1 — Create Product

Creates a financing product that defines the rules for a device loan.
This is an admin operation — partners cannot create products.

After running, inspect the result:
    SELECT * FROM products WHERE name = 'UAT Device Financing';
"""

import asyncio
from decimal import Decimal

from _shared import field, header, make_engine, make_session_factory, save_state, sql_hint

from app.schemas.product import ProductCreate
from app.services import product_service


async def main():
    header("STEP 1 — Create Product")

    engine = make_engine()
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        print("  Creating product: UAT Device Financing...")
        print()

        data = ProductCreate(
            name="UAT Device Financing",
            description="12-month device financing product — created by UAT script",
            product_type="DEVICE",
            interest_rate_model="FIXED",
            min_term_months=3,
            max_term_months=24,
            min_amount=Decimal("200.00"),
            max_amount=Decimal("2000.00"),
            default_interest_rate=Decimal("0.0999"),
            origination_fee=Decimal("0.00"),
            late_fee_rules={},
            eligibility_rules={
                "min_credit_score": 580,
                "max_dti": 0.45,
            },
        )

        product = await product_service.create_product(data, db)

    print("  Product created successfully!")
    print()
    field("ID:",               str(product.id))
    field("Name:",             product.name)
    field("Type:",             product.product_type)
    field("Rate Model:",       product.interest_rate_model)
    field("Interest Rate:",    f"{float(product.default_interest_rate) * 100:.2f}%")
    field("Term Range:",       f"{product.min_term_months} – {product.max_term_months} months")
    field("Amount Range:",     f"${product.min_amount:,.2f} – ${product.max_amount:,.2f}")
    field("Origination Fee:",  f"${product.origination_fee:,.2f}")
    field("Min Credit Score:", product.eligibility_rules.get("min_credit_score"))
    field("Max DTI:",          f"{product.eligibility_rules.get('max_dti') * 100:.0f}%")
    field("Active:",           "Yes" if product.is_active else "No")

    save_state({"product_id": str(product.id)})

    sql_hint(f"SELECT id, name, product_type, default_interest_rate, is_active FROM products WHERE id = '{product.id}';")

    print("  State saved.  Run step_2_create_partner.py next.")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
