# Financing API

A backend system for processing loans — from application through payoff.

## What it does

A business (a **partner**) integrates with this API to offer financing to their customers (the **borrowers**). The partner submits a loan application on the borrower's behalf, receives an instant approved or declined decision, and — if approved — a loan is created and a repayment schedule is generated automatically.

When the borrower makes a payment, the external payment processor sends a notification (a **webhook**) to this system, which applies the payment to the loan, updates the outstanding balance, and writes an audit trail entry.

The system never touches money directly. It is purely record-keeping and decisioning.

---

## Who uses it

| Actor | How they interact |
|---|---|
| **Partner** | Integrates via REST API using an API key. Submits applications, views loan status. |
| **Borrower** | End customer. The partner submits applications on their behalf. |
| **Payment processor** | External service (e.g. Stripe, Braintree). Sends payment settlement notifications via webhook. |
| **Admin** | Internal operator. Uses JWT-authenticated endpoints to manage products and partners. |

---

## How it works end to end

### Phase 1 — Admin setup (done once per product or partner)

Before any borrower can apply for financing, an admin must configure the system:

1. **Create a product** (`POST /api/v1/products`)
   The admin defines a financing type — interest rate, term limits, loan amount range, origination fee, and eligibility rules (minimum credit score, maximum DTI, allowed states, etc.). Products are reusable and shared across partners.

2. **Create a partner** (`POST /api/v1/partners`)
   The admin registers a business that will offer financing to their customers. The system issues an API key the partner will use to authenticate.

3. **Assign the product to the partner** (`POST /api/v1/partners/{id}/products`)
   This creates a `PartnerProduct` record authorizing the partner to offer that product. Optionally, the admin can set a rate or fee override specific to that partner. A partner can only offer products they have been explicitly assigned.

---

### Phase 2 — Partner onboards a borrower

When a customer wants to apply for financing through a partner's app or website:

4. **Create a borrower** (`POST /api/v1/borrowers`)
   The partner submits the customer's identity and contact details. The system stores only the last 4 digits of the SSN and a hash — never the full number.

5. **Add a payment method** (`POST /api/v1/borrowers/{id}/payment-methods`)
   The partner supplies a processor token (from Stripe, Braintree, etc.) representing the customer's payment instrument. Raw card or bank details are never sent to or stored by this system.

---

### Phase 3 — Loan application and decisioning

6. **Submit an application** (`POST /api/v1/applications`)
   The partner submits an application specifying the borrower, product, requested amount, and term. The system immediately:
   - Verifies the partner is authorized to offer the selected product
   - Resolves the effective interest rate and fees (partner override if set, otherwise product defaults)
   - Pulls a credit report from the credit bureau integration
   - Runs the underwriting rules engine against the product's eligibility rules
   - Returns an **instant APPROVED or DECLINED decision** — no waiting

7. **If approved — loan is originated automatically**
   On approval, the system creates a `Loan` record, generates the full amortization schedule, and writes a disbursement ledger entry. The response includes the `loan_id`, approved amount, rate, term, and monthly payment.

8. **If declined — reasons are returned**
   The response includes the specific decline reasons (e.g. `credit_score_below_minimum`, `dti_exceeds_maximum`). No loan is created.

> A borrower can only apply for products that their partner has been assigned. There is no cross-partner product shopping.

---

### Phase 4 — Loan servicing and repayment

9. **Borrower makes payments**
   The external payment processor charges the borrower's payment method and sends a settlement notification to `POST /api/v1/webhooks/payments`. This system never initiates charges.

10. **Payment is applied to the loan**
    On receiving the webhook, the system logs the raw event, applies the payment (splitting it into principal, interest, and fees), reduces the outstanding balance, and writes a ledger entry. Duplicate notifications from the processor are safely rejected using the `external_event_id` as an idempotency key.

11. **Final payment — loan closes**
    When a payment reduces the outstanding balance to zero, the loan status is set to `PAID_OFF` and `next_due_date` is cleared.

---

## Key concepts

### Products

