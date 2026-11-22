"""The queue's third thing: not the row, not the hint, but what an operator can *see*.

ADR-008 made the stream a hint and the database the truth. ADR-006's `to_dead` gave a poison message a
reason and a place to lie. Both were written before anything could read them back, and the gap that left
is the one this file closes:

* **A count is not a clock.** `/metrics/jobs-stream` published `pending`, `undelivered` and
  `dead_length`. Twelve hints that arrived in the last second and twelve that have been ignored for an
  hour are the same three numbers and two different incidents, and nothing in the product could tell
  them apart. These cases pin the arithmetic — every age is the store's clock minus the store's own id,
  so the two processes cannot disagree about it the way M15's limiter refused to.
* **An unknown must not look like a zero.** A store that will not give up its clock answers `None`.
  `0.0` would tell an operator the queue is young, which is the opposite of the truth and the exact
  failure an `except: return 0` writes.
* **A dead letter nobody can open is a `FLUSHALL` waiting to happen.** The reason has been written onto
  every entry since the transport landed; these cases prove a reader exists, reads the reason, and says
  how long the entry has been dead.
* **The loop is the queue.** `app.worker.run` had no case at all: not that a busy tick skips the sleep,
  not that an idle one takes it, not that `--max-jobs` is a real exit, and above all not the promise the
  whole transport rests on — that with no Redis at all the poll loop still carries every row.

The double below is a small stream, not a constant farm: ids come from the clock the fake is set to, the
pending list is ordered by id, and the group's cursor moves when a consumer reads. A figure computed from
it means the same thing it would mean from a server.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.worker as worker
from app.core.db import SessionLocal, init_db
from app.core.job_stream import DEAD_KEY, GROUP, STREAM_KEY, Entry, JobStream
from app.main import app
from app.models import Job, User

_now_ms = 1_700_000_000_000


class StreamDouble:
    """An in-memory Redis Streams: ids from a settable clock, ordering by id, a cursor per group."""

    def __init__(self, *, now_ms: int = _now_ms) -> None:
        self.now_ms = now_ms
        self.entries: list[tuple[int, int, dict[str, str]]] = []
        self.dead: list[tuple[int, int, dict[str, str]]] = []
        self.pending: list[dict[str, Any]] = []
        self.delivered_cursor: tuple[int, int] = (0, 0)
        self.consumers: list[str] = []
        self._seq = 0
        self.refuse_time = False

    # -- the clock ---------------------------------------------------------------------------------

    def set_clock(self, now_ms: int) -> None:
        self.now_ms = now_ms

    def time(self) -> tuple[int, int]:
        if self.refuse_time:
            raise ConnectionError("the store will not say what time it is")
        return self.now_ms // 1000, (self.now_ms % 1000) * 1000

    # -- writing -----------------------------------------------------------------------------------

    def _next_id(self, bucket: list[tuple[int, int, dict[str, str]]]) -> tuple[int, int]:
        self._seq += 1
        return (self.now_ms, self._seq)

    def xadd(self, name: str, fields: dict[str, str], **kwargs: Any) -> str:
        bucket = self.dead if name == DEAD_KEY else self.entries
        milliseconds, sequence = self._next_id(bucket)
        bucket.append((milliseconds, sequence, dict(fields)))
        return f"{milliseconds}-{sequence}"

    def xgroup_create(self, name: str, group: str, **kwargs: Any) -> bool:
        return True

    def xgroup_delconsumer(self, name: str, group: str, consumer: str) -> int:
        if consumer in self.consumers:
            self.consumers.remove(consumer)
        return 1

    def xack(self, name: str, group: str, *ids: str) -> int:
        self.pending = [row for row in self.pending if row["message_id"] not in ids]
        return len(ids)

    def xdel(self, name: str, *ids: str) -> int:
        return 0

    # -- reading -----------------------------------------------------------------------------------

    def xlen(self, name: str) -> int:
        return len(self.dead) if name == DEAD_KEY else len(self.entries)

    def xreadgroup(self, group: str, consumer: str, streams: dict[str, str], **kwargs: Any) -> Any:
        count = int(kwargs.get("count") or 10)
        undelivered = [entry for entry in self.entries if entry[:2] > self.delivered_cursor]
        batch = undelivered[:count]
        if not batch:
            return []
        self.delivered_cursor = batch[-1][:2]
        if consumer not in self.consumers:
            self.consumers.append(consumer)
        for milliseconds, sequence, _fields in batch:
            self.pending.append(
                {
                    "message_id": f"{milliseconds}-{sequence}",
                    "consumer": consumer,
                    "delivery_time": self.now_ms,
                    "times_delivered": 1,
                }
            )
        return [[STREAM_KEY, [[f"{m}-{s}", dict(fields)] for m, s, fields in batch]]]

    def xpending(self, name: str, group: str) -> dict[str, Any]:
        return {"consumers": [{"name": row["consumer"], "pending": 1} for row in self.pending]}

    def xpending_range(self, name: str, group: str, min: str, max: str, count: int, **kwargs: Any) -> Any:
        rows = []
        for row in self.pending[:count]:
            rows.append(
                {
                    "message_id": row["message_id"],
                    "consumer": row["consumer"],
                    "time_since_delivered": self.now_ms - row["delivery_time"],
                    "times_delivered": row["times_delivered"],
                }
            )
        return rows

    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None) -> Any:
        bucket = self.dead if name == DEAD_KEY else self.entries
        low = _parse_id(min[1:] if min.startswith("(") else min) or (0, 0)
        rows = [entry for entry in bucket if entry[:2] >= low]
        if count:
            rows = rows[:count]
        return [[f"{m}-{s}", dict(fields)] for m, s, fields in rows]

    def xrevrange(self, name: str, max: str = "+", min: str = "-", count: int | None = None) -> Any:
        rows = list(reversed(self.xrange(name, min=min, max=max)))
        return rows[:count] if count else rows

    def xinfo_groups(self, name: str) -> Any:
        undelivered = len([entry for entry in self.entries if entry[:2] > self.delivered_cursor])
        return [
            {
                "name": GROUP,
                "consumers": len(self.consumers),
                "pending": len(self.pending),
                "lag": undelivered,
                "last-delivered-id": f"{self.delivered_cursor[0]}-{self.delivered_cursor[1]}",
            }
        ]


def _parse_id(value: str) -> tuple[int, int] | None:
    if value in {"-", "+", ""}:
        return None
    milliseconds, _, sequence = value.partition("-")
    try:
        return int(milliseconds), int(sequence or 0)
    except ValueError:
        return None


def _stream(now_ms: int = _now_ms) -> tuple[JobStream, StreamDouble]:
    fake = StreamDouble(now_ms=now_ms)
    return JobStream(fake), fake


def _publish_two(stream: JobStream, fake: StreamDouble, *, at_ms: int) -> None:
    fake.set_clock(at_ms)
    stream.publish("job_first", "test_job")
    stream.publish("job_second", "test_job")
    fake.set_clock(at_ms + 5_000)


# -- the clock is part of the answer ----------------------------------------------------------------


def test_the_snapshot_ages_the_oldest_hint_nobody_has_taken() -> None:
    """`oldest_undelivered_seconds` is the "no worker is running" clock, and it is the server's."""
    stream, fake = _stream()
    _publish_two(stream, fake, at_ms=_now_ms)
    snapshot = stream.snapshot()
    assert snapshot["undelivered"] == 2, "nothing has been read, so the whole stream is undelivered"
    assert snapshot["oldest_undelivered_seconds"] == 5.0
    assert snapshot["oldest_pending_seconds"] is None, "no message has been delivered, so none is pending"


