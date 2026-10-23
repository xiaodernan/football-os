"""Async job management endpoints (spec §47).

Provides CRUD operations for background jobs including status tracking, result retrieval,
and cleanup. Jobs are created by long-running operations (video analysis, simulation runs,
knowledge ingestion) and can be polled for completion status.

A job is one account's background work, so every door asks whose it is. A job's list is the
caller's own rows; an id that belongs to somebody else answers 404 through
`ownership_or_admin` (an admin may read any *known* id, but the list still names only the
caller's work). Until this landing the create door dropped the caller it already required,
the list returned every account's rows, and the three id doors acted on a job id alone.

The state vocabulary is ADR-006's: `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED |
RETRYING`. The video pipeline used to write `DONE` — a state the ADR never named — so a
finished video job could still be "cancelled"; migration 0036 rewrites the rows it left.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, new_public_id, ownership_or_admin
from app.models import Job, User

router = APIRouter(prefix="/jobs", tags=["jobs"])

#: ADR-006's three end states. One author for the set: the cancel path refuses them, the delete
#: path admits them, and the status row's completion instant is read only for them.
TERMINAL_JOB_STATUSES: Final = ("COMPLETED", "FAILED", "CANCELLED")


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
    status: str | None = Query(None, description="Filter by status (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, RETRYING)"),
    type: str | None = Query(None, description="Filter by job type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List the caller's own jobs, with optional filtering by status and type."""
    query = select(Job).where(Job.user_id == user.id)

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
        user_id=user.id,
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


def _job_or_404(db: Session, job_id: str, user: User) -> Job:
    """The caller's row, or §51's two absences.

    An id nobody holds answers `no_such_job` with the id the caller named, as before. An id that
    exists under another account goes through `ownership_or_admin`, which answers the platform's
    `not_found` — the same 404 shape every other owned noun uses. A row written before the create
    door named its caller has no owner, so it reads as absent to everyone but an admin.
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_job", "message": f"Job {job_id} not found", "job_id": job_id})
    ownership_or_admin(user, job.user_id or "", "Job")
    return job


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Get detailed status of a specific job including result or error.

    `completed_at` is derived rather than stored: the model has no completion column, and
    `updated_at` is the instant of the row's last transition — which, for one of the three
    terminal states, is its completion.
    """
    job = _job_or_404(db, job_id, user)

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        payload=job.payload or {},
        result=job.result,
        error=job.error,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        completed_at=job.updated_at.isoformat() if job.status in TERMINAL_JOB_STATUSES and job.updated_at else None,
    )


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a job in a terminal state. A queued, running or retrying job cannot be deleted."""
    job = _job_or_404(db, job_id, user)

    if job.status not in TERMINAL_JOB_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "job_not_deletable",
                "message": f"Cannot delete {job.status.lower()} job. Cancel or wait for completion first.",
                "job_id": job_id,
                "status": job.status,
            },
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
    """Cancel a queued, running or retrying job. A terminal job cannot be cancelled again."""
    job = _job_or_404(db, job_id, user)

    if job.status in TERMINAL_JOB_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "job_not_cancellable",
                "message": f"Cannot cancel {job.status.lower()} job. It is already terminal.",
                "job_id": job_id,
                "status": job.status,
            },
        )

    job.status = "CANCELLED"
    db.commit()

    return {"message": f"Job {job_id} cancelled"}
