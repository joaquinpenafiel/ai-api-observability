import sqlite3

from src.database import (
    fetch_ai_requests,
    initialize_database,
    record_ai_request,
)


def test_initialize_database_creates_schema(tmp_path):
    database_path = tmp_path / "metrics.db"

    initialize_database(database_path)

    assert database_path.exists()

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'ai_request_metrics'
            """
        ).fetchone()

    assert table is not None


def test_record_and_fetch_ai_request(tmp_path):
    database_path = tmp_path / "metrics.db"

    initialize_database(database_path)

    row_id = record_ai_request(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        input_tokens=45,
        output_tokens=60,
        total_tokens=105,
        latency_ms=742.5,
        status="success",
        request_id="request-123",
        database_path=database_path,
    )

    rows = fetch_ai_requests(
        database_path=database_path,
    )

    assert row_id == 1
    assert len(rows) == 1

    assert rows[0]["provider"] == "gemini"
    assert rows[0]["model"] == "gemini-3.1-flash-lite"
    assert rows[0]["input_tokens"] == 45
    assert rows[0]["output_tokens"] == 60
    assert rows[0]["total_tokens"] == 105
    assert rows[0]["latency_ms"] == 742.5
    assert rows[0]["status"] == "success"
    assert rows[0]["request_id"] == "request-123"
    assert rows[0]["created_at"]


def test_fetch_ai_requests_orders_latest_first_and_limits(
    tmp_path,
):
    database_path = tmp_path / "metrics.db"

    initialize_database(database_path)

    for index in range(3):
        record_ai_request(
            provider="gemini",
            model="gemini-3.1-flash-lite",
            input_tokens=index,
            output_tokens=index,
            total_tokens=index * 2,
            latency_ms=100.0 + index,
            status="success",
            request_id=f"request-{index}",
            database_path=database_path,
        )

    rows = fetch_ai_requests(
        limit=2,
        database_path=database_path,
    )

    assert len(rows) == 2
    assert rows[0]["request_id"] == "request-2"
    assert rows[1]["request_id"] == "request-1"
