"""The Redis Streams transport under ADR-006's database state machine — the wake-up, not the truth.

ADR-006 chose a database-backed job state machine and left one sentence open: *"the same repository
interface can be driven by Redis/Celery later without touching call sites."* This module is that
sentence, and it is careful about which half of the promise it keeps. The database still owns every
state transition (`QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`), still holds the lease, still
decides who won a race. The stream carries one thing the database cannot: *"something was just queued,
wake up now"*.

That split is what makes the transport cheap to get wrong. A stream message is a **hint**:

* **Lost hint** — the row stays `QUEUED`; the poll loop (`app.services.jobs.drain_one`) finds it on its
  next tick. Delivery is late, never wrong.
* **Duplicated hint** — the worker claims that exact id with the same conditional `UPDATE … WHERE
  status='QUEUED'` the poll path uses; the loser sees `rowcount == 0` and acknowledges. Exactly-once
  execution on top of at-least-once delivery, and the guarantee is the database's, not the stream's.

Three Redis behaviours are load-bearing here and each is written down at its use site: the consumer
group is created with `MKSTREAM` so a fresh instance works with no setup step; `XAUTOCLAIM` recovers a
message whose consumer died mid-handler after a visibility timeout, and a message that exceeds
`max_deliveries` goes to the dead-letter stream with a reason instead of circulating forever; `XADD`
is capped with an approximate `MAXLEN` so a producer storm cannot grow the stream without bound — the
rows are the durable record, the stream is a window.

The client is a second connection to the same instance the cache tier uses. It is deliberately not the
cache's client: that one is created with the cache's timeouts and is torn down by `close_redis_cache()`
on an error path that must not take the queue with it.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Final, cast

import redis

logger = logging.getLogger(__name__)

#: One stream for every job type: the message carries the type, and one stream means one consumer
#: group, one pending list and one number to watch. Partitioning by type would multiply the
#: observability surface to buy parallelism this product does not need yet.
STREAM_KEY: Final = "football_os:jobs"

#: The group name is the contract between producers (the API) and consumers (the worker). Two
#: processes that disagree about it are two queues, and messages would sit unread in a group nobody
#: drains — so it is a constant here, not a per-call argument.
GROUP: Final = "football_os:jobs:workers"

DEAD_KEY: Final = "football_os:jobs:dead"

#: The cap is approximate (`MAXLEN ~`) because trimming exactly on every `XADD` makes the producer pay
#: for the consumer's backlog. Twenty thousand entries is far more than a single node's working set
#: and small enough that a forgotten consumer costs kilobytes, not gigabytes.
STREAM_MAXLEN: Final = 20_000
DEAD_MAXLEN: Final = 1_000

#: How long a message may sit unacknowledged before another consumer may claim it. A handler that
#: legitimately runs longer than this is a handler that should report progress, and ADR-006's lease is
#: the mechanism for that; this number is the transport's copy of the same idea.
PENDING_GRACE_MS: Final = 60_000

#: After this many deliveries the message is not retried again. The job row has its own
#: `max_attempts`; this bound exists so a *poison message* — one whose claim keeps failing for a reason
#: outside the handler — cannot circulate forever.
MAX_DELIVERIES: Final = 5

#: How far into the pending list the age scan looks. `XPENDING` returns the queue in id order, so the
#: first row is the oldest unfinished hint and needs no scan at all; the *most silent* consumer, though,
#: is only knowable by looking at how long each pending row has been idle, and an unbounded scan of a
#: million-entry PEL on an operator door is not a read, it is an outage. The window is reported beside
#: the figure (`pending_sampled`) so the number says what it measured.
PENDING_SAMPLE: Final = 256

#: The age keys as a degraded store publishes them: present, and `None`. Merged into every snapshot, so
#: a reader never has to guess whether an absent age means "no backlog" or "no Redis" — the ages are
#: always there, and `available` is what says which of the two it was.
_UNKNOWN_AGES: Final[dict[str, Any]] = {
    "oldest_undelivered_seconds": None,
    "oldest_pending_seconds": None,
    "pending_idle_seconds": None,
    "pending_sampled": 0,
}


class JobStreamUnavailable(RuntimeError):
    """Raised by `ensure_group` on a live client that refused the group. Never raised by `publish`."""


class Entry:
    """One stream message, parsed. `deliveries` is what the pending list says, not a guess."""

    __slots__ = ("id", "job_id", "job_type", "deliveries")

    def __init__(self, msg_id: str, job_id: str, job_type: str, deliveries: int = 1) -> None:
        self.id = msg_id
        self.job_id = job_id
        self.job_type = job_type
        self.deliveries = deliveries

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Entry(id={self.id!r}, job_id={self.job_id!r}, type={self.job_type!r}, deliveries={self.deliveries})"


def _decode(value: Any) -> str:
    """A field as text. The client asks for `decode_responses=True`; a test double may not."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _id_ms(msg_id: Any) -> int | None:
    """The millisecond part of a stream id — the instant the entry was added, stamped by the server.

    Redis mints `XADD` ids from the server's clock (the same reason M15 reads `TIME` inside the Lua
    script rather than trusting a caller), so an age computed as `server now − id` is one clock's
    subtraction, not two processes' agreement.
    """
    milliseconds, _, _sequence = _decode(msg_id).partition("-")
    try:
        return int(milliseconds)
    except ValueError:
        return None


