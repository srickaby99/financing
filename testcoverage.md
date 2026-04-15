# Test Coverage

All service tests live under `tests/services/`. Tests are run with SQLite in-memory via `aiosqlite` — the `DialectJSON` custom type ensures JSONB columns work transparently with SQLite.

**Run all tests:**
```
python -m pytest tests/ -v
```

**Run a single file:**
```
python -m pytest tests/services/test_product_service.py -v
```

**Total: 82 tests — 81 positive (+), 11 negative (-)**

---

## product_service (16 tests)

`tests/services/test_product_service.py`

| Test | Type | What it verifies |
|---|---|---|
| `test_create_product_returns_product` | + | Created product is persisted and returned with an ID |
| `test_create_product_stores_eligibility_rules` | + | JSONB `eligibility_rules` round-trip correctly |
| `test_create_product_defaults_active` | + | `is_active` defaults to `True` |
| `test_get_product_returns_existing` | + | Retrieves a product by ID |
| `test_get_product_raises_404_for_unknown_id` | - | Unknown product ID raises 404 |
| `test_list_products_returns_active` | + | Active products appear in active-only listing |
| `test_list_products_excludes_inactive` | + | Deactivated products are excluded from active-only listing |
| `test_list_products_includes_inactive_when_flag_off` | + | `active_only=False` returns inactive products |
| `test_update_product_changes_name` | + | Name update is persisted |
| `test_update_product_changes_rate` | + | Interest rate update is persisted |
| `test_update_product_raises_404_for_unknown_id` | - | Updating a non-existent product raises 404 |
| `test_resolve_effective_terms_uses_product_defaults` | + | Returns product defaults when `PartnerProduct` has no overrides |
| `test_resolve_effective_terms_uses_rate_override` | + | `PartnerProduct.rate_override` supersedes the product default |
| `test_resolve_effective_terms_uses_fee_override` | + | `PartnerProduct.origination_fee_override` supersedes the product default |
| `test_resolve_effective_terms_raises_403_when_not_assigned` | - | Partner not assigned to product raises 403 |
| `test_resolve_effective_terms_raises_403_when_inactive` | - | Inactive `PartnerProduct` raises 403 |

---

## partner_service (15 tests)

`tests/services/test_partner_service.py`

| Test | Type | What it verifies |
|---|---|---|
| `test_create_partner_returns_partner_and_key` | + | Returns partner record and a non-empty raw API key |
| `test_create_partner_stores_key_hash_not_raw` | + | Raw API key is not stored — only its hash |
| `test_create_partner_default_status_active` | + | New partners default to `ACTIVE` status |
| `test_create_partner_raises_409_for_duplicate_slug` | - | Duplicate slug raises 409 |
| `test_get_partner_returns_existing` | + | Retrieves a partner by ID |
| `test_get_partner_raises_404_for_unknown_id` | - | Unknown partner ID raises 404 |
| `test_authenticate_partner_returns_partner_for_valid_key` | + | Valid API key resolves to the correct partner |
| `test_authenticate_partner_raises_401_for_invalid_key` | - | Invalid API key raises 401 |
| `test_authenticate_partner_raises_403_for_suspended_partner` | - | Suspended partner raises 403 even with a valid key |
| `test_assign_product_creates_partner_product` | + | Assigning a product creates a `PartnerProduct` record |
| `test_assign_product_stores_rate_override` | + | Rate override is stored on the `PartnerProduct` |
| `test_assign_product_reactivates_existing` | + | Re-assigning a deactivated product reactivates it (no duplicate row) |
| `test_list_partner_products_returns_assigned` | + | Lists active products assigned to a partner |
| `test_list_partner_products_excludes_inactive` | + | Inactive `PartnerProduct` entries are excluded |
| `test_list_partner_products_empty_for_unassigned_partner` | + | Partner with no products returns empty list |

---

## borrower_service (10 tests)

`tests/services/test_borrower_service.py`

| Test | Type | What it verifies |
|---|---|---|
| `test_create_borrower_returns_borrower` | + | Borrower record created and returned with ID |
| `test_create_borrower_stores_only_last4` | + | Full SSN is not stored — only last 4 digits |
| `test_create_borrower_stores_ssn_hash` | + | SHA-256 hash of SSN is stored for deduplication |
| `test_create_borrower_raises_409_for_duplicate_ssn` | - | Duplicate SSN raises 409 |
| `test_get_borrower_returns_existing` | + | Retrieves a borrower by ID |
| `test_get_borrower_raises_404_for_unknown_id` | - | Unknown borrower ID raises 404 |
| `test_add_payment_method_creates_record` | + | Adds a payment method with correct borrower linkage |
| `test_add_payment_method_status_active` | + | New payment methods default to `ACTIVE` status |
| `test_add_default_payment_method_clears_previous_default` | + | Setting a new default clears the prior default flag |
| `test_add_non_default_payment_method_does_not_affect_existing_default` | + | Adding a non-default method leaves existing default unchanged |

---

## application_service (12 tests)

`tests/services/test_application_service.py`

The credit bureau is mocked in all tests via `patch("app.services.application_service.get_credit_client")`.

