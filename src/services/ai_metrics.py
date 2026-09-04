import time

from src.database import record_ai_request
from src.request_context import request_id_context


def start_ai_timer() -> float:
    return time.perf_counter()


def record_ai_success(
    *,
    started_at: float,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None = None,
) -> None:
    resolved_input_tokens = input_tokens or 0
    resolved_output_tokens = output_tokens or 0

    resolved_total_tokens = (
        total_tokens
        if total_tokens is not None
        else (
            resolved_input_tokens
            + resolved_output_tokens
        )
    )

    latency_ms = (
        time.perf_counter() - started_at
    ) * 1000

    record_ai_request(
        provider=provider,
        model=model,
        input_tokens=resolved_input_tokens,
        output_tokens=resolved_output_tokens,
        total_tokens=resolved_total_tokens,
        latency_ms=round(latency_ms, 2),
        status="success",
        request_id=request_id_context.get(),
    )


def record_ai_failure(
    *,
    started_at: float,
    provider: str,
    model: str,
    status: str,
) -> None:
    latency_ms = (
        time.perf_counter() - started_at
    ) * 1000

    record_ai_request(
        provider=provider,
        model=model,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        latency_ms=round(latency_ms, 2),
        status=status,
        request_id=request_id_context.get(),
    )
