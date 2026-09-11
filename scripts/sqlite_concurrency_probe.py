import argparse
import platform
import queue
import random
import sqlite3
import statistics
import sys
import tempfile
import threading
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


def parse_levels(raw: str) -> list[int]:
    return [
        int(value.strip())
        for value in raw.split(",")
        if value.strip()
    ]


def configure_database(
    database_path: Path,
    journal_mode: str,
) -> tuple[str, int]:
    with closing(
        connect_database(database_path)
    ) as connection:

        actual_mode = connection.execute(
            f"PRAGMA journal_mode={journal_mode}"
        ).fetchone()[0]

        synchronous = connection.execute(
            "PRAGMA synchronous"
        ).fetchone()[0]

        connection.commit()

    return str(actual_mode), int(synchronous)


def values_for(
    *,
    variant: str,
    concurrency: int,
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
        f"{variant}-{concurrency}-{request_number}",
    )


def current_write(
    *,
    database_path: Path,
    variant: str,
    concurrency: int,
    request_number: int,
) -> None:
    record_ai_request(
        provider="load-test",
        model="local",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost_usd=0.0,
        latency_ms=1.0,
        status="success",
        request_id=(
            f"{variant}-{concurrency}-{request_number}"
        ),
        database_path=database_path,
    )


def current_worker(
    *,
    database_path: Path,
    variant: str,
    concurrency: int,
    work_queue: queue.Queue,
    start_barrier: threading.Barrier,
    latencies: list[float],
    errors: list[str],
    result_lock: threading.Lock,
) -> None:
    start_barrier.wait()

    while True:
        request_number = work_queue.get()

        if request_number is None:
            work_queue.task_done()
            break

        started = time.perf_counter()

        try:
            current_write(
                database_path=database_path,
                variant=variant,
                concurrency=concurrency,
                request_number=request_number,
            )

            latency_ms = (
                time.perf_counter() - started
            ) * 1000

            with result_lock:
                latencies.append(latency_ms)

        except Exception as exc:
            with result_lock:
                errors.append(repr(exc))

        finally:
            work_queue.task_done()


def wal_persistent_worker(
    *,
    database_path: Path,
    variant: str,
    concurrency: int,
    work_queue: queue.Queue,
    start_barrier: threading.Barrier,
    latencies: list[float],
    errors: list[str],
    result_lock: threading.Lock,
) -> None:
    with closing(
        connect_database(database_path)
    ) as connection:

        start_barrier.wait()

        while True:
            request_number = work_queue.get()

            if request_number is None:
                work_queue.task_done()
                break

            started = time.perf_counter()

            try:
                connection.execute(
                    INSERT_SQL,
                    values_for(
                        variant=variant,
                        concurrency=concurrency,
                        request_number=request_number,
                    ),
                )

                # Keep one commit per write.
                # No transaction batching is introduced.
                connection.commit()

                latency_ms = (
                    time.perf_counter() - started
                ) * 1000

                with result_lock:
                    latencies.append(latency_ms)

            except Exception as exc:
                with result_lock:
                    errors.append(repr(exc))

            finally:
                work_queue.task_done()


def run_round(
    *,
    database_path: Path,
    variant: str,
    journal_mode: str,
    persistent: bool,
    concurrency: int,
    total_requests: int,
) -> dict:
    initialize_database(database_path)

    actual_mode, synchronous = configure_database(
        database_path,
        journal_mode,
    )

    work_queue = queue.Queue()

    for request_number in range(total_requests):
        work_queue.put(request_number)

    for _ in range(concurrency):
        work_queue.put(None)

    latencies: list[float] = []
    errors: list[str] = []

    result_lock = threading.Lock()

    start_barrier = threading.Barrier(
        concurrency + 1
    )

    target = (
        wal_persistent_worker
        if persistent
        else current_worker
    )

    threads = []

    for _ in range(concurrency):
        thread = threading.Thread(
            target=target,
            kwargs={
                "database_path": database_path,
                "variant": variant,
                "concurrency": concurrency,
                "work_queue": work_queue,
                "start_barrier": start_barrier,
                "latencies": latencies,
                "errors": errors,
                "result_lock": result_lock,
            },
        )

        thread.start()
        threads.append(thread)

    started_total = time.perf_counter()

    start_barrier.wait()

    work_queue.join()

    elapsed = time.perf_counter() - started_total

    for thread in threads:
        thread.join()

    lock_errors = sum(
        1
        for error in errors
        if "locked" in error.lower()
    )

    successes = len(latencies)

    attempt_rps = (
        total_requests / elapsed
        if elapsed > 0
        else 0.0
    )

    success_rps = (
        successes / elapsed
        if elapsed > 0
        else 0.0
    )

    error_rate = (
        len(errors) / total_requests * 100
        if total_requests > 0
        else 0.0
    )

    return {
        "variant": variant,
        "concurrency": concurrency,
        "journal_mode": actual_mode,
        "synchronous": synchronous,
        "ok": successes,
        "errors": len(errors),
        "lock_errors": lock_errors,
        "attempt_rps": attempt_rps,
        "success_rps": success_rps,
        "error_rate": error_rate,
        "p50": percentile(latencies, 0.50),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
    }


