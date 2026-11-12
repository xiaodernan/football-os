"""The background analyse door: enqueue → worker → the report the page polls.

The synchronous door (`POST .../analyse`) runs the pipeline in the request; the background door puts a
`QUEUED` row on the board (ADR-008) and answers 202 immediately. This file holds both halves against a
real clip: the door half checks the 202, the row's payload and the no-duplicate rule, and the worker
half drains exactly the row the door created and reads the result through the same job status endpoint
the browser polls.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, init_db
from app.models import Job, VideoAsset, VideoDetection
from app.services import jobs as runner
from app.services.video import drain

API = "/api/v1/video"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.fixture(scope="module")
def clips(tmp_path_factory: Any) -> dict[str, Path]:  # type: ignore[no-untyped-def]
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg/ffprobe are not installed on this host")
    directory = tmp_path_factory.mktemp("background-clips")
    moving = directory / "background.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=2:r=25", "-pix_fmt", "yuv420p", str(moving)],
        check=True,
    )
    return {"moving": moving}


@pytest.fixture()
def created_jobs() -> Any:
    ids: list[str] = []
    yield ids
    if not ids:
        return
    with SessionLocal() as session:
        for job_id in ids:
            session.query(VideoDetection).filter(VideoDetection.job_id == job_id).delete()
            row = session.get(Job, job_id)
            if row is not None:
                session.delete(row)
        session.commit()


def _upload(client: TestClient, path: Path) -> str:
    with path.open("rb") as handle:
        response = client.post(f"{API}/upload?title=background-fixture", files={"file": (path.name, handle.read(), "video/mp4")})
    assert response.status_code == 201, response.text
    return str(response.json()["asset"]["id"])


def test_the_background_door_answers_202_with_a_queued_row(auth_client: TestClient, clips: Any, created_jobs: list[str]) -> None:  # type: ignore[no-untyped-def]
    init_db()
    asset_id = _upload(auth_client, clips["moving"])
    response = auth_client.post(f"{API}/{asset_id}/analyse?background=true&target_frames=8")
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "QUEUED"
    assert payload["deduplicated"] is False
    job_id = str(payload["job_id"])
    created_jobs.append(job_id)
    assert payload["poll"] == f"/api/v1/jobs/{job_id}"

    with SessionLocal() as session:
        row = session.get(Job, job_id)
        assert row is not None
        assert row.type == "video.analyse"
        assert row.status == "QUEUED"
        assert (row.payload or {}).get("asset_id") == asset_id
        assert (row.payload or {}).get("target_frames") == 8
        assert row.attempts == 0

    # The same door, asked twice with a run still pending, names the pending row rather than starting a second.
    again = auth_client.post(f"{API}/{asset_id}/analyse?background=true&target_frames=8")
    assert again.status_code == 202, again.text
    again_payload = again.json()
    assert again_payload["deduplicated"] is True
    assert again_payload["job_id"] == job_id
    created_jobs.append(job_id)

    with SessionLocal() as session:
        pending = [row for row in session.query(Job).filter(Job.type == "video.analyse", Job.status == "QUEUED").all() if (row.payload or {}).get("asset_id") == asset_id]
        assert len(pending) == 1, f"expected one pending run for the clip, got {len(pending)}: {[row.id for row in pending]}"


def test_a_queued_row_from_the_door_drains_to_completed(auth_client: TestClient, clips: Any, created_jobs: list[str]) -> None:  # type: ignore[no-untyped-def]
    init_db()
    asset_id = _upload(auth_client, clips["moving"])
    response = auth_client.post(f"{API}/{asset_id}/analyse?background=true&target_frames=6")
    assert response.status_code == 202, response.text
    job_id = str(response.json()["job_id"])
    created_jobs.append(job_id)

    with SessionLocal() as session:
        while True:
            outcome = runner.drain_one(session, handlers={"video.analyse": drain.drain_analyse})
            if outcome is None:
                break
        row = session.get(Job, job_id)
        assert row is not None
        assert row.status == "COMPLETED", f"expected COMPLETED, got {row.status}: {row.error}"
        assert (row.result or {}).get("frames", 0) > 0

    status_response = auth_client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "COMPLETED"

    listing = auth_client.get(f"{API}/{asset_id}/jobs").json()
    assert any(item["id"] == job_id for item in listing["items"])
    assert listing["detections"] >= 1


def test_the_analyse_door_still_answers_inline_by_default(auth_client: TestClient, clips: Any) -> None:  # type: ignore[no-untyped-def]
    init_db()
    asset_id = _upload(auth_client, clips["moving"])
    response = auth_client.post(f"{API}/{asset_id}/analyse?target_frames=6")
    assert response.status_code == 200, response.text
    assert response.json()["asset"]["status"] == "analysed"
    assert response.json()["job"]["status"] == "COMPLETED"


def test_a_clip_the_background_door_enqueued_is_gone_when_the_clip_is_deleted(auth_client: TestClient, clips: Any, created_jobs: list[str]) -> None:  # type: ignore[no-untyped-def]
    init_db()
    asset_id = _upload(auth_client, clips["moving"])
    response = auth_client.post(f"{API}/{asset_id}/analyse?background=true&target_frames=6")
    assert response.status_code == 202, response.text
    created_jobs.append(str(response.json()["job_id"]))

    deleted = auth_client.delete(f"{API}/{asset_id}")
    assert deleted.status_code == 204, deleted.text
    with SessionLocal() as session:
        assert session.get(VideoAsset, asset_id) is None
        # The jobs ride the clip out — deleting a clip takes its own analysis jobs with it.
        assert not session.query(Job).filter(Job.type == "video.analyse").filter(Job.payload["asset_id"].as_string() == asset_id).count()


def test_an_unsupported_enqueue_is_refused_the_same_way_as_an_unsupported_upload(auth_client: TestClient) -> None:  # type: ignore[no-untyped-def]
    init_db()
    response = auth_client.post(f"{API}/vid_does_not_exist/analyse?background=true")
    assert response.status_code == 404, response.text
