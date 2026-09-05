from unittest.mock import AsyncMock

from src.database import (
    fetch_ai_requests,
    initialize_database,
    record_ai_request,
)

from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.main as main_module


client = TestClient(main_module.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()


def test_process():
    response = client.post(
        "/process",
        json={
            "text": "   Hello    API Integration Lab   ",
            "source": "test",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "test"
    assert data["normalized_text"] == "Hello API Integration Lab"
    assert data["character_count"] == 25
    assert "processed_at" in data


def test_process_rejects_empty_text():
    response = client.post(
        "/process",
        json={
            "text": "",
            "source": "test",
        },
    )

    assert response.status_code == 422


def test_github_repository_success(monkeypatch):
    repository_data = {
        "repository": "fastapi/fastapi",
        "description": "Test repository",
        "language": "Python",
        "stars": 100,
        "forks": 20,
        "open_issues": 5,
        "url": "https://github.com/fastapi/fastapi",
    }

    mocked_fetch = AsyncMock(return_value=repository_data)

    monkeypatch.setattr(
        main_module,
        "fetch_repository",
        mocked_fetch,
    )

    response = client.get("/github/fastapi/fastapi")

    assert response.status_code == 200
    assert response.json() == repository_data

    mocked_fetch.assert_awaited_once_with(
        "fastapi",
        "fastapi",
    )


def test_github_repository_not_found(monkeypatch):
    mocked_fetch = AsyncMock(
        side_effect=HTTPException(
            status_code=404,
            detail="Repository not found.",
        )
    )

    monkeypatch.setattr(
        main_module,
        "fetch_repository",
        mocked_fetch,
    )

    response = client.get(
        "/github/does-not-exist/does-not-exist"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Repository not found."
    }

def test_gemini_endpoint_records_metrics(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    mocked_result = {
        "provider": "gemini",
        "model": "gemini-3.1-flash-lite",
        "output": "Test Gemini result.",
        "usage": {
            "input_tokens": 25,
            "output_tokens": 10,
            "total_tokens": 35,
        },
    }

    mocked_analyze = AsyncMock(
        return_value=mocked_result,
    )

    monkeypatch.setattr(
        main_module,
        "analyze_text_with_gemini",
        mocked_analyze,
    )

    response = client.post(
        "/ai/gemini/analyze",
        headers={
            "X-Request-ID": "metrics-test-123",
        },
        json={
            "text": "Example input text.",
            "instruction": "Summarize this text.",
        },
    )

    assert response.status_code == 200

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "gemini"
    assert rows[0]["model"] == "gemini-3.1-flash-lite"
    assert rows[0]["input_tokens"] == 25
    assert rows[0]["output_tokens"] == 10
    assert rows[0]["total_tokens"] == 35
    assert rows[0]["status"] == "success"
    assert rows[0]["request_id"] == "metrics-test-123"
    assert rows[0]["latency_ms"] >= 0

def test_anthropic_endpoint_records_metrics(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "anthropic_metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    mocked_result = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "output": "Test Anthropic result.",
        "usage": {
            "input_tokens": 20,
            "output_tokens": 8,
        },
    }

    mocked_analyze = AsyncMock(
        return_value=mocked_result,
    )

    monkeypatch.setattr(
        main_module,
        "analyze_text",
        mocked_analyze,
    )

    response = client.post(
        "/ai/analyze",
        headers={
            "X-Request-ID": "anthropic-metrics-123",
        },
        json={
            "text": "Example input text.",
            "instruction": "Summarize this text.",
        },
    )

    assert response.status_code == 200

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "anthropic"
    assert rows[0]["model"] == "claude-sonnet-4-6"
    assert rows[0]["input_tokens"] == 20
    assert rows[0]["output_tokens"] == 8
    assert rows[0]["total_tokens"] == 28
    assert rows[0]["status"] == "success"
    assert (
        rows[0]["request_id"]
        == "anthropic-metrics-123"
    )
    assert rows[0]["latency_ms"] >= 0

def test_anthropic_disabled_provider_does_not_record_failure(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "disabled_anthropic_metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    mocked_analyze = AsyncMock(
        side_effect=HTTPException(
            status_code=503,
            detail=(
                "Anthropic provider credentials are not configured. "
                "In the public demo they are intentionally disabled; "
                "see README."
            ),
        )
    )

    monkeypatch.setattr(
        main_module,
        "analyze_text",
        mocked_analyze,
    )

    response = client.post(
        "/ai/analyze",
        json={
            "text": "Example input text.",
            "instruction": "Summarize this text.",
        },
    )

    assert response.status_code == 503

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert rows == []

def test_gemini_failure_records_metrics(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "failed_metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    mocked_analyze = AsyncMock(
        side_effect=HTTPException(
            status_code=429,
            detail="Gemini API rate limit exceeded.",
        )
    )

    monkeypatch.setattr(
        main_module,
        "analyze_text_with_gemini",
        mocked_analyze,
    )

    response = client.post(
        "/ai/gemini/analyze",
        headers={
            "X-Request-ID": "failed-metrics-123",
        },
        json={
            "text": "Example input text.",
            "instruction": "Summarize this text.",
        },
    )

    assert response.status_code == 429

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "gemini"
    assert rows[0]["model"] == main_module.settings.gemini_model
    assert rows[0]["input_tokens"] == 0
    assert rows[0]["output_tokens"] == 0
    assert rows[0]["total_tokens"] == 0
    assert rows[0]["status"] == "http_429"
    assert (
        rows[0]["request_id"]
        == "failed-metrics-123"
    )
    assert rows[0]["latency_ms"] >= 0

def test_gemini_disabled_provider_does_not_record_failure(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "disabled_gemini_metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    mocked_analyze = AsyncMock(
        side_effect=HTTPException(
            status_code=503,
            detail=(
                "Gemini provider credentials are not configured. "
                "In the public demo they are intentionally disabled; "
                "see README."
            ),
        )
    )

    monkeypatch.setattr(
        main_module,
        "analyze_text_with_gemini",
        mocked_analyze,
    )

    response = client.post(
        "/ai/gemini/analyze",
        json={
            "text": "Example input text.",
            "instruction": "Summarize this text.",
        },
    )

    assert response.status_code == 503

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert rows == []

def test_stats_endpoint_aggregates_ai_metrics(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "stats_metrics.db"

    monkeypatch.setattr(
        main_module.settings,
        "database_path",
        str(database_path),
    )

    initialize_database(database_path)

    record_ai_request(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        input_tokens=20,
        output_tokens=10,
        total_tokens=30,
        latency_ms=100.0,
        status="success",
        request_id="stats-1",
        database_path=database_path,
    )

    record_ai_request(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        input_tokens=30,
        output_tokens=20,
        total_tokens=50,
        latency_ms=200.0,
        status="http_429",
        request_id="stats-2",
        database_path=database_path,
    )

    record_ai_request(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=40,
        output_tokens=30,
        total_tokens=70,
        latency_ms=300.0,
        status="success",
        request_id="stats-3",
        database_path=database_path,
    )

    response = client.get("/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total_requests"] == 3
    assert data["successful_requests"] == 2
    assert data["failed_requests"] == 1

    assert data["total_input_tokens"] == 90
    assert data["total_output_tokens"] == 60
    assert data["total_tokens"] == 150

    assert data["average_latency_ms"] == 200.0

    assert len(data["providers"]) == 2

    providers = {
        item["provider"]: item
        for item in data["providers"]
    }

    assert providers["gemini"]["requests"] == 2
    assert providers["gemini"]["successful_requests"] == 1
    assert providers["gemini"]["failed_requests"] == 1
    assert providers["gemini"]["total_tokens"] == 80
    assert providers["gemini"]["average_latency_ms"] == 150.0

    assert providers["anthropic"]["requests"] == 1
    assert providers["anthropic"]["successful_requests"] == 1
    assert providers["anthropic"]["failed_requests"] == 0
    assert providers["anthropic"]["total_tokens"] == 70
    assert (
        providers["anthropic"]["average_latency_ms"]
        == 300.0
    )
def test_dashboard_page_is_served():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI API Metrics" in response.text
    assert (
        'src="/static/dashboard.js"'
        in response.text
    )


def test_dashboard_javascript_is_served():
    response = client.get(
        "/static/dashboard.js"
    )

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'fetch("/stats")' in response.text
    assert "loadDashboard" in response.text