def print_result(result: dict) -> None:
    print(
        f"{result['variant']:<23} "
        f"c={result['concurrency']:<3} "
        f"journal={result['journal_mode']:<6} "
        f"sync={result['synchronous']} "
        f"ok={result['ok']:<4} "
        f"err={result['errors']:<3} "
        f"locks={result['lock_errors']:<3} "
        f"attempt_rps={result['attempt_rps']:>7.2f} "
        f"success_rps={result['success_rps']:>7.2f} "
        f"error_rate={result['error_rate']:>6.2f}% "
        f"p50={result['p50']:>8.2f}ms "
        f"p95={result['p95']:>8.2f}ms "
        f"p99={result['p99']:>8.2f}ms"
    )


def print_summary(
    collected: dict[tuple[str, int], list[dict]]
) -> None:
    print()
    print("MEDIAN ACROSS REPEATS")
    print("=" * 150)

    for key in sorted(
        collected,
        key=lambda item: (item[1], item[0]),
    ):
        variant, concurrency = key
        rows = collected[key]

        median_success_rps = statistics.median(
            row["success_rps"] for row in rows
        )

        median_error_rate = statistics.median(
            row["error_rate"] for row in rows
        )

        median_locks = statistics.median(
            row["lock_errors"] for row in rows
        )

        median_p50 = statistics.median(
            row["p50"] for row in rows
        )

        median_p95 = statistics.median(
            row["p95"] for row in rows
        )

        median_p99 = statistics.median(
            row["p99"] for row in rows
        )

        print(
            f"{variant:<23} "
            f"c={concurrency:<3} "
            f"median_success_rps={median_success_rps:>7.2f} "
            f"median_error_rate={median_error_rate:>6.2f}% "
            f"median_locks={median_locks:>5.1f} "
            f"median_p50={median_p50:>8.2f}ms "
            f"median_p95={median_p95:>8.2f}ms "
            f"median_p99={median_p99:>8.2f}ms"
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

    parser.add_argument(
        "--levels",
        default="1,5,10,20,40",
    )

    args = parser.parse_args()

    levels = parse_levels(args.levels)

    print()
    print("SQLITE CONCURRENCY: CURRENT VS WAL+PERSISTENT")
    print("=" * 150)

    print(f"Python: {sys.version.split()[0]}")
    print(f"SQLite: {sqlite3.sqlite_version}")
    print(f"Platform: {platform.platform()}")
    print(f"Requests per round: {args.requests}")
    print(f"Repeats: {args.repeats}")
    print(f"Concurrency levels: {levels}")

    variants = [
        (
            "current",
            "DELETE",
            False,
        ),
        (
            "wal_persistent",
            "WAL",
            True,
        ),
    ]

    collected = {
        (name, concurrency): []
        for name, _, _ in variants
        for concurrency in levels
    }

    rng = random.Random(42)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        for repeat in range(args.repeats):
            print()
            print(f"REPEAT {repeat + 1}")
            print("-" * 150)

            cases = [
                (
                    name,
                    journal_mode,
                    persistent,
                    concurrency,
                )
                for concurrency in levels
                for (
                    name,
                    journal_mode,
                    persistent,
                ) in variants
            ]

            rng.shuffle(cases)

            for (
                name,
                journal_mode,
                persistent,
                concurrency,
            ) in cases:

                database_path = (
                    root
                    / (
                        f"r{repeat + 1}_"
                        f"{name}_"
                        f"c{concurrency}.db"
                    )
                )

                result = run_round(
                    database_path=database_path,
                    variant=name,
                    journal_mode=journal_mode,
                    persistent=persistent,
                    concurrency=concurrency,
                    total_requests=args.requests,
                )

                collected[
                    (name, concurrency)
                ].append(result)

                print_result(result)

    print_summary(collected)


if __name__ == "__main__":
    main()