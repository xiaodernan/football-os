"""The drain handler for the production video.analyse job — the producer half of the ADR-006 pair.

The queue (`app.services.jobs`) claims and commits; this module is what runs when it does. It executes
exactly the stage logic the synchronous door runs (`pipeline._measure`), under the job the claim already
handed it, and its only outward contract is what `drain_one` reads: success returns a compact summary,
failure raises `PipelineUnavailable`/`MediaToolMissing` unchanged so the drain's `fail()` records the reason —
no swallowing, no silent successes.

The synchronous door (`POST /video/{ident}/analyse`) remains the interactive path: the client that clicked
"analyse" holds the answer in the same HTTP response. This drain path is for the case that door cannot serve —
an ops sweep, a cron drain, a batch re-analyse — where no client is waiting on the wire. Neither path decides
football anything; both run the same measured stages.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import VideoAsset
from app.services.video.pipeline import PipelineUnavailable, _measure


def drain_analyse(job: Any) -> dict[str, Any]:
    """Run the production video.analyse job the queue claimed. Raises on failure so the drain records it."""
    started = time.perf_counter()
    session_factory = SessionLocal
    session: Session = session_factory()
    try:
        asset = session.get(VideoAsset, str(job.payload.get("asset_id")))
        if asset is None:
            raise PipelineUnavailable(f"the job names asset {str(job.payload.get('asset_id'))!r}, which is not on this database")
        target_frames = int(job.payload.get("target_frames") or 24)
        _stages, result, failure = _measure(
            session,
            asset,
            job,
            target_frames=target_frames,
            user_id=job.user_id or asset.owner_id,
            started=started,
        )
        if failure is not None:
            raise PipelineUnavailable(failure)
        return {
            "asset_id": asset.id,
            "frames": int(asset.frame_count or 0),
            "events": len(result["events"]) if result else 0,
            "provider": (result or {}).get("provider"),
            "demo_mode": (result or {}).get("demo_mode"),
            "total_ms": int((time.perf_counter() - started) * 1000),
        }
    finally:
        session.close()
