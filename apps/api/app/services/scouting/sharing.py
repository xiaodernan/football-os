"""§24's report behind a link a scout can hand over, and take back (M7, spec §24, §38, §40).

A scouting report is the first thing in this project that a manager is likely to want to *send* to somebody who
does not have an account, and the second output §38 permits beside the CV. The design is the CV link's, applied to
a different read:

* **Only the question is stored.** The row keeps the player, the role, the career, the comparator and the round —
  exactly the fields `POST /scout/report` takes — and no figure at all. Every number is recomputed by
  `report.build_report` at the moment of the request, which is what lets a report link age in the open: a player
  who moved club yesterday is shown at the club the stored row now names, not at the one the link was minted about.
* **A token is a capability, so it is stored raw.** §17's board token and §38's CV token are both
  `secrets.token_hex(16)`, 32 characters inside a `String(64)` unique column; a door that has to read the value back
  cannot store a digest.
* **Absence answers reach.** An unknown token, a closed one and somebody else's are one 404 with one sentence, for
  the reason §35 gives about rows: a door that distinguished them would report which tokens this build has heard of.
  The same rule covers revocation: a token that is not this account's answers `no_such_share`.
* **The question must be answerable before a token exists.** `open_share` builds the report first, so an unknown
  player, an unknown role or an unreadable career is refused at the mint rather than becoming a link that 404s or
  422s for every reader. Asking the same question twice returns the same live token — a share is a door, and
  re-opening a door should not move it.
* **Twenty open links per account.** A ledger is useful; an unbounded one is a way to fill a table from a loop. The
  cap counts live rows only, so closing links makes room, and the refusal names both figures.

`career` is stored as the career's slug, not the spelling the caller used: a request may name a career by id or by
slug, and one question should not mint two links because of it. On the public read the slug is resolved back to a
career **owned by the link's owner** — a link cannot be pointed at somebody else's career by editing a row, and a
career that has since been deleted leaves `career_available: false` with `team_fit: null`, which is the same answer
the private door gives when the career is not named. The account behind the link is not part of it: no user id,
display name or address is copied into the payload.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Career, ScoutReportShare, utcnow
from app.services.scouting.report import ReportRefusal, build_report

#: The same shape as every other share token in this project: 16 bytes printed as 32 hex characters.
TOKEN_BYTES: Final = 16

#: How many open links one account may hold. Closing one makes room, so the ceiling bounds the live ledger rather
#: than the account's history.
MAX_LIVE: Final = 20

REFUSALS: Final = (
    "no_such_share",
    "share_already_revoked",
    "share_subject_gone",
    "too_many_shares",
)

#: A link that never existed, a closed one and somebody else's are the one answer; a player the stored pool no
#: longer holds is the same absence one level down, and gets its own sentence so a reader is not told the link is
#: wrong when it is the question's subject that went.
NOT_FOUND_CODES: Final = frozenset({"no_such_share", "share_subject_gone"})
UNPROCESSABLE_CODES: Final[frozenset[str]] = frozenset()
CONFLICT_CODES: Final = frozenset({"share_already_revoked", "too_many_shares"})
#: A share is not a role — it is a key. Nothing in this tier answers 403.
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()
PUBLISHED: Final = REFUSALS


class ShareRefusal(RuntimeError):
    """A refusal with the figures beside the sentence, in the shape the `/scout` router answers from."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


def _live_rows(session: Session, user_id: str) -> list[ScoutReportShare]:
    """This account's open links, oldest first. Deterministic ordering, as every other ledger in this project has."""
    return list(
        session.scalars(
            select(ScoutReportShare)
            .where(ScoutReportShare.user_id == user_id, ScoutReportShare.revoked_at.is_(None))
            .order_by(ScoutReportShare.created_at, ScoutReportShare.id)
        )
    )


def _same_question(row: ScoutReportShare, *, player: str, role: str | None, career: str | None, compare_to: str | None, round_index: int | None) -> bool:
    """Whether a stored link already answers exactly this question, field by field.

    Compared in Python over the live rows rather than as a SQL tuple so `NULL` columns compare as the absence they
    are: an unnamed role and an unnamed comparator are part of a question, not wildcards in it.
    """
    return (
        row.player == player
        and (row.role or None) == (role or None)
        and (row.career or None) == (career or None)
        and (row.compare_to or None) == (compare_to or None)
        and row.round_index == round_index
    )


def _iso(value: datetime | None) -> str | None:
    """One spelling of a timestamp: UTC with an offset, whether the value came from this process or from SQLite.

    A freshly minted row carries the aware `utcnow()` it was built with, while the same row read back from SQLite is
    naive; printing each with `isoformat()` would give one link two spellings of one instant, and a page comparing
    the mint response with the ledger would see a difference that is not there.
    """
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def as_record(row: ScoutReportShare, *, token_visible: bool) -> dict[str, Any]:
    """One row in the shape every door prints it: the live link's token, and never a closed one's."""
    return {
        "share": row.id,
        "token": row.share_token if token_visible else None,
        "player": row.player,
        "role": row.role,
        "career": row.career,
        "compare_to": row.compare_to,
        "round_index": row.round_index,
        "opened_at": _iso(row.created_at),
        "revoked_at": _iso(row.revoked_at),
        "live": row.revoked_at is None,
    }


