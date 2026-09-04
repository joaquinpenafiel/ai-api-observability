import hashlib
import hmac

from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


client = TestClient(app)


def build_signature(
    payload: bytes,
    secret: str,
) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def test_webhook_accepts_valid_signature(monkeypatch):
    secret = "test-webhook-secret"
    payload = b'{"event":"customer.updated","id":123}'

    monkeypatch.setattr(
        settings,
        "webhook_secret",
        secret,
    )

    signature = build_signature(
        payload=payload,
        secret=secret,
    )

    response = client.post(
        "/webhooks/inbound",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "payload_bytes": len(payload),
    }


def test_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(
        settings,
        "webhook_secret",
        "test-webhook-secret",
    )

    payload = b'{"event":"customer.updated","id":123}'

    response = client.post(
        "/webhooks/inbound",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=invalid",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid webhook signature."
    }


def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(
        settings,
        "webhook_secret",
        "test-webhook-secret",
    )

    payload = b'{"event":"customer.updated","id":123}'

    response = client.post(
        "/webhooks/inbound",
        content=payload,
        headers={
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Webhook signature is missing."
    }


def test_webhook_requires_configuration(monkeypatch):
    monkeypatch.setattr(
        settings,
        "webhook_secret",
        None,
    )

    payload = b'{"event":"customer.updated","id":123}'

    response = client.post(
        "/webhooks/inbound",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=test",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Webhook service is not configured."
    }
