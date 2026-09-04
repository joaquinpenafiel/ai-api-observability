import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from src.config import settings
from src.database import initialize_database
from src.logging_config import configure_logging
from src.request_context import request_id_context
from src.services.ai_client import analyze_text
from src.services.ai_metrics import (
    record_ai_failure,
    record_ai_success,
    start_ai_timer,
)
from src.services.gemini_client import analyze_text_with_gemini
from src.services.github_client import fetch_repository

from src.services.webhook_security import verify_webhook_signature

configure_logging()
initialize_database()

logger = logging.getLogger("api")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Reproducible laboratory for REST API integration "
        "and data processing."
    ),
    version=settings.app_version,
)


class ProcessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source: str = Field(default="manual")


class AIAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    instruction: str = Field(
        default=(
            "Summarize the text clearly in three "
            "concise bullet points."
        ),
        min_length=1,
        max_length=500,
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = (
        request.headers.get("X-Request-ID")
        or str(uuid4())
    )

    context_token = request_id_context.set(request_id)
    start_time = time.perf_counter()

    try:
        try:
            response = await call_next(request)

        except Exception:
            duration_ms = (
                time.perf_counter() - start_time
            ) * 1000

            logger.exception(
                "Unhandled request error",
                extra={
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise

        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed",
            extra={
                "request_method": request.method,
                "request_path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response

    finally:
        request_id_context.reset(context_token)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/process")
def process_data(payload: ProcessRequest):
    normalized_text = " ".join(payload.text.split())

    return {
        "source": payload.source,
        "original_text": payload.text,
        "normalized_text": normalized_text,
        "character_count": len(normalized_text),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/github/{owner}/{repo}")
async def github_repository(owner: str, repo: str):
    return await fetch_repository(owner, repo)


@app.post("/ai/analyze")
async def ai_analyze(payload: AIAnalyzeRequest):
    return await analyze_text(
        text=payload.text,
        instruction=payload.instruction,
    )


@app.post("/ai/gemini/analyze")
async def gemini_analyze(payload: AIAnalyzeRequest):
    started_at = start_ai_timer()

    try:
        result = await analyze_text_with_gemini(
            text=payload.text,
            instruction=payload.instruction,
        )

    except HTTPException as exc:
        record_ai_failure(
            started_at=started_at,
            provider="gemini",
            model=settings.gemini_model,
            status=f"http_{exc.status_code}",
        )

        raise

    usage = result.get("usage", {})

    record_ai_success(
        started_at=started_at,
        provider=result["provider"],
        model=result["model"],
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )

    return result


@app.post("/webhooks/inbound")
async def inbound_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature")

    verify_webhook_signature(
        payload=payload,
        signature=signature,
    )

    return {
        "status": "accepted",
        "payload_bytes": len(payload),
    }