A **product** defines the rules for a type of financing — interest rate, term limits, loan amount range, fees, and eligibility requirements (minimum credit score, maximum debt-to-income ratio, allowed states, etc.).

Adding a new financing type (e.g. "12-month device financing" or "personal loan up to $25,000") means creating a new product record — no code changes required.

### Partners

A **partner** is a business that offers your financing products to their customers. Each partner authenticates with an API key. Partners are assigned to specific products via a `PartnerProduct` link, which can also carry per-partner rate or fee overrides.

### The loan lifecycle

```
Application submitted
        │
        ▼
  Underwriting runs
  (credit pull + rules engine)
        │
   ┌────┴────┐
   │         │
APPROVED  DECLINED ──► Response returned immediately (no waiting)
   │
   ▼
 Loan originated
 Repayment schedule generated
 Disbursement ledger entry written
        │
        ▼
 Borrower makes payments
 (processor notifies via webhook)
        │
        ▼
 Payment applied to loan
 Outstanding balance updated
 Ledger entry written
        │
        ▼
 Final payment → Loan marked PAID_OFF
```

### Underwriting

When an application is submitted, the system:

1. Looks up the product's eligibility rules (stored as JSON — e.g. `{"min_credit_score": 620, "max_dti": 0.45}`)
2. Pulls a credit report via the **credit bureau integration** (currently a deterministic stub; swap in a real bureau by adding one class and updating config)
3. Runs the rules engine — a pure function that evaluates the credit report against the product rules
4. Returns an instant APPROVED or DECLINED decision with decline reasons if applicable

### Payments

This system does not initiate charges. The external payment processor initiates charges and notifies this system via `POST /api/v1/webhooks/payments` when a payment settles. Every inbound notification is logged before processing, and duplicate event IDs are rejected idempotently.

### Audit trail

Every significant action — application decided, loan originated, payment applied — is written to an append-only `AuditLog` table. Audit rows are never updated or deleted.

### Ledger

Every financial movement — disbursements, payments, fees, adjustments — is recorded as an append-only double-entry `LedgerEntry`. Corrections use reversal entries, never updates.

---

## Tech stack

| Concern | Choice |
|---|---|
| API framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| Auth | JWT (admin) + API keys (partners) |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |

---

## API overview

All routes are versioned under `/api/v1/`. Interactive docs are available at `/docs` when running in development.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/applications` | Partner API key | Submit a loan application — returns instant decision |
| `GET` | `/api/v1/applications/{id}` | Partner API key | Retrieve an application |
| `GET` | `/api/v1/loans/{id}` | Partner API key | Retrieve a loan |
| `GET` | `/api/v1/loans/{id}/schedule` | Partner API key | Full amortization schedule |
| `GET` | `/api/v1/loans/{id}/payments` | Partner API key | Payment history |
| `POST` | `/api/v1/webhooks/payments` | None (processor-to-system) | Receive payment settlement notification |
| `POST` | `/api/v1/products` | Admin JWT | Create a product |
| `GET` | `/api/v1/products` | Admin JWT | List products |
| `GET` | `/api/v1/products/{id}` | Admin JWT | Get a product |
| `PATCH` | `/api/v1/products/{id}` | Admin JWT | Update a product |
| `POST` | `/api/v1/partners` | Admin JWT | Create a partner |
| `GET` | `/api/v1/partners/{id}` | Admin JWT | Get a partner |
| `POST` | `/api/v1/partners/{id}/products` | Admin JWT | Assign a product to a partner |
| `GET` | `/api/v1/partners/{id}/products` | Admin JWT | List a partner's assigned products |
| `POST` | `/api/v1/borrowers` | Partner API key | Create a borrower record |
| `GET` | `/api/v1/borrowers/{id}` | Partner API key | Get a borrower |
| `POST` | `/api/v1/borrowers/{id}/payment-methods` | Partner API key | Add a tokenized payment method |
| `POST` | `/api/v1/auth/token` | Credentials | Issue an admin JWT |
| `GET` | `/health` | None | Health check |

---

## Data model

See [`docs/erd.md`](docs/erd.md) for the full entity relationship diagram.

## Project structure

```
app/
  main.py               — FastAPI app factory, router registration
  api/v1/               — Route handlers (thin — delegate to services)
  domain/               — Pure business logic, no I/O
    loan_calculator.py  — Amortization, interest accrual, APR, payoff amount
    underwriting.py     — Eligibility rules engine
    repayment.py        — Repayment schedule generation
  integrations/
    credit/             — Credit bureau abstraction
      base.py           — Abstract CreditBureauClient interface
      dummy.py          — Deterministic stub (no real bureau needed for dev/test)
  services/             — Orchestrates domain + database + audit
    application_service.py
    loan_service.py
    payment_service.py
    product_service.py
    partner_service.py
    borrower_service.py
    audit_service.py
  models/               — SQLAlchemy ORM models (source of truth for schema)
  schemas/              — Pydantic request/response models
  db/
    session.py          — Async session factory
    base.py             — Declarative base
    types.py            — DialectJSON: JSONB on Postgres, JSON on SQLite (for tests)
  core/
    config.py           — Settings via pydantic-settings (.env)
    security.py         — JWT encode/decode
