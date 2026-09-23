"""Test configuration: SQLite by default, or a dedicated database via FOOTBALL_OS_TEST_DATABASE_URL.

ADR-002 keeps SQLite as the local fallback; the Postgres leg is what CI and production run, so
``FOOTBALL_OS_TEST_DATABASE_URL=postgresql+psycopg2://… pytest`` must point at a throwaway database.
Whichever engine a run uses, it owns the storage it clears: a server-backed run gets its own database,
and a file-backed run gets its own file, so two overlapping runs never share a schema.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

_DB_PATH = Path(tempfile.gettempdir()) / f"football_os_tests_{uuid.uuid4().hex[:6]}.db"
os.environ["DATABASE_URL"] = os.environ.get("FOOTBALL_OS_TEST_DATABASE_URL") or f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["STORAGE_DIR"] = str(Path(tempfile.gettempdir()) / "football_os_test_storage")  # M5 uploads land here, not in the repo tree.
os.environ["APP_SECRET"] = "test-secret-not-for-production"
os.environ["ENV"] = "test"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,58}")


def _run_scoped_url(url: str) -> str:
    """Repoint a server-backed test URL at a database name only this run owns.

    The session fixture begins by emptying the schema, so two overlapping runs on one fixed name make
    each other's tables vanish mid-test. The failure then lands in whichever query happens to run first
    — in practice a `relation "training_drills" does not exist` raised inside a test that asserts a 403
    and never touches that table — and disappears on a rerun, which is the worst shape a defect can
    take. A name per run removes the race instead of retrying it.

    The rewrite is pure string work, done here at import rather than in the fixture, because a test
    module importing an app module binds `app.core.db.engine` to `DATABASE_URL` at that moment; waiting
    until the fixture runs would leave the engine pointed at the old name. The database itself is only
    created by the fixture, so `--collect-only` leaves nothing behind.
    """
    if url.startswith("sqlite"):
        return url
    parsed = make_url(url)
    if parsed.database is None or not _IDENTIFIER.fullmatch(parsed.database):
        raise RuntimeError(f"test database name {parsed.database!r} is not a plain identifier; this fixture has to create and drop it")
    if "test" not in parsed.database.lower():
        raise RuntimeError("FOOTBALL_OS_TEST_DATABASE_URL must name a throwaway database containing 'test'.")
    # `str(url)` renders the password as `***`, which then authenticates as a literal asterisk. The
    # value goes into DATABASE_URL, so it has to be the real render.
    return parsed.set(database=f"{parsed.database}_{uuid.uuid4().hex[:6]}").render_as_string(hide_password=False)


os.environ["DATABASE_URL"] = _run_scoped_url(os.environ["DATABASE_URL"])

# The file this run may delete: its own generated one, never a path someone pointed the run at, and
# never the shared default another overlapping run is using (`init_db` creates the schema, so a fresh
# name needs no clearing).
_OWNED_SQLITE_FILE: Path | None = None
if os.environ["DATABASE_URL"] == f"sqlite:///{_DB_PATH.as_posix()}":
    _OWNED_SQLITE_FILE = _DB_PATH


def _maintenance_engine(url: str):  # type: ignore[no-untyped-def]
    """An AUTOCOMMIT, NullPool connection to the server's maintenance database.

    `CREATE/DROP DATABASE` cannot run inside a transaction, and a pooled connection would keep the very
    database being dropped open, so both settings are load-bearing here.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    parsed = make_url(url)
    return create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool)


def _provision(url: str) -> str:
    """Create this run's database plus the extension its columns need, and hand back its name.

    `vector` is not in `template1` on this server — it was installed per database — so a freshly created
    database has to gain it before `init_db()` reaches `knowledge_chunks.embedding`.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    name = str(make_url(url).database)
    maintenance = _maintenance_engine(url)
    try:
        with maintenance.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        maintenance.dispose()
    target = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with target.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as error:  # noqa: BLE001 - a half-created database must not outlive the reason it failed
        target.dispose()
        _release(url, name)
        raise RuntimeError(f"could not prepare the isolated test database {name!r}: {error}") from None
    target.dispose()
    return name


def _release(url: str, name: str) -> None:
    """Drop the run's database. FORCE so a connection still in a pool cannot hold it open."""
    from sqlalchemy import text

    maintenance = _maintenance_engine(url)
    try:
        with maintenance.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        maintenance.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    from app.core.db import SessionLocal, engine, init_db
    from app.seed_data import seed_catalogue
    from app.services.knowledge import sync_knowledge

    run_database: str | None = None
    if not os.environ["DATABASE_URL"].startswith("sqlite"):
        # A server-backed run gets its own database, so tests can still hardcode emails and start empty.
        run_database = _provision(os.environ["DATABASE_URL"])
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
    if run_database is not None:
        engine.dispose()
        _release(os.environ["DATABASE_URL"], run_database)
    elif _OWNED_SQLITE_FILE is not None:
        engine.dispose()
        # A run that named its own file cleans it up, so %TEMP% holds the suites rather than their debris.
        for stale in (_OWNED_SQLITE_FILE, *_OWNED_SQLITE_FILE.parent.glob(f"{_OWNED_SQLITE_FILE.stem}.db-*")):
            stale.unlink(missing_ok=True)


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
