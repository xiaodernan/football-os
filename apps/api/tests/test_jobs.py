"""Tests for the async job system (spec §47)."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import Job, User

#: The e-mail addresses this module registers. The test database is shared across files, so an account
#: — and every `QUEUED` row its doors wrote — outlives the case that made it, and the next module's
#: `claim(limit=1)` takes a stranger's job. `test_job_runner.py` documents the hazard for its own rows;
#: this file was the one leaving them behind.
_emails: set[str] = set()

#: The same addresses, never cleared — the population `TestNothingSurvivesItsCase` judges.
_seen: set[str] = set()


@pytest.fixture(autouse=True)
def _the_module_pays_for_its_own_rows() -> Iterator[None]:
    """Delete the account a case registered and every row that account's doors wrote.

    The queue's correctness cases ask `claim(limit=1)` "what is the next job?", and that question is
    answered by the *table*, not by the case asking it. A row left here is a row a later module claims.
    """
    yield
    from app.core.db import SessionLocal

    with SessionLocal() as session:
        owned = list(session.scalars(select(User.id).where(User.email.in_(_emails))))
        if owned:
            session.query(Job).filter(Job.user_id.in_(owned)).delete(synchronize_session=False)
            session.query(User).filter(User.id.in_(owned)).delete(synchronize_session=False)
            session.commit()
    _emails.clear()


def _register(email: str) -> None:
    """Name an account this module made, so the teardown deletes it and the witness can count it."""
    _emails.add(email)
    _seen.add(email)


def _auth_client() -> TestClient:
    """Create a user and return an authenticated client."""
    client = TestClient(app)
    email = "job-test@example.com"
    password = "TestPass1234!"
    _register(email)
    payload = {
        "email": email,
        "password": password,
        "display_name": "Job Tester",
        "role": "player",
        "accepts_data_policy": True,
    }
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_list_jobs_empty():
    """GET /jobs returns empty list when no jobs exist."""
    client = _auth_client()
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert data["total"] >= 0


def test_create_job():
    """POST /jobs creates a new job with valid payload."""
    client = _auth_client()
    payload = {
        "type": "video_analysis",
        "payload": {"video_id": "vid_123", "task": "detect_events"},
    }
    resp = client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "video_analysis"
    assert data["status"] == "QUEUED"
    assert "id" in data


def test_get_job_status():
    """GET /jobs/{job_id} returns job details."""
    client = _auth_client()
    # Create a job first
    create_resp = client.post(
        "/api/v1/jobs",
        json={"type": "simulation", "payload": {"match_id": "m_1"}},
    )
    job_id = create_resp.json()["id"]

    # Fetch it
    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert data["type"] == "simulation"


def test_get_nonexistent_job():
    """GET /jobs/{job_id} returns 404 for missing jobs."""
    client = _auth_client()
    resp = client.get("/api/v1/jobs/job_nonexistent")
    assert resp.status_code == 404


def test_cancel_queued_job():
    """POST /jobs/{job_id}/cancel transitions queued job to cancelled."""
    client = _auth_client()
    # Create a job
    create_resp = client.post(
        "/api/v1/jobs",
        json={"type": "scouting_report", "payload": {"player_id": "p_1"}},
    )
    job_id = create_resp.json()["id"]

    # Cancel it
    cancel_resp = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    data = cancel_resp.json()
    assert data["message"] == f"Job {job_id} cancelled"


def test_delete_completed_job():
    """DELETE /jobs/{job_id} removes completed or failed jobs."""
    client = _auth_client()
    # Create a job
    create_resp = client.post(
        "/api/v1/jobs",
        json={"type": "training_plan", "payload": {"athlete_id": "a_1"}},
    )
    job_id = create_resp.json()["id"]

    # Mark it as completed (simulate worker finishing it)
    from app.core.db import SessionLocal
    from app.models import Job
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        job.status = "COMPLETED"
        job.result = {"output": "done"}
        session.commit()
    finally:
        session.close()

    # Delete it
    delete_resp = client.delete(f"/api/v1/jobs/{job_id}")
    assert delete_resp.status_code == 200

    # Verify it's gone
    get_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert get_resp.status_code == 404


def test_list_jobs_with_pagination():
    """GET /jobs supports limit and offset parameters."""
    client = _auth_client()
    # Create multiple jobs
    for i in range(5):
        client.post(
            "/api/v1/jobs",
            json={"type": "research", "payload": {"query": f"test_{i}"}},
        )

    # List with limit
    resp = client.get("/api/v1/jobs?per_page=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["jobs"]) <= 2
    assert data["total"] >= 5


def test_list_jobs_by_type():
    """GET /jobs can filter by job type."""
    client = _auth_client()
    # Create jobs of different types
    client.post(
        "/api/v1/jobs",
        json={"type": "video_analysis", "payload": {}},
    )
    client.post(
        "/api/v1/jobs",
        json={"type": "simulation", "payload": {}},
    )

    # Filter by type
    resp = client.get("/api/v1/jobs?type=video_analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["type"] == "video_analysis" for item in data["jobs"])


def _player() -> tuple[TestClient, str]:
    """A fresh account and its user id.

    Jobs are per-account work, so the cases below need two *distinct* accounts; the module-level
    `_auth_client` deliberately reuses one fixed email for the older cases.
    """
    from app.core.db import SessionLocal

    client = TestClient(app)
    email = f"job-owner-{uuid4().hex[:8]}@example.test"
    _register(email)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass1234!",
            "display_name": "Job Owner",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"registration failed: {response.text}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None, f"the register door answered but no row exists for {email}"
        return client, user.id


def _create(client: TestClient, job_type: str = "simulation") -> str:
    response = client.post("/api/v1/jobs", json={"type": job_type, "payload": {"match_id": "m_1"}})
    assert response.status_code == 200, f"the create door refused: {response.text}"
    return str(response.json()["id"])


def _set_status(job_id: str, status: str) -> None:
    """Stand in for the worker that owns the transition, so the door is judged on the row it reads."""
    from app.core.db import SessionLocal

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job is not None, f"job {job_id} disappeared before the transition could be written"
        job.status = status
        job.result = {"output": "done"} if status == "COMPLETED" else None
        session.commit()


class TestTheJobBelongsToItsCreator:
    """§47's jobs are a caller's own background work; no door used to ask whose."""

    def test_the_created_job_names_its_creator(self) -> None:
        owner, owner_id = _player()
        job_id = _create(owner)

        from app.core.db import SessionLocal

        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None, f"the create door answered {job_id} but no row exists"
            assert job.user_id == owner_id, f"the door stored user_id={job.user_id!r} for a job {owner_id!r} created"

    def test_the_list_is_the_callers_own_work(self) -> None:
        first, _ = _player()
        second, _ = _player()
        mine = {_create(first) for _ in range(2)}
        theirs = _create(second)

        listed = first.get("/api/v1/jobs")
        assert listed.status_code == 200
        assert {row["id"] for row in listed.json()["jobs"]} == mine, (
            f"the list answered {[row['id'] for row in listed.json()['jobs']]!r} for an account owning {sorted(mine)!r}"
        )
        assert listed.json()["total"] == 2, f"total counted {listed.json()['total']} rows, not the caller's two"

        other = second.get("/api/v1/jobs").json()
        assert {row["id"] for row in other["jobs"]} == {theirs}
        assert other["total"] == 1, f"the second account's total read {other['total']}"

    def test_a_foreign_id_reads_as_absent_on_every_door(self) -> None:
        owner, _ = _player()
        stranger, _ = _player()
        job_id = _create(owner)

        read = stranger.get(f"/api/v1/jobs/{job_id}")
        assert read.status_code == 404, f"a stranger read another account's job: {read.status_code} {read.text}"
        assert read.json()["detail"]["code"] == "not_found", f"the refusal named {read.json()['detail']!r}"

        delete = stranger.delete(f"/api/v1/jobs/{job_id}")
        assert delete.status_code == 404, f"a stranger deleted another account's job: {delete.status_code} {delete.text}"
        assert delete.json()["detail"]["code"] == "not_found"

        cancel = stranger.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancel.status_code == 404, f"a stranger cancelled another account's job: {cancel.status_code} {cancel.text}"
        assert cancel.json()["detail"]["code"] == "not_found"

        kept = owner.get(f"/api/v1/jobs/{job_id}")
        assert kept.status_code == 200, "the owner lost access after a stranger's attempts"
        assert kept.json()["status"] == "QUEUED", f"a stranger's attempts moved the job to {kept.json()['status']!r}"

    def test_an_admin_reads_a_foreign_job_but_not_the_list(self, admin_client: TestClient) -> None:
        """`ownership_or_admin` grants an admin a known id; a *list* is still the caller's own work."""
        owner, _ = _player()
        job_id = _create(owner)

        assert admin_client.get(f"/api/v1/jobs/{job_id}").status_code == 200
        listed = admin_client.get("/api/v1/jobs")
        assert listed.status_code == 200
        assert job_id not in {row["id"] for row in listed.json()["jobs"]}, "the list widened for an admin"


