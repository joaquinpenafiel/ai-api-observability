import hashlib
import hmac
import logging

from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger("api.webhook")


def verify_webhook_signature(
    payload: bytes,
    signature: str | None,
) -> None:
    if not settings.webhook_secret:
        logger.error("Webhook secret is not configured")

        raise HTTPException(
            status_code=503,
            detail="Webhook service is not configured.",
        )

    if not signature:
        logger.warning("Webhook signature is missing")

        raise HTTPException(
            status_code=401,
            detail="Webhook signature is missing.",
        )

    expected_signature = hmac.new(
        settings.webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    expected_header = f"sha256={expected_signature}"

    if not hmac.compare_digest(
        expected_header,
        signature,
    ):
        logger.warning("Invalid webhook signature")

        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature.",
        )

    logger.info("Webhook signature verified")
