"""The queue's two halves: the row is the truth, the stream is the wake-up.

The claims this file holds, in the order they matter:

* A hint is a **hint**. With no Redis the worker still drains the board, and with a duplicated hint the
  job still runs once — because the claim is a conditional `UPDATE`, not a message counter.
* An expired lease is the only thing that revives a `RUNNING` row, and a row out of attempts is failed
  rather than resurrected. Without the second rule a poison job is claimed forever.
* A message that will not settle goes to the dead-letter stream **with its reason**, written before the
  acknowledgement — the reverse order loses the only thing that makes a dead letter useful.

The unit cases use a fake client; the `integration` cases skip themselves when `REDIS_URL` does not
point at a live server, which is CI's job to provide (the workflow starts the same container the
compose file publishes).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.core.db import SessionLocal, init_db
from app.core.job_stream import GROUP, MAX_DELIVERIES, Entry, JobStream
from app.models import Job, User
from app.services import job_broker
from app.services import jobs as runner
from app.services.job_handlers import clear_cache, register, registered_types
from app.services.job_handlers import handlers as build_handlers

#: Rows this module created, torn down with the fixture. Without it the shared test database keeps the
#: QUEUED rows these cases leave behind, and the next file's `claim(limit=1)` picks one of them instead
#: of its own — a failure in `test_job_runner`, three files away from its cause.
_created: list[tuple[str, str]] = []


@pytest.fixture()
def db() -> Iterator[Any]:
    init_db()
    session = SessionLocal()
    _created.clear()
    try:
        yield session
    finally:
        for job_id, user_id in _created:
            session.query(Job).filter(Job.id == job_id).delete()
            session.query(User).filter(User.id == user_id).delete()
        session.commit()
        session.close()
        _created.clear()


def _queued(db: Any, ident: str, job_type: str = "test_job", *, status: str = "QUEUED") -> Job:
    ident = f"{ident}_{uuid4().hex[:8]}"
    user = User(id=f"usr_{ident}", email=f"{ident}@broker.test", password_hash="x", display_name=ident, role="player")
    db.add(user)
    db.commit()
    job = Job(id=f"job_{ident}", type=job_type, status=status, payload={}, user_id=user.id)
    db.add(job)
    db.commit()
    _created.append((job.id, user.id))
    return job


class FakeClient:
    """Enough of the Streams surface for the paths under test, in redis-py's return shapes."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, str]]] = []
        self.acked: list[str] = []
        self.dead: list[dict[str, str]] = []
        self.refuse_xadd = False
        self._seq = 0

    def xgroup_create(self, name: str, group: str, **kwargs: Any) -> bool:
        return True

    def xadd(self, name: str, fields: dict[str, str], **kwargs: Any) -> str:
        if self.refuse_xadd:
            raise ConnectionError("upstream refused")
        self._seq += 1
        message_id = f"{self._seq}-0"
        if name.endswith(":dead"):
            self.dead.append(dict(fields))
        else:
            self.messages.append((message_id, dict(fields)))
        return message_id

    def xreadgroup(self, group: str, consumer: str, streams: dict[str, str], **kwargs: Any) -> Any:
        if not self.messages:
            return []
        batch, self.messages = self.messages[:2], self.messages[2:]
        return [["football_os:jobs", [[mid, fields] for mid, fields in batch]]]

    def xautoclaim(self, name: str, group: str, consumer: str, **kwargs: Any) -> Any:
        return ["0-0", [], []]

    def xack(self, name: str, group: str, *ids: str) -> int:
        self.acked.extend(ids)
        return len(ids)

    def xlen(self, name: str) -> int:
        return len(self.dead) if name.endswith(":dead") else len(self.messages)

    def xinfo_groups(self, name: str) -> Any:
        return [{"name": GROUP, "pending": 0, "consumers": 1, "lag": 0}]


# -- the hint is optional -------------------------------------------------------------------------


def test_a_publish_without_a_client_is_a_no_op_rather_than_an_error() -> None:
    stream = JobStream(None)
    assert stream.publish("job_x", "test_job") is None
    assert stream.available is False
    assert stream.publish_failures == 0, "no store configured is a configuration, not a failure"


