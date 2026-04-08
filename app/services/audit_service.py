"""Audit logging helper.

Usage in any service:
    await audit(db, entity_type="Loan", entity_id=loan.id, action="status_changed",
                before={"status": "ACTIVE"}, after={"status": "PAID_OFF"})
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ActorType, AuditLog


async def audit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID | str,
    action: str,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: uuid.UUID | str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> None:
    """Append an audit log entry. Does not commit — caller owns the transaction."""
    db.add(AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id else None,
        before=before,
        after=after,
        note=note,
    ))
