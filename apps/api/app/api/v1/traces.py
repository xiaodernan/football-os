"""The trace door: read a request's spans back (M12 observability).

One door, `GET /api/v1/traces/{trace_id}`, answers the question the M12 document could not:
what did this request actually do, and how long did each part take.

The answer is the spans of one trace, oldest first, each with the parent it hung from - so the
tree is in the answer rather than reconstructed by the reader. A trace id nobody stored answers
404 with the same code any other absent record answers, and a trace id that exists but belongs
to another account's request is not a thing this tier can offer: the store is an operator's
window, so the door is auth-gated like every other one in this API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.core.span_store import read_trace
from app.models import User

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("/{trace_id}")
def trace_detail(
    trace_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Every span of one trace, oldest first."""
    if not trace_id or len(trace_id) > 64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_trace", "message": f"no stored trace {trace_id!r}"})

    spans = read_trace(db, trace_id)
    if not spans:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_trace", "message": f"no stored trace {trace_id!r}"})

    return {
        "trace_id": trace_id,
        "span_count": len(spans),
        "duration_ms": sum(span.duration_ms for span in spans),
        "spans": [
            {
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "name": span.name,
                "kind": span.kind,
                "status": span.status,
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration_ms": span.duration_ms,
                "attributes": span.attributes_json,
            }
            for span in spans
        ],
    }