def test_a_refused_publish_is_counted_and_never_raised() -> None:
    """The row is already committed when this runs; a Redis blip must not become a failed request."""
    fake = FakeClient()
    fake.refuse_xadd = True
    stream = JobStream(fake)
    assert job_broker.publish_queued(Job(id="job_x", type="test_job", status="QUEUED"), stream=stream) is None
    assert stream.publish_failures == 1


def test_a_published_hint_carries_the_id_and_the_type() -> None:
    fake = FakeClient()
    stream = JobStream(fake)
    assert stream.publish("job_42", "video.analyse") == "1-0"
    message_id, fields = fake.messages[0]
    assert fields["job_id"] == "job_42" and fields["type"] == "video.analyse"
    assert stream.published == 1


def test_drain_stream_without_a_store_reports_nothing_done(db: Any) -> None:
    assert job_broker.drain_stream(db, handlers={}, consumer="c1", stream=JobStream(None)) == 0


def test_a_handler_that_raises_leaves_the_job_failed_and_the_message_acknowledged(db: Any) -> None:
    """The message did its job. Retrying it would re-run what the state machine already judged."""
    fake = FakeClient()
    stream = JobStream(fake)
    job = _queued(db, "boom")

    def explode(_job: Job) -> Any:
        raise RuntimeError("handler said no")

    stream.publish(job.id, job.type)
    assert job_broker.drain_stream(db, handlers={"test_job": explode}, consumer="c1", stream=stream) == 1
    db.refresh(job)
    assert job.status == "FAILED" and "handler said no" in (job.error or "")
    assert fake.acked == ["1-0"]


def test_a_duplicate_hint_runs_the_job_once(db: Any) -> None:
    """At-least-once delivery over an exactly-once claim: the second hint finds nothing to claim."""
    fake = FakeClient()
    stream = JobStream(fake)
    job = _queued(db, "twice")
    seen: list[str] = []
    stream.publish(job.id, job.type)
    stream.publish(job.id, job.type)

    assert job_broker.drain_stream(db, handlers={"test_job": lambda row: seen.append(row.id)}, consumer="c1", stream=stream) == 1
    assert job_broker.drain_stream(db, handlers={"test_job": lambda row: seen.append(row.id)}, consumer="c1", stream=stream) == 0
    assert seen == [job.id]
    assert fake.acked == ["1-0", "2-0"], "the hint that lost the race is still answered"


def test_a_hint_naming_a_row_that_is_gone_is_acknowledged_without_error(db: Any) -> None:
    fake = FakeClient()
    stream = JobStream(fake)
    stream.publish("job_that_never_existed", "test_job")
    assert job_broker.drain_stream(db, handlers={}, consumer="c1", stream=stream) == 0
    assert fake.acked == ["1-0"]


def test_a_poison_message_moves_to_the_dead_letter_stream(db: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient()
    stream = JobStream(fake)
    entry = Entry("9-0", "job_poison", "test_job", deliveries=MAX_DELIVERIES + 1)
    # `read` answers delivery count 1 for a fresh message, which is right; a poison message is one the
    # pending list has handed out many times, so the entry is injected at its real count.
    monkeypatch.setattr(stream, "read", lambda consumer, count=8, block_ms=1: [entry])
    assert job_broker.drain_stream(db, handlers={}, consumer="c1", stream=stream) == 0
    assert fake.dead and fake.dead[0]["reason"].startswith("delivered")
    assert fake.dead[0]["job_id"] == "job_poison" and fake.acked == ["9-0"]
    assert stream.dead_lettered == 1


# -- the claim is the truth ----------------------------------------------------------------------


def test_claim_by_id_marks_the_row_running_and_bumps_attempts(db: Any) -> None:
    job = _queued(db, "by_id")
    claimed = runner.claim_by_id(db, job.id)
    assert claimed is not None
    db.refresh(job)
    assert job.status == "RUNNING" and job.attempts == 1 and job.lease_expires_at is not None


def test_claim_by_id_loses_cleanly_to_a_second_claim(db: Any) -> None:
    job = _queued(db, "by_id_race")
    assert runner.claim_by_id(db, job.id) is not None
    assert runner.claim_by_id(db, job.id) is None


def test_claim_by_id_refuses_a_terminal_row(db: Any) -> None:
    job = _queued(db, "done_one", status="COMPLETED")
    assert runner.claim_by_id(db, job.id) is None


def test_claim_by_id_on_a_missing_row_answers_none(db: Any) -> None:
    assert runner.claim_by_id(db, "job_nobody_made") is None


# -- the sweep revives only what a worker actually lost --------------------------------------------


def _running(db: Any, ident: str, *, lease_offset_seconds: int, attempts: int = 1, max_attempts: int = 3) -> Job:
    job = _queued(db, ident, status="RUNNING")
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_offset_seconds)
    job.attempts = attempts
    job.max_attempts = max_attempts
    db.commit()
    return job


