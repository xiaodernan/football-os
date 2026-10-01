"""Video analysis endpoints (spec §14, §47, §61, §62).

Everything here needs a session and only ever touches the caller's own clips: a video is the most
identifying data a user can upload, so there is no public read of any kind — not a listing, not a
frame, not a filename. The upload path is where the platform's one file-ingress door lives, so the
allow-list checks the bytes rather than the label, and the size ceiling is configured, not assumed.

The analysis endpoints run the pipeline during the request and record a Job row for it. There is no
queue and no worker, and nothing in the response claims otherwise (spec §47, PRINCIPLE 1).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import Job, User, UserPlayer, VideoAsset, VideoDetection
from app.services.video import pipeline
from app.services.video.media import MediaToolMissing, to_png

router = APIRouter(prefix="/video", tags=["video"])

NOT_FOUND: Final = {"code": "not_found", "message": "No such clip for this account"}
MAX_CLIPS_PER_USER: Final = 20
FRAME_STATUSES: Final = ("analysed",)
READ_CHUNK: Final = 64 * 1024
_BYTE_RANGE: Final = re.compile(r"^bytes=(?:(?P<start>\d+)-(?P<end>\d*)|-(?P<suffix>\d+))$")


def _mine(session: Session, user: User) -> Any:
    return select(VideoAsset).where(VideoAsset.owner_id == user.id)


def _range_of(header: str | None, size: int) -> tuple[str, int, int]:
    """How to read the file: `("full", 0, 0)`, `("partial", start, stop)` inclusive, or `("unsatisfiable", 0, 0)`.

    An open-ended start means "to the end"; a bare `bytes=-N` means the last N bytes, which is how a
    player reaches the metadata at the tail of an mp4. Anything this parser does not recognise —
    including a multi-range request — is served whole, which RFC 9110 allows a server to do.
    """
    if not header:
        return ("full", 0, 0)
    match = _BYTE_RANGE.match(header.strip())
    if match is None:
        return ("full", 0, 0)
    raw_start, raw_suffix = match.group("start"), match.group("suffix")
    if raw_start is None:
        return ("partial", max(size - int(raw_suffix), 0), size - 1)
    start = int(raw_start)
    if start >= size:
        return ("unsatisfiable", 0, 0)
    end = match.group("end")
    return ("partial", start, min(int(end), size - 1) if end else size - 1)


def _serve_slice(path: Path, media_type: str, range_header: str | None) -> Response:
    """Stream `path` back, honouring one byte range if the request asked for one."""
    size = path.stat().st_size
    if size == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    kind, start, stop = _range_of(range_header, size)
    if kind == "full":
        start, stop = 0, size - 1
    headers = {"Accept-Ranges": "bytes"}
    if kind == "unsatisfiable":
        headers["Content-Range"] = f"bytes */{size}"
        raise HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail={"code": "range_not_satisfiable", "message": f"this clip is {size} bytes"},
            headers=headers,
        )
    length = stop - start + 1
    if kind == "partial":
        headers["Content-Range"] = f"bytes {start}-{stop}/{size}"

    def chunks() -> Any:
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(READ_CHUNK, remaining))
                if not block:
                    return
                remaining -= len(block)
                yield block

    headers["Content-Length"] = str(length)
    return StreamingResponse(chunks(), status_code=206 if kind == "partial" else 200, media_type=media_type, headers=headers)


def _one(session: Session, user: User, ident: str) -> VideoAsset:
    asset = session.scalar(_mine(session, user).where(VideoAsset.id == ident))
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return asset


def _analysis_jobs(session: Session, asset_id: str) -> list[Job]:
    """This clip's runs, newest first. The job rows carry the measured summary a later report re-reads."""
    rows = list(session.scalars(select(Job).where(Job.type == "video.analyse").order_by(Job.created_at.desc()).limit(20)).all())
    return [job for job in rows if job.payload.get("asset_id") == asset_id]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_clip(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Accept a clip: size and container checked against the bytes, then probed."""
    limit(request, 12, 60, scope="video_upload")
    if int(db.scalar(select(func.count()).select_from(VideoAsset).where(VideoAsset.owner_id == user.id)) or 0) >= MAX_CLIPS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "video_limit", "message": f"{MAX_CLIPS_PER_USER} clips per account is the current ceiling"},
        )
    data = await file.read()
    try:
        # One place decides both limits — the route does not re-check the size, so it cannot disagree.
        asset = pipeline.store_upload(db, user_id=user.id, filename=file.filename or "clip", data=data, title=title)
    except pipeline.UploadTooLarge as error:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"code": "too_large", "message": str(error)}) from error
    except pipeline.UploadRejection as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"code": "unsupported_container", "message": str(error)}) from error
    return pipeline.report_for(db, asset)


@router.get("")
def list_clips(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 60, scope="video_list")
    stmt = _mine(db, user).order_by(VideoAsset.created_at.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return {
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "filename": row.filename,
                "status": row.status,
                "duration_s": row.duration_s,
                "width": row.width,
                "height": row.height,
                "size_bytes": row.size_bytes,
                "content_type": row.content_type,
                "frame_count": row.frame_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "data_origin": row.data_origin,
                "is_demo_data": row.is_demo_data,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "limit_per_user": MAX_CLIPS_PER_USER,
        "privacy": "Only this account can see or fetch these clips.",
    }


@router.get("/{ident}")
def clip_report(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The same report the analysis returned, rebuilt from what the last run stored."""
    limit(request, 60, 60, scope="video_detail")
    asset = _one(db, user, ident)
    runs = _analysis_jobs(db, asset.id)
    return pipeline.report_for(db, asset, job=runs[0] if runs else None)


@router.post("/{ident}/analyse")
def analyse_clip(
    ident: str,
    request: Request,
    target_frames: int = Query(default=24, ge=4, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Sample the clip and measure it. Runs now, in this request, and records the job either way."""
    limit(request, 10, 60, scope="video_analyse")
    asset = _one(db, user, ident)
    try:
        return pipeline.analyse_asset(db, asset, target_frames=target_frames, user_id=user.id)
    except MediaToolMissing as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "media_tools_missing", "message": str(error)},
        ) from error


@router.get("/{ident}/file")
def clip_file(
    ident: str,
    request: Request,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    """The clip itself, to its owner only — the browser needs it to show what was analysed.

    A `<video>` element asks for byte ranges, and a server that cannot answer them makes the player
    download the whole file before it can seek. So this route reads only the slice it was asked for,
    and never the whole clip into memory.
    """
    limit(request, 30, 60, scope="video_file")
    asset = _one(db, user, ident)
    stored = Path(settings.storage_dir) / asset.storage_key
    if not stored.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return _serve_slice(stored, asset.content_type or "application/octet-stream", range_header)


@router.get("/{ident}/frames/{index}")
def clip_frame(
    ident: str,
    index: int,
    request: Request,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    """One sampled frame as PNG, from the same set the measurements came from."""
    limit(request, 120, 60, scope="video_frame")
    asset = _one(db, user, ident)
    directory = Path(settings.storage_dir) / "frames" / asset.id
    frames = sorted(directory.glob("frame-*.ppm"))
    if not 0 <= index < len(frames):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_frame", "message": f"this clip has {len(frames)} sampled frames"},
        )
    try:
        png = to_png(frames[index])
    except MediaToolMissing as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "media_tools_missing", "message": str(error)}) from error
    return _serve_slice(png, "image/png", range_header)


@router.get("/{ident}/jobs")
def clip_jobs(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The bookkeeping for this clip's runs, so a report can be traced to the job that made it."""
    limit(request, 30, 60, scope="video_jobs")
    asset = _one(db, user, ident)
    relevant = _analysis_jobs(db, asset.id)
    return {
        "items": [
            {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "attempts": job.attempts,
                "error": job.error,
                "result": job.result,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in relevant
        ],
        "total": len(relevant),
        "detections": int(db.scalar(select(func.count()).select_from(VideoDetection).where(VideoDetection.asset_id == asset.id)) or 0),
        "note": "Recorded during the request that asked for the work; there is no queue and no worker behind these rows.",
    }


@router.post("/{ident}/link-player")
def link_player(
    ident: str,
    request: Request,
    player_id: str = Query(..., min_length=1, max_length=40),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Link this clip to one of the caller's football identities (spec §14, M5 item 3)."""
    limit(request, 20, 60, scope="video_link_player")
    asset = _one(db, user, ident)
    player = db.scalar(select(UserPlayer).where(UserPlayer.id == player_id, UserPlayer.user_id == user.id))
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "No such football identity for this account"})
    asset.player_id = player_id
    db.commit()
    return {"id": asset.id, "player_id": asset.player_id, "message": "Clip linked to player"}


@router.post("/{ident}/link-match")
def link_match(
    ident: str,
    request: Request,
    match_id: str = Query(..., min_length=1, max_length=40),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Link this clip to an M6 simulation match (spec §14, M5 item 3)."""
    limit(request, 20, 60, scope="video_link_match")
    asset = _one(db, user, ident)
    from app.models import SimulationMatch
    match = db.scalar(select(SimulationMatch).where(SimulationMatch.id == match_id, SimulationMatch.owner_id == user.id))
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "No such match for this account"})
    asset.match_id = match_id
    db.commit()
    return {"id": asset.id, "match_id": asset.match_id, "message": "Clip linked to match"}


@router.post("/{ident}/share")
def share_clip(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create a revocable share link for this clip (spec §17 precedent, M5 item 3)."""
    import secrets
    limit(request, 10, 60, scope="video_share")
    asset = _one(db, user, ident)
    if not asset.share_token:
        asset.share_token = secrets.token_hex(16)
        asset.shared_at = datetime.now(UTC)
    asset.visibility = "shared"
    db.commit()
    return {
        "id": asset.id,
        "share_token": asset.share_token,
        "share_url": f"/video/shared/{asset.share_token}",
        "visibility": asset.visibility,
    }


@router.delete("/{ident}/share")
def revoke_share(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Revoke the share link for this clip (spec §17 precedent)."""
    limit(request, 10, 60, scope="video_share_revoke")
    asset = _one(db, user, ident)
    asset.share_token = None
    asset.shared_at = None
    asset.visibility = "private"
    db.commit()
    return {"id": asset.id, "visibility": asset.visibility, "share_url": None}


@router.get("/shared/{token}")
def read_shared_clip(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Public read of a shared clip — no session, no owner identity (spec §17 precedent)."""
    limit(request, 60, 60, scope="video_shared_read")
    asset = db.scalar(select(VideoAsset).where(VideoAsset.share_token == token, VideoAsset.visibility == "shared"))
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "This link no longer points at a clip"})
    # Public read: no owner identity, no account link
    return {
        "id": asset.id,
        "title": asset.title,
        "filename": asset.filename,
        "duration_s": asset.duration_s,
        "width": asset.width,
        "height": asset.height,
        "status": asset.status,
        "frame_count": asset.frame_count,
        "data_origin": asset.data_origin,
        "is_demo_data": asset.is_demo_data,
    }


@router.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_clip(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> None:
    """Delete the record and the stored bytes: an upload right implies a take-back-right (spec §61)."""
    limit(request, 20, 60, scope="video_delete")
    asset = _one(db, user, ident)
    stored = Path(settings.storage_dir) / asset.storage_key
    frames = Path(settings.storage_dir) / "frames" / asset.id
    db.delete(asset)
    db.commit()
    stored.unlink(missing_ok=True)
    for leftover in frames.glob("frame-*"):
        leftover.unlink(missing_ok=True)
    if frames.exists():
        frames.rmdir()
