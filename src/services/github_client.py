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

    try:
        async with httpx.AsyncClient(
            timeout=settings.github_timeout_seconds
        ) as client:
            response = await client.get(url, headers=headers)

    except httpx.TimeoutException:
        logger.warning(
            "GitHub API request timed out",
            extra={
                "repository": repository,
            },
        )

        raise HTTPException(
            status_code=504,
            detail="GitHub API request timed out.",
        )

    except httpx.RequestError:
        logger.error(
            "Unable to connect to GitHub API",
            extra={
                "repository": repository,
            },
        )

        raise HTTPException(
            status_code=502,
            detail="Unable to connect to GitHub API.",
        )

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