def test_the_undelivered_window_begins_one_past_the_group_cursor() -> None:
    """The age is of the first hint *after* the cursor, not of the oldest hint in the window.

    This is the arithmetic a `(` exclusive range would have expressed, and the reason it is spelled as
    `ms-(seq+1)` is that `deliveries()` already found redis-py and the server disagree about the symbol.
    Read the cursor itself and the second hint's age would be attributed to the first.
    """
    stream, fake = _stream()
    _publish_two(stream, fake, at_ms=_now_ms)
    stream.read("c1", count=1)
    fake.set_clock(_now_ms + 9_000)
    snapshot = stream.snapshot()
    assert snapshot["undelivered"] == 1
    assert snapshot["oldest_undelivered_seconds"] == 9.0, "the second hint was added at the same instant as the first, so its age is the whole elapsed clock"
    assert snapshot["oldest_pending_seconds"] == 9.0


def test_the_age_of_a_hint_and_the_silence_of_its_consumer_are_different_figures() -> None:
    """A hint can be old and freshly delivered at once, and an operator needs both numbers.

    The first hint entered the queue at `T`, was handed to a consumer at `T + 3 s`, and the clock now
    reads `T + 10 s`. `oldest_pending_seconds` is ten; `pending_idle_seconds` is seven. Collapse them
    into one field and the two diagnoses they support — "the work is late" and "the worker has stopped
    talking" — collapse with them.
    """
    stream, fake = _stream()
    fake.set_clock(_now_ms)
    stream.publish("job_first", "test_job")
    fake.set_clock(_now_ms + 3_000)
    stream.read("c1", count=8)
    fake.set_clock(_now_ms + 10_000)
    snapshot = stream.snapshot()
    assert snapshot["oldest_pending_seconds"] == 10.0
    assert snapshot["pending_idle_seconds"] == 7.0
    assert snapshot["pending_sampled"] == 1