| Test | Type | What it verifies |
|---|---|---|
| `test_submit_application_approved` | + | Good credit returns `APPROVED` with a `loan_id` |
| `test_submit_application_approved_returns_monthly_payment` | + | Approved response includes `monthly_payment` in underwriting result |
| `test_submit_application_approved_records_credit_score` | + | Underwriting result captures the credit score pulled |
| `test_submit_application_declined_low_credit` | - | Score below `min_credit_score` returns `DECLINED` with decline reasons |
| `test_submit_application_declined_high_dti` | - | DTI above `max_dti` rule returns `DECLINED` with a DTI reason |
| `test_submit_application_declined_has_no_loan` | - | Declined applications do not originate a loan (`loan_id` is `None`) |
| `test_submit_application_raises_422_amount_too_high` | - | Requested amount above product maximum raises 422 |
| `test_submit_application_raises_422_amount_too_low` | - | Requested amount below product minimum raises 422 |
| `test_submit_application_raises_404_for_unknown_borrower` | - | Unknown borrower ID raises 404 |
| `test_submit_application_raises_403_partner_not_authorized` | - | Partner not assigned to product raises 403 |
| `test_get_application_returns_existing` | + | Retrieves an existing application by ID |
| `test_get_application_raises_404_for_unknown_id` | - | Unknown application ID raises 404 |

---

## loan_service (13 tests)

`tests/services/test_loan_service.py`

Loan origination is tested indirectly through the `approved_application` fixture, which exercises the full `submit_application → originate_loan` path.

| Test | Type | What it verifies |
|---|---|---|
| `test_get_loan_returns_existing` | + | Retrieves a loan by ID |
| `test_get_loan_raises_404_for_unknown_id` | - | Unknown loan ID raises 404 |
| `test_originated_loan_has_correct_principal` | + | Loan principal matches the approved amount |
| `test_originated_loan_status_is_active` | + | Newly originated loans are `ACTIVE` |
| `test_originated_loan_outstanding_balance_equals_principal` | + | Initial outstanding balance equals principal |
| `test_originated_loan_has_next_due_date` | + | `next_due_date` is populated at origination |
| `test_originated_loan_creates_disbursement_ledger_entry` | + | `DISBURSEMENT` ledger entry is created at origination with correct amount |
| `test_get_loan_schedule_returns_correct_number_of_entries` | + | Schedule has one entry per month of the loan term |
| `test_get_loan_schedule_periods_are_sequential` | + | Schedule periods are numbered 1 through `term_months` |
| `test_get_loan_schedule_final_balance_is_zero` | + | Final schedule entry `balance_after` is zero (amortization closes) |
| `test_get_loan_schedule_returns_empty_for_unknown_loan` | + | Non-existent loan returns empty schedule (no 404) |
| `test_get_loan_payments_empty_before_any_payment` | + | No payments before any webhook is received |
| `test_get_loan_payments_returns_empty_for_unknown_loan` | + | Non-existent loan returns empty list (no 404) |

---

## payment_service (7 tests)

`tests/services/test_payment_service.py`

| Test | Type | What it verifies |
|---|---|---|
| `test_webhook_creates_event_record` | + | Inbound webhook creates an `InboundWebhookEvent` record |
| `test_webhook_records_event_type` | + | `event_type` is stored on the webhook event |
| `test_webhook_applies_payment_to_loan` | + | Payment is applied synchronously and loan balance decreases |
| `test_webhook_creates_payment_record` | + | A `Payment` record is created with the correct amount |
| `test_webhook_marks_event_processed` | + | Event `status` is `PROCESSED` after successful payment application |
| `test_webhook_idempotent_on_duplicate_event_id` | - | Same `event_id` sent twice returns same event; no duplicate payment or balance reduction |
| `test_full_payoff_marks_loan_paid_off` | + | Paying the full outstanding balance transitions loan to `PAID_OFF` and clears `next_due_date` |

---

## audit_service (9 tests)

`tests/services/test_audit_service.py`

| Test | Type | What it verifies |
|---|---|---|
| `test_audit_creates_log_entry` | + | `audit()` adds an `AuditLog` row after commit |
| `test_audit_stores_entity_type_and_action` | + | `entity_type` and `action` fields are stored correctly |
| `test_audit_stores_before_and_after` | + | `before`/`after` JSON state snapshots round-trip correctly |
| `test_audit_stores_actor_type_and_id` | + | `actor_type` and `actor_id` are stored when provided |
| `test_audit_defaults_actor_type_to_system` | + | Default `actor_type` is `SYSTEM` when not specified |
| `test_audit_stores_note` | + | Optional `note` field is stored when provided |
| `test_audit_does_not_persist_without_commit` | - | `audit()` adds to session but does not auto-commit — caller owns the transaction |
| `test_audit_application_decision_is_logged` | + | Submitting an application creates an `application_decided` audit entry |
| `test_audit_loan_origination_is_logged` | + | Approving an application creates a `loan_originated` audit entry |

---

## Test Infrastructure

**`tests/conftest.py`** — root fixtures:
- SQLite in-memory engine per test session
- `db` fixture: per-test `AsyncSession` with automatic rollback
- `client` fixture: async `httpx.AsyncClient` for route tests

**`tests/services/conftest.py`** — shared service fixtures:
- `product` — a `DEVICE` type product with `min_credit_score: 580` and `max_dti: 0.45`
- `partner` — returns `(Partner, raw_api_key)` tuple
- `partner_product` — links the `partner` and `product` fixtures
- `borrower` — a `Borrower` record
- `approved_application` — runs the full approval flow with a mocked credit bureau; returns an `ApplicationRead` with `loan_id` populated
