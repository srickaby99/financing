"""Tests for audit_service — audit log creation and correctness."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.audit import ActorType, AuditLog
from app.services.audit_service import audit


# ---------------------------------------------------------------------------
# audit()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_creates_log_entry(db):
    """(+) Calling audit() adds an AuditLog row after commit."""
    entity_id = uuid.uuid4()
    await audit(db, entity_type="Loan", entity_id=entity_id, action="test_action")
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.action == "test_action"


@pytest.mark.asyncio
async def test_audit_stores_entity_type_and_action(db):
    """(+) entity_type and action are stored correctly."""
    entity_id = uuid.uuid4()
    await audit(db, entity_type="LoanApplication", entity_id=entity_id, action="application_decided")
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one()
    assert entry.entity_type == "LoanApplication"
    assert entry.action == "application_decided"


@pytest.mark.asyncio
async def test_audit_stores_before_and_after(db):
    """(+) before/after state snapshots are stored as JSONB."""
    entity_id = uuid.uuid4()
    await audit(
        db,
        entity_type="Loan",
        entity_id=entity_id,
        action="status_changed",
        before={"status": "ACTIVE"},
        after={"status": "PAID_OFF"},
    )
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one()
    assert entry.before["status"] == "ACTIVE"
    assert entry.after["status"] == "PAID_OFF"


@pytest.mark.asyncio
async def test_audit_stores_actor_type_and_id(db):
    """(+) actor_type and actor_id are stored correctly."""
    entity_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    await audit(
        db,
        entity_type="LoanApplication",
        entity_id=entity_id,
        action="submitted",
        actor_type=ActorType.PARTNER,
        actor_id=actor_id,
    )
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one()
    assert entry.actor_type == ActorType.PARTNER
    assert entry.actor_id == str(actor_id)


@pytest.mark.asyncio
async def test_audit_defaults_actor_type_to_system(db):
    """(+) Default actor_type is SYSTEM when not specified."""
    entity_id = uuid.uuid4()
    await audit(db, entity_type="Loan", entity_id=entity_id, action="auto_action")
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one()
    assert entry.actor_type == ActorType.SYSTEM


@pytest.mark.asyncio
async def test_audit_stores_note(db):
    """(+) Optional note field is stored when provided."""
    entity_id = uuid.uuid4()
    await audit(
        db,
        entity_type="Payment",
        entity_id=entity_id,
        action="payment_applied",
        note="External ref txn_abc123",
    )
    await db.commit()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one()
    assert entry.note == "External ref txn_abc123"


@pytest.mark.asyncio
async def test_audit_does_not_persist_without_commit(db):
    """(-) audit() adds to session but does not auto-commit — caller owns the transaction."""
    entity_id = uuid.uuid4()
    await audit(db, entity_type="Loan", entity_id=entity_id, action="uncommitted_action")
    # Deliberately not committing

    await db.rollback()

    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == str(entity_id))
    )
    entry = result.scalar_one_or_none()
    assert entry is None


@pytest.mark.asyncio
async def test_audit_application_decision_is_logged(db, approved_application):
    """(+) Submitting an application creates an audit entry for the decision."""
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == str(approved_application.id),
            AuditLog.action == "application_decided",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None


@pytest.mark.asyncio
async def test_audit_loan_origination_is_logged(db, approved_application):
    """(+) Approving an application creates an audit entry for loan origination."""
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == str(approved_application.loan_id),
            AuditLog.action == "loan_originated",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
