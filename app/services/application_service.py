"""Application service — the core of the loan origination flow.

submit_application() is the critical path:
  1. Validate partner can offer the product
  2. Resolve effective rate/fees (via PartnerProduct)
  3. Pull credit report (via CreditBureauClient)
  4. Run underwriting rules engine (pure domain function)
  5. Persist application with decision
  6. If approved: originate the loan
  7. Return the immediate decision response
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import underwriting as uw
from app.integrations import get_credit_client
from app.models.application import ApplicationStatus, LoanApplication
from app.models.borrower import Borrower
from app.models.product import Product
from app.schemas.application import ApplicationCreate, ApplicationRead, UnderwritingResult
from app.services import product_service


async def submit_application(
    data: ApplicationCreate,
    partner_id: uuid.UUID,
    db: AsyncSession,
) -> ApplicationRead:
    # 1. Load product and validate partner access / resolve effective terms
    product: Product = await product_service.get_product(data.product_id, db)
    effective_rate, effective_fee = await product_service.resolve_effective_terms(
        partner_id, data.product_id, db
    )

    # Validate requested amount within product bounds
    requested = data.requested_amount
    if requested < Decimal(str(product.min_amount)) or requested > Decimal(str(product.max_amount)):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Requested amount must be between {product.min_amount} and {product.max_amount}",
        )

    # 2. Load borrower
    result = await db.execute(select(Borrower).where(Borrower.id == data.borrower_id))
    borrower = result.scalar_one_or_none()
    if not borrower:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower not found")

    # 3. Pull credit report
    credit_client = get_credit_client()
    credit_report = await credit_client.pull_credit_report(borrower)

    # 4. Run underwriting rules engine
    decision = uw.evaluate_application(
        credit_score=credit_report.credit_score,
        monthly_income=credit_report.monthly_income,
        monthly_debt_obligations=credit_report.monthly_debt_obligations,
        requested_amount=requested,
        requested_term_months=data.requested_term_months,
        borrower_state=borrower.state,
        eligibility_rules=product.eligibility_rules or {},
        effective_rate=effective_rate,
        effective_origination_fee=effective_fee,
    )

    app_status = ApplicationStatus.APPROVED if decision.approved else ApplicationStatus.DECLINED
    underwriting_result = {
        "approved": decision.approved,
        "credit_score": decision.credit_score,
        "dti": str(decision.dti) if decision.dti is not None else None,
        "approved_amount": str(decision.approved_amount) if decision.approved_amount else None,
        "approved_rate": str(decision.approved_rate) if decision.approved_rate else None,
        "approved_term_months": decision.approved_term_months,
        "monthly_payment": str(decision.monthly_payment) if decision.monthly_payment else None,
        "decline_reasons": decision.decline_reasons,
    }

    # 5. Persist application
    application = LoanApplication(
        borrower_id=data.borrower_id,
        product_id=data.product_id,
        partner_id=partner_id,
        requested_amount=requested,
        requested_term_months=data.requested_term_months,
        status=app_status,
        underwriting_result=underwriting_result,
        decided_at=datetime.now(UTC),
    )
    db.add(application)
    await db.flush()  # get application.id before originating

    # 6. Audit the underwriting decision
    from app.models.audit import ActorType
    from app.services.audit_service import audit
    await audit(
        db,
        entity_type="LoanApplication",
        entity_id=application.id,
        action="application_decided",
        actor_type=ActorType.PARTNER,
        actor_id=partner_id,
        after=underwriting_result,
    )

    # 7. Originate loan if approved
    loan_id = None
    if decision.approved:
        from app.services import loan_service
        loan = await loan_service.originate_loan(
            application=application,
            approved_amount=decision.approved_amount,
            effective_rate=effective_rate,
            effective_fee=effective_fee,
            term_months=decision.approved_term_months,
            db=db,
        )
        loan_id = loan.id

    await db.commit()
    await db.refresh(application)

    # 7. Build response
    uw_result = UnderwritingResult(
        approved=decision.approved,
        credit_score=decision.credit_score,
        dti=decision.dti,
        approved_amount=decision.approved_amount,
        approved_rate=decision.approved_rate,
        approved_term_months=decision.approved_term_months,
        monthly_payment=decision.monthly_payment,
        decline_reasons=decision.decline_reasons,
    )

    return ApplicationRead(
        id=application.id,
        borrower_id=application.borrower_id,
        product_id=application.product_id,
        partner_id=application.partner_id,
        requested_amount=application.requested_amount,
        requested_term_months=application.requested_term_months,
        status=application.status,
        underwriting_result=uw_result,
        created_at=application.created_at,
        decided_at=application.decided_at,
        loan_id=loan_id,
    )


async def get_application(application_id: uuid.UUID, db: AsyncSession) -> LoanApplication:
    from fastapi import HTTPException, status
    result = await db.execute(select(LoanApplication).where(LoanApplication.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app
