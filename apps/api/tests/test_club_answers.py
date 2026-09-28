"""#51: one refusal code means one HTTP answer, at *every* door of the tier.

§40 published "a code means one thing" for its own table and §41 kept it, and the rule was true *inside* each
tier and false *between* them. Three routers each assembled their own code→status map by hand: `/club/academy/…`
listed §39's, §40's, §41's and §42's codes because it is the door that raises them, and `/club/…` listed §39's
alone. A code raised at a door that had not listed it fell through to **400**, so `GET /club/{ident}/entitlements`
— which reaches §42's `no_such_entitlement_plan` whenever the plan row an operator can edit is missing — answered 400 while
the academy door answered the same code 404. Two sentences in the platform's own published table, two different
statuses for the same words.

These assertions are read off the maps and the functions themselves rather than from a list written here, so a
tier that adds codes without adding them everywhere fails in this file rather than in front of a caller. The
behavioural pair below (`_refusal` handed a real refusal) is the one that was red before the table was unified:
at `9ee3408`, `grep -c no_such_entitlement_plan app/api/v1/club.py` answers `0` — the code was nowhere in that door's table.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import status

from app.api.v1 import club as club_router
from app.api.v1 import club_academy as academy_router
from app.api.v1 import entitlements as entitlements_router
from app.core import security
from app.services import entitlements as ent
from app.services.club import academy as edu
from app.services.club import answers
from app.services.club import organizations as club
from app.services.club import reports as rep
from app.services.club import sessions as sess
from app.services.club.organizations import ClubRefusal

#: Matches is absent until §39's last noun lands, and importing a module that does not exist would turn every
#: test in this file into a collection error — which is a red that proves nothing.
try:
    from app.services.club import matches as mat
except ImportError:  # pragma: no cover - the state of the tree until §48
    mat = None

#: Every door that answers a `ClubRefusal`, by the name the reader uses for it.
DOORS = {
    "/club": club_router,
    "/club/academy": academy_router,
    "/entitlements": entitlements_router,
}

#: The tier's own published code lists — what a caller can be refused with, in the words the rulebook prints.
PUBLISHED_CODES = (*club.REFUSALS, *edu.REFUSALS, *edu.SHARED_REFUSALS, *sess.PUBLISHED, *rep.REFUSALS, *ent.REFUSALS)


def test_every_club_door_answers_from_the_one_table() -> None:
    """Not "agree on the codes they share" — literally the same object, so re-forking it fails here.

    Two hand-written tables can be equal today and differ the day somebody adds a tier to one of them, which is
    exactly how this file's bug was made. Identity is the assertion that cannot be re-broken by an edit elsewhere.
    """
    for name, door in DOORS.items():
        assert door._ANSWERS is answers.ANSWERS, f"{name} assembles its own answer table again; a code raised there will be answered 400 by omission"


@pytest.mark.parametrize("code", sorted(set(PUBLISHED_CODES)))
def test_a_published_code_has_an_answer_everywhere_it_can_be_raised(code: str) -> None:
    """A code any door can be refused with must be registered, at every door, with one status.

    §40's helpers (`_iso`, `_clip`, `_require_scope`) are reachable from §39's routes, and §42's meter is reached
    from `/club/{ident}/entitlements` today, so "raised only at the academy door" is not a safe assumption about
    the call graph — an assumption about who-calls-whom is the thing that broke last time.
    """
    answers_seen = {name: door._ANSWERS.get(code) for name, door in DOORS.items()}
    missing = [name for name, seen in answers_seen.items() if seen is None]
    assert not missing, f"{code} is published by the tier and falls through to 400 at {missing}"
    assert len(set(answers_seen.values())) == 1, f"{code} answers {answers_seen}: one code, one status"


def test_the_status_a_code_earns_is_the_tiers_own_claim_not_the_routers_guess() -> None:
    """A tier says which answer it wants by putting the code in one of its four sets; the table obeys.

    Without this, moving a code between sets would be invisible: every door would keep answering whatever the
    previous assembly happened to produce.
    """
    for module in (club, edu, sess, rep, ent):
        for code in module.NOT_FOUND_CODES:
            assert answers.ANSWERS[code] == status.HTTP_404_NOT_FOUND, f"{code} is an absence and was not answered as one"
        for code in module.UNPROCESSABLE_CODES:
            assert answers.ANSWERS[code] == status.HTTP_422_UNPROCESSABLE_ENTITY, f"{code} is a figure the caller can correct"
        for code in module.CONFLICT_CODES:
            assert answers.ANSWERS[code] == status.HTTP_409_CONFLICT, f"{code} collides with a row that already exists"


def test_forty_three_names_one_right_per_matrix_and_the_table_knows_the_whole_vocabulary() -> None:
    """Two claims, because the one this file made before was true only of a ledger that could not see the doors.

    The previous version asserted `forbidden == ["insufficient_role"]` over the assembled table. That read as a
    statement about 403 across the platform, and it was false when written: three sites raised an unregistered
    `account_inactive` and two raised an unregistered `forbidden` at `/knowledge/ingest`, none of them visible to
    a census over the club tiers alone. Registering the platform's own 403s (`app/core/security.py` is in `TIERS`)
    makes the ledger tell the truth about the territory, and the truth is scoped, not single:

    * every 403 the table answers with is in the platform's declared vocabulary — no third spelling is reachable;
    * a tier that prints a role matrix spends 403 on `insufficient_role` alone, and the tiers that print no matrix
      spend it on nothing.
    """
    forbidden = sorted(code for code, answer in answers.ANSWERS.items() if answer == status.HTTP_403_FORBIDDEN)
    assert forbidden == sorted(security.FORBIDDEN_CODES), f"403 was raised in words the table never registered: {sorted(set(forbidden) ^ set(security.FORBIDDEN_CODES))}"
    assert club.FORBIDDEN_CODES == frozenset({security.INSUFFICIENT_ROLE}), "the matrix tier's one 403 is the standing sentence"
    for name, module in {"edu": edu, "sess": sess, "rep": rep, "ent": ent}.items():
        assert not module.FORBIDDEN_CODES, f"{name} answers 403 with {sorted(module.FORBIDDEN_CODES)}; only a door with a role matrix may spend 403"


def test_no_tier_answers_403_with_a_code_outside_the_platform_vocabulary() -> None:
    """A tier may only claim a 403 the platform has already named, so a fourth sentence cannot be minted locally."""
    for module in (club, edu, sess, rep, ent):
        assert module.FORBIDDEN_CODES <= security.FORBIDDEN_CODES, f"{module.__name__} claims 403 for {sorted(module.FORBIDDEN_CODES - security.FORBIDDEN_CODES)}, which is not a platform sentence"


def test_no_code_is_claimed_by_two_modules_with_different_meanings() -> None:
    """The disjointness the academy door's comment promises, checked over the whole tier.

    Over each module's `PUBLISHED` set where it has one, not its raw `REFUSALS`: §41's session codes *include*
    `date_shape` and `text_too_long` because the tier raises them and §40 owns them, and `PUBLISHED` is exactly
    the set that declines to claim them twice. Asserting against `REFUSALS` would fail on honest bookkeeping.
    """
    seen: dict[str, str] = {}
    for name, module in {"club": club, "edu": edu, "sess": sess, "rep": rep, "ent": ent}.items():
        for code in getattr(module, "PUBLISHED", module.REFUSALS):
            assert code not in seen, f"{code} is §{seen[code]}'s and {name}'s: one code, one meaning"
            seen[code] = name


def test_a_code_two_tiers_registered_with_two_answers_is_refused_at_import() -> None:
    """`assemble()` decides a collision loudly instead of letting the last layer of the literal win.

    A guard nobody can reach is worth nothing, so this builds the collision rather than hunting for one: two
    stand-in tiers, one code, two statuses.
    """
    first = SimpleNamespace(__name__="first", NOT_FOUND_CODES=frozenset({"duplicate_code"}))
    second = SimpleNamespace(__name__="second", CONFLICT_CODES=frozenset({"duplicate_code"}))
    with pytest.raises(RuntimeError, match="duplicate_code"):
        answers.assemble(first, second)
    # The control: the same two modules, agreeing, assemble into the table the caller was promised.
    agree = SimpleNamespace(__name__="agree", CONFLICT_CODES=frozenset({"only_collision"}))
    assert answers.assemble(second, agree) == {"duplicate_code": status.HTTP_409_CONFLICT, "only_collision": status.HTTP_409_CONFLICT}


@pytest.mark.parametrize("code", ["no_such_entitlement_plan", "no_such_feature", "entitlement_limit"])
def test_the_meter_refusals_answer_the_same_at_both_doors(code: str) -> None:
    """Behavioural, through the function each route actually calls.

    This is the case that was red at `9ee3408`: §42's codes were in the academy door's table and in nobody
    else's, so `GET /club/{ident}/entitlements` — which looks the plan row up — answered a missing plan as a
    malformed request.
    """
    error = ClubRefusal(code, f"a {code} refusal built by the suite")
    expected = {
        "no_such_entitlement_plan": status.HTTP_404_NOT_FOUND,
        "no_such_feature": status.HTTP_404_NOT_FOUND,
        "entitlement_limit": status.HTTP_409_CONFLICT,
    }[code]
    for name, door in DOORS.items():
        raised = door._refusal(error)
        assert raised.status_code == expected, f"{code} answered {raised.status_code} at {name} and {expected} elsewhere"
        assert raised.detail["code"] == code


def test_a_code_nobody_registered_is_answered_400_not_the_nearest_4xx() -> None:
    """The documented fall-through, held from the other side.

    Without this, the union above could be "fixed" by mapping every unknown code to 422 and the silence would
    look like coverage. An unregistered code is supposed to be loud, not convenient.
    """
    assert "a_code_no_module_owns" not in answers.ANSWERS
    raised = club_router._refusal(ClubRefusal("a_code_no_module_owns", "invented by the suite"))
    assert raised.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.skipif(mat is None, reason="§39's Matches tier has not landed yet")
def test_the_fixture_tier_registers_every_code_it_raises() -> None:
    """`Matches` raises §40's codes as well as its own, so the one table must know all of them."""
    assert mat is not None
    for code in mat.REFUSALS:
        assert code in answers.ANSWERS, f"{code} would be answered 400 at the door that raises it"
    assert not mat.FORBIDDEN_CODES, "403 is §39's single `insufficient_role` and stays that way"


def test_the_capabilities_doors_publish_the_table_they_answer_from() -> None:
    """A page that names a status the door does not use teaches a caller to expect an answer that never comes.

    `answers.published()` is what both rulebooks build their rows with, so the printed figure and the raised
    exception cannot be written apart — which is the same defect class this file was opened for, one level up.
    """
    for code in sorted(set(PUBLISHED_CODES)):
        assert answers.published((code,)) == {code: answers.ANSWERS[code]}
    assert answers.published(("a_code_no_module_owns",)) == {"a_code_no_module_owns": status.HTTP_400_BAD_REQUEST}