def open_share(
    session: Session,
    user_id: str,
    *,
    player: str,
    role: str | None,
    career: Career | None,
    compare_to: str | None,
    round_index: int | None,
) -> dict[str, Any]:
    """Mint a link over one §24 question, or return the live one that already answers it.

    The report is built *before* a token exists: a link should not be creatable for a player the pool does not hold,
    a role this catalogue does not name, or a comparator the world has never heard of. `ReportRefusal` and
    `MarketRefusal` therefore travel to the router from here, and the router answers them from the same table the
    private report door uses.

    `career` is stored as its slug and `player` as the canonical slug the built report names, so a request that
    spelled either by id gets the same token as one that spelled it by slug.
    """
    report = build_report(session, player, role=role, career=career, compare_to=compare_to, round_index=round_index)
    canonical_player = str(report["player"]["slug"])
    canonical_career = career.slug if career is not None else None
    for row in _live_rows(session, user_id):
        if _same_question(row, player=canonical_player, role=role, career=canonical_career, compare_to=compare_to, round_index=round_index):
            return {**as_record(row, token_visible=True), "created": False, "max_live": MAX_LIVE}
    live = _live_rows(session, user_id)
    if len(live) >= MAX_LIVE:
        raise ShareRefusal(
            "too_many_shares",
            f"this account already holds {len(live)} open report links, the ceiling this tier sets; close one before opening another",
            live=len(live),
            max_live=MAX_LIVE,
        )
    row = ScoutReportShare(
        id=new_public_id("srs"),
        user_id=user_id,
        share_token=secrets.token_hex(TOKEN_BYTES),
        player=canonical_player,
        role=role,
        career=canonical_career,
        compare_to=compare_to,
        round_index=round_index,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(row)
    session.commit()
    return {**as_record(row, token_visible=True), "created": True, "max_live": MAX_LIVE}


def list_shares(session: Session, user_id: str) -> dict[str, Any]:
    """Every link this account ever opened, newest first, with a closed link's token left out.

    A revoked token is a dead key; printing it on a page invites a reader to try it in the address bar. The row still
    says when it shut, which is the part the owner asked for.
    """
    rows = list(
        session.scalars(
            select(ScoutReportShare)
            .where(ScoutReportShare.user_id == user_id)
            .order_by(ScoutReportShare.created_at.desc(), ScoutReportShare.id.desc())
        )
    )
    live = [row for row in rows if row.revoked_at is None]
    return {
        "shares": [as_record(row, token_visible=row.revoked_at is None) for row in rows],
        "counts": {"opened": len(rows), "live": len(live), "revoked": len(rows) - len(live)},
        "max_live": MAX_LIVE,
    }


def revoke(session: Session, user_id: str, token: str) -> dict[str, Any]:
    """Close the link a token opens. The row survives; only the door shuts.

    A token that is not this account's answers `no_such_share`, the same as one that never existed: the owner-scoped
    lookup is what makes "somebody else's link" indistinguishable from "no link" without inventing a second code.
    """
    row = session.scalar(select(ScoutReportShare).where(ScoutReportShare.share_token == str(token), ScoutReportShare.user_id == user_id))
    if row is None:
        raise ShareRefusal("no_such_share", f"no link of yours answers to {str(token)!r}", token=str(token))
    if row.revoked_at is not None:
        raise ShareRefusal(
            "share_already_revoked",
            f"that link was already closed at {_iso(row.revoked_at)}",
            token=str(token),
            revoked_at=_iso(row.revoked_at),
        )
    row.revoked_at = utcnow()
    row.updated_at = row.revoked_at
    session.commit()
    return as_record(row, token_visible=False)


def public_report(session: Session, token: str) -> dict[str, Any]:
    """What an unauthenticated reader sees: the report for the stored question, re-read from the rows.

    `career` is resolved back to a career this link's owner holds, and only if it still exists. A deleted career
    leaves `career_named: true` / `career_available: false` beside a null `team_fit`, which is the private door's
    own answer for "no career was named" rather than an error: the link is still a valid question, and the world
    simply no longer has the half of it that was a club.

    A player the pool no longer holds is `share_subject_gone` (404). Other report refusals — a role the catalogue
    has since dropped, a comparator that has gone — travel as themselves, answered by the router from `ANSWERS`:
    this module does not invent a second status for a code another tier already owns.
    """
    row = _live_by_token(session, token)
    career: Career | None = None
    if row.career:
        career = session.scalar(select(Career).where(Career.slug == str(row.career), Career.owner_id == row.user_id))
    try:
        report = build_report(
            session,
            row.player,
            role=row.role,
            career=career,
            compare_to=row.compare_to,
            round_index=row.round_index,
        )
    except ReportRefusal as error:
        if str(error.code) == "no_such_player":
            raise ShareRefusal(
                "share_subject_gone",
                f"the player this link was opened about ({row.player!r}) is not in the stored pool any more",
                player=row.player,
                token=str(token),
            ) from None
        raise
    return {
        **report,
        "asked_for": {
            "player": row.player,
            "role": row.role,
            "career": row.career,
            "compare_to": row.compare_to,
            "round_index": row.round_index,
        },
        "shared": {
            "opened_at": _iso(row.created_at),
            "player_slug": str(report["player"]["slug"]),
            "career_named": row.career is not None,
            "career_available": career is not None,
            "note": (
                "this page is a live read of the question its owner shared, not a copy: every figure is counted from "
                "the stored rows at the moment of the request, so a player who moved club after this link was opened "
                "is shown at the club the rows name now. The account behind it is not part of the link."
            ),
        },
        "demo_data": True,
    }


def _live_by_token(session: Session, token: str) -> ScoutReportShare:
    """The one lookup a stranger is allowed to make: a token, and only an open one."""
    row = session.scalar(select(ScoutReportShare).where(ScoutReportShare.share_token == str(token), ScoutReportShare.revoked_at.is_(None)))
    if row is None:
        # One sentence for "never existed", "closed" and "somebody else's", because a door that distinguished them
        # would be reporting which tokens this build has heard of.
        raise ShareRefusal("no_such_share", f"no open link answers to {str(token)!r}", token=str(token))
    return row
