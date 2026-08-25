import httpx
from fastapi import HTTPException


GITHUB_API_BASE = "https://api.github.com"


async def fetch_repository(owner: str, repo: str):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "api-integration-lab",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="GitHub API request timed out.",
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to GitHub API.",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Repository not found.",
        )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API returned status {response.status_code}.",
        )

    data = response.json()

    return {
        "repository": data["full_name"],
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues": data["open_issues_count"],
        "url": data["html_url"],
    }