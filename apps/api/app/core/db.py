"""Engine + session management with an honest SQLite fallback (ADR-002)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import API_ROOT, settings


class Base(DeclarativeBase):
    pass


def _build_engine(url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        Path(API_ROOT / "football_os.db").parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False
    kwargs: dict[str, object] = {
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if not url.startswith("sqlite"):
        kwargs.update(pool_size=10, max_overflow=20)
    return create_engine(url, **kwargs)


engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:  # pragma: no cover - trivial
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def has_pgvector(db: Session) -> bool:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return False
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'"))
        return True
    except Exception:
        db.rollback()
        return False


def init_db() -> None:
    """Create tables for fresh local/test databases. Production uses Alembic."""
    from app import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
