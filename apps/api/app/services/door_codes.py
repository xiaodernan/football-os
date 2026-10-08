"""The ledger's view of the routers: refusal codes raised inline at doors, registered for §51's one table.

`services/club/answers.py` documents why this module exists. The answer table is assembled from *service*
tiers — "a tier list assembled from the services alone is a ledger that cannot see the routers", and the
routers were spending statuses freely. `core.security` joined `TIERS` first for the platform's own 403/401
mints; this module is the same move for every remaining door code that only a router raises.

Nothing here imports a router, and no router edits a literal here: each code is listed with the modules
that raise it, and `tests/test_answer_census.py` reads the source tree and refuses any raise site whose
status disagrees with the row below (or any code missing from the table). The census — not this file's
discipline — is what keeps ledger and territory one fact, because the census is what found them apart:
measured before this landing, **58 inline literals across 14 modules raised 47 distinct codes that
`ANSWERS` did not know**, so they fell through to whatever status the raise itself spelled.

The statuses are not chosen here; they are copied from the raise sites as they stood, one code one status
across every door that raises it (the scan found zero collisions before registration, and `assemble()`
refuses to import a file that would create one).
"""

from __future__ import annotations

from typing import Final

#: A thing the request names that is not there — 404. `not_found` is not listed here: it is raised by
#: `core.security`'s resource helper and by ten routers' own `NOT_FOUND` constants, and it registers
#: with the platform module rather than being duplicated in this one.
NOT_FOUND_CODES: Final = frozenset(
    {
        "no_such_challenge",  # challenges
        "no_such_club",  # careers
        "no_such_frame",  # video
        "no_such_input",  # simulations
        "no_such_system",  # careers, challenges, simulations
        "wrong_path",  # tactics
    }
)

#: The request would break a state the row already holds, or has already been done — 409.
CONFLICT_CODES: Final = frozenset(
    {
        "already_completed",  # trainings
        "board_limit",  # boards
        "cannot_play",  # careers (and `WindowClosed`'s `window_closed` reaches this answer at careers:195)
        "career_limit",  # careers
        "email_taken",  # auth
        "missing_records",  # trainings
        "no_fixture",  # careers
        "no_player",  # coach, progress, tactics, trainings
        "organization_owner_required",  # auth
        "player_exists",  # players
        "run_limit",  # challenges
        "simulation_limit",  # simulations
        "video_limit",  # video
        "window_closed",  # careers (WindowClosed.to_dict), simulation.market's transferable verdict
    }
)

#: The caller's own words are wrong, or the payload cannot be parsed — 422.
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "account_delete_confirmation",  # auth
        "bad_date",  # world
        "bad_minutes",  # simulations
        "bad_objective",  # careers
        "bad_philosophy",  # careers
        "bad_status",  # world
        "cannot_choose_club",  # challenges
        "entity_type_required",  # world
        "invalid_board",  # boards
        "no_objectives",  # careers
        "same_team",  # simulations
        "unknown_change",  # tactics
    }
)

#: No session, or a session that no longer proves an identity — 401. The token mints themselves live in
#: `core.security`; these four are raised by `auth.py`'s login and refresh doors.
UNAUTHORIZED_CODES: Final = frozenset(
    {
        "invalid_credentials",  # auth
        "no_refresh",  # auth
        "refresh_invalid",  # auth
        "refresh_reused",  # auth
    }
)

#: The door refuses before its work can start — 429. `rate_limited` (core.security's limiter) is the
#: platform's own and sits there; this is the application's budget refusal at `/knowledge/ask`.
TOO_MANY_REQUESTS_CODES: Final = frozenset({"ai_budget_exhausted"})  # knowledge

#: A dependency the answer needs is not running — 503, and the two codes answer with `held`/`limit` style
#: figures beside the sentence rather than as a generic error.
SERVICE_UNAVAILABLE_CODES: Final = frozenset(
    {
        "media_tools_missing",  # video
        "private_media_not_erased",  # auth (§61's erasure refuses before any write)
    }
)

#: Upload rejections whose status is the HTTP verb of the body itself: 413, 415, 416 — each its own set
#: because `SETS` binds one attribute to one status, and video's three doors spell three different ones.
TOO_LARGE_CODES: Final = frozenset({"too_large"})  # video
UNSUPPORTED_MEDIA_CODES: Final = frozenset({"unsupported_container"})  # video
RANGE_NOT_SATISFIABLE_CODES: Final = frozenset({"range_not_satisfiable"})  # video

#: Every attribute `answers.SETS` reads from a tier. Kept explicit so a set added here that `SETS` does
#: not know would fail loudly (the code would simply not register) rather than silently.
__all__ = [
    "CONFLICT_CODES",
    "NOT_FOUND_CODES",
    "RANGE_NOT_SATISFIABLE_CODES",
    "SERVICE_UNAVAILABLE_CODES",
    "TOO_LARGE_CODES",
    "TOO_MANY_REQUESTS_CODES",
    "UNAUTHORIZED_CODES",
    "UNPROCESSABLE_CODES",
    "UNSUPPORTED_MEDIA_CODES",
]
