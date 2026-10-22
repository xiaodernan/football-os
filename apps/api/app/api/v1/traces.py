"""The trace door: read a request's spans back (M12 observability).

One door, `GET /api/v1/traces/{trace_id}`, answers the question the M12 document could not:
what did this request actually do, and how long did each part take.

The answer is the spans of one trace, oldest first, each with the parent it hung from - so the
tree is in the answer rather than reconstructed by the reader. A trace id nobody stored answers
404 with the same code any other absent record answers.

The store is an **operator's window**, and the door asks for the operator's standing. A stored
SERVER span carries the request's concrete `http.target` - measured on a share route as
`/api/v1/share/boards/secret-share-token` - and `request_spans` has no column that says whose
request it was, so any authenticated account holding a trace id could read another account's
path and query string. The check runs before the lookup: a non-admin is refused the same way for
an id that exists and one that does not.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, role_refusal, standing_check
from app.core.span_store import read_trace
from app.models import User

router = APIRouter(prefix="/traces", tags=["traces"])

#: The standing this door asks for, validated against the platform's vocabulary at import.
TRACE_STANDING: Final = standing_check(("admin",))


@router.get("/{trace_id}")
def trace_detail(
    trace_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Every span of one trace, oldest first. An operator's window, not a caller's own record."""
    if user.role not in TRACE_STANDING:
        raise role_refusal(
            held=user.role,
            required=TRACE_STANDING,
            message="Only an admin account may read stored request traces",
        )
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