def test_the_idle_figure_is_the_quietest_consumer_in_the_window_not_the_oldest_hint() -> None:
    """Two hints, delivered at different instants: the maximum silence wins, not the first row."""
    stream, fake = _stream()
    fake.set_clock(_now_ms)
    stream.publish("job_first", "test_job")
    stream.read("c1", count=8)
    fake.set_clock(_now_ms + 4_000)
    stream.publish("job_second", "test_job")
    stream.read("c2", count=8)
    fake.set_clock(_now_ms + 6_000)
    snapshot = stream.snapshot()
    assert snapshot["pending_sampled"] == 2
    assert snapshot["oldest_pending_seconds"] == 6.0, "both hints share the first millisecond"
    assert snapshot["pending_idle_seconds"] == 6.0, "the first consumer has been silent since the first delivery"


def test_a_store_that_will_not_tell_time_answers_unknown_and_never_zero() -> None:
    """The one case that decides whether an outage can be misread as an idle queue."""
    stream, fake = _stream()
    _publish_two(stream, fake, at_ms=_now_ms)
    fake.refuse_time = True
    snapshot = stream.snapshot()
    assert snapshot["oldest_undelivered_seconds"] is None
    assert snapshot["oldest_pending_seconds"] is None
    assert snapshot["pending_idle_seconds"] is None
    assert snapshot["undelivered"] == 2, "the counts the store can give are still given"


def test_the_door_publishes_the_same_age_keys_with_and_without_a_store() -> None:
    """A reader must not guess whether an absent field means "no backlog" or "no Redis"."""
    empty = JobStream(None).snapshot()
    stream, fake = _stream()
    _publish_two(stream, fake, at_ms=_now_ms)
    full = stream.snapshot()
    ages = {"oldest_undelivered_seconds", "oldest_pending_seconds", "pending_idle_seconds", "pending_sampled"}
    assert ages <= set(empty), f"the degraded snapshot lost {sorted(ages - set(empty))}"
    assert all(key in full for key in ages)
    assert empty["oldest_undelivered_seconds"] is None and empty["pending_sampled"] == 0