def _age_seconds(now_ms: int | None, then_ms: int | None) -> float | None:
    """Seconds between two server-clock instants, or `None` when either side is unknown.

    `None` and `0` are different answers and the door must not blur them: `0` says the queue is young,
    `None` says this process could not read the clock. A degraded store has always been allowed to say
    "unknown" here — the alternative is an operator dashboard that reads "0 s" during an outage.
    """
    if now_ms is None or then_ms is None:
        return None
    return round(max(0.0, (now_ms - then_ms) / 1000.0), 3)


def _server_now_ms(client: Any) -> int | None:
    """The store's own clock in milliseconds, or `None` when the store will not say."""
    try:
        seconds, microseconds = cast("Any", client.time())
    except Exception:  # noqa: BLE001 — an unreadable clock is an unknown age, never a zero age
        return None
    try:
        return int(seconds) * 1000 + int(microseconds) // 1000
    except (TypeError, ValueError):
        return None


def _pending_field(row: Any, index: int, key: str) -> Any:
    """One field of a `XPENDING` row, in either shape redis-py has ever returned.

    The dict form is what `decode_responses=True` gives; the positional form is what a client without it
    gives. `deliveries()` already reads both, and a reader that only knew one would silently report a
    zero age rather than an error.
    """
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, list | tuple) and len(row) > index:
        return row[index]
    return None


