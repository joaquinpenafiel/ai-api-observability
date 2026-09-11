import argparse
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.database import (
    connect_database,
    initialize_database,
    record_ai_request,
)


INSERT_SQL = """
INSERT INTO ai_request_metrics (
    created_at,
    provider,
    model,
    input_tokens,
    output_tokens,
    total_tokens,
    estimated_cost_usd,
    latency_ms,
    status,
    request_id
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def configure_journal(
    database_path: Path,
    journal_mode: str,
) -> tuple[str, int]:
    with closing(connect_database(database_path)) as connection:
        actual_mode = connection.execute(
            f"PRAGMA journal_mode={journal_mode}"
        ).fetchone()[0]

        synchronous = connection.execute(
            "PRAGMA synchronous"
        ).fetchone()[0]

        connection.commit()

    return str(actual_mode), int(synchronous)


def make_values(
    *,
    variant: str,
    request_number: int,
) -> tuple:
    return (
        datetime.now(timezone.utc).isoformat(),
        "load-test",
        "local",
        10,
        20,
        30,
        0.0,
        1.0,
        "success",
        f"{variant}-{request_number}",
    )


def run_per_write_connection(
    *,
    database_path: Path,
    journal_mode: str,
    total_requests: int,
    variant: str,
) -> dict:
    initialize_database(database_path)

    actual_mode, synchronous = configure_journal(
        database_path,
        journal_mode,
    )

    latencies = []
    errors = []

    started_total = time.perf_counter()

    for request_number in range(total_requests):
        started = time.perf_counter()

        try:
            record_ai_request(
                provider="load-test",
                model="local",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                estimated_cost_usd=0.0,
                latency_ms=1.0,
                status="success",
                request_id=f"{variant}-{request_number}",
                database_path=database_path,
            )

            latencies.append(
                (time.perf_counter() - started) * 1000
            )

        except Exception as exc:
            errors.append(repr(exc))

    elapsed = time.perf_counter() - started_total

    return build_result(
        variant=variant,
        journal_mode=actual_mode,
        synchronous=synchronous,
        total_requests=total_requests,
        latencies=latencies,
        errors=errors,
        elapsed=elapsed,
    )


def run_persistent_connection(
    *,
    database_path: Path,
    journal_mode: str,
    total_requests: int,
    variant: str,
) -> dict:
    initialize_database(database_path)

    actual_mode, synchronous = configure_journal(
        database_path,
        journal_mode,
    )

    latencies = []
    errors = []

    started_total = time.perf_counter()

    with closing(connect_database(database_path)) as connection:

        for request_number in range(total_requests):
            started = time.perf_counter()

            try:
                connection.execute(
                    INSERT_SQL,
                    make_values(
                        variant=variant,
                        request_number=request_number,
                    ),
                )

                # Important:
                # keep one commit per write so batching is NOT
                # introduced as another experimental variable.
                connection.commit()

                latencies.append(
                    (time.perf_counter() - started) * 1000
                )

            except Exception as exc:
                errors.append(repr(exc))

    elapsed = time.perf_counter() - started_total

    return build_result(
        variant=variant,
        journal_mode=actual_mode,
        synchronous=synchronous,
        total_requests=total_requests,
        latencies=latencies,
        errors=errors,
        elapsed=elapsed,
    )


def build_result(
    *,
    variant: str,
    journal_mode: str,
    synchronous: int,
    total_requests: int,
    latencies: list[float],
    errors: list[str],
    elapsed: float,
) -> dict:
    successful = len(latencies)

    return {
        "variant": variant,
        "journal_mode": journal_mode,
        "synchronous": synchronous,
        "ok": successful,
        "errors": len(errors),
        "elapsed": elapsed,
        "success_rps": (
            successful / elapsed
            if elapsed > 0
            else 0.0
        ),
        "p50": percentile(latencies, 0.50),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
    }


def print_result(result: dict) -> None:
    print(
        f"{result['variant']:<24} "
        f"journal={result['journal_mode']:<6} "
        f"sync={result['synchronous']} "
        f"ok={result['ok']:<4} "
        f"err={result['errors']:<3} "
        f"rps={result['success_rps']:>8.2f} "
        f"p50={result['p50']:>8.2f}ms "
        f"p95={result['p95']:>8.2f}ms "
        f"p99={result['p99']:>8.2f}ms"
    )


def print_summary(results: dict[str, list[dict]]) -> None:
    print()
    print("MEDIAN ACROSS REPEATS")
    print("=" * 110)

    for variant, rows in results.items():
        rps = statistics.median(
            row["success_rps"] for row in rows
        )

        p50 = statistics.median(
            row["p50"] for row in rows
        )

        p95 = statistics.median(
            row["p95"] for row in rows
        )

        p99 = statistics.median(
            row["p99"] for row in rows
        )

        errors = sum(
            row["errors"] for row in rows
        )

        print(
            f"{variant:<24} "
            f"median_rps={rps:>8.2f} "
            f"median_p50={p50:>8.2f}ms "
            f"median_p95={p95:>8.2f}ms "
            f"median_p99={p99:>8.2f}ms "
            f"total_errors={errors}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--requests",
        type=int,
        default=200,
    )

    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    print()
    print("SQLITE WAL / CONNECTION LIFECYCLE PROBE")
    print("=" * 110)

    print(f"Python: {sys.version.split()[0]}")
    print(f"SQLite: {sqlite3.sqlite_version}")
    print(f"Platform: {platform.platform()}")
    print(f"Requests per variant: {args.requests}")
    print(f"Repeats: {args.repeats}")

    variants = [
        (
            "delete_per_write",
            run_per_write_connection,
            "DELETE",
        ),
        (
            "wal_per_write",
            run_per_write_connection,
            "WAL",
        ),
        (
            "delete_persistent",
            run_persistent_connection,
            "DELETE",
        ),
        (
            "wal_persistent",
            run_persistent_connection,
            "WAL",
        ),
    ]

    collected = {
        name: []
        for name, _, _ in variants
    }

    rng = random.Random(42)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        for repeat in range(args.repeats):
            print()
            print(f"REPEAT {repeat + 1}")
            print("-" * 110)

            order = variants.copy()
            rng.shuffle(order)

            for name, runner, journal_mode in order:
                database_path = (
                    root
                    / f"{repeat}_{name}.db"
                )

                result = runner(
                    database_path=database_path,
                    journal_mode=journal_mode,
                    total_requests=args.requests,
                    variant=name,
                )

                collected[name].append(result)

                print_result(result)

    print_summary(collected)


if __name__ == "__main__":
    main()