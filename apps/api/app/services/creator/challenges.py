"""Career challenges: §36's fifth kind of content, an authored rule a run of somebody's own is judged by.

§36 lists six kinds of content a user can create. The fifth is a **Career Challenge** - an author names
an objective, a target and a window of rounds, and another account enters it with a career of their own.

The tier's rule holds here too: **a publication stores the author's words and the rule, never an
entrant's career or its results**. A challenge row holds a title, its own summary, a visibility and the
rule: one of `OBJECTIVE_KINDS` - the same four sums a career's own objectives use - a target and a
window. An attempt row holds the entrant's own **address** of a career and the round the window opened
at (`start_round`). It holds no win, point, goal or verdict.

Everything a verdict shows is summed on the read from that career's own `career_fixtures` rows through
`record_of`, over the rows whose `round_index` falls after `start_round` and no further than the
window. A target only *earns* once the window has closed, exactly as M6's authored scenarios judge a
run, so a run cannot be declared won in round two of eight.

Two consequences:

* **an attempt survives its career.** `career_slug` is a plain pointer, not a foreign key, so an entrant
  may erase their career without an attempt blocking it; the read then keeps the bare address and says
  `career_missing` rather than summing nothing into a zero.
* **an attempt is its entrant's alone.** A read shows every viewer the author's rule and the count of
  attempts; only the viewer's own attempt is attached, with its verdict. Another account's career
  address never leaves its owner's reads.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    OBJECTIVE_FORMULA,
    OBJECTIVE_KINDS,
    Career,
    CareerFixture,
    CreatorCareerAttempt,
    CreatorCareerChallenge,
    User,
)
from app.services.creator.publishing import (
    VISIBILITIES,
    CreatorRefusal,
    _slug_of,
    _text,
    ensure_profile,
    visible_authors,
)
from app.services.simulation.career import record_of

#: How many career challenges one creator may publish.
MAX_CAREER_CHALLENGES_PER_CREATOR: Final = 30
CAREER_CHALLENGE_TITLE_MAX: Final = 160
CAREER_CHALLENGE_SLUG_MAX: Final = 80
CAREER_CHALLENGE_SUMMARY_MAX: Final = 600
#: A target of zero would be met before a round was played, so the floor is one; the ceiling is one
#: published number for every kind, and the objective's own formula says which sum is compared with it.
CAREER_CHALLENGE_TARGET_MIN: Final = 1
CAREER_CHALLENGE_TARGET_MAX: Final = 99
#: A window is a stretch of a season, not a whole football life; 38 is a full league campaign.
CAREER_CHALLENGE_WINDOW_MIN: Final = 1
CAREER_CHALLENGE_WINDOW_MAX: Final = 38

#: The verdicts an attempt can read as. `met` and `missed` are only ever read once the window closed;
#: `career_retired` names a window that can no longer close; `career_missing` names an address that
#: outlived its career.
ATTEMPT_STATUSES: Final = ("in_progress", "met", "missed", "career_retired", "career_missing")

#: The tier's own vocabulary for this noun, published by the rules door beside the others'.
FORMULAS: Final = {
    "attempts": "count of the attempt rows this challenge holds - one per account by constraint, so it is a number of runs, not of rounds",
    "played": "count of the entrant's career_fixtures rows whose round_index falls after start_round and within the challenge's window",
    "remaining": "window_rounds - played, floored at zero; a run is judged when the window closes",
    "actual": "the challenge's objective summed from the rows inside the window by the objective's own published formula",
    "career_challenges": "count of every career-challenge row this database holds",
    "career_attempts": "count of every attempt row this database holds across all challenges",
}

LIMITATION: Final = (
    "a career challenge stores the author's title, its own summary, a visibility and the rule - one objective "
    "kind, a target and a window of rounds - never an entrant, a result or any career's figures. An attempt "
    "stores the address of the entrant's own career and the round the window opened at; every figure a verdict "
    "shows is summed on that read from the career's own career_fixtures rows, using the same sums M6 judges a "
    "career's objectives with, and a target only earns once the window has closed. A career erased after entry "
    "leaves a bare address rather than erasing the attempt, and no account's career is visible to another"
)


def _visibility(visibility: Any) -> str:
    word = str(visibility or "").strip().lower()
    if word not in VISIBILITIES:
        raise CreatorRefusal(
            "career_challenge_visibility",
            f"a career challenge is {' or '.join(repr(item) for item in VISIBILITIES)}; {word!r} would select nobody and the door cannot tell that from a mistake",
            sent=word,
            visibilities=list(VISIBILITIES),
        )
    return word


def _objective(kind: Any) -> str:
    word = str(kind or "").strip().lower()
    if word not in OBJECTIVE_KINDS:
        raise CreatorRefusal(
            "career_challenge_objective",
            f"a career challenge is judged by one of {' '.join(repr(item) for item in OBJECTIVE_KINDS)}; {word!r} is not a sum any career publishes",
            sent=word,
            kinds=list(OBJECTIVE_KINDS),
        )
    return word


def _target(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise CreatorRefusal(
            "career_challenge_target", f"a target is a whole number, and {value!r} is not", sent=str(value)
        ) from None
    if number < CAREER_CHALLENGE_TARGET_MIN or number > CAREER_CHALLENGE_TARGET_MAX:
        raise CreatorRefusal(
            "career_challenge_target",
            f"a target is between {CAREER_CHALLENGE_TARGET_MIN} and {CAREER_CHALLENGE_TARGET_MAX} and this one is {number}",
            target=number,
            min=CAREER_CHALLENGE_TARGET_MIN,
            max=CAREER_CHALLENGE_TARGET_MAX,
        )
    return number


def _window(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise CreatorRefusal(
            "career_challenge_window", f"a window is a whole number of rounds, and {value!r} is not", sent=str(value)
        ) from None
    if number < CAREER_CHALLENGE_WINDOW_MIN or number > CAREER_CHALLENGE_WINDOW_MAX:
        raise CreatorRefusal(
            "career_challenge_window",
            f"a window is between {CAREER_CHALLENGE_WINDOW_MIN} and {CAREER_CHALLENGE_WINDOW_MAX} rounds and this one is {number}",
            window=number,
            min=CAREER_CHALLENGE_WINDOW_MIN,
            max=CAREER_CHALLENGE_WINDOW_MAX,
        )
    return number


def career_challenge_counts(session: Session, *, ready: bool) -> dict[str, int]:
    """The rulebook's counts of this tier's challenge tables."""
    if not ready:
        return {"career_challenges": 0, "career_attempts": 0}
    return {
        "career_challenges": int(session.scalar(select(func.count()).select_from(CreatorCareerChallenge)) or 0),
        "career_attempts": int(session.scalar(select(func.count()).select_from(CreatorCareerAttempt)) or 0),
    }


def _challenge(session: Session, ident: Any) -> CreatorCareerChallenge:
    row = session.get(CreatorCareerChallenge, str(ident))
    if row is None:
        raise CreatorRefusal(
            "no_such_career_challenge", f"no career challenge answers to {str(ident)!r}", challenge=str(ident)
        )
    return row


def _owned(session: Session, challenge_id: Any, actor_id: str) -> CreatorCareerChallenge:
    row = _challenge(session, challenge_id)
    if row.author_id != actor_id:
        raise CreatorRefusal(
            "no_such_career_challenge",
            f"no career challenge of yours answers to {str(challenge_id)!r}",
            challenge=str(challenge_id),
        )
    return row


def _own_career(session: Session, actor_id: str, ident: Any) -> Career:
    """The career an entry pins. Unknown and somebody else's career answer the same way: absence."""
    key = str(ident or "").strip()
    if not key:
        raise CreatorRefusal(
            "no_such_attempted_career",
            "an entry pins a career of your own, and this one names none",
            career=key,
        )
    row = session.scalar(select(Career).where(or_(Career.slug == key, Career.id == key)))
    if row is None or row.owner_id != actor_id:
        raise CreatorRefusal(
            "no_such_attempted_career",
            f"no career of yours answers to {key!r}, so there is no run to pin",
            career=key,
        )
    return row


