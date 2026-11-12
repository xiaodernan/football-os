"""The video drain handler end to end, against a real tiny clip and the real pipeline stages.

The queue is real only if a production job type runs through it. This file proves that path for
`video.analyse` itself: upload a clip built by the test, enqueue a job onto the runner, drain it, and
read the report — without touching the live /video door, which the `tests/test_video.py` suite already
holds to its own contract.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.core.db import SessionLocal, init_db
from app.models import Job, User
from app.services import jobs as runner
from app.services.video import drain

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _clip(path: Path) -> None:
    import numpy as np  # type: ignore[import-not-found]

    width, height, frames = 64, 36, 12
    for index in range(frames):
        frame = np.full((height, width, 3), 40, dtype=np.uint8)
        offset = 2 + index
        frame[6:30, offset : offset + 12] = 220
        (path / f"frame_{index:03d}.pgm").write_bytes(_pgm(frame))
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", "6", "-i", str(path / "frame_%03d.pgm"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-s", f"{width}x{height}", str(path / "tiny.mp4"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _pgm(frame: Any) -> bytes:  # type: ignore[no-untyped-def]
    header = f"P5\n{frame.shape[1]} {frame.shape[0]}\n255\n".encode("ascii")
    return header + frame.tobytes()


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not on this host; the video drain cannot be walked")
def test_a_queued_video_analyse_job_drains_to_completed_on_a_real_clip() -> None:
    init_db()

    with SessionLocal() as session:
        user = session.query(User).filter(User.role == "player").first()
        if user is None:
            user = User(id="usr_drain_video", email="drain-video@example.test", password_hash="x", display_name="Drain", role="player")
            session.add(user)
            session.commit()
        user_id = str(user.id)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _clip(work)
        clip_bytes = (work / "tiny.mp4").read_bytes()

        from app.services.video.pipeline import detect_container, store_upload

        upload_rejection = detect_container(clip_bytes)
        assert upload_rejection == "video/mp4", upload_rejection
        with SessionLocal() as session:
            asset = store_upload(session, user_id=user_id, filename="drain-fixture.mp4", data=clip_bytes, max_bytes=50 * 1024 * 1024)
            assert asset is not None and asset.owner_id == user_id
            asset_id = str(asset.id)

        with SessionLocal() as session:
            job = Job(
                id="job_drain_test_1",
                type="video.analyse",
                status="QUEUED",
                payload={"asset_id": asset_id, "target_frames": 6},
                user_id=user_id,
            )
            session.add(job)
            session.commit()

        with SessionLocal() as session:
            # The suite runs in one shared database; other files may have left QUEUED rows ahead of ours.
            # Drain until nothing is claimable — the same loop the worker runs — rather than assume
            # exactly one job exists on this board.
            while True:
                outcome = runner.drain_one(session, handlers={"video.analyse": drain.drain_analyse})
                if outcome is None:
                    break
            happened = session.get(Job, "job_drain_test_1")
            assert happened is not None
            assert happened.status == "COMPLETED", f"expected COMPLETED after drain, got {happened.status}: {happened.error}"
            assert (happened.result or {}).get("frames", 0) > 0, "the drained job claims the pipeline produced frames"


def test_the_drain_handler_is_named_stably() -> None:
    assert drain.drain_analyse is not None
    assert drain.drain_analyse.__module__ == "app.services.video.drain"
