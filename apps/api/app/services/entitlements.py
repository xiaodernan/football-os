"""§42's entitlement architecture: a plan is a ceiling read from data, and payment is nowhere in it.

The spec lists five parts — Feature, Plan, Limit, Usage, Entitlement — and says in terms that the MVP must not wire
a payment vendor yet. This module is the whole of that, with two rules it will not break:

* **The matrix is the table, not a constant.** `entitlements` has had no consumer since it was created in `0001`,
  so the rows are seeded here from `DEFAULT_MATRIX` and read back on every question. A page that printed a limit
  from a Python list while the table said something else would be a claim with two answers, which is the failure
  mode this tier has been built to avoid.
* **A ceiling is only published where it is enforced.** `enforced` names the features a write is actually refused
  on; the rest are listed as *ceilings the data holds*, with the limitation sentence saying plainly that no door
  refuses on them yet. An unenforced limit presented as a rule is the same kind of document as a stored report
  body that nobody recomputed.

Usage is counted from `usage_events` at read time — a row per act, never a stored counter — and the same act
cannot spend a ceiling twice, because the act's own row identity is part of the usage key.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Entitlement, UsageEvent, utc_today

#: §42's seven plan names, in the order the spec lists them. Nothing here implies a price or a payment.
PLANS: Final = ("free", "player", "pro", "coach", "club", "academy", "enterprise")

#: What may be metered, and against which kind of subject. `organizations` belongs to an account; the rest belong
#: to a tenant, because that is where the rows live.
FEATURES: Final[dict[str, str]] = {
    "organizations": "user",
    "club_members": "organization",
    "team_sheets": "organization",
    "plans_open": "organization",
    "sessions_recorded": "organization",
    "reports_saved": "organization",
}

MONTH = "month"
DAY = "day"

#: The seeded matrix. Every plan can do everything; the numbers rise with the plan. `free` is the plan an account
#: holds when nothing has granted it anything else, so these are the ceilings that bite today.
DEFAULT_MATRIX: Final[dict[str, dict[str, tuple[int, str]]]] = {
    plan: {
        "organizations": (limits[0], MONTH),
        "club_members": (limits[1], MONTH),
        "team_sheets": (limits[2], MONTH),
        "plans_open": (limits[3], MONTH),
        "sessions_recorded": (limits[4], DAY),
        "reports_saved": (limits[5], DAY),
    }
    for plan, limits in {
        "free": (1, 5, 1, 3, 5, 1),
        "player": (1, 5, 1, 3, 10, 2),
        "pro": (2, 10, 2, 10, 30, 5),
        "coach": (3, 30, 4, 30, 60, 10),
        "club": (5, 60, 8, 80, 150, 20),
        "academy": (8, 120, 16, 200, 400, 40),
        "enterprise": (40, 1000, 100, 2000, 5000, 200),
    }.items()
}

#: The features a write is actually refused on. §41's Reports is the first door metered this way; the rest are
#: published as ceilings and enforced by the tiers that own them as each is wired.
ENFORCED: Final = ("reports_saved",)

#: The plan a subject holds when nothing has granted it anything else. Named once because three tiers read it:
#: the meter that refuses, the door that prints the ceiling, and the `free` row of the matrix above.
DEFAULT_PLAN: Final = "free"

NO_PAYMENT: Final = "no price, no currency, no payment provider and no checkout appears anywhere in this tier: a plan is a ceiling read from the entitlements table, and §42 says the architecture comes before any payment"

REFUSALS: Final = ("no_such_entitlement_plan", "no_such_feature", "entitlement_limit", "usage_period_shape")
NOT_FOUND_CODES: Final[frozenset[str]] = frozenset({"no_such_entitlement_plan", "no_such_feature"})
CONFLICT_CODES: Final[frozenset[str]] = frozenset({"entitlement_limit"})
UNPROCESSABLE_CODES: Final[frozenset[str]] = frozenset({"usage_period_shape"})
# §42 has no refusal of its own that is about standing: an exceeded ceiling is a 409, and 403 stays §39's.
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()


def ensure_matrix(session: Session) -> int:
    """Seed the matrix from `DEFAULT_MATRIX` and report how many rows it holds. Idempotent by (feature, plan)."""
    held = {(row.feature, row.plan): row for row in session.scalars(select(Entitlement).where(Entitlement.feature.in_(list(FEATURES)), Entitlement.plan.in_(list(PLANS))))}
    added = 0
    for plan, features in DEFAULT_MATRIX.items():
        for feature, (limit_value, period) in features.items():
            existing = held.get((feature, plan))
            if existing is None:
                session.add(Entitlement(id=new_public_id("ent"), feature=feature, plan=plan, limit_value=limit_value, period=period))
                added += 1
            # An existing row is left alone. The seed is how the table gets its rows, not how it
            # keeps them: if the seeder could overwrite an edit, the matrix would be a constant wearing a
            # table's clothes, and `matrix_from_table` would be publishing a number that had already been
            # changed back.
    session.commit()
    return int(session.scalar(select(func.count()).select_from(Entitlement)) or 0)


def matrix_from_table(session: Session) -> dict[str, dict[str, list[Any]]]:
    """The matrix the rulebook publishes, read from the rows — not from `DEFAULT_MATRIX`.

    The seed is how the table gets its numbers; the table is what they are. Printed from the constant, the door
    would keep saying `1 per day` after somebody edited the row to `0`, and the tier's own claim that a plan is
    data would be a sentence about a copy.
    """
    built: dict[str, dict[str, list[Any]]] = {plan: {} for plan in PLANS}
    for row in session.scalars(select(Entitlement).where(Entitlement.plan.in_(list(PLANS)), Entitlement.feature.in_(list(FEATURES)))):
        built.setdefault(row.plan, {})[row.feature] = [int(row.limit_value), row.period]
    return built


def period_key(period: str, on: date) -> str:
    return on.isoformat()[:7] if period == MONTH else on.isoformat()


def ceiling(session: Session, plan: str, feature: str) -> tuple[int, str] | None:
    row = session.scalar(select(Entitlement).where(Entitlement.plan == plan, Entitlement.feature == feature))
    return (int(row.limit_value), row.period) if row else None


def used(session: Session, subject_id: str, feature: str, *, on: date | None = None) -> int:
    limit_row = _require_feature(feature)
    period = limit_row[1]
    day = on or utc_today()
    total = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.units), 0)).where(UsageEvent.subject_id == subject_id, UsageEvent.feature == feature, UsageEvent.period_key == period_key(period, day))
    )
    return int(total or 0)


def _require_feature(feature: str) -> tuple[int, str]:
    if feature not in FEATURES:
        from app.services.club.organizations import ClubRefusal

        raise ClubRefusal("no_such_feature", f"{feature!r} is not a feature this tier meters; it knows {sorted(FEATURES)}", feature=feature, features=sorted(FEATURES))
    return DEFAULT_MATRIX[DEFAULT_PLAN][feature]


def record(session: Session, *, subject_id: str, subject_kind: str, feature: str, plan: str, source_id: str, units: int = 1, on: date | None = None) -> dict[str, Any]:
    """Note the act. Counting it twice is prevented by the row, not by a caller's care."""
    day = on or utc_today()
    limit_row = ceiling(session, plan, feature) or _require_feature(feature)
    existing = session.scalar(
        select(UsageEvent).where(UsageEvent.subject_id == subject_id, UsageEvent.feature == feature, UsageEvent.period_key == period_key(limit_row[1], day), UsageEvent.source_id == source_id)
    )
    if existing is not None:
        return {"recorded": False, "duplicate_of": existing.id, "feature": feature, "period_key": existing.period_key}
    session.add(
        UsageEvent(
            id=new_public_id("usg"),
            subject_id=subject_id,
            subject_kind=subject_kind,
            feature=feature,
            plan=plan,
            period_key=period_key(limit_row[1], day),
            source_id=source_id,
            units=int(units),
            recorded_on=day.isoformat(),
        )
    )
    session.commit()
    return {"recorded": True, "feature": feature, "period_key": period_key(limit_row[1], day)}


