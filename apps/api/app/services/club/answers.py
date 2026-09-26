"""One refusal code, one HTTP answer — at *every* door of the club tier.

The rule §40 published for itself (*a code means one thing*) only holds if it means one **status** too. Until
this module there were two answer tables, hand-assembled one per router, and they did not list the same codes:
`/club/academy/…` knew §40's, §41's and §42's codes because it is the door that raises them, and `/club/…` knew
only §39's. A code raised at the door that had not listed it fell through to a **400**, so the same sentence
could be answered two ways depending on which router the request entered — and `GET /club/{ident}/entitlements`
could already reach §42's `no_such_entitlement_plan`, which answers 404 at one door and 400 at the other.

Two things follow, and both are the point of this file rather than an incidental benefit:

* **The table is assembled from the services' own sets, in one place.** A tier adds four sets to its module and
  appends its module to `TIERS`; it does not edit a literal in a router. That is what keeps the two doors from
  drifting apart again, which is how this hole was made in the first place.
* **A collision is refused at import time, not resolved by dictionary order.** Assembling by `dict.fromkeys`
  layer after layer means the *last* tier listed wins a code two tiers both registered — silently, and with an
  answer that depends on the order of a literal. `assemble()` raises instead, so the mistake surfaces as a
  collection error naming both statuses rather than as a door that answers 409 where its own published table
  says 422. The suite still holds the sets pairwise-disjoint: this makes the ordering harmless, not correct.

Anything not registered at all answers 400. That is deliberate and is held by a test from the other side: an
unmapped code is a bug in the door that raised it, and a 400 saying *bad request* is closer to the truth than a
guessed 4xx.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import HTTPException, status

from app.services import entitlements as ent_status
from app.services.club import academy as edu
from app.services.club import organizations as club
from app.services.club import reports as rep
from app.services.club import sessions as sess
from app.services.club.organizations import ClubRefusal

#: The four questions a tier answers, in the order a reader checks them: is it absent, is the request
#: correctable, did it collide with a row that already exists, or does the caller simply not hold the right.
#: A tier that has no such set omits it; `assemble` reads the attributes that are there.
SETS: Final = (
    ("NOT_FOUND_CODES", status.HTTP_404_NOT_FOUND),
    ("UNPROCESSABLE_CODES", status.HTTP_422_UNPROCESSABLE_ENTITY),
    ("CONFLICT_CODES", status.HTTP_409_CONFLICT),
    ("FORBIDDEN_CODES", status.HTTP_403_FORBIDDEN),
)

#: Every part of the tier whose refusals a club door can be the first to print. §48's `matches` joins this list
#: and nothing else changes: both routers read the table assembled from it.
TIERS: Final = (club, edu, sess, rep, ent_status)


def assemble(*tiers: Any) -> dict[str, int]:
    """code → status, over the tiers' own sets. A code two tiers claim with different answers is refused here."""
    table: dict[str, int] = {}
    for tier in tiers:
        name = str(getattr(tier, "__name__", tier)).rpartition(".")[2]
        for attribute, answer in SETS:
            for code in tuple(getattr(tier, attribute, ()) or ()):
                held = table.get(str(code))
                if held is not None and held != answer:
                    raise RuntimeError(f"refusal code {str(code)!r} is registered as {held} by one tier and {answer} by {name}.{attribute}; one code means one answer")
                table[str(code)] = answer
    return table


#: The one table both club routers answer from.
ANSWERS: Final[dict[str, int]] = assemble(*TIERS)


def published(*codes: Any) -> dict[str, int]:
    """The rows a capabilities door prints for the codes it claims to answer with.

    Deriving the table here rather than at each router is what makes `refusal_answers` the same object the door
    answers from: a copy written beside the route could name a status the route does not use, and a page printing
    it would teach a caller to expect an answer that never comes. An unregistered code publishes as the fall-through
    it would actually earn — measured at this landing, **every** code §39 through §42 publishes is registered, so no
    row of the printed table is a fall-through today; one appearing later is a bug in the tier that added it, and
    `test_answers_agree.py` is what turns that bug red rather than a reader finding it.
    """
    return {str(code): ANSWERS.get(str(code), status.HTTP_400_BAD_REQUEST) for code in (item for group in codes for item in group)}


def refusal(error: ClubRefusal) -> HTTPException:
    """The HTTP answer a refusal deserves, at either door, from the one table."""
    return HTTPException(ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


__all__ = ["ANSWERS", "SETS", "TIERS", "assemble", "published", "refusal"]
