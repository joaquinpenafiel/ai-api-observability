import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from src.config import settings
from src.logging_config import configure_logging
from src.services.github_client import fetch_repository
from src.request_context import request_id_context

configure_logging()

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