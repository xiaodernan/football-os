"""§38's second permitted output: a link a person can hand over, and take back (M10, spec §38, §40).

The CV in `services/portfolio/cv.py` stores no figures, so a share link stores no figures either. What it stores is
the two things that are genuinely new — the token that opens the door and the list of section names its owner chose
to publish — and everything a public reader sees is re-read from `build_cv` at the moment of the request. That is
why a training session completed *after* a link was minted appears on that link: the link points at a read, not at a
snapshot.

Four decisions here are inherited rather than invented:

* **The token is a capability, so it is stored raw.** §17's `tactic_boards.share_token` is the project's only other
  share link: `secrets.token_hex(16)` — 32 characters of `[0-9a-f]` — in a `String(64)` unique column. A door that
  must read the value back to serve it cannot store a digest, unlike `refresh_sessions`, which the server only ever
  compares.
* **Absence answers reach.** An unknown token and a closed one — whether it was this account's or somebody else's —
  are the same 404 with the same sentence. A door that said "this link exists, it just closed" would confirm the
  existence of rows it is not allowed to mention — §35's rule, applied to a link. A *live* token does open the door
  for whoever holds it: that is what a share link is, and the pair of cases in the test file states both sides.
* **One open link per account, and it publishes the account's CV, not a player the caller names.** The body of the
  write door carries section names only. A `player` field would have to be checked for ownership, and the check would
  need an answer for "that id exists but is not yours" — which is exactly the sentence this file's third rule refuses
  to print. So the link resolves through §38's own single reader, `cv.player_of`, and shows what the owner's own CV
  door shows. One resolution rule, one home (§50).
* **A minor's `videos` cannot be published** (§40: do not make a child's videos, contact details or private profile
  public). The threshold is `services.club.academy.MINOR_AGE`, imported rather than restated (§49's one constant),
  and the age comes from the same row the CV itself reads.

`videos` is the only section the minors' rule blocks, and that is a measurement rather than a judgement: of §38's ten
sections `videos` is the only one whose items name files, and the CV carries no geographic location and no contact
field at all — `position` is a football position. The stronger minimisation is structural: `public_cv` drops the
`account` block before anything leaves the door, so no user id, display name or address can reach an unauthenticated
caller through this path even by accident, and the test file asserts that over the emitted payload's keys rather than
over this paragraph.
"""

from __future__ import annotations

import secrets
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import CvShare, utcnow
from app.services.club.academy import MINOR_AGE
from app.services.portfolio import cv as portfolio

#: §17's board token, kept as the shape of a share token here too: 16 bytes printed as 32 hex characters, inside the
#: `String(64)` column the migration declares.
TOKEN_BYTES: Final = 16

#: The names a share may carry are §38's ten, `matches` and `stats` included. Publishing an unfilled section
#: publishes the reason it is unfilled, which is what the private door does with the same rows; a link that silently
#: dropped those two would be the one place in this tier where §38's order stops being §38's order.
PUBLISHABLE: Final = tuple(portfolio.SECTIONS)

#: §40's rule for this tier, as data. A list rather than a hard `if` so the rules door can print what is withheld and
#: why, and so a later slice that adds a withheld section adds one name here instead of another branch.
MINOR_BLOCKED: Final = ("videos",)

#: What a public reader is never handed. `account` is the block §38's private door uses to say whose CV it is, and
#: `public_cv` builds its answer without ever copying that block in; the rest are the identifying fields inside the
#: player block, dropped by the projection. `data_origin` is not personal data and is the project's demo-mode honesty
#: field, so it stays where the sections already carry it.
PRIVATE_KEYS: Final = ("user_id", "email", "display_name", "account", "id", "visibility")

REFUSALS: Final = (
    "no_such_share",
    "section_unknown",
    "minor_section_blocked",
    "share_already_revoked",
)

