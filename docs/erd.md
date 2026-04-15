# Entity Relationship Diagram

> **Maintenance rule:** This diagram must be updated any time a model in `app/models/` changes — added tables, removed columns, new foreign keys, renamed fields. A PR that modifies a model file without a corresponding update to this diagram should not be merged.

```mermaid
erDiagram
    Partner {
        uuid id PK
        string name
        string slug
        string status
        string api_key_hash
    }

    Product {
        uuid id PK
        string name
        string product_type
        string interest_rate_model
        int min_term_months
        int max_term_months
        decimal min_amount
        decimal max_amount
        decimal default_interest_rate
        decimal origination_fee
        json late_fee_rules
        json eligibility_rules
        bool collateral_required
        bool is_active
    }

    PartnerProduct {
        uuid id PK
        uuid partner_id FK
        uuid product_id FK
        bool is_active
        decimal rate_override
        decimal origination_fee_override
    }

    Borrower {
        uuid id PK
        string first_name
        string last_name
        date date_of_birth
        string ssn_last4
        string ssn_hash
        string email
        string phone
        string address_line1
        string city
        string state
        string zip_code
    }

    PaymentMethod {
        uuid id PK
        uuid borrower_id FK
        string type
        string processor_token
        string last4
        string brand
        bool is_default
        string status
    }

    LoanApplication {
        uuid id PK
        uuid borrower_id FK
        uuid product_id FK
        uuid partner_id FK
        decimal requested_amount
        int requested_term_months
        string status
        json underwriting_result
        timestamp created_at
        timestamp decided_at
    }

    Loan {
        uuid id PK
        uuid application_id FK
        uuid product_id FK
        uuid borrower_id FK
        decimal principal
        decimal interest_rate
        int term_months
        decimal origination_fee
        date origination_date
        date maturity_date
        string status
        decimal outstanding_balance
        date next_due_date
    }

    RepaymentScheduleEntry {
        uuid id PK
        uuid loan_id FK
        int period
        date due_date
        decimal principal_due
        decimal interest_due
        decimal balance_after
    }

    Payment {
        uuid id PK
        uuid loan_id FK
        decimal amount
        date payment_date
        decimal principal_applied
        decimal interest_applied
        decimal fees_applied
        string external_reference_id
        string status
    }

    InboundWebhookEvent {
        uuid id PK
        string source
        string event_type
        string external_event_id
        json payload
        string raw_headers
        timestamp received_at
        timestamp processed_at
        string status
        uuid payment_id FK
    }

    LedgerEntry {
        uuid id PK
        uuid loan_id FK
        uuid payment_id FK
        string entry_type
        string debit_account
        string credit_account
        decimal amount
        timestamp created_at
    }

    AuditLog {
        uuid id PK
        string entity_type
        string entity_id
        string action
        string actor_type
        string actor_id
        json before
        json after
        string note
        timestamp created_at
    }

    Partner ||--o{ PartnerProduct : "offers"
    Product ||--o{ PartnerProduct : "offered via"
    Partner ||--o{ LoanApplication : "originates"
    Product ||--o{ LoanApplication : "governs"
    Borrower ||--o{ LoanApplication : "applies"
    Borrower ||--o{ PaymentMethod : "has"
    LoanApplication ||--o| Loan : "originates"
    Product ||--o{ Loan : "governs"
    Borrower ||--o{ Loan : "holds"
    Loan ||--o{ RepaymentScheduleEntry : "has"
    Loan ||--o{ Payment : "receives"
    Loan ||--o{ LedgerEntry : "has"
    Payment ||--o{ LedgerEntry : "generates"
    Payment ||--o| InboundWebhookEvent : "created by"
```

## Tables

| Table | Description |
|---|---|
| `partners` | Businesses that offer financing products to their customers |
| `products` | Financing product definitions — rules, rates, limits |
| `partner_products` | Which products a partner may offer; holds per-partner rate/fee overrides |
| `borrowers` | End customers applying for financing |
| `payment_methods` | Tokenized payment instruments — no raw card/bank data stored |
| `loan_applications` | Applications submitted by partners on behalf of borrowers |
| `loans` | Active financing agreements created on application approval |
| `repayment_schedule_entries` | Month-by-month amortization schedule for each loan |
| `payments` | Payments applied to loans, sourced from processor webhook notifications |
| `inbound_webhook_events` | Append-only log of every inbound payment notification (idempotency key: `external_event_id`) |
| `ledger_entries` | Append-only double-entry ledger — disbursements, payments, fees, adjustments |
| `audit_log` | Append-only record of every significant system action |