def _attempt_of(session: Session, challenge_id: str, account_id: str) -> CreatorCareerAttempt | None:
    return session.scalar(
        select(CreatorCareerAttempt).where(
            CreatorCareerAttempt.challenge_id == challenge_id,
            CreatorCareerAttempt.account_id == account_id,
        )
    )


def publish_career_challenge(
    session: Session,
    actor_id: str,
    *,
    title: Any,
    summary: Any = "",
    visibility: Any = "public",
    objective: Any = "wins",
    target: Any = 0,
    window_rounds: Any = 0,
) -> dict[str, Any]:
    """Publish the rule: an objective, a target and a window, with the author's words around it."""
    ensure_profile(session, actor_id)
    wanted_title = _text(
        title, CAREER_CHALLENGE_TITLE_MAX, "career_challenge_title", "career challenge title", required=True
    )
    wanted_visibility = _visibility(visibility)
    kind = _objective(objective)
    wanted_target = _target(target)
    wanted_window = _window(window_rounds)

    mine = int(
        session.scalar(
            select(func.count())
            .select_from(CreatorCareerChallenge)
            .where(CreatorCareerChallenge.author_id == actor_id)
        )
        or 0
    )
    if mine >= MAX_CAREER_CHALLENGES_PER_CREATOR:
        raise CreatorRefusal(
            "career_challenge_limit",
            f"a creator may publish {MAX_CAREER_CHALLENGES_PER_CREATOR} career challenges and this account has {mine}",
            challenges=mine,
            max=MAX_CAREER_CHALLENGES_PER_CREATOR,
        )

    slug = _slug_of(wanted_title)[:CAREER_CHALLENGE_SLUG_MAX]
    taken = session.scalar(
        select(CreatorCareerChallenge).where(
            CreatorCareerChallenge.author_id == actor_id, CreatorCareerChallenge.slug == slug
        )
    )
    if taken is not None:
        raise CreatorRefusal(
            "slug_taken",
            f"this account already publishes a career challenge called {slug!r}, and a reader cannot tell two rules apart by a name",
            slug=slug,
        )

    row = CreatorCareerChallenge(
        id=new_public_id("ccc"),
        author_id=actor_id,
        slug=slug,
        title=wanted_title,
        summary=_text(
            summary,
            CAREER_CHALLENGE_SUMMARY_MAX,
            "career_challenge_summary",
            "career challenge summary",
            required=False,
        ),
        visibility=wanted_visibility,
        objective_kind=kind,
        target=wanted_target,
        window_rounds=wanted_window,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return read_career_challenge(session, row.id, actor_id)


def _attempt_view(
    session: Session, challenge: CreatorCareerChallenge, attempt: CreatorCareerAttempt
) -> dict[str, Any]:
    """One run, judged now from the entrant's own fixture rows - nothing here is stored."""
    formula = OBJECTIVE_FORMULA.get(challenge.objective_kind, "not a recognised objective kind")
    window = int(challenge.window_rounds)
    start = int(attempt.start_round)
    career = session.scalar(select(Career).where(Career.slug == attempt.career_slug))
    if career is None:
        return {
            "id": attempt.id,
            "career": {
                "slug": attempt.career_slug,
                "manager_name": None,
                "club_name": None,
                "status": None,
                "path": None,
                "stored": False,
            },
            "start_round": start,
            "window": {
                "start_round": start,
                "end_round": start + window,
                "rounds": window,
                "played": None,
                "remaining": None,
                "closed": False,
            },
            "status": "career_missing",
            "actual": None,
            "target": challenge.target,
            "target_met": None,
            "earned": False,
            "formula": formula,
            "rounds": [],
            "reason": "the career this run was pinned to no longer exists, so the address is kept and nothing is summed into a zero",
        }

    rows = list(
        session.scalars(
            select(CareerFixture)
            .where(
                CareerFixture.career_id == career.id,
                CareerFixture.round_index > start,
                CareerFixture.round_index <= start + window,
            )
            .order_by(CareerFixture.round_index)
        ).all()
    )
    record = record_of(rows)
    actual = int(
        {
            "wins": record["won"],
            "points": record["points"],
            "goal_difference": record["goal_difference"],
            "unbeaten": record["unbeaten_run"],
        }[challenge.objective_kind]
    )
    played = len(rows)
    closed = played >= window
    target_met = actual >= int(challenge.target)
    if closed:
        status = "met" if target_met else "missed"
        reason = f"the window closed after {played} of {window} rounds with {actual} against a target of {challenge.target}"
    elif career.status != "active":
        status = "career_retired"
        reason = f"the career was retired after {played} of {window} rounds, so the window cannot close and the run is not judged"
    else:
        status = "in_progress"
        reason = f"{played} of {window} rounds are in the window and {window - played} remain; the verdict is read when the window closes"
    return {
        "id": attempt.id,
        "career": {
            "slug": career.slug,
            "manager_name": career.manager_name,
            "club_name": career.club_name,
            "status": career.status,
            "path": f"/career/{career.slug}",
            "stored": True,
        },
        "start_round": start,
        "window": {
            "start_round": start,
            "end_round": start + window,
            "rounds": window,
            "played": played,
            "remaining": max(0, window - played),
            "closed": closed,
        },
        "status": status,
        "actual": actual,
        "target": challenge.target,
        "target_met": target_met,
        "earned": status == "met",
        "formula": formula,
        "rounds": [
            {
                "round_index": row.round_index,
                "outcome": row.outcome,
                "club_goals": row.club_goals,
                "opponent_goals": row.opponent_goals,
                "points": row.points,
            }
            for row in rows
        ],
        "reason": reason,
    }


def _attempts_of(session: Session, challenge_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(CreatorCareerAttempt)
            .where(CreatorCareerAttempt.challenge_id == challenge_id)
        )
        or 0
    )


