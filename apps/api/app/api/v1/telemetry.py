"""The browser's behavioural beacon — a public, minimal, shape-checked door.

One row per web navigation. Anonymous by design: no account, no identity, no cookie value,
only a client-minted random session reference and the page the browser was on. The row is
also never served back to a browser; the admin console reads aggregates computed on the fly.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import limit
from app.models import PageView

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_PATH = re.compile(r"^/[A-Za-z0-9\-._~!$&'()*+,;=:@/]*$")
_SESSION = re.compile(r"^[A-Za-z0-9_-]{8,48}$")


class PageViewIn(BaseModel):
    session_ref: str = Field(min_length=8, max_length=48)
    path: str = Field(min_length=1, max_length=200)
    dwell_ms: int = Field(default=0, ge=0, le=3_600_000)
    bounced: bool = False


@router.post("/page-view", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=True)
def page_view(request: Request, payload: PageViewIn, db: Session = Depends(get_db)) -> Response:
    limit(request, 240, 60, scope="telemetry_page_view")
    path = payload.path.strip()
    if not _PATH.match(path) or "//" in path or ".." in path:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_path", "message": "The path is outside the accepted shape."})
    session_ref = payload.session_ref.strip()
    if not _SESSION.match(session_ref):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_session", "message": "The session reference is outside the accepted shape."})
    db.add(PageView(session_ref=session_ref, path=path, dwell_ms=payload.dwell_ms, bounced=payload.bounced, seeded=False))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
