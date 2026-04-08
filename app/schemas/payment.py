import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus, WebhookStatus


class PaymentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    loan_id: uuid.UUID
    amount: Decimal
    payment_date: date
    principal_applied: Decimal
    interest_applied: Decimal
    fees_applied: Decimal
    external_reference_id: str | None
    status: PaymentStatus
    created_at: datetime


class InboundPaymentWebhook(BaseModel):
    """Body of an inbound payment notification from an external processor."""
    event_id: str = Field(description="Unique event ID from the processor (idempotency key)")
    event_type: str = Field(description="e.g. payment.settled, payment.failed")
    loan_id: uuid.UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_date: date
    external_reference_id: str = Field(description="Processor-side transaction ID")


class WebhookEventRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    source: str
    event_type: str
    external_event_id: str
    received_at: datetime
    processed_at: datetime | None
    status: WebhookStatus
    payment_id: uuid.UUID | None
