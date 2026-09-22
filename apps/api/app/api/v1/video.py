"""Video analysis endpoints (spec §14, §47, §61, §62).

Everything here needs a session and only ever touches the caller's own clips: a video is the most
identifying data a user can upload, so there is no public read of any kind — not a listing, not a
frame, not a filename. The upload path is where the platform's one file-ingress door lives, so the
allow-list checks the bytes rather than the label, and the size ceiling is configured, not assumed.

The analysis endpoints run the pipeline during the request and record a Job row for it. There is no
queue and no worker, and nothing in the response claims otherwise (spec §47, PRINCIPLE 1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import Job, User, VideoAsset, VideoDetection
from app.services.video import pipeline
from app.services.video.media import MediaToolMissing, to_png

router = APIRouter(prefix="/video", tags=["video"])

NOT_FOUND: Final = {"code": "not_found", "message": "No such clip for this account"}
MAX_CLIPS_PER_USER: Final = 20
FRAME_STATUSES: Final = ("analysed",)


def _mine(session: Session, user: User) -> Any:
    return select(VideoAsset).where(VideoAsset.owner_id == user.id)


def _one(session: Session, user: User, ident: str) -> VideoAsset:
    asset = session.scalar(_mine(session, user).where(VideoAsset.id == ident))
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return asset


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
        asset = pipeline.store_upload(db, user_id=user.id, filename=file.filename or "clip", data=data)
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
    limit(request, 60, 60, scope="video_detail")
    return pipeline.report_for(db, _one(db, user, ident))


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
def clip_file(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    """The clip itself, to its owner only — the browser needs it to show what was analysed."""
    limit(request, 30, 60, scope="video_file")
    asset = _one(db, user, ident)
    stored = Path(settings.storage_dir) / asset.storage_key
    if not stored.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return Response(content=stored.read_bytes(), media_type=asset.content_type or "application/octet-stream")


@router.get("/{ident}/frames/{index}")
def clip_frame(ident: str, index: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
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
    return Response(content=png.read_bytes(), media_type="image/png")


@router.get("/{ident}/jobs")
def clip_jobs(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The bookkeeping for this clip's runs, so a report can be traced to the job that made it."""
    limit(request, 30, 60, scope="video_jobs")
    asset = _one(db, user, ident)
    jobs = list(db.scalars(select(Job).where(Job.type == "video.analyse").order_by(Job.created_at.desc()).limit(20)).all())
    relevant = [job for job in jobs if job.payload.get("asset_id") == asset.id]
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
