from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.main as main_module


client = TestClient(main_module.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()


def test_process():
    response = client.post(
        "/process",
        json={
            "text": "   Hello    API Integration Lab   ",
            "source": "test",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "test"
    assert data["normalized_text"] == "Hello API Integration Lab"
    assert data["character_count"] == 25
    assert "processed_at" in data


def test_process_rejects_empty_text():
    response = client.post(
        "/process",
        json={
            "text": "",
            "source": "test",
        },
    )

    assert response.status_code == 422


def test_github_repository_success(monkeypatch):
    repository_data = {
        "repository": "fastapi/fastapi",
        "description": "Test repository",
        "language": "Python",
        "stars": 100,
        "forks": 20,
        "open_issues": 5,
        "url": "https://github.com/fastapi/fastapi",
    }

    mocked_fetch = AsyncMock(return_value=repository_data)

    monkeypatch.setattr(
        main_module,
        "fetch_repository",
        mocked_fetch,
    )

    response = client.get("/github/fastapi/fastapi")

    assert response.status_code == 200
    assert response.json() == repository_data

    mocked_fetch.assert_awaited_once_with(
        "fastapi",
        "fastapi",
    )


def test_github_repository_not_found(monkeypatch):
    mocked_fetch = AsyncMock(
        side_effect=HTTPException(
            status_code=404,
            detail="Repository not found.",
        )
    )

    monkeypatch.setattr(
        main_module,
        "fetch_repository",
        mocked_fetch,
    )

    response = client.get(
        "/github/does-not-exist/does-not-exist"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Repository not found."
    }