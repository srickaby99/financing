# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A financial backend for loan processing built with **Python + FastAPI** and **PostgreSQL**. The system handles the full loan lifecycle: application → underwriting → origination → servicing → payoff.

The central design principle is a **product-driven data model**: a `Product` entity defines the rules and parameters for a financing type (device financing, personal loans, computer purchase loans, etc.), and all loans reference a product. New financing types are added by configuring a new product, not by changing code.

## Tech Stack

| Concern | Choice |
|---|---|
| API framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| Auth | JWT (via `python-jose` or `authlib`) |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |

## Development Commands

### Setup
```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (bash); Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then fill in DATABASE_URL etc.
```

### Run the API
```bash
python -m uvicorn app.main:app --reload
```

### Database migrations
```bash
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "description"
python -m alembic downgrade -1
```

### Tests
```bash
python -m pytest                       # all tests
python -m pytest tests/unit/test_loan_calculator.py   # single file
python -m pytest -k "test_approval"    # single test by name
python -m pytest --cov=app             # with coverage
```

### Lint / format
```bash
python -m ruff check .
python -m ruff format .
```

## Architecture

### Layer structure

```
app/
  main.py               # FastAPI app factory, router registration
  api/                  # Route handlers (thin — delegate to services)
    v1/
      loans.py
      applications.py
      products.py
      payments.py
      auth.py
      webhooks.py       # Inbound payment notifications from external processor
  domain/               # Pure business logic, no I/O
    loan_calculator.py  # Amortization, interest accrual, APR
    underwriting.py     # Eligibility rules engine
    repayment.py        # Schedule generation
  integrations/         # Adapters for external systems
    credit/
      base.py           # CreditBureauClient abstract base class (interface)
      dummy.py          # DummyCreditBureauClient — rule-based stub for development/testing
      models.py         # CreditReport, CreditScore dataclasses (shared across implementations)
  services/             # Orchestrates domain + DB + tasks
    loan_service.py
    application_service.py
    payment_service.py
  models/               # SQLAlchemy ORM models (source of truth for schema)
  schemas/              # Pydantic request/response models (never expose ORM models directly)
  tasks/                # Celery task definitions
    notifications.py
    payment_processing.py
  db/
    session.py          # Async session factory
    base.py             # Declarative base
  core/
    config.py           # Settings via pydantic-settings
    security.py         # JWT encode/decode
```

### Core data model

```
Product
  ├── id, name, description
  ├── product_type (enum: DEVICE, PERSONAL, AUTO, PURCHASE, ...)
  ├── interest_rate_model (FIXED | VARIABLE)
  ├── min/max_term_months, min/max_amount
  ├── origination_fee, late_fee rules
  ├── collateral_required (bool)
  └── eligibility_rules (JSONB — flexible per-product rules)

Partner
  ├── id, name, slug (unique)
  ├── status (ACTIVE | SUSPENDED)
  └── api_key_hash  (partners authenticate with API keys scoped to their account)

PartnerProduct  (controls which products a partner may offer; extensibility hook for future per-partner overrides)
  ├── partner_id → Partner
  ├── product_id → Product
  ├── is_active
  └── rate_override, origination_fee_override  (nullable — if set, supersedes Product defaults)

Borrower  (system owns this record — needed for billing and collections)
  ├── id
  ├── Identity: first_name, last_name, date_of_birth, ssn_last4, ssn_hash
  ├── Contact: email, phone, mailing_address (street, city, state, zip)
  └── created_at, updated_at

PaymentMethod  (tokenized — raw card/bank details never stored)
  ├── id, borrower_id → Borrower
  ├── type (ACH | CARD)
  ├── processor_token  (opaque token from payment processor, e.g. Stripe, Braintree)
  ├── last4, bank_name / card_brand
  ├── is_default
  └── status (ACTIVE | EXPIRED | REMOVED)

LoanApplication
  ├── id, borrower_id → Borrower
  ├── product_id → Product
  ├── partner_id → Partner  (which partner originated this application)
  ├── requested_amount, requested_term_months
  ├── status (DRAFT | SUBMITTED | APPROVED | DECLINED | EXPIRED)
  ├── underwriting_result (JSONB — decision details, score, reasons)
  └── created_at, decided_at

## Deferred Design Areas

- **Disbursement** — how funds reach the borrower or merchant is not yet designed. A `disbursement_method` field should be added to `Loan` when this is tackled. The `LedgerEntry` model already accommodates a `DISBURSEMENT` entry type.

---

Loan  (created upon origination of an approved application)
  ├── id, application_id → LoanApplication
  ├── product_id → Product
  ├── borrower_id → Borrower
  ├── principal, interest_rate, term_months
  ├── origination_date, maturity_date
  ├── status (ACTIVE | PAID_OFF | DEFAULTED | CHARGED_OFF)
  └── outstanding_balance, next_due_date

RepaymentSchedule
  ├── loan_id → Loan
  └── rows: (period, due_date, principal_due, interest_due, balance_after)

Payment
  ├── id, loan_id → Loan
  ├── amount, payment_date
  ├── principal_applied, interest_applied, fees_applied
  ├── external_reference_id  (ID from the external payment processor notification)
  └── status (PENDING | SETTLED | FAILED | REVERSED)

InboundWebhookEvent  (append-only log of all inbound payment notifications)
  ├── id, source (payment processor name / slug)
  ├── event_type, external_event_id  (for idempotency — reject duplicates)
  ├── payload (JSONB — raw body as received)
  ├── processed_at, status (RECEIVED | PROCESSED | FAILED | IGNORED)
  └── payment_id → Payment (nullable — set after successful processing)

LedgerEntry  (append-only, double-entry)
  ├── loan_id, payment_id (nullable)
  ├── entry_type (DISBURSEMENT | PAYMENT | FEE | ADJUSTMENT | WRITEOFF)
  ├── debit_account, credit_account, amount
  └── created_at
```

