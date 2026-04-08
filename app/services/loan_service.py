import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.loan_calculator import generate_amortization_schedule
from app.models.application import LoanApplication
from app.models.ledger import EntryType, LedgerEntry
from app.models.loan import Loan, LoanStatus, RepaymentScheduleEntry


async def originate_loan(
    application: LoanApplication,
    approved_amount: Decimal,
    effective_rate: Decimal,
    effective_fee: Decimal,
    term_months: int,
    db: AsyncSession,
) -> Loan:
    """Create a Loan from an approved application.

    Generates the repayment schedule and posts the initial DISBURSEMENT
    ledger entry (amount is a placeholder until disbursement flow is built).
    """
    today = date.today()
    maturity = today + timedelta(days=term_months * 30)  # approximation; schedule has exact dates

    loan = Loan(
        application_id=application.id,
        product_id=application.product_id,
        borrower_id=application.borrower_id,
        principal=approved_amount,
        interest_rate=effective_rate,
        term_months=term_months,
        origination_fee=effective_fee,
        origination_date=today,
        maturity_date=maturity,
        status=LoanStatus.ACTIVE,
        outstanding_balance=approved_amount,
    )
    db.add(loan)
    await db.flush()  # get loan.id

    # Generate and persist amortization schedule
    schedule = generate_amortization_schedule(approved_amount, effective_rate, term_months, today)
    for row in schedule:
        db.add(
            RepaymentScheduleEntry(
                loan_id=loan.id,
                period=row.period,
                due_date=row.due_date,
                principal_due=row.principal_due,
                interest_due=row.interest_due,
                balance_after=row.balance_after,
            )
        )

    # Set next due date from first schedule entry
    if schedule:
        loan.next_due_date = schedule[0].due_date

    # Post DISBURSEMENT ledger entry (deferred — amount recorded, method TBD)
    db.add(
        LedgerEntry(
            loan_id=loan.id,
            entry_type=EntryType.DISBURSEMENT,
            debit_account="loans_receivable",
            credit_account="cash",
            amount=approved_amount,
        )
    )

    from app.services.audit_service import audit
    await audit(
        db,
        entity_type="Loan",
        entity_id=loan.id,
        action="loan_originated",
        after={
            "principal": str(approved_amount),
            "interest_rate": str(effective_rate),
            "term_months": term_months,
            "origination_date": str(today),
        },
    )

    return loan


async def get_loan(loan_id: uuid.UUID, db: AsyncSession) -> Loan:
    from fastapi import HTTPException, status
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return loan


async def get_loan_schedule(loan_id: uuid.UUID, db: AsyncSession) -> list[RepaymentScheduleEntry]:
    result = await db.execute(
        select(RepaymentScheduleEntry)
        .where(RepaymentScheduleEntry.loan_id == loan_id)
        .order_by(RepaymentScheduleEntry.period)
    )
    return list(result.scalars().all())


async def get_loan_payments(loan_id: uuid.UUID, db: AsyncSession):
    from app.models.payment import Payment
    result = await db.execute(
        select(Payment)
        .where(Payment.loan_id == loan_id)
        .order_by(Payment.payment_date)
    )
    return list(result.scalars().all())
