import asyncio

import httpx
import pytest
from fastapi import HTTPException

from src.config import settings
from src.services.github_client import fetch_repository


SUCCESS_DATA = {
    "full_name": "fastapi/fastapi",
    "description": "FastAPI framework",
    "language": "Python",
    "stargazers_count": 100,
    "forks_count": 20,
    "open_issues_count": 5,
    "html_url": "https://github.com/fastapi/fastapi",
}


class FakeAsyncClient:
    responses = []
    calls = 0

    def __init__(self, *args, **kwargs):
        self._responses = list(self.__class__.responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        type(self).calls += 1
        item = self._responses.pop(0)

        if isinstance(item, Exception):
            raise item

        return item


def configure_fake_client(monkeypatch, responses):
    FakeAsyncClient.responses = responses
    FakeAsyncClient.calls = 0

    monkeypatch.setattr(
        "src.services.github_client.httpx.AsyncClient",
        FakeAsyncClient,
    )

    monkeypatch.setattr(
        settings,
        "github_backoff_seconds",
        0.0,
    )

    monkeypatch.setattr(
        settings,
        "github_max_retries",
        2,
    )


def test_retries_server_errors_then_recovers(monkeypatch):
    configure_fake_client(
        monkeypatch,
        [
            httpx.Response(500),
            httpx.Response(502),
            httpx.Response(200, json=SUCCESS_DATA),
        ],
    )

    result = asyncio.run(
        fetch_repository("fastapi", "fastapi")
    )

    assert FakeAsyncClient.calls == 3
    assert result["repository"] == "fastapi/fastapi"


def test_does_not_retry_not_found(monkeypatch):
    configure_fake_client(
        monkeypatch,
        [
            httpx.Response(404),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            fetch_repository("missing", "repository")
        )

    assert FakeAsyncClient.calls == 1
    assert exc_info.value.status_code == 404


def test_stops_after_maximum_retries(monkeypatch):
    configure_fake_client(
        monkeypatch,
        [
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            fetch_repository("fastapi", "fastapi")
        )

    assert FakeAsyncClient.calls == 3
    assert exc_info.value.status_code == 502

def test_handles_http_429_without_retry(monkeypatch):
    configure_fake_client(
        monkeypatch,
        [
            httpx.Response(
                429,
                headers={
                    "Retry-After": "30",
                },
            ),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            fetch_repository("fastapi", "fastapi")
        )

    assert FakeAsyncClient.calls == 1
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "30"


def test_detects_github_primary_rate_limit(monkeypatch):
    configure_fake_client(
        monkeypatch,
        [
            httpx.Response(
                403,
                headers={
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "9999999999",
                },
            ),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            fetch_repository("fastapi", "fastapi")
        )

    assert FakeAsyncClient.calls == 1
    assert exc_info.value.status_code == 429