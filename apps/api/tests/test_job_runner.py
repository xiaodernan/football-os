"""The drain: one bare claiming race at a time, both engines, nothing claimed twice.

The compare-and-set claim is the whole point — `SKIP LOCKED` is not available on SQLite, so the
queue's correctness on both legs of CI rides on the conditional update's rowcount. This file is the
witness it works both ways.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.core.db import SessionLocal, init_db
from app.models import Job, User
from app.services import jobs as runner


@pytest.fixture()
def db() -> Iterator[Any]:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _queued(db: Any, ident: str, job_type: str = "test_job") -> Job:
    user = User(id=f"usr_{ident}", email=f"{ident}@runner.test", password_hash="x", display_name=ident, role="player")
    db.add(user)
    db.commit()
    job = Job(id=f"job_{ident}", type=job_type, status="QUEUED", payload={}, user_id=user.id)
    db.add(job)
    db.commit()
    return job


def test_a_claim_marks_the_row_running_and_bumps_its_attempts(db: Any) -> None:
    job = _queued(db, "claim_one")
    claimed = runner.claim(db, limit=1)
    assert [row.id for row in claimed] == [job.id]
    db.refresh(job)
    assert job.status == "RUNNING" and job.attempts == 1 and job.lease_expires_at is not None


def test_a_second_claim_does_not_see_what_the_first_already_claimed(db: Any) -> None:
    """The compare-and-set race, one worker at a time: rowcount 1 for exactly one of them."""
    job = _queued(db, "race_one")
    first = runner.claim(db, limit=1)
    second = runner.claim(db, limit=1)  # the row is RUNNING now; the conditional update finds nothing
    assert [row.id for row in first] == [job.id]
    assert second == []


def test_the_drain_runs_the_registered_handler_and_marks_it_completed(db: Any) -> None:
    job = _queued(db, "drain_ok", job_type="ingest")
    ran: list[str] = []

    def handle(row: Job) -> dict[str, Any]:
        ran.append(row.id)
        return {"chunks": 155}

    outcome = runner.drain_one(db, handlers={"ingest": handle})
    assert outcome is not None and outcome.id == job.id
    db.refresh(job)
    assert ran == [job.id], "the registered handler received the claimed row"
    assert job.status == "COMPLETED" and job.progress == 100 and (job.result or {}).get("chunks") == 155


def test_the_drain_fails_not_holds_a_job_no_handler_knows(db: Any) -> None:
    """A type nothing registered is FAILED with the answer in the error, never a silent hold."""
    job = _queued(db, "drain_unknown", job_type="nope")
    outcome = runner.drain_one(db, handlers={})
    assert outcome is not None and outcome.id == job.id
    db.refresh(job)
    assert job.status == "FAILED" and "no handler registered" in (job.error or "")


def test_a_handler_that_raises_leaves_the_job_failed_not_the_queue_poisoned(db: Any) -> None:
    job = _queued(db, "drain_raise", job_type="boom")

    def explode(_row: Job) -> dict[str, Any]:
        raise RuntimeError("the ingest door is down")

    outcome = runner.drain_one(db, handlers={"boom": explode})
    assert outcome is not None
    db.refresh(job)
    assert job.status == "FAILED" and "RuntimeError" in (job.error or "") and "the ingest door is down" in (job.error or "")


def test_the_drain_claims_in_created_order(db: Any) -> None:
    first = _queued(db, "order_one")
    second = _queued(db, "order_two")
    _ = first, second
    outcome = runner.drain_one(db, handlers={"test_job": lambda row: {"seen": [row.id]}})
    assert outcome is not None and outcome.id == "job_order_one"