def guard(session: Session, *, subject_id: str, feature: str, plan: str, source_id: str) -> dict[str, Any]:
    """Refuse the act that would spend past the ceiling, printing both figures. Called before the write."""
    limit_value, period = ceiling(session, plan, feature) or _require_feature(feature)
    key = period_key(period, utc_today())
    # Re-asking the same act is not a second spend: the row carrying this `source_id` already paid for it, so the
    # ceiling is compared only against a genuinely new act. Without this, an update would be refused by the very
    # meter the original act consumed.
    already_paid = session.scalar(select(UsageEvent.id).where(UsageEvent.subject_id == subject_id, UsageEvent.feature == feature, UsageEvent.period_key == key, UsageEvent.source_id == source_id))
    if already_paid is not None:
        spent = used(session, subject_id, feature, on=utc_today())
        return {"used": spent, "limit": limit_value, "period": period, "remaining": max(0, limit_value - spent), "counted": "already"}
    already = used(session, subject_id, feature, on=utc_today())
    if already >= limit_value:
        from app.services.club.organizations import ClubRefusal

        raise ClubRefusal(
            "entitlement_limit",
            f"a {plan!r} plan gets {limit_value} {feature} per {period}, and this subject has used {already}; the act is refused, not queued",
            feature=feature,
            plan=plan,
            used=already,
            limit=limit_value,
            period=period,
            enforced=feature in ENFORCED,
        )
    return {"used": already, "limit": limit_value, "period": period, "remaining": limit_value - already}


def entitlements_view(session: Session, subject_id: str, *, plan: str, subject_kind: str) -> dict[str, Any]:
    today = utc_today()
    rows = []
    for feature, kind in FEATURES.items():
        if kind != subject_kind:
            continue
        limit_value, period = ceiling(session, plan, feature) or DEFAULT_MATRIX[plan][feature]
        spent = used(session, subject_id, feature, on=today)
        rows.append(
            {
                "feature": feature,
                "plan": plan,
                "limit": limit_value,
                "period": period,
                "used": spent,
                "remaining": max(0, limit_value - spent),
                "enforced": feature in ENFORCED,
                "acts": int(
                    session.scalar(
                        select(func.count()).select_from(UsageEvent).where(UsageEvent.subject_id == subject_id, UsageEvent.feature == feature, UsageEvent.period_key == period_key(period, today))
                    )
                    or 0
                ),
            }
        )
    return {
        "plan": plan,
        "subject_kind": subject_kind,
        "items": rows,
        "as_of": today.isoformat(),
        "formula": "used = sum of `units` over this subject's usage rows whose period_key matches the current one; remaining = limit - used, floored at zero and never used to imply a queue",
        "rule": "a ceiling read from the entitlements table, compared against usage counted now — there is no stored total to go out of date, and no price anywhere",
    }


def rules() -> dict[str, Any]:
    return {
        "plans": list(PLANS),
        "features": {feature: kind for feature, kind in FEATURES.items()},
        "enforced": list(ENFORCED),
        "published_not_enforced": [feature for feature in FEATURES if feature not in ENFORCED],
        "periods": [DAY, MONTH],
        "default_plan": DEFAULT_PLAN,
        "no_payment": NO_PAYMENT,
        "usage_rule": "one row per act; the ceiling is compared against a count taken at read time, so deleting an act removes its spend",
        "refusals": list(REFUSALS),
    }