```

---

## Setup and running

### Prerequisites

- Python 3.12+
- PostgreSQL (running locally or via Docker)

### Install dependencies

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (bash)
# source .venv/bin/activate     # Linux / Mac
pip install -r requirements-dev.txt
```

### Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set `DATABASE_URL` to point at your PostgreSQL instance. All other defaults work for local development.

### Run database migrations

```bash
python -m alembic upgrade head
```

### Start the API

```bash
python -m uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## Testing

Tests use SQLite in-memory — no database setup required.

```bash
python -m pytest                         # all tests
python -m pytest tests/services/ -v     # service layer only, verbose
python -m pytest -k "test_approval"     # single test by name
python -m pytest --cov=app              # with coverage report
```

**Current coverage: 82 tests across 7 service modules — all passing.**

| Module | Tests |
|---|---|
| `product_service` | 16 |
| `partner_service` | 15 |
| `loan_service` | 13 |
| `application_service` | 12 |
| `audit_service` | 9 |
| `borrower_service` | 10 |
| `payment_service` | 7 |

---

## Lint and format

```bash
python -m ruff check .
python -m ruff format .
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment name. `production` disables `/docs`. |
| `SECRET_KEY` | `change-me` | JWT signing key. Change in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT lifetime. |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string. |
| `CREDIT_BUREAU_IMPL` | `dummy` | Credit bureau implementation. `dummy` uses the built-in stub. |
| `ADMIN_API_KEY` | `change-me` | Password for the admin JWT endpoint. Change in production. |

---

## Design notes

- **Product-driven model** — financing types are data, not code. New products are created via API; the rules engine interprets them at runtime.
- **Partner rate overrides** — `PartnerProduct` can carry a `rate_override` and `origination_fee_override`, allowing per-partner pricing without duplicating product records.
- **Raw payment credentials are never stored** — `PaymentMethod` holds only a processor token (e.g. Stripe token) and display metadata. Card/bank details live exclusively with the processor.
- **Everything runs synchronously** — underwriting runs in the request path; payment processing runs when the webhook arrives. The `tasks/` directory exists as the seam for a future task queue.
- **Services own transactions** — `commit()` and `rollback()` happen in the service layer, not in route handlers.
- **Domain functions are pure** — `loan_calculator.py` and `underwriting.py` take plain data in and return plain data out. No database access, easy to unit test.

---

## What's not built yet

- **Disbursement** — how funds reach the borrower is not yet designed. The `LedgerEntry` model already has a `DISBURSEMENT` type, and the data model notes a `disbursement_method` field for `Loan` as the natural place to add this.
- **Real credit bureau integration** — the dummy client is the only implementation. Adding a real one (Experian, Equifax, etc.) means implementing `CreditBureauClient` and pointing `CREDIT_BUREAU_IMPL` at it.
- **Background task queue** — currently everything is synchronous. Celery or similar can be wired in at `app/tasks/` when needed.
- **Expanded auth** — the admin JWT endpoint validates against a single env-var key. A proper user store and role-based access control are the natural next step.
