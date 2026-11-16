"""The shared-passphrase admin console door — one gate, read-only aggregates.

Every visitor who knows the passphrase (123 by default, overridable with `ADMIN_PASSPHRASE`)
can read the behavioural aggregates. The passphrase is compared in constant time and the
counts are recomputed from the rows on every read — nothing is cached, nothing is stored
for the console, and the console never sees any account's identity.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import limit
from app.services.behavior import compute_behavior
from app.services.behavior_coach import compute_admin_coach_read

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_passphrase(passphrase: str | None = Header(default=None, alias="x-admin-passphrase")) -> None:
    expected = settings.admin_passphrase.encode("utf-8")
    offered = (passphrase or "").encode("utf-8")
    if not hmac.compare_digest(expected, offered):
        raise HTTPException(
            status_code=401,
            detail={"code": "admin_refused", "message": "The passphrase is wrong."},
        )


@router.get("/behavior", dependencies=[Depends(require_admin_passphrase)])
def behavior(request: Request, window_days: int = Query(default=90, ge=7, le=365), db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 60, 60, scope="admin_behavior")
    return compute_behavior(db, window_days=window_days)


@router.get("/coach-read", dependencies=[Depends(require_admin_passphrase)])
def coach_read(request: Request, window_days: int = Query(default=90, ge=7, le=365), db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 10, 10, scope="admin_coach_read")
    return compute_admin_coach_read(db, window_days=window_days)
