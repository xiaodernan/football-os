"""What M5 can currently serve, read from the database and the host rather than from the code (spec §59).

`capabilities` used to answer `m5_video_analysis: false` after the milestone had been verified, because
the flag was written as a literal before the feature existed and nobody went back for it. That is the
failure mode this module exists to remove: the answer is now derived from the two facts the endpoint
actually depends on — the tables are there, and the media tools the pipeline shells out to are on this
host's PATH. Either can go false on its own, and the reason is reported beside the flag.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models import VideoAsset, VideoDetection
from app.services.video.media import ffmpeg_path, ffprobe_path


def video_tables_present(session: Session) -> bool:
    names = inspect(session.get_bind()).get_table_names()
    return VideoAsset.__tablename__ in names and VideoDetection.__tablename__ in names


def video_counts(session: Session) -> dict[str, int]:
    if not video_tables_present(session):
        return {"assets": 0, "detections": 0}
    return {
        "assets": int(session.scalar(select(func.count()).select_from(VideoAsset)) or 0),
        "detections": int(session.scalar(select(func.count()).select_from(VideoDetection)) or 0),
    }


def video_readiness(session: Session) -> dict[str, Any]:
    """The flag, and each reason it could be false, stated separately."""
    tools = {"ffmpeg": ffmpeg_path() is not None, "ffprobe": ffprobe_path() is not None}
    tables = video_tables_present(session)
    return {
        "ready": tables and all(tools.values()),
        "tables_present": tables,
        "media_tools": tools,
        "counts": video_counts(session),
        "provider": "demo-pixel-stats",
        "note": "the vision provider measures pixels and labels itself demo; no real football event is claimed",
    }


__all__ = ["video_counts", "video_readiness", "video_tables_present"]
