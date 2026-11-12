"""The handler registry: which job types this build can actually run (spec §47, ADR-006).

`app.services.jobs` is deliberately ignorant of job types — it takes a `dict[str, Handler]` so the
runner can be tested without importing the pipeline, and so a deployment can run a subset. This module
is the one place that answers *"what is registered?"*, and it answers with a function rather than a
module-level dict so the pipeline's imports (which reach for media tooling) happen when a worker
starts, not when the API imports the package.

A type that is not here is not silently ignored: `run_claimed` fails the row with
`no_handler_registered`, which is the honest end state and the reason this registry is explicit. Adding
a type means adding it here, and `test_job_handlers` asserts the set of types the doors create is a
subset of the set this registry can run — the gap between those two sets is work that would be lost.
"""

from __future__ import annotations

from typing import Any, Final

from app.services.jobs import Handler

#: Types registered by importable modules. A handler is a callable taking the claimed `Job`.
_BUILTIN_TYPES: Final = ("video.analyse",)

_registry: dict[str, Handler] | None = None
_extra: dict[str, Handler] = {}


def register(job_type: str, handler: Handler) -> None:
    """Add a type from outside this module — an extension point, and what tests use.

    Registered handlers survive `handlers()` being rebuilt; the built-in set is re-derived each call so
    a module reloaded under a test does not leave a stale callable behind.
    """
    _extra[job_type] = handler


def handlers() -> dict[str, Handler]:
    """Every runnable type, built-ins included. Cheap after the first call."""
    global _registry
    if _registry is not None:
        combined = dict(_registry)
        combined.update(_extra)
        return combined
    built: dict[str, Handler] = {}
    built["system.echo"] = _echo
    try:
        from app.services.video.drain import drain_analyse

        built["video.analyse"] = drain_analyse
    except Exception:  # noqa: BLE001 — a missing media stack costs one type, not the worker
        # Import-time failure here is a deployment without the video extras. The remaining types still
        # run; `video.analyse` will fail with `no_handler_registered`, which is visible in `/jobs`.
        pass
    _registry = built
    combined = dict(built)
    combined.update(_extra)
    return combined


def _echo(job: Any) -> dict[str, Any]:
    """The queue's own smoke test: returns the payload, touches nothing.

    Every other type in this registry needs something to work on — an asset, a file, a row with a
    foreign key — which makes "is the queue alive?" impossible to ask without also asking "is that
    object still there?". `system.echo` answers the first question alone, so a deployment check is one
    `POST /jobs` and one worker tick, and a failure is the queue's rather than the fixture's.
    """
    return {"echo": job.payload, "job_id": job.id, "attempts": job.attempts}


def registered_types() -> tuple[str, ...]:
    return tuple(sorted(handlers()))


def clear_cache() -> None:
    """Forget the built-in set. Tests call this after monkeypatching a module."""
    global _registry
    _registry = None


__all__: list[str] = ["clear_cache", "handlers", "register", "registered_types"]
