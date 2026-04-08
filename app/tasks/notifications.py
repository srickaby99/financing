"""Notification stubs — plug in an email provider when ready."""

import logging

logger = logging.getLogger(__name__)


async def send_approval_notification(application_id: str) -> None:
    logger.info("Approval notification for application %s", application_id)
    # TODO: load application + borrower, send via email provider (SES, SendGrid, etc.)


async def send_payment_confirmation(payment_id: str) -> None:
    logger.info("Payment confirmation for payment %s", payment_id)
    # TODO: load payment + loan + borrower, send receipt