### Key design rules

- **`Product.eligibility_rules`** is a JSONB field holding a rule set (e.g. min credit score, max DTI, allowed states). The `domain/underwriting.py` rules engine evaluates these against applicant data so product-specific rules require no code changes.
- **`PartnerProduct` is the extensibility seam** — today it controls access (which partners can offer which products). In the future, `rate_override` and `fee_override` fields allow per-partner pricing without duplicating product records. The underwriting service always resolves effective rate/fees through `PartnerProduct` before applying `Product` defaults.
- **Partner authentication uses API keys**, not JWT. JWT is for borrower-facing or internal flows. Partners include their API key in the `Authorization` header; the system resolves the `Partner` record from the key hash.
- **Credit bureau is behind an abstract interface** — `integrations/credit/base.py` defines `CreditBureauClient` as an abstract base class. `DummyCreditBureauClient` is the only implementation for now, applying simple configurable rules. Swapping in a real bureau (Experian, Equifax, etc.) means adding a new implementation class and changing the binding in config — no changes to the underwriting service.
- **Payments are initiated externally** — the financing system never initiates charges. It exposes `POST /api/v1/webhooks/payments` to receive settlement notifications from the external processor. Every inbound call is logged to `InboundWebhookEvent` before processing (idempotency: duplicate `external_event_id` values are rejected). The Celery `payment_processing` task handles applying the payment to the loan and writing ledger entries.
- **Raw payment credentials are never stored** — `PaymentMethod` holds only a processor token (Stripe, Braintree, etc.) plus display metadata (`last4`, `card_brand`). The actual card/bank details live exclusively with the payment processor.
- **`AuditLog` is append-only** — every significant system action (application decided, loan originated, payment applied) is recorded via `audit_service.audit()`. Never update or delete audit rows. If per-entity history tables are needed later (Option B), this table is the migration source.
- **`LedgerEntry` is append-only** — never update or delete ledger rows. Corrections use reversal entries.
- **Services own transactions** — SQLAlchemy session commit/rollback happens in the service layer, not in route handlers or domain functions.
- **Domain functions are pure** — `loan_calculator.py` and `underwriting.py` take plain data in, return plain data out. No DB access, no side effects. This makes them easy to unit test.
- **Everything executes synchronously.** Underwriting runs in the request path; payment processing runs synchronously when the webhook is received. No background task queue.
- **`app/tasks/` contains notification and payment processing functions** — they are plain `async def` functions, not queued tasks. When async processing is needed in future, this is where the queue integration goes.
- **API versioning** — all routes live under `/api/v1/`. Breaking changes get a new version prefix.
- **Never return ORM models from route handlers** — always serialize through a Pydantic response schema.
