"""Async job management endpoints (spec §47).

Provides CRUD operations for background jobs including status tracking, result retrieval,
and cleanup. Jobs are created by long-running operations (video analysis, simulation runs,
knowledge ingestion) and can be polled for completion status.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, new_public_id
from app.models import Job, User

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobListResponse(BaseModel):
    jobs: list[dict[str, Any]]
    total: int
    page: int
    per_page: int


class JobCreateRequest(BaseModel):
    type: str
    payload: dict[str, Any] = {}


class JobCreateResponse(BaseModel):
    id: str
    type: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    id: str
    type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_at: str
    updated_at: str | None
    completed_at: str | None


@router.get("", response_model=JobListResponse)
def list_jobs(
    status: str | None = Query(None, description="Filter by status (QUEUED, RUNNING, COMPLETED, FAILED)"),
    type: str | None = Query(None, description="Filter by job type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List jobs with optional filtering by status and type."""
    query = select(Job)

    if status:
        query = query.where(Job.status == status.upper())
    if type:
        query = query.where(Job.type == type)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = int(db.scalar(count_query) or 0)

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(Job.created_at.desc()).offset(offset).limit(per_page)
    jobs = db.execute(query).scalars().all()

    return JobListResponse(
        jobs=[
            {
                "id": job.id,
                "type": job.type,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=JobCreateResponse)
def create_job(
    body: JobCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    """Create a new job. In production, this would trigger a worker to process it."""
    job = Job(
        id=new_public_id("job"),
        type=body.type,
        status="QUEUED",
        payload=body.payload,
        created_at=datetime.now(UTC),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobCreateResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        created_at=job.created_at.isoformat(),
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Get detailed status of a specific job including result or error."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        payload=job.payload or {},
        result=job.result,
        error=job.error,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        completed_at=None,  # Job model doesn't have this field yet
    )


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a completed or failed job. Cannot delete running jobs."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in ("RUNNING", "QUEUED"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete {job.status.lower()} job. Cancel or wait for completion first.",
        )

    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} deleted"}


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Cancel a queued or running job."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in ("COMPLETED", "FAILED"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel {job.status.lower()} job. It is already terminal.",
        )

    job.status = "CANCELLED"
    job.completed_at = datetime.now(UTC)
    db.commit()

    return {"message": f"Job {job_id} cancelled"}
