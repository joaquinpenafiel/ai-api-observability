import asyncio
import logging

import httpx
from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger("api.ai")


async def analyze_text(text: str, instruction: str):
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key is not configured")

        raise HTTPException(
            status_code=503,
            detail="AI service is not configured.",
        )

    url = (
        f"{settings.anthropic_api_base.rstrip('/')}"
        "/v1/messages"
    )

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": settings.anthropic_max_tokens,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Task:\n{instruction}\n\n"
                    f"Text:\n{text}"
                ),
            }
        ],
    }

    max_attempts = settings.anthropic_max_retries + 1

    async with httpx.AsyncClient(
        timeout=settings.anthropic_timeout_seconds
    ) as client:

        for attempt in range(1, max_attempts + 1):

            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

            except httpx.TimeoutException:
                if attempt < max_attempts:
                    delay = (
                        settings.anthropic_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    logger.warning(
                        (
                            "Anthropic API request timed out; "
                            "retrying in %.2f seconds "
                            "(attempt %s/%s)"
                        ),
                        delay,
                        attempt,
                        max_attempts,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise HTTPException(
                    status_code=504,
                    detail="AI provider request timed out.",
                )

            except httpx.RequestError:
                if attempt < max_attempts:
                    delay = (
                        settings.anthropic_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    logger.warning(
                        (
                            "Unable to connect to Anthropic API; "
                            "retrying in %.2f seconds "
                            "(attempt %s/%s)"
                        ),
                        delay,
                        attempt,
                        max_attempts,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise HTTPException(
                    status_code=502,
                    detail="Unable to connect to AI provider.",
                )

            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                response_headers = {}

                if retry_after:
                    response_headers["Retry-After"] = retry_after

                raise HTTPException(
                    status_code=429,
                    detail="AI provider rate limit exceeded.",
                    headers=response_headers or None,
                )

            if response.status_code >= 500:
                if attempt < max_attempts:
                    delay = (
                        settings.anthropic_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    await asyncio.sleep(delay)
                    continue

                raise HTTPException(
                    status_code=502,
                    detail=(
                        "AI provider returned status "
                        f"{response.status_code}."
                    ),
                )

            break

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail="AI provider authentication failed.",
        )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=(
                "AI provider returned status "
                f"{response.status_code}."
            ),
        )

    data = response.json()

    text_blocks = [
        block["text"]
        for block in data.get("content", [])
        if (
            block.get("type") == "text"
            and block.get("text")
        )
    ]

    if not text_blocks:
        raise HTTPException(
            status_code=502,
            detail="AI provider returned no text content.",
        )

    output = "\n".join(text_blocks)
    usage = data.get("usage", {})

    logger.info(
        "AI analysis completed",
        extra={
            "model": data.get(
                "model",
                settings.anthropic_model,
            ),
            "external_status_code": response.status_code,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        },
    )

    return {
        "provider": "anthropic",
        "model": data.get(
            "model",
            settings.anthropic_model,
        ),
        "output": output,
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        },
    }
