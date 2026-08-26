import asyncio
import logging

import httpx
from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger("api.github")


async def fetch_repository(owner: str, repo: str):
    repository = f"{owner}/{repo}"
    url = f"{settings.github_api_base.rstrip('/')}/repos/{repository}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "api-integration-lab",
    }

    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    max_attempts = settings.github_max_retries + 1

    async with httpx.AsyncClient(
        timeout=settings.github_timeout_seconds
    ) as client:

        for attempt in range(1, max_attempts + 1):

            try:
                response = await client.get(url, headers=headers)

            except httpx.TimeoutException:
                if attempt < max_attempts:
                    delay = settings.github_backoff_seconds * (
                        2 ** (attempt - 1)
                    )

                    logger.warning(
                        (
                            "GitHub API request timed out; "
                            "retrying in %.2f seconds "
                            "(attempt %s/%s)"
                        ),
                        delay,
                        attempt,
                        max_attempts,
                    )

                    await asyncio.sleep(delay)
                    continue

                logger.warning(
                    "GitHub API request timed out after all attempts",
                    extra={
                        "repository": repository,
                    },
                )

                raise HTTPException(
                    status_code=504,
                    detail="GitHub API request timed out.",
                )

            except httpx.RequestError:
                if attempt < max_attempts:
                    delay = settings.github_backoff_seconds * (
                        2 ** (attempt - 1)
                    )

                    logger.warning(
                        (
                            "Unable to connect to GitHub API; "
                            "retrying in %.2f seconds "
                            "(attempt %s/%s)"
                        ),
                        delay,
                        attempt,
                        max_attempts,
                    )

                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "Unable to connect to GitHub API after all attempts",
                    extra={
                        "repository": repository,
                    },
                )

                raise HTTPException(
                    status_code=502,
                    detail="Unable to connect to GitHub API.",
                )

            rate_limit_remaining = response.headers.get(
                "x-ratelimit-remaining"
            )

            is_rate_limited = (
                response.status_code == 429
                or (
                    response.status_code == 403
                    and rate_limit_remaining == "0"
                )
            )

            if is_rate_limited:
                retry_after = response.headers.get("retry-after")
                rate_limit_reset = response.headers.get(
                    "x-ratelimit-reset"
                )

                logger.warning(
                    "GitHub API rate limit exceeded",
                    extra={
                        "repository": repository,
                        "external_status_code": response.status_code,
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_reset": rate_limit_reset,
                        "retry_after": retry_after,
                    },
                )

                response_headers = {}

                if retry_after:
                    response_headers["Retry-After"] = retry_after

                raise HTTPException(
                    status_code=429,
                    detail="GitHub API rate limit exceeded.",
                    headers=response_headers or None,
                )

            if response.status_code >= 500:
                if attempt < max_attempts:
                    delay = settings.github_backoff_seconds * (
                        2 ** (attempt - 1)
                    )

                    logger.warning(
                        (
                            "GitHub API returned %s; "
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

                logger.error(
                    "GitHub API server error after all attempts",
                    extra={
                        "repository": repository,
                        "external_status_code": response.status_code,
                    },
                )

                raise HTTPException(
                    status_code=502,
                    detail=(
                        "GitHub API returned status "
                        f"{response.status_code}."
                    ),
                )

            break

    if response.status_code == 404:
        logger.info(
            "GitHub repository not found",
            extra={
                "repository": repository,
                "external_status_code": response.status_code,
            },
        )

        raise HTTPException(
            status_code=404,
            detail="Repository not found.",
        )

    if response.is_error:
        logger.error(
            "GitHub API returned an error",
            extra={
                "repository": repository,
                "external_status_code": response.status_code,
            },
        )

        raise HTTPException(
            status_code=502,
            detail=f"GitHub API returned status {response.status_code}.",
        )

    data = response.json()

    logger.info(
        "GitHub repository fetched",
        extra={
            "repository": repository,
            "external_status_code": response.status_code,
        },
    )

    return {
        "repository": data["full_name"],
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues": data["open_issues_count"],
        "url": data["html_url"],
    }