def test_requeue_expired_revives_a_lost_lease_without_spending_an_attempt(db: Any) -> None:
    job = _running(db, "lost", lease_offset_seconds=-5)
    revived = runner.requeue_expired(db)
    assert job.id in [row.id for row in revived]
    db.refresh(job)
    assert job.status == "QUEUED" and job.lease_expires_at is None
    assert job.attempts == 1, "the claim already counted this attempt; the sweep must not count it twice"


def test_requeue_expired_leaves_a_live_lease_alone(db: Any) -> None:
    job = _running(db, "alive", lease_offset_seconds=60)
    assert runner.requeue_expired(db) == []
    db.refresh(job)
    assert job.status == "RUNNING"


def test_requeue_expired_fails_a_job_that_spent_its_attempts(db: Any) -> None:
    job = _running(db, "poison", lease_offset_seconds=-1, attempts=3, max_attempts=3)
    runner.requeue_expired(db)
    db.refresh(job)
    assert job.status == "FAILED" and "max_attempts" in (job.error or "")


def test_requeue_expired_ignores_a_row_that_was_never_claimed(db: Any) -> None:
    """`lease_expires_at IS NULL` is not a lost lease — it is a row nobody has picked up."""
    job = _queued(db, "unclaimed", status="RUNNING")
    job.lease_expires_at = None
    db.commit()
    assert runner.requeue_expired(db) == []
    db.refresh(job)
    assert job.status == "RUNNING"


# -- the registry answers what this build can run -------------------------------------------------


def test_the_registry_can_run_the_types_the_doors_create() -> None:
    clear_cache()
    assert "video.analyse" in registered_types(), "the door creates this type; a worker that cannot run it fails every row"


def test_the_smoke_test_type_runs_without_a_fixture() -> None:
    clear_cache()
    job = Job(id="job_smoke", type="system.echo", status="QUEUED", payload={"ping": 1})
    result = build_handlers()["system.echo"](job)
    assert result["echo"] == {"ping": 1} and result["job_id"] == "job_smoke"


def test_registering_a_type_makes_it_runnable() -> None:
    clear_cache()
    register("test.registered", lambda job: {"ok": job.id})
    assert "test.registered" in registered_types()
    assert "test.registered" in build_handlers()


# -- live Redis ----------------------------------------------------------------------------------


def _live_client() -> Any:
    try:
        import redis

        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1, socket_timeout=2, decode_responses=True)
        client.ping()
        return client
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture()
def live_stream() -> Iterator[JobStream]:
    client = _live_client()
    if client is None:
        pytest.skip("no live Redis at REDIS_URL; the integration cases need one")
    suffix = uuid4().hex[:8]
    stream = JobStream(client, stream=f"football_os:test:jobs:{suffix}", group=f"football_os:test:jobs:{suffix}", dead=f"football_os:test:dead:{suffix}")
    stream.ensure_group()
    try:
        yield stream
    finally:
        for key in (stream.stream, stream.dead):
            client.delete(key)


