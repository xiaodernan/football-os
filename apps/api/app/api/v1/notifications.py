"""The notification tier's doors (spec module 27).

Everything under `/notifications` needs a session, and a notification the caller does
not own reads as 404 (`ownership_or_admin`) — the same absence every private tier
answers with, so probing ids learns nothing. There is no public door and no 403 here:
what the caller may not read simply does not answer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.notifications import list_for, mark_all_read, mark_read, unread_total

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def my_notifications(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 60, scope="notifications_list")
    return list_for(db, user.id, page=page)


@router.get("/unread-total")
def my_unread_total(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, int]:
    """The number the nav badge shows. Cheap enough to poll."""
    limit(request, 120, 60, scope="notifications_unread")
    return {"unread_total": unread_total(db, user.id)}


@router.post("/read-all")
def read_everything(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 20, 60, scope="notifications_read_all")
    return mark_all_read(db, user.id)


@router.post("/{ident}/read")
def read_one(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 60, scope="notifications_read_one")
    row = mark_read(db, user.id, ident)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "No such notification for this account"})
    return row