class JobStream:
    """The publish/consume half of the job queue. Every method degrades instead of raising.

    `client is None` is a supported state: a deployment with no Redis keeps the poll loop and loses
    only the wake-up. That is why the constructor takes the client rather than a URL — the singleton
    below is the only place that knows how to build one, and a test can hand in a double.
    """

    def __init__(
        self,
        client: Any | None,
        *,
        stream: str = STREAM_KEY,
        group: str = GROUP,
        dead: str = DEAD_KEY,
    ) -> None:
        self._client = client
        self.stream = stream
        self.group = group
        self.dead = dead
        #: Counters this process owns. `published` above `taken` on a single node means the consumer is
        #: behind; both above zero with `reclaimed` climbing means handlers are dying mid-flight. The
        #: name is `taken` and not `read` because `read` is this class's method, and an attribute that
        #: shadows a method turns the next call into `'int' object is not callable`.
        self.published = 0
        self.taken = 0
        self.acknowledged = 0
        self.reclaimed = 0
        self.dead_lettered = 0
        self.publish_failures = 0
        self._group_ready = False

    # -- lifecycle ---------------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._client is not None

    def ensure_group(self) -> bool:
        """Create the group at `$` so only messages published *after* it exist are delivered.

        `$` rather than `0`: a group created at zero on an existing stream would re-deliver every
        historical hint, and each of those would be a database claim that returns nothing. The rows
        that are still queued are the poll loop's business.
        """
        client = self._client
        if client is None:
            return False
        if self._group_ready:
            return True
        try:
            client.xgroup_create(self.stream, self.group, id="$", mkstream=True)
        except redis.ResponseError as exc:
            # BUSYGROUP is success: another worker created it first, which is the normal case when a
            # deployment starts several consumers at once.
            if "BUSYGROUP" not in str(exc):
                logger.warning("job stream: group creation refused: %s", exc)
                return False
        except Exception as exc:  # noqa: BLE001 — a transport failure must not stop the worker booting
            logger.warning("job stream: group creation failed: %s (%s)", exc.__class__.__name__, exc)
            return False
        self._group_ready = True
        return True

    # -- producer ----------------------------------------------------------------------------

    def publish(self, job_id: str, job_type: str, *, maxlen: int = STREAM_MAXLEN) -> str | None:
        """Announce a queued job. Returns the message id, or `None` when the hint was not sent.

        Never raises: the caller has already committed the row, and a queue that turns a Redis blip
        into a failed HTTP request would be worse than a queue that is one tick late.
        """
        client = self._client
        if client is None:
            return None
        try:
            message_id = cast("Any", client.xadd(
                self.stream,
                {"job_id": job_id, "type": job_type, "queued_at": f"{time.time():.3f}"},
                maxlen=maxlen,
                approximate=True,
            ))
        except Exception as exc:  # noqa: BLE001 — the row is already committed; the hint is best effort
            self.publish_failures += 1
            logger.warning("job stream: publish failed for %s: %s", job_id, exc)
            return None
        self.published += 1
        return _decode(message_id) if message_id is not None else None

    # -- consumer ----------------------------------------------------------------------------

    def read(self, consumer: str, *, count: int = 8, block_ms: int = 1) -> list[Entry]:
        """Take up to `count` undelivered messages for `consumer`, newest group position first.

        `block_ms` defaults to 1 rather than 0: the worker's loop also polls the database and renews
        nothing, so parking here forever would make an idle worker unresponsive to a shutdown signal.
        """
        client = self._client
        if client is None or not self.ensure_group():
            return []
        try:
            reply = cast("Any", client.xreadgroup(
                self.group,
                consumer,
                {self.stream: ">"},
                count=count,
                block=block_ms,
            ))
        except Exception as exc:  # noqa: BLE001 — a read failure is a slow tick, not a crash
            logger.warning("job stream: read failed: %s", exc)
            return []
        entries = self._parse(reply)
        self.taken += len(entries)
        return entries

    def reclaim(self, consumer: str, *, min_idle_ms: int = PENDING_GRACE_MS, count: int = 8) -> list[Entry]:
        """Take over messages whose consumer stopped acknowledging them.

        `XAUTOCLAIM` is the whole reason this queue can survive a killed worker. The alternative —
        a second stream of "in flight" bookkeeping — is the same information maintained twice.
        """
        client = self._client
        if client is None or not self.ensure_group():
            return []
        try:
            reply = cast("Any", client.xautoclaim(
                self.stream,
                self.group,
                consumer,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=count,
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("job stream: reclaim failed: %s", exc)
            return []
        # redis-py returns (next_cursor, entries, deleted_ids) since 4.2; a double may return the
        # two-tuple older servers produced. Both shapes are read here.
        entries_raw = reply[1] if isinstance(reply, list | tuple) and len(reply) > 1 else []
        entries = self._parse([[self.stream, entries_raw]]) if entries_raw else []
        if entries:
            self.reclaimed += len(entries)
            for entry in entries:
                entry.deliveries = self.deliveries(entry.id) or entry.deliveries
        return entries

    def deliveries(self, msg_id: str) -> int:
        """How many times this message has been handed to a consumer, read from the pending list.

        `XPENDING … start end count` was removed from redis-py's surface — `xpending` is now the
        summary form and the range form is `xpending_range`, whose bounds are **exclusive**. Both facts
        cost a silent zero here before they were written down: the old call raised `TypeError` into the
        `except`, every delivery count read 0, and the poison-message rule would never have fired.

        The window is `(ms-1)-0 .. ms-(seq+1)`: one millisecond wide around the id, which includes it
        despite the exclusive bounds and keeps the scan bounded no matter how long the pending list is.
        """
        client = self._client
        if client is None:
            return 0
        milliseconds, _, sequence = msg_id.partition("-")
        try:
            lower = f"{max(0, int(milliseconds) - 1)}-0"
            upper = f"{int(milliseconds)}-{int(sequence or 0) + 1}"
        except ValueError:
            return 0
        try:
            rows = cast("Any", client.xpending_range(self.stream, self.group, lower, upper, 64)) or []
        except Exception:  # noqa: BLE001 — a count we cannot read is a count we do not act on
            return 0
        for row in rows:
            if isinstance(row, dict):
                if _decode(row.get("message_id", "")) != msg_id:
                    continue
                return int(row.get("times_delivered", 0) or 0)
            if isinstance(row, list | tuple) and len(row) > 3 and _decode(row[0]) == msg_id:
                return int(row[3])
        return 0

    def ack(self, *ids: str) -> int:
        client = self._client
        if client is None or not ids:
            return 0
        try:
            acked = int(cast("Any", client.xack(self.stream, self.group, *ids)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("job stream: ack failed: %s", exc)
            return 0
        self.acknowledged += acked
        return acked

    def leave(self, consumer: str) -> bool:
        """Deregister a consumer that is exiting cleanly, so `consumers` counts live processes.

        Redis never forgets a consumer name: a group accumulates one entry per `XREADGROUP` identity
        that has ever run, so the count an operator reads would otherwise be "processes since the group
        was created" — and the one diagnosis the number supports, *"no worker is running"*, would never
        be readable again after the first restart.

        `XGROUP DELCONSUMER` also deletes that consumer's pending entries, which is why this is guarded
        on a zero count: a consumer with unacked messages is a consumer whose work is not finished, and
        deregistering it would drop messages the reclaim path is about to rescue.
        """
        client = self._client
        if client is None:
            return False
        try:
            summary = cast("Any", client.xpending(self.stream, self.group)) or {}
        except Exception:  # noqa: BLE001
            return False
        # The summary lists only consumers that *hold* pending messages, so a name that is absent is a
        # name with nothing outstanding — the safe case, not the unknown one. Reading the absence as
        # "cannot tell" would leave every clean exit registered, which is the defect this method exists
        # to fix.
        held = 0
        for entry in summary.get("consumers", []) if isinstance(summary, dict) else []:
            if _decode(entry.get("name", "")) == consumer:
                held = int(entry.get("pending", 0) or 0)
                break
        if held > 0:
            return False
        try:
            client.xgroup_delconsumer(self.stream, self.group, consumer)
        except Exception as exc:  # noqa: BLE001
            logger.warning("job stream: could not deregister %s: %s", consumer, exc)
            return False
        return True

    def to_dead(self, entry: Entry, *, reason: str, maxlen: int = DEAD_MAXLEN) -> bool:
        """Move a message that will not succeed off the live stream, with the reason attached.

        Order matters: the dead-letter `XADD` comes *before* the `XACK`. A crash between the two
        duplicates the dead letter, which an operator reads; the reverse order loses the reason, which
        is the only thing that makes the dead letter worth having.
        """
        client = self._client
        if client is None:
            return False
        try:
            client.xadd(
                self.dead,
                {
                    "job_id": entry.job_id,
                    "type": entry.job_type,
                    "reason": reason[:500],
                    "original_id": entry.id,
                    "deliveries": str(entry.deliveries),
                },
                maxlen=maxlen,
                approximate=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("job stream: dead-letter write failed: %s", exc)
            return False
        self.ack(entry.id)
        self.dead_lettered += 1
        return True

    # -- reporting ---------------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """What an operator needs to tell "idle" from "stuck", from the server's own numbers.

        Four counts answer *how much* — `stream_length` is the window's size, `pending` is messages
        handed out but never acknowledged (a consumer is dying), `undelivered` is messages no consumer
        has taken (no consumer is running), and `dead_length` is the pile that no retry will fix.

        Three ages answer *since when*, and they are the ones a count cannot substitute for: a queue of
        twelve hints that arrived in the last second and a queue of twelve hints that have been ignored
        for an hour are the same number and different incidents. Every age is `None` rather than `0` when
        the store would not say, and the four age keys travel in every snapshot including a storeless
        one — checked 2026-11-23 against a live queue and a `JobStream(None)`. The counts are not all
        present without a store, and that is a difference and not a gap: `available: false` is published
        in the same payload, so an absent `pending` reads as "no Redis" and never as "an idle queue".
        """
        payload: dict[str, Any] = {
            "available": self.available,
            "stream": self.stream,
            "group": self.group,
            "published": self.published,
            "taken": self.taken,
            "acknowledged": self.acknowledged,
            "reclaimed": self.reclaimed,
            "dead_lettered": self.dead_lettered,
            "publish_failures": self.publish_failures,
            **_UNKNOWN_AGES,
        }
        client = self._client
        if client is None:
            return payload
        try:
            payload["stream_length"] = int(cast("Any", client.xlen(self.stream)))
            payload["dead_length"] = int(cast("Any", client.xlen(self.dead)))
        except Exception:  # noqa: BLE001
            return payload
        last_delivered: str | None = None
        try:
            groups = cast("Any", client.xinfo_groups(self.stream)) or []
            for group in groups:
                name = _decode(group.get("name", ""))
                if name != self.group:
                    continue
                payload["pending"] = int(group.get("pending", 0))
                payload["consumers"] = int(group.get("consumers", 0))
                payload["undelivered"] = max(0, int(group.get("lag", 0) or 0))
                last_delivered = _decode(group.get("last-delivered-id", "")) or None
                break
        except Exception:  # noqa: BLE001 — the group may not exist yet, which is a valid state
            payload["pending"] = 0
            payload["undelivered"] = payload.get("stream_length", 0)
        payload.update(self.ages(client, last_delivered=last_delivered))
        return payload

    def ages(self, client: Any, *, last_delivered: str | None = None) -> dict[str, Any]:
        """The three ages, each read from the server's clock and the server's own ids.

        * `oldest_undelivered_seconds` — since when has a hint existed that nobody has been given? This
          is the *"the worker is not running"* figure, and it keeps growing while `consumers` reads 0.
        * `oldest_pending_seconds` — since when has the oldest unfinished hint existed at all? This is the
          age of the work, which is what a caller experiences as latency.
        * `pending_idle_seconds` — since when has the busiest pending message's consumer said nothing?
          This is the *"a worker is alive and stuck inside a handler"* figure, and it is a different
          number from the one above it: a hint can be old and freshly delivered at the same time.

        `pending_sampled` names the population the idle maximum was judged over, because a maximum over
        the first 256 pending rows is not a maximum over the pending list.
        """
        now_ms = _server_now_ms(client)
        ages: dict[str, Any] = {
            "oldest_undelivered_seconds": None,
            "oldest_pending_seconds": None,
            "pending_idle_seconds": None,
            "pending_sampled": 0,
        }
        ages["oldest_undelivered_seconds"] = self._oldest_undelivered_seconds(client, now_ms, last_delivered)
        try:
            rows = cast("Any", client.xpending_range(self.stream, self.group, "-", "+", PENDING_SAMPLE)) or []
        except Exception:  # noqa: BLE001 — an unreadable pending list is an unknown age
            return ages
        ages["pending_sampled"] = len(rows)
        if not rows:
            return ages
        ages["oldest_pending_seconds"] = _age_seconds(now_ms, _id_ms(_pending_field(rows[0], 0, "message_id")))
        # `time_since_delivered` is per entry and measured from that entry's last delivery, so the
        # largest one in the window is the consumer that has been silent longest.
        silences = [_pending_field(row, 2, "time_since_delivered") for row in rows]
        readable = [int(value) for value in silences if value is not None]
        if readable:
            ages["pending_idle_seconds"] = round(max(readable) / 1000.0, 3)
        return ages

    def _oldest_undelivered_seconds(self, client: Any, now_ms: int | None, last_delivered: str | None) -> float | None:
        """The age of the first entry after the group's cursor — the oldest hint no consumer has seen.

        The window starts one sequence number past the cursor rather than with the `(` exclusive-range
        syntax: `deliveries()` already found that redis-py's bounds and the server's version differ here,
        and an id built as `ms-(seq+1)` is correct on both. A stream whose cursor is already at the end
        returns nothing, which is the honest `None`: there is no undelivered message to age.
        """
        if last_delivered is None or last_delivered == "0-0":
            minimum = "-"
        else:
            milliseconds, _, sequence = last_delivered.partition("-")
            try:
                minimum = f"{int(milliseconds)}-{int(sequence or 0) + 1}"
            except ValueError:
                return None
        try:
            rows = cast("Any", client.xrange(self.stream, min=minimum, max="+", count=1)) or []
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None
        return _age_seconds(now_ms, _id_ms(rows[0][0]))

    def dead_letters(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Read the pile that no retry will fix — newest first, with the reason and how long it has been there.

        `to_dead` writes the reason because a dead letter without one is a count an operator cannot act
        on; until this method existed, that reason was written and then never read by anything in the
        product, and `dead_length` was the only thing the dead-letter stream contributed to the door.
        """
        client = self._client
        if client is None:
            return []
        try:
            rows = cast("Any", client.xrevrange(self.dead, count=limit)) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("job stream: dead-letter read failed: %s", exc)
            return []
        now_ms = _server_now_ms(client)
        letters: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, list | tuple) or len(row) < 2:
                continue
            msg_id = _decode(row[0])
            fields = row[1] or {}
            get = fields.get if isinstance(fields, dict) else (lambda _key, _default=None: "")
            letters.append(
                {
                    "id": msg_id,
                    "job_id": _decode(get("job_id", "")),
                    "job_type": _decode(get("type", "")),
                    "reason": _decode(get("reason", "")),
                    "deliveries": int(get("deliveries", 0) or 0),
                    "original_id": _decode(get("original_id", "")),
                    "dead_for_seconds": _age_seconds(now_ms, _id_ms(msg_id)),
                }
            )
        return letters

    # -- internals ---------------------------------------------------------------------------

    def _parse(self, reply: Any) -> list[Entry]:
        """Turn `XREADGROUP`/`XAUTOCLAIM` output into `Entry`s, tolerating bytes or text."""
        entries: list[Entry] = []
        if not reply:
            return entries
        for stream_block in reply:
            if not isinstance(stream_block, list | tuple) or len(stream_block) < 2:
                continue
            for item in stream_block[1]:
                if not isinstance(item, list | tuple) or len(item) < 2:
                    continue
                msg_id = _decode(item[0])
                fields = item[1] or {}
                job_id = _decode(fields.get("job_id", "")) if isinstance(fields, dict) else ""
                job_type = _decode(fields.get("type", "")) if isinstance(fields, dict) else ""
                if not job_id:
                    # A message with no job id cannot be claimed, so it cannot be served. Acknowledge
                    # it out of the pending list rather than let it sit there as permanent debt.
                    self.ack(msg_id)
                    continue
                entries.append(Entry(msg_id, job_id, job_type))
        return entries


_job_stream: JobStream | None = None


def _url() -> str:
    #: A separate URL so the queue can live on an instance with different persistence from the cache
    #: tier — the queue wants `appendfsync everysec`, a cache wants `maxmemory-policy allkeys-lru`.
    return os.getenv("JOB_STREAM_REDIS_URL") or os.getenv("REDIS_URL") or "redis://localhost:6379/0"


def get_job_stream() -> JobStream:
    """The process-wide stream client, or one that reports itself unavailable.

    A failed connect is remembered for the life of the process, exactly like the cache tier: a worker
    with no Redis should not pay a two-second connect timeout on every tick to prove it.
    """
    global _job_stream
    if _job_stream is not None:
        return _job_stream
    try:
        # Half a second, not two: `POST /jobs` publishes on the request thread, and a hint that cannot
        # be sent in 500 ms is a hint the poll loop will replace a tick later — a caller should not wait
        # two seconds to be told a queue is busy. The worker inherits the same bound, which is ample for
        # a one-millisecond blocking read.
        client: Any = redis.from_url(
            _url(),
            socket_connect_timeout=1,
            socket_timeout=0.5,
            decode_responses=True,
        )
        if client is None:
            raise ConnectionError("redis.from_url returned no client")
        client.ping()
        stream = JobStream(client)
        logger.info("job stream connected: %s", stream.stream)
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.warning("job stream unavailable, the poll loop carries the queue: %s (%s)", exc.__class__.__name__, exc)
        stream = JobStream(None)
    _job_stream = stream
    return _job_stream


def close_job_stream() -> None:
    global _job_stream
    if _job_stream is not None and _job_stream._client is not None:  # noqa: SLF001 — the module owns the client
        try:
            _job_stream._client.close()  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pass
    _job_stream = None