def _view(session: Session, row: CreatorCareerChallenge, viewer_id: str) -> dict[str, Any]:
    author = session.get(User, row.author_id)
    attempt = _attempt_of(session, row.id, viewer_id)
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary,
        "visibility": row.visibility,
        "published_on": row.published_on,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
        "author": {"id": row.author_id, "display_name": author.display_name if author else ""},
        "objective": {
            "kind": row.objective_kind,
            "target": row.target,
            "formula": OBJECTIVE_FORMULA.get(row.objective_kind, "not a recognised objective kind"),
        },
        "window_rounds": row.window_rounds,
        "figures": {"attempts": _attempts_of(session, row.id)},
        "attempt": _attempt_view(session, row, attempt) if attempt is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def _reachable(session: Session, challenge_id: Any, viewer_id: str) -> CreatorCareerChallenge:
    """One challenge, if this reader may reach it. A challenge they may not reach is answered as absence."""
    row = _challenge(session, challenge_id)
    if row.visibility == "followers" and row.author_id not in set(visible_authors(session, viewer_id)):
        raise CreatorRefusal(
            "no_such_career_challenge",
            f"no career challenge answers to {str(challenge_id)!r}",
            challenge=str(challenge_id),
        )
    return row


def read_career_challenge(session: Session, challenge_id: Any, viewer_id: str) -> dict[str, Any]:
    """One challenge, with the viewer's own run judged from their career's rows on this read."""
    row = _reachable(session, challenge_id, viewer_id)
    return _view(session, row, viewer_id)


