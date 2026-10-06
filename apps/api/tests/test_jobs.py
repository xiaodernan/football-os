"""Tests for the async job system (spec §47)."""

from fastapi.testclient import TestClient

from app.main import app


def _auth_client() -> TestClient:
    """Create a user and return an authenticated client."""
    client = TestClient(app)
    email = "job-test@example.com"
    password = "TestPass1234!"
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