class TestTheTerminalState:
    """ADR-006's machine ends at COMPLETED | FAILED | CANCELLED; the doors knew two of the three."""

    def test_a_cancelled_job_cannot_be_cancelled_again(self) -> None:
        owner, _ = _player()
        job_id = _create(owner)
        assert owner.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200

        again = owner.post(f"/api/v1/jobs/{job_id}/cancel")
        assert again.status_code == 409, f"a second cancel answered {again.status_code}: {again.text}"
        assert again.json()["detail"]["code"] == "job_not_cancellable"

    def test_every_terminal_state_refuses_the_cancel(self) -> None:
        owner, _ = _player()
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            job_id = _create(owner)
            _set_status(job_id, status)
            refused = owner.post(f"/api/v1/jobs/{job_id}/cancel")
            assert refused.status_code == 409, f"a {status} job accepted a cancel: {refused.status_code} {refused.text}"

    def test_a_retrying_job_cannot_be_deleted(self) -> None:
        """ADR-006 names RETRYING between RUNNING and the end states; a row about to run again is not disposable."""
        owner, _ = _player()
        job_id = _create(owner)
        _set_status(job_id, "RETRYING")

        refused = owner.delete(f"/api/v1/jobs/{job_id}")
        assert refused.status_code == 409, f"a RETRYING job accepted a delete: {refused.status_code} {refused.text}"
        assert refused.json()["detail"]["code"] == "job_not_deletable"
        assert owner.get(f"/api/v1/jobs/{job_id}").status_code == 200, "the row disappeared despite the refusal"

    def test_the_completed_at_field_names_the_terminal_instant(self) -> None:
        owner, _ = _player()
        job_id = _create(owner)
        queued = owner.get(f"/api/v1/jobs/{job_id}")
        assert queued.status_code == 200
        assert queued.json()["completed_at"] is None, "a queued job already named a completion"

        _set_status(job_id, "COMPLETED")
        finished = owner.get(f"/api/v1/jobs/{job_id}")
        assert finished.status_code == 200
        body = finished.json()
        assert body["completed_at"] is not None, "a completed job answered completed_at=null"
        assert body["completed_at"] == body["updated_at"], (
            f"completed_at {body['completed_at']!r} is not the row's last transition {body['updated_at']!r}"
        )


