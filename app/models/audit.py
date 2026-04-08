import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ActorType(StrEnum):
    PARTNER = "partner"
    SYSTEM = "system"
    ADMIN = "admin"


class AuditLog(Base):
    """Append-only record of every significant system action.

    Covers all entities — loan lifecycle, payments, product changes, etc.
    Never update or delete rows. If Option B (per-entity history tables)
    is adopted later, this table can be migrated into them.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What was affected
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g. "Loan", "LoanApplication"
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)    # UUID as string for flexibility

    # What happened
    action: Mapped[str] = mapped_column(String(80), nullable=False)       # e.g. "status_changed", "payment_applied"

    # Who did it
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ActorType.SYSTEM)
    actor_id: Mapped[str | None] = mapped_column(String(36))              # partner.id, admin user id, etc.

    # State snapshot — both nullable so partial logging is valid
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)

    # Optional free-text context (e.g. decline reason summary, error message)
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
