import argparse
import asyncio
import sqlite3
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.database import (
    initialize_database,
    record_ai_request,
)


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


def print_http_result(
    endpoint: str,
    concurrency: int,
    total: int,
    elapsed: float,
    latencies: list[float],
    errors: int,
) -> None:
    rps = total / elapsed if elapsed > 0 else 0.0

    print(
        f"{endpoint:<10} "
        f"c={concurrency:<3} "
        f"n={total:<4} "
        f"ok={len(latencies):<4} "
        f"err={errors:<3} "
        f"rps={rps:>8.2f} "
        f"p50={percentile(latencies, 0.50):>8.2f}ms "
        f"p95={percentile(latencies, 0.95):>8.2f}ms "
        f"p99={percentile(latencies, 0.99):>8.2f}ms"
    )


async def execute_http_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    method: str,
    url: str,
    payload: dict | None,
) -> tuple[float | None, bool]:
    async with semaphore:
        started = time.perf_counter()

        try:
            response = await client.request(
                method,
                url,
                json=payload,
            )

            latency_ms = (
                time.perf_counter() - started
            ) * 1000

            return (
                latency_ms,
                200 <= response.status_code < 300,
            )

        except Exception:
            return None, False


async def run_http_round(
    *,
    base_url: str,
    method: str,
    endpoint: str,
    payload: dict | None,
    concurrency: int,
    total_requests: int,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )

    async with httpx.AsyncClient(
        timeout=10.0,
        limits=limits,
    ) as client:

        # Small warm-up, not included in measurements.
        for _ in range(5):
            try:
                await client.request(
                    method,
                    f"{base_url}{endpoint}",
                    json=payload,
                )
            except Exception:
                pass

        started = time.perf_counter()

        tasks = [
            execute_http_request(
                client,
                semaphore,
                method,
                f"{base_url}{endpoint}",
                payload,
            )
            for _ in range(total_requests)
        ]

        results = await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - started

    latencies = [
        latency
        for latency, success in results
        if success and latency is not None
    ]

    errors = total_requests - len(latencies)

    print_http_result(
        endpoint,
        concurrency,
        total_requests,
        elapsed,
        latencies,
        errors,
    )


async def run_http(
    *,
    base_url: str,
    levels: list[int],
    total_requests: int,
) -> None:
    cases = [
        (
            "POST",
            "/process",
            {
                "text": "load test request",
                "source": "local-load-probe",
            },
        ),
        (
            "GET",
            "/stats",
            None,
        ),
    ]

    print()
    print("HTTP LOAD PROBE")
    print("=" * 110)

    for method, endpoint, payload in cases:
        print()
        print(f"Endpoint: {method} {endpoint}")
        print("-" * 110)

        for concurrency in levels:
            await run_http_round(
                base_url=base_url,
                method=method,
                endpoint=endpoint,
                payload=payload,
                concurrency=concurrency,
                total_requests=total_requests,
            )


def sqlite_write(
    *,
    database_path: Path,
    request_number: int,
    concurrency: int,
) -> tuple[float | None, str | None]:
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
            request_id=(
                f"load-{concurrency}-{request_number}"
            ),
            database_path=database_path,
        )

        latency_ms = (
            time.perf_counter() - started
        ) * 1000

        return latency_ms, None

    except sqlite3.Error as exc:
        return None, str(exc)

    except Exception as exc:
        return None, repr(exc)


def run_sqlite_round(
    *,
    database_path: Path,
    concurrency: int,
    total_requests: int,
) -> None:
    initialize_database(database_path)

    started = time.perf_counter()

    latencies: list[float] = []
    errors: list[str] = []

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(
                sqlite_write,
                database_path=database_path,
                request_number=index,
                concurrency=concurrency,
            )
            for index in range(total_requests)
        ]

        for future in as_completed(futures):
            latency, error = future.result()

            if latency is not None:
                latencies.append(latency)

            if error is not None:
                errors.append(error)

    elapsed = time.perf_counter() - started

    lock_errors = sum(
        1
        for error in errors
        if "locked" in error.lower()
    )

    rps = total_requests / elapsed if elapsed > 0 else 0.0

    print(
        f"sqlite     "
        f"c={concurrency:<3} "
        f"n={total_requests:<4} "
        f"ok={len(latencies):<4} "
        f"err={len(errors):<3} "
        f"locks={lock_errors:<3} "
        f"rps={rps:>8.2f} "
        f"p50={percentile(latencies, 0.50):>8.2f}ms "
        f"p95={percentile(latencies, 0.95):>8.2f}ms "
        f"p99={percentile(latencies, 0.99):>8.2f}ms"
    )


def run_sqlite(
    *,
    levels: list[int],
    total_requests: int,
) -> None:
    print()
    print("SQLITE WRITE CONTENTION PROBE")
    print("=" * 110)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        for concurrency in levels:
            database_path = (
                root
                / f"metrics_c{concurrency}.db"
            )

            run_sqlite_round(
                database_path=database_path,
                concurrency=concurrency,
                total_requests=total_requests,
            )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=("http", "sqlite"),
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=200,
    )

    parser.add_argument(
        "--levels",
        default="1,5,10,20,40",
    )

    args = parser.parse_args()

    levels = parse_levels(args.levels)

    if args.mode == "http":
        asyncio.run(
            run_http(
                base_url=args.base_url.rstrip("/"),
                levels=levels,
                total_requests=args.requests,
            )
        )

    else:
        run_sqlite(
            levels=levels,
            total_requests=args.requests,
        )


if __name__ == "__main__":
    main()