# -- the pile that will never succeed ---------------------------------------------------------------


def test_a_dead_letter_reads_back_with_its_reason_and_its_age() -> None:
    """The reason has been written since ADR-006; this is the reader that makes it actionable."""
    stream, fake = _stream()
    fake.set_clock(_now_ms)
    stream.publish("job_poison", "test_job")
    entry = Entry(f"{_now_ms}-1", "job_poison", "test_job", deliveries=6)
    assert stream.to_dead(entry, reason="delivered 6 times without an acknowledgement") is True
    fake.set_clock(_now_ms + 120_000)
    letters = stream.dead_letters()
    assert len(letters) == 1
    letter = letters[0]
    assert letter["job_id"] == "job_poison"
    assert letter["reason"].startswith("delivered 6 times"), "the reason is the whole point of the pile"
    assert letter["deliveries"] == 6
    assert letter["original_id"] == entry.id
    assert letter["dead_for_seconds"] == 120.0


def test_the_dead_letter_read_is_newest_first_and_bounded_by_what_was_asked() -> None:
    stream, fake = _stream()
    for index in range(3):
        stream.to_dead(Entry(f"{_now_ms + index}-1", f"job_{index}", "test_job", deliveries=5), reason=f"reason {index}")
    letters = stream.dead_letters(limit=2)
    assert [letter["job_id"] for letter in letters] == ["job_2", "job_1"], "newest first, and the oldest is the one a `limit` drops"


def test_no_store_and_an_empty_pile_are_both_answered_without_an_error() -> None:
    assert JobStream(None).dead_letters() == []
    stream, _fake = _stream()
    assert stream.dead_letters() == []


# -- the doors that publish them --------------------------------------------------------------------


def test_the_dead_letter_door_answers_the_operator_with_the_shape_it_documents(admin_client: TestClient) -> None:
    refused = TestClient(app).get("/api/v1/metrics/jobs-stream/dead")
    assert refused.status_code == 401, "the door describes the deployment, so it does not answer anonymously"
    answered = admin_client.get("/api/v1/metrics/jobs-stream/dead")
    assert answered.status_code == 200, answered.text[:300]
    body = answered.json()
    assert {"available", "stream", "asked", "returned", "letters"} <= set(body)
    assert body["stream"] == DEAD_KEY
    assert body["returned"] == len(body["letters"]) <= body["asked"]
    assert "dead_length" not in body, "the total is /jobs-stream's figure and this door does not mint a second copy of it"


def test_the_dead_letter_door_refuses_a_limit_outside_its_bounds(admin_client: TestClient) -> None:
    """`limit` is a read the store performs, so the door bounds it rather than honouring a number."""
    refused = admin_client.get("/api/v1/metrics/jobs-stream/dead", params={"limit": 0})
    assert refused.status_code == 422, f"a zero-length read was accepted: {refused.text[:200]}"
    capped = admin_client.get("/api/v1/metrics/jobs-stream/dead", params={"limit": 5_000})
    assert capped.status_code == 422, "an unbounded read would XREVRANGE the whole pile on a request thread"


# -- the loop is the queue --------------------------------------------------------------------------


#: Rows this module created, torn down with the fixture below.
_created: list[tuple[str, str]] = []


@pytest.fixture()
def db() -> Iterator[Any]:
    """A session, and a promise that the rows this file leaves QUEUED are gone when it ends.

    `test_job_broker.py` documented the hazard: the test database is shared, so a `QUEUED` row that
    outlives its case is picked up by the next file's `claim(limit=1)` and fails three files away from
    its cause. The loop cases here create three echo jobs and execute one by design.
    """
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


def _echo_job(db: Any) -> str:
    ident = uuid4().hex[:8]
    user = User(id=f"usr_q{ident}", email=f"q{ident}@queue.test", password_hash="x", display_name=f"q{ident}", role="player")
    db.add(user)
    db.commit()
    job = Job(id=f"job_q{ident}", type="system.echo", status="QUEUED", payload={}, user_id=user.id)
    db.add(job)
    db.commit()
    _created.append((job.id, user.id))
    return job.id