class TestNothingSurvivesItsCase:
    """The witness for the autouse teardown, and therefore for the six cases in `test_job_runner.py`.

    Collected last, so every creating case above has already been torn down: a row that outlives its case
    is a row the next module's `claim(limit=1)` takes, which is how a leak in this file becomes a failure
    three files away — measured 2026-11-23, six of `test_job_runner.py`'s cases died that way at HEAD.
    """

    def test_no_job_this_file_registered_survives_its_case(self) -> None:
        from app.core.db import SessionLocal

        owner, owner_id = _player()
        assert _create(owner), "the create door refused, so the count below would prove nothing"
        assert len(_seen) > 1, f"only this case's own account is registered ({sorted(_seen)}), so nothing is witnessed"
        with SessionLocal() as session:
            survived = list(
                session.scalars(select(User.id).where(User.email.in_(sorted(_seen)), User.id != owner_id))
            )
            stranded = (
                session.scalar(select(func.count()).select_from(Job).where(Job.user_id.in_(survived)))
                if survived
                else 0
            )
        assert not survived and not stranded, (
            f"{len(survived)} account(s) and {stranded} job row(s) outlived the case that made them — "
            "the teardown above is what keeps the next module's `claim(limit=1)` honest"
        )
        assert owner.get("/api/v1/jobs").json()["total"] == 1, "the live case lost its own row"
