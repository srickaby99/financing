"""Payment service — handles inbound payment notifications."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import InboundWebhookEvent, WebhookStatus
from app.schemas.payment import InboundPaymentWebhook
from app.tasks.payment_processing import apply_payment_to_loan


async def receive_payment_webhook(
    data: InboundPaymentWebhook,
    source: str,
    db: AsyncSession,
) -> InboundWebhookEvent:
    # Idempotency check
    result = await db.execute(
        select(InboundWebhookEvent).where(
            InboundWebhookEvent.external_event_id == data.event_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    event = InboundWebhookEvent(
        source=source,
        event_type=data.event_type,
        external_event_id=data.event_id,
        payload=data.model_dump(mode="json"),
        status=WebhookStatus.RECEIVED,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await apply_payment_to_loan(event.id, db)
    await db.refresh(event)
    return event