def test_the_tick_carries_the_queue_when_no_stream_exists(db: Any) -> None:
    """The promise the whole transport rests on: a lost hint costs a tick, never a job.

    `test_drain_stream_without_a_store_reports_nothing_done` next door proves the stream half returns
    zero. This proves the other half — that the row is not forgotten with it — which is what makes
    `poll_fallback` the queue's floor rather than a legacy path.

    The tick is bounded per pass (`TICK_POLL_FALLBACK` board rows) and claims the oldest row first, and
    the shared test database carries QUEUED rows other modules leave behind, so one tick's slots are
    not necessarily this row's. The promise being proved is *drain toward empty*, so the case ticks
    until the board has answered this row and asserts the row's own state, not a tick count.
    """
    from app.services import job_broker
    from app.services.job_handlers import handlers as build_handlers

    job_id = _echo_job(db)
    executed = 0
    for _ in range(8):
        executed += job_broker.tick(db, consumer="c1", handlers=build_handlers(), stream=JobStream(None))
        db.expire_all()
        if db.get(Job, job_id).status != "QUEUED":
            break
    assert executed >= 1, "a QUEUED row with no hint anywhere is still work the tick must find"
    assert db.get(Job, job_id).status == "COMPLETED", "the poll loop is the floor: the row survives the missing hint"


def test_a_busy_tick_does_not_sleep_and_an_idle_one_does(db: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sleep is what makes an idle worker cost nothing; skipping it is what makes a drain fast.

    `--once` exits at the idle tick *before* the sleep, so this walks the loop the way a deployed
    worker runs it: no budget, no once-flag, and the fake sleep raises the stop the second idle tick
    would have slept through. That shape is also the only one that proves the sleep is on the
    `done == 0` branch rather than on a timer.
    """
    sleeps: list[float] = []
    left: list[str] = []

    class LeavingStream(JobStream):
        def leave(self, consumer: str) -> bool:
            left.append(consumer)
            return True

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        worker._stopping = True

    monkeypatch.setattr(worker.time, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "get_job_stream", lambda: LeavingStream(None))
    worker._stopping = False
    job_id = _echo_job(db)
    executed = worker.run(consumer="c1", interval=0.25, max_jobs=None, sweep_every=0, once=False)
    assert executed >= 1, "the tick that found the job should have run it"
    assert sleeps == [0.25], f"exactly one idle tick should have slept, got {sleeps}"
    assert left == ["c1"], "the loop leaves the group on the way out, however it was stopped"
    db.expire_all()
    assert db.get(Job, job_id).status == "COMPLETED"


def test_the_loop_spends_its_budget_inside_the_tick_not_only_between_ticks(db: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--max-jobs` is a ceiling, not a checkpoint.

    One tick drains the stream (`TICK_LIMIT`) and then the board (`TICK_POLL_FALLBACK`), so before the
    loop sized a tick by what was left, `--max-jobs 1` with three rows queued executed all three in its
    first tick and only then noticed it was over budget. `docs/runbooks/jobs.md` calls that flag the
    ceiling for a cron sweep, which is the promise this case holds.
    """
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)
    left: list[str] = []

    class LeavingStream(JobStream):
        def leave(self, consumer: str) -> bool:
            left.append(consumer)
            return True

    monkeypatch.setattr(worker, "get_job_stream", lambda: LeavingStream(None))
    worker._stopping = False
    for _ in range(3):
        _echo_job(db)
    executed = worker.run(consumer="c9", interval=0, max_jobs=1, sweep_every=0, once=True)
    assert executed == 1, f"the tick spent past its budget: {executed}"
    assert left == ["c9"], "a consumer that exits cleanly must stop counting as a live worker"