def list_career_challenges(
    session: Session, viewer_id: str, *, creator: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """The shelf of career challenges as far as this reader may reach, each named by its own runs."""
    following = visible_authors(session, viewer_id)[1:]
    own = creator is not None and str(creator) == viewer_id
    allowed = (
        list(VISIBILITIES)
        if own
        else (["public", "followers"] if (creator is not None and str(creator) in following) else ["public"])
    )
    statement = select(CreatorCareerChallenge).where(CreatorCareerChallenge.visibility.in_(allowed))
    if creator is not None:
        statement = statement.where(CreatorCareerChallenge.author_id == str(creator))
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        session.scalars(
            statement.order_by(
                CreatorCareerChallenge.published_on.desc(), CreatorCareerChallenge.id.desc()
            ).limit(max(1, min(int(limit), 100)))
        ).all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        author = session.get(User, row.author_id)
        items.append(
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "summary": row.summary,
                "visibility": row.visibility,
                "published_on": row.published_on,
                "author": {"id": row.author_id, "display_name": author.display_name if author else ""},
                "objective": {
                    "kind": row.objective_kind,
                    "target": row.target,
                    "formula": OBJECTIVE_FORMULA.get(row.objective_kind, "not a recognised objective kind"),
                },
                "window_rounds": row.window_rounds,
                "attempts": _attempts_of(session, row.id),
                "entered": _attempt_of(session, row.id, viewer_id) is not None,
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": int(MAX_CAREER_CHALLENGES_PER_CREATOR),
        "creator": str(creator) if creator is not None else None,
        "formulas": dict(FORMULAS),
        "rule": LIMITATION,
    }


def enter_career_challenge(
    session: Session, actor_id: str, challenge_id: Any, *, career: Any
) -> dict[str, Any]:
    """Pin the caller's own career to the challenge: the round it stands at is where the window opens."""
    row = _reachable(session, challenge_id, actor_id)
    own = _own_career(session, actor_id, career)
    own_window = int(own.challenge_window or 0)
    if own.status != "active" or (own_window and int(own.rounds_played) >= own_window):
        raise CreatorRefusal(
            "career_challenge_inactive",
            f"the career {own.slug!r} cannot play another round, so there is no window to enter",
            career=own.slug,
            status=own.status,
            challenge_window=own_window,
            rounds_played=own.rounds_played,
        )
    existing = _attempt_of(session, row.id, actor_id)
    if existing is not None:
        raise CreatorRefusal(
            "career_challenge_entered",
            f"this account already entered this challenge with {existing.career_slug!r}; withdraw that run before making another",
            attempt=existing.id,
            career=existing.career_slug,
            start_round=existing.start_round,
        )
    attempt = CreatorCareerAttempt(
        id=new_public_id("cca"),
        challenge_id=row.id,
        account_id=actor_id,
        career_slug=own.slug,
        start_round=int(own.rounds_played),
    )
    session.add(attempt)
    session.commit()
    return {**read_career_challenge(session, row.id, actor_id), "entered": True}


def withdraw_career_challenge(session: Session, actor_id: str, challenge_id: Any) -> dict[str, Any]:
    """Withdraw the caller's own run. The career it pinned is untouched."""
    row = _reachable(session, challenge_id, actor_id)
    attempt = _attempt_of(session, row.id, actor_id)
    if attempt is None:
        raise CreatorRefusal(
            "no_such_career_attempt",
            f"this account holds no run in the career challenge answering to {str(challenge_id)!r}",
            challenge=str(challenge_id),
        )
    career = attempt.career_slug
    session.delete(attempt)
    session.commit()
    return {"status": "withdrawn", "challenge": row.id, "career": career}


def erase_career_challenge(session: Session, actor_id: str, challenge_id: Any) -> dict[str, Any]:
    """Erase your own challenge. The runs on it go with it; the careers they pinned are untouched."""
    row = _owned(session, challenge_id, actor_id)
    erased = row.id
    session.delete(row)
    session.commit()
    return {"status": "erased", "challenge": erased}


def rules(session: Session, *, ready: bool) -> dict[str, Any]:
    """This noun's own vocabulary, published beside the guide's, the program's and the other objects'."""
    return {
        "career_challenge_caps": {
            "career_challenge_max": MAX_CAREER_CHALLENGES_PER_CREATOR,
            "career_challenge_title_max": CAREER_CHALLENGE_TITLE_MAX,
            "career_challenge_slug_max": CAREER_CHALLENGE_SLUG_MAX,
            "career_challenge_summary_max": CAREER_CHALLENGE_SUMMARY_MAX,
            "career_challenge_target_min": CAREER_CHALLENGE_TARGET_MIN,
            "career_challenge_target_max": CAREER_CHALLENGE_TARGET_MAX,
            "career_challenge_window_min": CAREER_CHALLENGE_WINDOW_MIN,
            "career_challenge_window_max": CAREER_CHALLENGE_WINDOW_MAX,
        },
        "career_challenge_objective_kinds": {kind: OBJECTIVE_FORMULA[kind] for kind in OBJECTIVE_KINDS},
        "career_challenge_formulas": dict(FORMULAS),
        "career_challenge_counts": career_challenge_counts(session, ready=ready),
        "career_challenge_rule": LIMITATION,
    }
