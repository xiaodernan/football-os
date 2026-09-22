"""The video pipeline: upload → probe → sample frames → measure → report (spec §14, §47, §62, §77).

Honesty rules this module is built around:

* an upload is accepted only if its **own bytes** look like a supported container, so a renamed
  executable or a JPEG called `.mp4` is refused on content, not on a filename;
* the stages are recorded as a real `Job` row with per-stage timings, and a `ModelCall` row for the
  vision pass — including its failure. There is no background worker and none is implied: the work
  happens during the request that asks for it, which is what PRINCIPLE 1 (no premature queue
  infrastructure) buys back in boringness;
* if ffmpeg or ffprobe is missing, the job fails with that sentence and no events are invented;
* every event carries the provider, model and `demo_mode` that produced it, and the report repeats
  the provider's own `limitations`, because "the non-pitch pixels moved 0.04 frame widths" is not the
  same statement as "the winger made a run behind".
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.models import Job, ModelCall, VideoAsset, VideoDetection
from app.providers import get_storage_provider, get_vision_provider
from app.services.video.media import MediaToolMissing, extract_frames, frame_interval, probe

__all__ = [
    "PipelineUnavailable",
    "UploadRejection",
    "UploadTooLarge",
    "analyse_asset",
    "detect_container",
    "report_for",
    "store_upload",
]

MAX_FRAMES: Final = 60
CONTAINER_SIGNATURES: Final = {
    b"ftyp": "video/mp4",
    b"MOVI": "video/quicktime",
    b"\x1a\x45\xdf\xa3": "video/webm",
}
EXTENSIONS: Final = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}


class UploadRejection(ValueError):
    """Why a file was refused, in the message the client sees."""


class PipelineUnavailable(RuntimeError):
    """ffprobe/ffmpeg are absent, so analysis cannot run at all."""


class UploadTooLarge(UploadRejection):
    """Bigger than the configured ceiling. Its own type so the route can answer 413, not 415."""


@dataclass
class Stage:
    name: str
    status: str = "done"
    progress: int = 0
    detail: dict[str, Any] = field(default_factory=dict)
    ms: int = 0


def detect_container(data: bytes) -> str:
    """Which supported container the bytes actually are, by their own signature."""
    if len(data) < 12:
        raise UploadRejection("the file is too small to be a video container")
    for signature, content_type in CONTAINER_SIGNATURES.items():
        if signature in data[:16] or data[4:8] == signature:
            if content_type not in settings.video_allowed_types:
                raise UploadRejection(f"{content_type} is not in the allowed upload types")
            return content_type
    raise UploadRejection("not a supported video container (accepted: mp4, mov, webm, recognised by their own bytes)")


def _frames_dir(asset_id: str) -> Path:
    path = Path(settings.storage_dir) / "frames" / asset_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_upload(session: Session, *, user_id: str, filename: str, data: bytes, max_bytes: int | None = None) -> VideoAsset:
    """Validate, size-check, hash and persist an upload, then read its container facts."""
    if not data:
        raise UploadRejection("the upload was empty")
    ceiling = settings.video_max_bytes if max_bytes is None else max_bytes
    if len(data) > ceiling:
        raise UploadTooLarge(f"the upload is {len(data)} bytes, which exceeds the {ceiling} byte ceiling")
    container = detect_container(data)
    digest = hashlib.sha256(data).hexdigest()
    asset_id = new_public_id("vid")
    key = f"video/{user_id}/{asset_id}{EXTENSIONS[container]}"
    storage = get_storage_provider()
    storage.put(key, data, container)
    location = _stored_path(key)

    try:
        info = probe(location)
    except MediaToolMissing as error:
        asset = VideoAsset(
            id=asset_id,
            owner_id=user_id,
            title=(filename or "clip")[:160],
            filename=filename[:240],
            storage_key=key,
            content_type=container,
            size_bytes=len(data),
            sha256=digest,
            status="failed",
            error=str(error),
            data_origin="user",
            is_demo_data=False,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    asset = VideoAsset(
        id=asset_id,
        owner_id=user_id,
        title=(filename or "clip")[:160],
        filename=filename[:240],
        storage_key=key,
        content_type=container,
        size_bytes=len(data),
        sha256=digest,
        status="uploaded",
        duration_s=info.duration_s,
        width=info.width,
        height=info.height,
        fps=info.fps,
        codec=info.codec,
        bitrate_kbps=info.bitrate_kbps,
        media={**info.to_dict(), "container_signature": container},
        data_origin="user",
        is_demo_data=False,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def analyse_asset(session: Session, asset: VideoAsset, *, target_frames: int = 24, user_id: str | None = None) -> dict[str, Any]:
    """Run the stages, write the rows, and return the report the client sees."""
    job = Job(
        id=new_public_id("job"),
        type="video.analyse",
        status="RUNNING",
        payload={"asset_id": asset.id, "target_frames": target_frames},
        progress=5,
        user_id=user_id or asset.owner_id,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    stages: list[Stage] = []
    started = time.perf_counter()
    try:
        stage_started = time.perf_counter()
        info = probe(_stored_path(asset.storage_key))
        stages.append(Stage("probe", detail=info.to_dict(), progress=20, ms=int((time.perf_counter() - stage_started) * 1000)))
        asset.duration_s = info.duration_s
        asset.width = info.width
        asset.height = info.height
        asset.fps = info.fps
        asset.codec = info.codec
        asset.bitrate_kbps = info.bitrate_kbps

        stage_started = time.perf_counter()
        interval = frame_interval(info.duration_s, target_frames=target_frames)
        frames = extract_frames(_stored_path(asset.storage_key), _frames_dir(asset.id), interval_s=interval, max_frames=MAX_FRAMES)
        stages.append(
            Stage(
                "extract_frames",
                detail={"frames": len(frames), "interval_s": interval, "sample_times": [frame.time_s for frame in frames[:8]]},
                progress=55,
                ms=int((time.perf_counter() - stage_started) * 1000),
            )
        )
        if not frames:
            raise PipelineUnavailable("ffmpeg produced no frames for this clip, so nothing could be measured")

        provider = get_vision_provider()
        vision_started = time.perf_counter()
        result = provider.analyze_frames([frame.path.read_bytes() for frame in frames], task="track_movement")
        vision_ms = int((time.perf_counter() - vision_started) * 1000)
        result["frame_times"] = [frame.time_s for frame in frames]
        result["frame_interval_s"] = interval
        stages.append(Stage("analyse", detail={"provider": result["provider"], "events": len(result["events"])}, progress=90, ms=vision_ms))

        session.add(
            ModelCall(
                id=new_public_id("mcl"),
                provider=result["provider"],
                model=result["model"],
                feature="video.analyse",
                user_id=user_id or asset.owner_id,
                latency_ms=vision_ms,
                estimated_cost_usd=0.0,
                actual_cost_usd=0.0,
                success=True,
                demo_mode=bool(result["demo_mode"]),
            )
        )
        session.execute(delete(VideoDetection).where(VideoDetection.asset_id == asset.id))
        for event in result["events"]:
            session.add(
                VideoDetection(
                    id=new_public_id("vdt"),
                    asset_id=asset.id,
                    job_id=job.id,
                    kind=str(event["kind"]),
                    t_s=float(event["t_s"]),
                    x=float(event["x"]),
                    y=float(event["y"]),
                    confidence=float(event["confidence"]),
                    why=str(event["why"]),
                    detail=event,
                    provider=result["provider"],
                    model=result["model"],
                    demo_mode=bool(result["demo_mode"]),
                )
            )
        asset.frame_count = len(frames)
        asset.frame_interval_s = interval
        asset.media = {**(asset.media or {}), "last_analysis": {stage.name: stage.detail for stage in stages}, "commands": {"probe": info.probe_command}}
        asset.status = "analysed"
        asset.error = None
        job.status = "DONE"
        job.progress = 100
        job.result = {
            "events": len(result["events"]),
            "frames": len(frames),
            "provider": result["provider"],
            "demo_mode": result["demo_mode"],
            "total_ms": int((time.perf_counter() - started) * 1000),
            # The measured summary and the stage rows are stored with the job so that a report read
            # later — a reload, a second visit — shows the same numbers, not an empty panel. The
            # events themselves are already rows, so repeating them here would only bloat the job.
            "stages": [
                {"name": stage.name, "status": stage.status, "progress": stage.progress, "detail": stage.detail, "ms": stage.ms}
                for stage in stages
            ],
            "analysis": {key: value for key, value in result.items() if key != "events"},
        }
        session.commit()
        return report_for(session, asset, job=job, stages=stages, analysis=result)
    except (MediaToolMissing, PipelineUnavailable) as error:
        message = str(error)
        asset.status = "failed"
        asset.error = message
        job.status = "FAILED"
        job.progress = 100
        job.error = message
        session.add(
            ModelCall(
                id=new_public_id("mcl"),
                provider=get_vision_provider().name,
                model="ffmpeg ppm + pure-python statistics",
                feature="video.analyse",
                user_id=user_id or asset.owner_id,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error=message,
                demo_mode=True,
            )
        )
        session.commit()
        return report_for(session, asset, job=job, stages=stages, analysis=None, failure=message)


def _stored_path(key: str) -> Path:
    return (Path(settings.storage_dir) / key).resolve()


def report_for(
    session: Session,
    asset: VideoAsset,
    *,
    job: Job | None = None,
    stages: Sequence[Stage | dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    failure: str | None = None,
) -> dict[str, Any]:
    """The report a client renders: stored facts, the measured events, and what none of it means.

    `stages` may be live `Stage` rows from a run happening now, or the plain dicts a finished job kept
    — the two report the same thing, and a report read back must not look thinner than the one the
    analysis returned.
    """
    stored = {} if job is None else (job.result or {})
    if stages is None:
        stages = stored.get("stages") or None
    if analysis is None and stored.get("analysis"):
        analysis = stored["analysis"]
    stage_rows: list[dict[str, Any]] = [
        stage if isinstance(stage, dict) else {"name": stage.name, "status": stage.status, "progress": stage.progress, "detail": stage.detail, "ms": stage.ms}
        for stage in stages or []
    ]
    detections = list(session.scalars(select(VideoDetection).where(VideoDetection.asset_id == asset.id).order_by(VideoDetection.t_s)).all())
    return {
        "asset": {
            "id": asset.id,
            "title": asset.title,
            "filename": asset.filename,
            "content_type": asset.content_type,
            "size_bytes": asset.size_bytes,
            "sha256": asset.sha256,
            "status": asset.status,
            "duration_s": asset.duration_s,
            "width": asset.width,
            "height": asset.height,
            "fps": asset.fps,
            "codec": asset.codec,
            "bitrate_kbps": asset.bitrate_kbps,
            "frame_count": asset.frame_count,
            "frame_interval_s": asset.frame_interval_s,
            "data_origin": asset.data_origin,
            "is_demo_data": asset.is_demo_data,
            "error": asset.error,
        },
        "job": None if job is None else {"id": job.id, "type": job.type, "status": job.status, "progress": job.progress, "error": job.error, "result": job.result},
        "stages": stage_rows,
        "detections": [
            {
                "id": row.id,
                "kind": row.kind,
                "t_s": row.t_s,
                "x": row.x,
                "y": row.y,
                "confidence": row.confidence,
                "why": row.why,
                "provider": row.provider,
                "model": row.model,
                "demo_mode": row.demo_mode,
            }
            for row in detections
        ],
        "analysis": analysis,
        "failure": failure,
        "privacy": "The clip and its frames belong to the uploading account; nothing here is published, and the file is served only to its owner.",
        "disclaimer": (
            "Detections are pixel statistics from a demo provider: positions of the centre of non-pitch pixels, and movement of "
            "that centre between samples. They are not players, not a ball, and not football events."
        ),
    }
