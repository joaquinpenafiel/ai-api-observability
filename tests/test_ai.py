import asyncio

import httpx
import pytest
from fastapi import HTTPException

from src.config import settings
from src.services.ai_client import analyze_text


def test_ai_analysis_success(monkeypatch):
    monkeypatch.setattr(
        settings,
        "anthropic_api_key",
        "test-api-key",
    )

    async def mock_post(
        self,
        url,
        headers=None,
        json=None,
    ):
        return httpx.Response(
            status_code=200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [
                    {
                        "type": "text",
                        "text": "Test analysis result.",
                    }
                ],
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 8,
                },
            },
            request=httpx.Request(
                "POST",
                url,
            ),
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        mock_post,
    )

    result = asyncio.run(
        analyze_text(
            text="Example input text.",
            instruction="Summarize this text.",
        )
    )

    assert result["provider"] == "anthropic"
    assert result["model"] == "claude-sonnet-4-6"
    assert result["output"] == "Test analysis result."
    assert result["usage"]["input_tokens"] == 20
    assert result["usage"]["output_tokens"] == 8


def test_ai_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        settings,
        "anthropic_api_key",
        None,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            analyze_text(
                text="Example input.",
                instruction="Analyze this.",
            )
        )

    assert exc_info.value.status_code == 503
    assert (
        exc_info.value.detail
        == "AI service is not configured."
    )


def test_ai_rate_limit(monkeypatch):
    monkeypatch.setattr(
        settings,
        "anthropic_api_key",
        "test-api-key",
    )

    async def mock_post(
        self,
        url,
        headers=None,
        json=None,
    ):
        return httpx.Response(
            status_code=429,
            headers={
                "retry-after": "2",
            },
            json={
                "type": "error",
            },
            request=httpx.Request(
                "POST",
                url,
            ),
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        mock_post,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            analyze_text(
                text="Example input.",
                instruction="Analyze this.",
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "2"
