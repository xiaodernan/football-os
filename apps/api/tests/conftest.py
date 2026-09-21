"""Test configuration: an isolated SQLite database per run (ADR-002 fallback path)."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

_DB_PATH = Path(tempfile.gettempdir()) / "football_os_tests.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["APP_SECRET"] = "test-secret-not-for-production"
os.environ["ENV"] = "test"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

if _DB_PATH.exists():
    _DB_PATH.unlink()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    from app.core.db import SessionLocal, init_db
    from app.seed_data import seed_catalogue

    init_db()
    session = SessionLocal()
    try:
        seed_catalogue(session)
    finally:
        session.close()
    yield


@pytest.fixture()
def client() -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client) -> Iterator:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"user-{uuid.uuid4().hex[:10]}@example.test",
            "password": "strong-pass-1234",
            "display_name": "Test User",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    yield client
    client.headers.pop("Authorization", None)


@pytest.fixture()
def player_id(auth_client) -> str:  # type: ignore[no-untyped-def]
    response = auth_client.post(
        "/api/v1/players",
        json={"name": "Test Midfielder", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])