@pytest.mark.integration
def test_a_live_round_trip_publishes_reads_and_acknowledges(live_stream: JobStream) -> None:
    live_stream.publish("job_live_1", "test_job")
    entries = live_stream.read("c1", count=4, block_ms=50)
    assert [(entry.job_id, entry.job_type) for entry in entries] == [("job_live_1", "test_job")]
    assert live_stream.ack(entries[0].id) == 1
    assert live_stream.snapshot()["pending"] == 0


@pytest.mark.integration
def test_a_group_created_at_dollar_does_not_replay_history() -> None:
    """History is the poll loop's business: replaying it would claim rows that are already done.

    Needs its own stream, because the interesting order is publish-then-create-group — the fixture's
    group already exists by the time a test body runs, which is the normal boot order and the wrong
    order to prove this claim.
    """
    client = _live_client()
    if client is None:
        pytest.skip("no live Redis at REDIS_URL; the integration cases need one")
    suffix = uuid4().hex[:8]
    stream = JobStream(client, stream=f"football_os:test:jobs:{suffix}", group=f"football_os:test:jobs:{suffix}", dead=f"football_os:test:dead:{suffix}")
    try:
        stream.publish("job_before_group", "test_job")
        assert stream.ensure_group()
        stream.publish("job_after_group", "test_job")
        entries = stream.read("c1", count=8, block_ms=50)
        assert [entry.job_id for entry in entries] == ["job_after_group"]
    finally:
        client.delete(stream.stream, stream.dead)


@pytest.mark.integration
def test_reclaim_takes_a_message_from_a_consumer_that_stopped_acknowledging(live_stream: JobStream) -> None:
    live_stream.publish("job_orphan", "test_job")
    first = live_stream.read("dead-consumer", count=1, block_ms=50)
    assert len(first) == 1
    recovered = live_stream.reclaim("live-consumer", min_idle_ms=0, count=4)
    assert [entry.job_id for entry in recovered] == ["job_orphan"]
    assert recovered[0].deliveries == 2, "a reclaim is a second delivery, and the count says so"


@pytest.mark.integration
def test_a_dead_letter_carries_its_reason_and_clears_the_pending_list(live_stream: JobStream) -> None:
    live_stream.publish("job_doomed", "test_job")
    entries = live_stream.read("c1", count=1, block_ms=50)
    assert live_stream.to_dead(entries[0], reason="delivered 6 times without an acknowledgement")
    snapshot = live_stream.snapshot()
    assert snapshot["pending"] == 0 and snapshot["dead_length"] == 1


@pytest.mark.integration
def test_end_to_end_the_hint_runs_the_row_it_names(db: Any, live_stream: JobStream) -> None:
    job = _queued(db, "end_to_end")
    job_broker.publish_queued(job, stream=live_stream)
    assert job_broker.drain_stream(db, handlers={"test_job": lambda row: {"ran": row.id}}, consumer="c1", stream=live_stream) == 1
    db.refresh(job)
    assert job.status == "COMPLETED" and job.result == {"ran": job.id}
    assert live_stream.snapshot()["pending"] == 0


@pytest.mark.integration
def test_a_clean_exit_deregisters_the_consumer(live_stream: JobStream) -> None:
    """`consumers` must mean "processes alive", or the one diagnosis it supports is unreadable."""
    live_stream.publish("job_bye", "test_job")
    entries = live_stream.read("leaver", count=1, block_ms=50)
    live_stream.ack(entries[0].id)
    assert live_stream.snapshot()["consumers"] == 1
    assert live_stream.leave("leaver") is True
    assert live_stream.snapshot()["consumers"] == 0


@pytest.mark.integration
def test_a_consumer_holding_unacked_work_is_not_deregistered(live_stream: JobStream) -> None:
    """Deregistering it would delete its pending entries — the messages reclaim exists to rescue."""
    live_stream.publish("job_hold", "test_job")
    live_stream.read("holder", count=1, block_ms=50)
    assert live_stream.leave("holder") is False
    assert live_stream.snapshot()["pending"] == 1
