from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.payment import InboundPaymentWebhook, WebhookEventRead
from app.services import payment_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payments", response_model=WebhookEventRead, status_code=200)
async def receive_payment_notification(
    data: InboundPaymentWebhook,
    db: AsyncSession = Depends(get_db),
    x_payment_source: str = Header(default="unknown"),
):
    """Receive a payment settlement notification from an external processor.

    Always returns 200 quickly. Processing is handed off to a Celery task.
    Duplicate event_ids are accepted idempotently.
    """
    event = await payment_service.receive_payment_webhook(data, source=x_payment_source, db=db)
    return event
