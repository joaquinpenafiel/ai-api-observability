import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ai_request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL,
    status TEXT NOT NULL,
    request_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_metrics_created_at
ON ai_request_metrics(created_at);

CREATE INDEX IF NOT EXISTS idx_ai_metrics_provider
ON ai_request_metrics(provider);
"""


def _database_path(
    database_path: str | Path | None = None,
) -> Path:
    path = Path(
        database_path
        if database_path is not None
        else settings.database_path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def connect_database(
    database_path: str | Path | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        _database_path(database_path),
        timeout=5.0,
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database(
    database_path: str | Path | None = None,
) -> None:
    with closing(
        connect_database(database_path)
    ) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()


def record_ai_request(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    latency_ms: float,
    status: str,
    request_id: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with closing(
        connect_database(database_path)
    ) as connection:
        cursor = connection.execute(
            """
            INSERT INTO ai_request_metrics (
                created_at,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                latency_ms,
                status,
                request_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                latency_ms,
                status,
                request_id,
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)


def fetch_ai_requests(
    *,
    limit: int = 100,
    database_path: str | Path | None = None,
) -> list[dict]:
    with closing(
        connect_database(database_path)
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                latency_ms,
                status,
                request_id
            FROM ai_request_metrics
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]
