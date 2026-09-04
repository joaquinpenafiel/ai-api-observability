import asyncio
import logging

import httpx
from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger("api.gemini")


async def analyze_text_with_gemini(
    text: str,
    instruction: str,
):
    if not settings.gemini_api_key:
        logger.error("Gemini API key is not configured")

        raise HTTPException(
            status_code=503,
            detail="Gemini AI service is not configured.",
        )

    url = (
        f"{settings.gemini_api_base.rstrip('/')}/v1beta/"
        f"models/{settings.gemini_model}:generateContent"
    )

    headers = {
        "x-goog-api-key": settings.gemini_api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"Task:\n{instruction}\n\n"
                            f"Text:\n{text}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": settings.gemini_max_tokens,
        },
    }

    max_attempts = settings.gemini_max_retries + 1

    async with httpx.AsyncClient(
        timeout=settings.gemini_timeout_seconds
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
                        settings.gemini_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    logger.warning(
                        (
                            "Gemini API request timed out; "
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
                    detail="Gemini API request timed out.",
                )

            except httpx.RequestError:
                if attempt < max_attempts:
                    delay = (
                        settings.gemini_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    logger.warning(
                        (
                            "Unable to connect to Gemini API; "
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
                    detail="Unable to connect to Gemini API.",
                )

            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")

                logger.warning(
                    "Gemini API rate limit exceeded",
                    extra={
                        "external_status_code": response.status_code,
                        "retry_after": retry_after,
                    },
                )

                response_headers = {}

                if retry_after:
                    response_headers["Retry-After"] = retry_after

                raise HTTPException(
                    status_code=429,
                    detail="Gemini API rate limit exceeded.",
                    headers=response_headers or None,
                )

            if response.status_code >= 500:
                if attempt < max_attempts:
                    delay = (
                        settings.gemini_backoff_seconds
                        * (2 ** (attempt - 1))
                    )

                    logger.warning(
                        (
                            "Gemini API returned %s; "
                            "retrying in %.2f seconds "
                            "(attempt %s/%s)"
                        ),
                        response.status_code,
                        delay,
                        attempt,
                        max_attempts,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Gemini API returned status "
                        f"{response.status_code}."
                    ),
                )

            break

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail="Gemini API authentication failed.",
        )

    if response.is_error:
        logger.error(
            "Gemini API returned an error",
            extra={
                "external_status_code": response.status_code,
            },
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini API returned status "
                f"{response.status_code}."
            ),
        )

    data = response.json()

    candidates = data.get("candidates", [])

    if not candidates:
        raise HTTPException(
            status_code=502,
            detail="Gemini API returned no candidates.",
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    text_blocks = [
        part["text"]
        for part in parts
        if part.get("text")
    ]

    if not text_blocks:
        raise HTTPException(
            status_code=502,
            detail="Gemini API returned no text content.",
        )

    output = "\n".join(text_blocks)
    usage = data.get("usageMetadata", {})

    logger.info(
        "Gemini analysis completed",
        extra={
            "model": settings.gemini_model,
            "external_status_code": response.status_code,
            "input_tokens": usage.get("promptTokenCount"),
            "output_tokens": usage.get(
                "candidatesTokenCount"
            ),
            "total_tokens": usage.get("totalTokenCount"),
        },
    )

    return {
        "provider": "gemini",
        "model": settings.gemini_model,
        "output": output,
        "usage": {
            "input_tokens": usage.get("promptTokenCount"),
            "output_tokens": usage.get(
                "candidatesTokenCount"
            ),
            "total_tokens": usage.get("totalTokenCount"),
        },
    }
