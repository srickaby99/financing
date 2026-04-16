# UAT Scripts

Interactive user acceptance tests that run against the real PostgreSQL database.
Each step creates real data you can inspect before moving to the next step.

## Prerequisites

- PostgreSQL running and migrations applied (`python -m alembic upgrade head`)
- `.env` file configured with a valid `DATABASE_URL`
- Dependencies installed (`pip install -r requirements-dev.txt`)

## How to run

Run each step from the **project root**, then query the database to verify before proceeding.

```bash
cd C:\Users\srick\Projects\Financing
```

### Step 1 — Create a product

```bash
python scripts/uat/step_1_create_product.py
```

Creates the financing product that defines rates, limits, and eligibility rules.

Verify:
```sql
SELECT id, name, product_type, default_interest_rate, is_active FROM products WHERE name = 'UAT Device Financing';
```

---

### Step 2 — Create a partner

```bash
python scripts/uat/step_2_create_partner.py
```

Creates the business that will offer the product. Displays the API key once — it is never stored in plain text.

Verify:
```sql
SELECT id, name, slug, status FROM partners WHERE slug = 'uat-partner';
```

---

### Step 3 — Assign product to partner

```bash
python scripts/uat/step_3_assign_product.py
```

Authorizes the partner to offer the device financing product.

Verify:
```sql
SELECT pp.id, pa.name AS partner, pr.name AS product, pp.is_active
FROM partner_products pp
JOIN partners pa ON pa.id = pp.partner_id
JOIN products pr ON pr.id = pp.product_id
WHERE pa.slug = 'uat-partner';
```

---

### Step 4 — Create a borrower

```bash
python scripts/uat/step_4_create_borrower.py
```

Registers the customer. Note that only the last 4 digits of the SSN are stored — never the full number.

Verify:
```sql
SELECT id, first_name, last_name, email, ssn_last4, state FROM borrowers WHERE email = 'jane.smith.uat@example.com';
```

---

### Step 5 — Submit a loan application

```bash
python scripts/uat/step_5_submit_application.py
```

Submits the application. The system runs underwriting immediately using the dummy credit bureau and returns an instant APPROVED or DECLINED decision. If approved, a loan and full repayment schedule are created.

Verify:
```sql
-- Application decision
SELECT id, status, requested_amount, decided_at FROM loan_applications ORDER BY created_at DESC LIMIT 1;

-- Originated loan
SELECT id, status, principal, outstanding_balance, interest_rate, next_due_date FROM loans ORDER BY created_at DESC LIMIT 1;

-- First 3 periods of the repayment schedule
SELECT period, due_date, principal_due, interest_due, balance_after
FROM repayment_schedule_entries
WHERE loan_id = (SELECT id FROM loans ORDER BY created_at DESC LIMIT 1)
ORDER BY period LIMIT 3;
```

---

### Step 6 — Make a payment

```bash
python scripts/uat/step_6_make_payment.py
```

Simulates the payment processor sending a settlement notification. One monthly payment is applied to the loan. The balance decreases and a ledger entry is written.

Verify:
```sql
-- Reduced loan balance
SELECT id, status, outstanding_balance FROM loans ORDER BY created_at DESC LIMIT 1;

-- Payment record
SELECT id, amount, principal_applied, interest_applied, status FROM payments ORDER BY created_at DESC LIMIT 1;

-- Ledger entry
SELECT entry_type, debit_account, credit_account, amount FROM ledger_entries ORDER BY created_at DESC LIMIT 3;

-- Audit trail
SELECT action, before, after FROM audit_log ORDER BY created_at DESC LIMIT 3;
```

---

### Step 7 — Full payoff

```bash
python scripts/uat/step_7_full_payoff.py
```

Pays off the remaining balance in full. The loan status transitions to `PAID_OFF` and `next_due_date` is cleared.

Verify:
```sql
SELECT id, status, outstanding_balance, next_due_date FROM loans ORDER BY created_at DESC LIMIT 1;
```

---

## Cleanup

When you are done reviewing and want to re-run the UAT:

```bash
python scripts/uat/cleanup.py
```

This deletes all UAT records from the database in the correct order and resets the state file so the steps can be run again from the beginning.

---

## State file

Each step saves the IDs it creates to `scripts/uat/uat_state.json` so subsequent steps can reference them. The cleanup script deletes this file. Do not edit it manually.
