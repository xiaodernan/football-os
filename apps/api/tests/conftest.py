"""Test configuration: SQLite by default, or a dedicated database via FOOTBALL_OS_TEST_DATABASE_URL.

ADR-002 keeps SQLite as the local fallback; the Postgres leg is what CI and production run, so
``FOOTBALL_OS_TEST_DATABASE_URL=postgresql+psycopg2://… pytest`` must point at a throwaway database.
"""

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
os.environ["DATABASE_URL"] = os.environ.get("FOOTBALL_OS_TEST_DATABASE_URL") or f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["STORAGE_DIR"] = str(Path(tempfile.gettempdir()) / "football_os_test_storage")  # M5 uploads land here, not in the repo tree.
os.environ["APP_SECRET"] = "test-secret-not-for-production"
os.environ["ENV"] = "test"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

if os.environ["DATABASE_URL"].startswith("sqlite") and _DB_PATH.exists():
    _DB_PATH.unlink()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    from app.core.db import Base, SessionLocal, engine, init_db
    from app.seed_data import seed_catalogue
    from app.services.knowledge import sync_knowledge

    if not os.environ["DATABASE_URL"].startswith("sqlite"):
        # A server-backed run reuses one database, so tests can hardcode emails; start empty.
        if "test" not in os.environ["DATABASE_URL"].lower():
            raise RuntimeError("FOOTBALL_OS_TEST_DATABASE_URL must name a throwaway database containing 'test'.")
        Base.metadata.drop_all(bind=engine)
    init_db()
    session = SessionLocal()
    try:
        seed_catalogue(session)
        # The API ingests the corpus on boot, so tests must see the same universe it serves.
        report = sync_knowledge(session)
        if not report.ok:
            raise RuntimeError("knowledge ingestion failed for the test database: " + "; ".join(report.errors))
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
