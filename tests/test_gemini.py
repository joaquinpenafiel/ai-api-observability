import asyncio

import httpx
import pytest
from fastapi import HTTPException

from src.config import settings
from src.services.gemini_client import analyze_text_with_gemini


def test_gemini_analysis_success(monkeypatch):
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
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
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Test Gemini result."
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 25,
                    "candidatesTokenCount": 10,
                    "totalTokenCount": 35,
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
        analyze_text_with_gemini(
            text="Example input text.",
            instruction="Summarize this text.",
        )
    )

    assert result["provider"] == "gemini"
    assert result["model"] == settings.gemini_model
    assert result["output"] == "Test Gemini result."
    assert result["usage"]["input_tokens"] == 25
    assert result["usage"]["output_tokens"] == 10
    assert result["usage"]["total_tokens"] == 35


def test_gemini_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
        None,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            analyze_text_with_gemini(
                text="Example input.",
                instruction="Analyze this.",
            )
        )

    assert exc_info.value.status_code == 503
    assert (
    exc_info.value.detail
    == (
        "Gemini provider credentials are not configured. "
        "In the public demo they are intentionally disabled; "
        "see README."
    )
)


def test_gemini_rate_limit(monkeypatch):
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
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
                "error": {
                    "message": "Rate limit exceeded."
                }
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
            analyze_text_with_gemini(
                text="Example input.",
                instruction="Analyze this.",
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "2"
