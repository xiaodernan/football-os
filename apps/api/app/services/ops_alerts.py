"""Operator alerts about the platform's own spend (M13 Phase 6 item 21).

The cost advisor already names a month that has crossed its ceiling. Naming it on a page only reaches a reader
who opens the page, and the reader who needs it is the one not looking. This module is the part that tells
somebody without being asked.

**The delivery decision, made here rather than left open: a signed webhook plus a stored ledger.** Every pager,
chat room and email relay this project is likely to use accepts an HTTPS POST, so the channel is one URL and no
vendor SDK; email over SMTP would have made the suite depend on a mailbox, and a vendor client would have made
the alert channel a second thing to configure, pin and mock. The ledger is the other half: an outbound POST is a
fact that disappears when the answer does, so the row is written *before* any attempt and keeps the question
"was it sent, and if not why not" answerable afterwards.

The row is also the sweep's queue. A failed POST is retried by the next sweep, up to `MAX_DELIVERY_ATTEMPTS`,
because the alternative -- a webhook that was down for one minute swallowing the month's only warning -- is the
failure this channel exists to prevent. A sweep with no webhook configured still records the alert and says so;
the ledger is then the delivery channel, and a webhook configured later picks the undelivered rows up on the next
sweep, because a month already over its ceiling must not go unannounced merely because the channel arrived after
it did.

`dedupe_key` names the condition rather than the reader: one month over its ceiling raises one alert however many
sweeps run, and a month that is first over its *pace* and later over its ceiling raises the warning and then the
critical alert, because those are two different facts and a pager should hear both.

The payload is signed with `APP_SECRET` over the exact bytes sent, so a receiver can tell an alert from a
stranger's POST to the same URL. Nothing here changes which provider a door calls: the advisor stays an advisor,
and this is the doorbell attached to it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.models import OpsAlert, User
from app.services.cost_advisor import monthly_state

#: How the alert and its deduplication are derived, published beside the ledger.
ALERT_FORMULA: Final = (
    "an alert is raised once per (kind, month, condition): monthly_state is recomputed from model_calls at each "
    "sweep, and dedupe_key = cost_monthly_ceiling:<month>:<projected_over|exceeded> means a condition is one row "
    "however many sweeps see it"
)

#: The channel as configured, stated in every answer so a reader knows whether "stored" also means "sent".
DELIVERY_NOTE: Final = (
    "a webhook is configured (OPS_ALERT_WEBHOOK_URL); each alert is POSTed once per sweep until the receiver "
    "answers 2xx, or the attempt ceiling is reached"
)
NO_WEBHOOK_NOTE: Final = (
    "no webhook is configured (set OPS_ALERT_WEBHOOK_URL); alerts are recorded in this ledger only, and a webhook "
    "configured later delivers them on the next sweep"
)

#: A dead receiver stops being retried here. The row keeps its last error and stays on the ledger.
MAX_DELIVERY_ATTEMPTS: Final = 5
WEBHOOK_TIMEOUT_SECONDS: Final = 5.0
STATE_OPEN: Final = "open"
STATE_ACKNOWLEDGED: Final = "acknowledged"


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


def signature_of(body: bytes) -> str:
    """The HMAC a receiver verifies: sha256 over the exact bytes, keyed by the platform's own secret."""
    return hmac.new(settings.app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post(url: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    """One best-effort POST. The answer is a fact for the row, never an exception for the sweep."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Football-Alert-Signature": f"sha256={signature_of(body)}",
            "X-Football-Alert-Id": str(payload.get("alert", "")),
            "User-Agent": "football-os-ops-alerts/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as answer:
            if 200 <= answer.status < 300:
                return True, None
            return False, f"HTTP {answer.status}"
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return False, str(error)[:300]


def _row(alert: OpsAlert) -> dict[str, Any]:
    return {
        "alert": alert.id,
        "kind": alert.kind,
        "level": alert.level,
        "state": alert.state,
        "dedupe_key": alert.dedupe_key,
        "summary": alert.summary,
        "detail": alert.detail,
        "delivery_channel": alert.delivery_channel,
        "delivery_attempts": alert.delivery_attempts,
        "delivered_at": _iso(alert.delivered_at),
        "delivery_error": alert.delivery_error,
        "acknowledged_at": _iso(alert.acknowledged_at),
        "acknowledged_by": alert.acknowledged_by,
        "raised_at": _iso(alert.created_at),
    }


def _payload(alert: OpsAlert) -> dict[str, Any]:
    return {
        "alert": alert.id,
        "kind": alert.kind,
        "level": alert.level,
        "month": (alert.detail or {}).get("month"),
        "summary": alert.summary,
        "detail": alert.detail,
        "raised_at": _iso(alert.created_at),
        "sent_at": datetime.now(UTC).isoformat(),
        "signature_version": 1,
    }


def _due(session: Session, *, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The month's state and, if it warrants one, the alert the state names.

    `None` means there is nothing to say: no ceiling configured, or a month under both its spend and its pace.
    """
    monthly = monthly_state(session, now=now)
    if not monthly["configured"]:
        return monthly, None
    month = str(monthly["month"])
    ceiling = float(monthly["ceiling_usd"] or 0.0)
    spend = float(monthly["spend_usd"])
    if monthly["exceeded"]:
        over = round(spend - ceiling, 4)
        return monthly, {
            "kind": "cost_monthly_ceiling",
            "level": "critical",
            "dedupe_key": f"cost_monthly_ceiling:{month}:exceeded",
            "summary": f"${spend:.2f} spent in {month} against a ${ceiling:.2f} ceiling, ${over:.2f} over",
        }
    if monthly["projected_over"]:
        projection = float(monthly["projected_month_end_usd"])
        return monthly, {
            "kind": "cost_monthly_ceiling",
            "level": "warning",
            "dedupe_key": f"cost_monthly_ceiling:{month}:projected_over",
            "summary": f"${spend:.2f} spent in {month}, projected ${projection:.2f} by month end against a ${ceiling:.2f} ceiling",
        }
    return monthly, None


def evaluate(session: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """One sweep: raise the alert the month warrants (once), then deliver everything still undelivered.

    The write commits before delivery begins, so an alert that cannot reach its receiver is still on the ledger
    the sweeper can read. The answer says what was raised, what was already held, and what left the building.
    """
    monthly, due = _due(session, now=now)
    raised: list[dict[str, Any]] = []
    already: list[str] = []
    if due is not None:
        held = session.scalar(select(OpsAlert).where(OpsAlert.dedupe_key == due["dedupe_key"]))
        if held is None:
            row = OpsAlert(
                id=new_public_id("alert"),
                kind=due["kind"],
                level=due["level"],
                dedupe_key=due["dedupe_key"],
                summary=due["summary"],
                detail={**monthly, "trigger": due["dedupe_key"], "source": "cost_advisor.monthly_state"},
                state=STATE_OPEN,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            raised.append(_row(row))
        else:
            already.append(held.id)

    delivery = deliver_pending(session)
    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "monthly": monthly,
        "raised": raised,
        "already_held": already,
        "delivery": delivery,
        "formula": ALERT_FORMULA,
        "limitation": (
            "the month-to-date figure is recomputed from model_calls on this sweep, not read from a provider invoice; "
            "the webhook is attempted (never guaranteed) up to the attempt ceiling, and the ledger is the record of "
            "what happened"
        ),
    }


def deliver_pending(session: Session) -> dict[str, Any]:
    """POST every undelivered alert the webhook may still take, and record each attempt's outcome.

    A row is attempted when it has never been delivered and has attempts left. A success stamps `delivered_at`
    and is never sent again; a failure keeps the receiver's own words in `delivery_error` for the operator who
    reads the ledger. With no webhook configured nothing is attempted, the rows are marked `recorded`, and the
    next configured sweep is the one that delivers them.
    """
    url = settings.ops_alert_webhook_url.strip()
    pending = list(
        session.scalars(
            select(OpsAlert)
            .where(OpsAlert.delivered_at.is_(None), OpsAlert.delivery_attempts < MAX_DELIVERY_ATTEMPTS)
            .order_by(OpsAlert.created_at.asc())
        ).all()
    )
    attempted = delivered = failed = 0
    for alert in pending:
        if not url:
            if alert.delivery_channel != "recorded":
                alert.delivery_channel = "recorded"
                session.commit()
            continue
        attempted += 1
        alert.delivery_channel = "webhook"
        alert.delivery_attempts += 1
        ok, error = _post(url, _payload(alert))
        if ok:
            alert.delivered_at = datetime.now(UTC)
            alert.delivery_error = None
            delivered += 1
        else:
            alert.delivery_error = error
            failed += 1
        session.commit()
        session.refresh(alert)
    # With no URL nothing is pending: a recorded alert is complete in the only channel it has, and calling it
    # pending would make every ledger look like a backlog of failed deliveries.
    remaining = 0
    if url:
        remaining = int(
            session.scalar(
                select(func.count())
                .select_from(OpsAlert)
                .where(OpsAlert.delivered_at.is_(None), OpsAlert.delivery_attempts < MAX_DELIVERY_ATTEMPTS)
            )
            or 0
        )
    return {
        "channel": "webhook" if url else "recorded",
        "attempted": attempted,
        "delivered": delivered,
        "failed": failed,
        "pending": remaining,
        "max_attempts": MAX_DELIVERY_ATTEMPTS,
        "note": DELIVERY_NOTE if url else NO_WEBHOOK_NOTE,
    }


def list_alerts(session: Session, *, state: str | None = None, limit: int = 50) -> dict[str, Any]:
    """The ledger, newest first, with the counts an operator triaging it needs beside the rows."""
    query = select(OpsAlert).order_by(OpsAlert.created_at.desc()).limit(max(1, limit))
    if state in (STATE_OPEN, STATE_ACKNOWLEDGED):
        query = query.where(OpsAlert.state == state)
    rows = list(session.scalars(query).all())
    total = int(session.scalar(select(func.count()).select_from(OpsAlert)) or 0)
    open_count = int(session.scalar(select(func.count()).select_from(OpsAlert).where(OpsAlert.state == STATE_OPEN)) or 0)
    acknowledged = int(session.scalar(select(func.count()).select_from(OpsAlert).where(OpsAlert.state == STATE_ACKNOWLEDGED)) or 0)
    # Pending means a webhook would attempt it on the next sweep. With no URL configured that set is empty: the
    # ledger is the channel, and an alert delivered to it is not a failure waiting to happen.
    pending = 0
    if settings.ops_alert_webhook_url.strip():
        pending = int(
            session.scalar(
                select(func.count())
                .select_from(OpsAlert)
                .where(OpsAlert.delivered_at.is_(None), OpsAlert.delivery_attempts < MAX_DELIVERY_ATTEMPTS)
            )
            or 0
        )
    return {
        "items": [_row(row) for row in rows],
        "total": total,
        "open": open_count,
        "acknowledged": acknowledged,
        "pending_delivery": pending,
        "channel": "webhook" if settings.ops_alert_webhook_url.strip() else "recorded",
        "formula": ALERT_FORMULA,
        "note": DELIVERY_NOTE if settings.ops_alert_webhook_url.strip() else NO_WEBHOOK_NOTE,
    }


def acknowledge(session: Session, user: User, alert_id: str) -> dict[str, Any] | None:
    """Mark one alert acknowledged by the operator who read it. An unknown id is `None`, the caller's 404."""
    row = session.get(OpsAlert, alert_id)
    if row is None:
        return None
    if row.state != STATE_ACKNOWLEDGED:
        row.state = STATE_ACKNOWLEDGED
        row.acknowledged_at = datetime.now(UTC)
        row.acknowledged_by = user.id
        session.commit()
        session.refresh(row)
    return _row(row)


__all__ = [
    "ALERT_FORMULA",
    "DELIVERY_NOTE",
    "MAX_DELIVERY_ATTEMPTS",
    "NO_WEBHOOK_NOTE",
    "STATE_ACKNOWLEDGED",
    "STATE_OPEN",
    "acknowledge",
    "deliver_pending",
    "evaluate",
    "list_alerts",
    "signature_of",
]
