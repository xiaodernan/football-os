"""One refusal code, one HTTP answer — at *every* door, in any tier.

This file opened as the club tier's, and §35's community tier registers here rather than assembling a table of
its own: a table that lives inside one router is what let the same sentence earn two statuses, and a second
project-wide table would do that again one milestone later.

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

from app.core import security
from app.services import door_codes
from app.services import entitlements as ent_status
from app.services.club import academy as edu
from app.services.club import announcements as ann
from app.services.club import matches as mat
from app.services.club import organizations as club
from app.services.club import reports as rep
from app.services.club import sessions as sess
from app.services.club.organizations import ClubRefusal
from app.services.community import posts as community
from app.services.creator import publishing as creator
from app.services.knowledge_graph import verbs as graph
from app.services.portfolio import cv as portfolio
from app.services.portfolio import sharing as portfolio_share

#: The four questions a tier answers, in the order a reader checks them: is it absent, is the request
#: correctable, did it collide with a row that already exists, or does the caller simply not hold the right.
#: A tier that has no such set omits it; `assemble` reads the attributes that are there.
#:
#: The last six pairs exist because the tree raised statuses the first four could not describe, and the
#: codes answering them therefore lived *outside* the table: a 401 session refusal, a 413/415/416 upload
#: rejection, a 429 budget or rate refusal, a 503 dependency refusal. One attribute still binds exactly
#: one status — the assembly is unchanged — and `tests/test_answer_census.py` is what holds every raise
#: site to the row it registered.
SETS: Final = (
    ("NOT_FOUND_CODES", status.HTTP_404_NOT_FOUND),
    ("UNPROCESSABLE_CODES", status.HTTP_422_UNPROCESSABLE_ENTITY),
    ("CONFLICT_CODES", status.HTTP_409_CONFLICT),
    ("FORBIDDEN_CODES", status.HTTP_403_FORBIDDEN),
    ("UNAUTHORIZED_CODES", status.HTTP_401_UNAUTHORIZED),
    ("TOO_LARGE_CODES", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
    ("UNSUPPORTED_MEDIA_CODES", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE),
    ("RANGE_NOT_SATISFIABLE_CODES", status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE),
    ("TOO_MANY_REQUESTS_CODES", status.HTTP_429_TOO_MANY_REQUESTS),
    ("SERVICE_UNAVAILABLE_CODES", status.HTTP_503_SERVICE_UNAVAILABLE),
)

#: Every tier whose refusals a door can be the first to print. §48's `matches` joined this list and nothing else
#: changed: both club routers read the table assembled from it. §35's `community` joins it for the same reason —
#: a code means one status *project-wide*, and a second table assembled inside the community router is how the
#: hole described above was made. Nothing here imports a router, and no service imports this module, so a tier
#: from another milestone can be listed without the club tier having to know anything about it. §38's `portfolio`
#: joins with no code of its own: the tier prints its refusal table from this one, and an empty registration here is
#: what keeps a code added by a later portfolio slice from being answered one way there and another at `/club`.
#:
#: `core.security` is not a milestone tier and joins for a reason the others did not have: it answers 403 for
#: *every* door — `current_user` refuses a switched-off account before any tier's code is reached — and until §60's
#: census it did that with two codes (`account_inactive`, and the `forbidden` a router minted at `/knowledge/ingest`)
#: that appeared nowhere in this table. A tier list assembled from the services alone is a ledger that cannot see
#: the routers, and the routers were spending 403 freely. Registering the platform's own 403 codes here is what
#: makes the ledger and the territory one fact.
#:
#: §30's knowledge graph joins last. Its `no_such_node` is the fifth code in the table that means *absent*, and it
#: reaches here through `/graph/nodes/…` — a door with a router of its own, which is exactly the shape that let
#: §51's two answer tables drift apart. A tier that reads the assembled table and registers its sets in one motion
#: cannot make that hole again.
#:
#: `services.door_codes` joins after it for the reason `core.security` joined: the ledger assembled from the
#: services cannot see codes that only a router raises, and §60's second census measured 47 of them at 58 raise
#: sites answering from a literal in the raise rather than from any table. It is a constants module — it imports
#: nothing and nothing raises through it — so registering it widens what the table *knows* without creating a
#: second way to refuse.
TIERS: Final = (club, edu, mat, sess, rep, ann, ent_status, community, creator, portfolio, portfolio_share, security, graph, door_codes)


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
    `tests/test_club_answers.py::test_a_code_nobody_registered_is_answered_400_not_the_nearest_4xx` is what turns
    that bug red rather than a reader finding it. (This sentence cited `test_answers_agree.py`, a file that has
    never existed in this repository; the assertion it described is real and lives under the name above.)
    """
    return {str(code): ANSWERS.get(str(code), status.HTTP_400_BAD_REQUEST) for code in (item for group in codes for item in group)}


def refusal(error: ClubRefusal) -> HTTPException:
    """The HTTP answer a refusal deserves, at either door, from the one table."""
    return HTTPException(ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


__all__ = ["ANSWERS", "SETS", "TIERS", "assemble", "published", "refusal"]