#: Nothing in this tier answers 403: §35, §36 and §38 all keep that status for `insufficient_role`, and a share link
#: is not a role — it is a key.
NOT_FOUND_CODES: Final = frozenset({"no_such_share"})
UNPROCESSABLE_CODES: Final = frozenset({"section_unknown", "minor_section_blocked"})
CONFLICT_CODES: Final = frozenset({"share_already_revoked"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()
PUBLISHED: Final = REFUSALS


class ShareRefusal(RuntimeError):
    """A refusal with the figures beside the sentence, in the shape every tier's router already answers from."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


def _ordered(names: Any) -> list[str]:
    """The caller's list, deduplicated and put back into §38's own order.

    A share stores a set of names but prints them in the spec's order, so the order a person ticked boxes in cannot
    change the order a reader's page is built in.
    """
    wanted = {str(name) for name in (names or [])}
    return [key for key in PUBLISHABLE if key in wanted]


def _check_sections(session: Session, user_id: str, requested: Any) -> None:
    """The two ways a list of section names is refused, both answered before a token is minted.

    It reads the caller's raw list, not `_ordered`'s cleaned one: a validator that receives the output of the helper
    which drops unknown names can never fire. That shape was measured, not assumed — the first run of this tier's
    tests asked for `wallet` and got a link back.
    """
    requested_names = {str(name) for name in (requested or [])}
    unknown = sorted(requested_names - set(PUBLISHABLE))
    if unknown:
        raise ShareRefusal(
            "section_unknown",
            f"{', '.join(unknown)} is not one of §38's ten sections — this tier publishes {list(PUBLISHABLE)}",
            unknown=unknown,
            publishable=list(PUBLISHABLE),
        )
    player = portfolio.player_of(session, user_id, None)
    if player is not None and int(player.age) < MINOR_AGE:
        blocked = sorted(requested_names & set(MINOR_BLOCKED))
        if blocked:
            raise ShareRefusal(
                "minor_section_blocked",
                (
                    f"the account's player is {int(player.age)}, under {MINOR_AGE}, and §40 keeps a minor's "
                    f"{', '.join(blocked)} out of a public link"
                ),
                age=int(player.age),
                threshold=MINOR_AGE,
                blocked=blocked,
                publishable=[key for key in PUBLISHABLE if key not in MINOR_BLOCKED],
            )


def _live(session: Session, user_id: str) -> CvShare | None:
    """The account's open link, if it has one. Deterministic ordering, the same reason §38's player read has it."""
    return session.scalars(
        select(CvShare).where(CvShare.user_id == user_id, CvShare.revoked_at.is_(None)).order_by(CvShare.created_at, CvShare.id)
    ).first()


def as_record(row: CvShare, *, token_visible: bool) -> dict[str, Any]:
    """One row in the shape every door prints it: the live link's token, and never a closed one's."""
    return {
        "share": row.id,
        "token": row.share_token if token_visible else None,
        "sections": [str(key) for key in (row.sections or [])],
        "opened_at": row.created_at.isoformat() if row.created_at is not None else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at is not None else None,
        "live": row.revoked_at is None,
    }


def share(session: Session, user_id: str, *, sections: Any) -> dict[str, Any]:
    """Open a link over the named sections, or re-point the one that is already open.

    Re-pointing keeps the token, which is §17's rule that "an old link keeps working": what changes is what the link
    shows, not where it lives. A fresh token is minted only when no live row exists, so an account has one open link
    at a time and every closed one stays on the ledger with the time it shut. An empty list is an answer, not a
    refusal — a link that publishes nothing still publishes §38's order, ten deep, as withheld.
    """
    _check_sections(session, user_id, sections)
    chosen = _ordered(sections)
    row = _live(session, user_id)
    if row is None:
        row = CvShare(
            id=new_public_id("cvs"),
            user_id=user_id,
            share_token=secrets.token_hex(TOKEN_BYTES),
            sections=chosen,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(row)
    else:
        row.sections = chosen
        row.updated_at = utcnow()
    session.commit()
    record = as_record(row, token_visible=True)
    record["withheld"] = [key for key in PUBLISHABLE if key not in chosen]
    return record


def list_shares(session: Session, user_id: str) -> dict[str, Any]:
    """Every link this account ever opened, newest first, with a closed link's token left out.

    A revoked token is a dead key, and printing it on a page invites a reader to try it in the address bar; the row
    still says when it closed, which is the part the owner asked for.
    """
    rows = list(session.scalars(select(CvShare).where(CvShare.user_id == user_id).order_by(CvShare.created_at.desc(), CvShare.id.desc())))
    live = [row for row in rows if row.revoked_at is None]
    return {
        "shares": [as_record(row, token_visible=row.revoked_at is None) for row in rows],
        "counts": {"opened": len(rows), "live": len(live), "revoked": len(rows) - len(live)},
        "publishable": list(PUBLISHABLE),
        "minor_blocked": list(MINOR_BLOCKED),
        "minor_age": MINOR_AGE,
    }


def revoke(session: Session, user_id: str, token: str) -> dict[str, Any]:
    """Close the link a token opens. The row survives; only the door shuts.

    A token that is not this account's answers `no_such_share`, the same as one that never existed: the owner-scoped
    lookup is what makes "somebody else's link" indistinguishable from "no link" without inventing a second code.
    """
    row = session.scalar(select(CvShare).where(CvShare.share_token == str(token), CvShare.user_id == user_id))
    if row is None:
        raise ShareRefusal("no_such_share", f"no link of yours answers to {str(token)!r}", token=str(token))
    if row.revoked_at is not None:
        raise ShareRefusal(
            "share_already_revoked",
            f"that link was already closed at {row.revoked_at.isoformat()}",
            token=str(token),
            revoked_at=row.revoked_at.isoformat(),
        )
    row.revoked_at = utcnow()
    row.updated_at = row.revoked_at
    session.commit()
    return as_record(row, token_visible=False)


def public_cv(session: Session, token: str) -> dict[str, Any]:
    """What an unauthenticated reader sees: the published sections of one CV, and nothing that identifies an account.

    The projection is the whole of the privacy claim, so it is written as a subtraction a reader can check: build the
    same ten-section CV the owner's own door builds, keep only the sections this row names, drop the `account` block
    and every `PRIVATE_KEYS` field, and recompute the counts over what is left rather than shipping the owner's
    numbers. `formulas` follows the same rule — an expression for a section this link does not publish would tell a
    stranger that a section exists and is being hidden.
    """
    row = _live_by_token(session, token)
    chosen = [str(key) for key in (row.sections or [])]
    full = portfolio.build_cv(session, row.user_id)
    published = [section for section in full["sections"] if str(section["section"]) in chosen]
    withheld = [section for section in full["sections"] if str(section["section"]) not in chosen]
    filled = [str(section["section"]) for section in published if section["available"]]
    unfilled = [str(section["section"]) for section in published if not section["available"]]
    player = full.get("player")
    return {
        "player": {key: value for key, value in (player or {}).items() if key not in PRIVATE_KEYS},
        "has_player": full["has_player"],
        "sections": published,
        "withheld": [{"section": str(section["section"]), "title": str(section["title"]), "reason": "not published on this link"} for section in withheld],
        "unfilled_reasons": full["unfilled_reasons"],
        "counts": {"sections": len(published), "filled": len(filled), "unfilled": unfilled},
        "published_sections": chosen,
        "formulas": {name: expression for name, expression in full["formulas"].items() if str(name).split(".", 1)[0] in chosen},
        "opened_at": row.created_at.isoformat() if row.created_at is not None else None,
        "limitation": (
            "this page is a live read of the sections its owner published, not a copy: the figures are counted from the "
            "rows §38's formulas name at the moment of the request, so a session completed after this link was opened "
            "changes what this link shows. The account behind it is not part of the link."
        ),
    }


def _live_by_token(session: Session, token: str) -> CvShare:
    """The one lookup a stranger is allowed to make: a token, and only an open one."""
    row = session.scalar(select(CvShare).where(CvShare.share_token == str(token), CvShare.revoked_at.is_(None)))
    if row is None:
        # One sentence for "never existed", "closed" and "somebody else's", because a door that distinguished them
        # would be reporting which tokens this build has heard of.
        raise ShareRefusal("no_such_share", f"no open link answers to {str(token)!r}", token=str(token))
    return row
