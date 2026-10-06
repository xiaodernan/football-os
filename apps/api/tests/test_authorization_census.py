"""#68: §60's authorization census — every 403 this API answers comes from a code the table knows.

Spec §60 lists `Authorization` and `RBAC` as must-haves, and §51 settled what one refusal code means. Both were
being *nearly* obeyed, in a way no existing test could see. Measured at `f928640`, before this file existed:

* `answers.ANSWERS` held exactly one code answering 403 — §39's `insufficient_role` — and the case in
  `test_club_answers.py` that this landing rewrote asserted that it was the only one. The assertion was true. It
  read the assembled table, and the table is assembled from the **services**.
* Meanwhile `app/` raised 403 from five sites outside any tier: `auth.py:86`, `auth.py:110` and
  `core/security.py:104` with `account_inactive`, and `core/security.py:112` and `api/v1/knowledge.py:212` with
  `forbidden`. Two codes, neither registered, five doors, zero cases between them.

So the ledger said one 403 and the territory said three. A guard that enumerates the ledger cannot catch a
router that never writes to it — which is the general shape of this file: **the population is read off the source
tree, not off the declaration that the declaration was supposed to police.**

What the census allows, and why: exactly two modules hold a 403 status literal — `core/security.py`, which mints
one per registered code, and `services/club/answers.py`, which binds a tier's `FORBIDDEN_CODES` set to the status in
the assembly. Every other module that wants 403 to mean something registers a code and raises through a builder, so
it never spells a status.

Three findings this file settles rather than assumes:

* `("admin", "staff", "operator")` was `/knowledge/ingest`'s allow-list. `staff` and `operator` name nothing:
  `core/security.ROLES` has seven standings, `services/club/access.ROLES` has six *tenant* standings, and
  `staff` is real only as a §39 announcement **audience** — a predicate over a roster, not a standing an account
  holds. And they were genuinely unreachable rather than merely unlisted: `RegisterIn.role` is a `Literal` of six
  values, so the door that creates accounts cannot create a `staff` one either.
* `require_roles()` in `core/security.py` was the helper that minted `forbidden`, and **no router imported it**
  (measured repo-wide: two hits, both in its own file — its definition and its `__all__` entry). It was deleted
  rather than repaired; a second way to refuse a role, used by nobody, is how the first way spread.
* No test in this suite mentioned `admin` at all before this file, so the platform's highest standing had never
  reached an admin-only door. The success case below is the first time that path runs.

The census proved itself against territory rather than against my own edits, within the hour. A second agent's
account-deletion route was written into `auth.py` while this file's mutation probe was mid-leg, and the case that
bans a third holder went red on it: that route spent 403 on `invalid_password`, a code no answer table registers.
Nothing had to be taught about it and no allow-list had to be widened — the population is read off the tree, so a
router that never writes to the ledger is in the census the moment it is saved. That read was left open here rather
than papered over, and the erasure route has since landed, so the gap is closed in the direction this file named:
`invalid_password` is a third constant in `core/security.py`, raised through `password_refusal()`, and the
reachability case below now earns all three codes at three different doors. The same landing made
`current_user` stop answering for an erased account: with the row gone it raised `account_inactive`, a 403 whose one
meaning is "this account is switched off" — describing an account that is not there. A missing row is now the same
401 an undecodable token earns, which is what `test_account_deletion.py` asserts after a confirmed erasure.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.v1 import knowledge as knowledge_router
from app.core import security
from app.core.db import SessionLocal
from app.models import User
from app.schemas import RegisterIn
from app.services.club import answers

APP_ROOT = Path(security.__file__).resolve().parent.parent
FORBIDDEN = status.HTTP_403_FORBIDDEN

#: The modules allowed to hold a 403 status literal, each with the reason it is allowed.
#:
#: Two, not one: `core/security.py` mints the registered answers, and `services/club/answers.py` is the assembly
#: that binds *some future tier's* `FORBIDDEN_CODES` set to 403 — a module that declares the mapping rather than
#: spending it. The ban is on a third module spelling the status, which is what five of them did before this file.
ALLOWED_HOLDERS = {
    "app/core/security.py": "mints one 403 answer per registered code",
    "app/services/club/answers.py": "binds a tier's FORBIDDEN_CODES to 403 in the assembly table",
}


def _module_sources() -> dict[str, str]:
    """Every module the shipped API is made of, keyed by its path from `apps/api`.

    Read off the tree rather than from a list written here, so a new router that spends 403 is in the population
    the first time it is saved and not the first time somebody remembers to add it to an allow-list.
    """
    return {path.relative_to(APP_ROOT.parent).as_posix(): path.read_text(encoding="utf-8") for path in sorted(APP_ROOT.rglob("*.py")) if "__pycache__" not in path.parts}


class TestFortyThreeIsRaisedFromTheTable:
    def test_only_the_modules_that_own_the_codes_hold_the_status(self) -> None:
        sources = _module_sources()
        holders = sorted(name for name, text in sources.items() if "HTTP_403" in text)
        assert holders == sorted(ALLOWED_HOLDERS), (
            f"403 is being spelled somewhere that registers no code: {sorted(set(holders) - set(ALLOWED_HOLDERS))} (whole census: {holders}). "
            f"A door that wants 403 has two ways out, both in `core/security.py`: raise through an existing builder "
            f"({sorted(b.__name__ for b in (security.role_refusal, security.inactive_refusal))}), which spells no status, "
            f"or register a third code in FORBIDDEN_CODES with its own builder so the assembly answers it. "
            f"Spelling the status here is the third way, and it is the one that leaves the ledger silent."
        )

    def test_the_floor_comes_from_the_same_scan_as_the_ban(self) -> None:
        """"Nobody spent 403" must not be readable as "the scan saw nothing".

        The ban above is an equality over a population this function builds; if the population were empty — a wrong
        root, a renamed package — the equality would hold of nothing. So each allowed holder is counted by the same
        scan, and each count is a fact about that module: the minting module holds one literal per registered code,
        the assembly holds the one row that pairs a set with the status.
        """
        sources = _module_sources()
        holders = [name for name, text in sources.items() if "HTTP_403" in text]
        assert len(holders) == len(ALLOWED_HOLDERS), f"the floor and the ban disagree: {sorted(holders)}"
        assert sources["app/core/security.py"].count("status.HTTP_403_FORBIDDEN") == len(security.FORBIDDEN_CODES), (
            f"security.py spells {sources['app/core/security.py'].count('status.HTTP_403_FORBIDDEN')} 403 literals and this file registers "
            f"{len(security.FORBIDDEN_CODES)} codes; a 403 with no builder is a 403 spelled at a raise site again"
        )
        assert sources["app/services/club/answers.py"].count("status.HTTP_403_FORBIDDEN") == 1, "the assembly pairs each set with one status exactly once; a second row is a second meaning"

    def test_the_registered_codes_are_exactly_the_ones_the_table_answers_with(self) -> None:
        table = {code for code, answer in answers.ANSWERS.items() if answer == FORBIDDEN}
        assert table == set(security.FORBIDDEN_CODES), f"the ledger and the vocabulary disagree: {sorted(table)} vs {sorted(security.FORBIDDEN_CODES)}"

    def test_no_tier_registers_a_code_that_is_not_in_the_platform_vocabulary(self) -> None:
        """`insufficient_role` may be spent by a tier *and* by the platform, but only as the same word.

        §39's set and `security`'s both list `insufficient_role`; `assemble()` allows that because they agree on
        the status, and this case allows it because they are the same sentence. Anything else a tier spends 403
        with has to be a code the platform has already agreed means something.
        """
        for tier in answers.TIERS:
            for code in frozenset(getattr(tier, "FORBIDDEN_CODES", frozenset())):
                assert code in security.FORBIDDEN_CODES, f"{tier.__name__} spends 403 with {code!r}, which the platform has not registered"

    @pytest.mark.parametrize("code", sorted(security.FORBIDDEN_CODES))
    def test_every_registered_forty_three_is_reachable_and_answered_as_one(self, client: TestClient, code: str) -> None:
        """Each code is not merely listed — a door answers with it, and answers 403, and only that.

        A registry nobody can reach is a wish. `insufficient_role` is earned at `/knowledge/ingest` by a caller
        whose standing is below it; `account_inactive` is earned at `/auth/me` by an account switched off; and
        `invalid_password` is earned at `DELETE /auth/account` by a signed-in account that typed its own password
        wrong. The three branches are the three codes, so a fourth one added to `FORBIDDEN_CODES` fails here
        until somebody shows the door it is answered at.
        """
        if code == security.INSUFFICIENT_ROLE:
            response = client.post("/api/v1/auth/register", json={"email": "census-insufficient@example.test", "password": "strong-pass-1234", "display_name": "Census", "role": "player", "accepts_data_policy": True})
            token = response.json()["access_token"]
            refused = client.post("/api/v1/knowledge/ingest", json={}, headers={"Authorization": f"Bearer {token}"})
        elif code == security.ACCOUNT_INACTIVE:
            email = "census-inactive@example.test"
            registered = client.post("/api/v1/auth/register", json={"email": email, "password": "strong-pass-1234", "display_name": "Census", "role": "player", "accepts_data_policy": True})
            token = registered.json()["access_token"]
            session = SessionLocal()
            try:
                row = session.query(User).filter(User.email == email).one()
                row.is_active = False
                session.commit()
            finally:
                session.close()
            refused = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        else:
            registered = client.post("/api/v1/auth/register", json={"email": "census-password@example.test", "password": "strong-pass-1234", "display_name": "Census", "role": "player", "accepts_data_policy": True})
            token = registered.json()["access_token"]
            refused = client.request(
                "DELETE",
                "/api/v1/auth/account",
                json={"confirm": "DELETE", "password": "not-the-stored-password"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert refused.status_code == FORBIDDEN, f"{code} was answered {refused.status_code}, not 403: {refused.text}"
        detail = refused.json()["detail"]
        assert detail["code"] == code
        assert answers.ANSWERS[code] == FORBIDDEN, f"{code} answers {refused.status_code} at the door and {answers.ANSWERS[code]} in the table"


class TestAStandingMustExistBeforeADoorCanAskForIt:
    def test_an_invented_standing_is_refused_rather_than_stored(self) -> None:
        """Both ends of the guard, through the shipped function.

        `("staff",)` is not an arbitrary choice: it is the exact word `/knowledge/ingest` shipped believing was a
        standing. Accepting it would mean the guard cannot tell a role from an audience.
        """
        assert security.standing_check(("admin", "player")) == ("admin", "player")
        with pytest.raises(RuntimeError, match="staff"):
            security.standing_check(("staff",))
        with pytest.raises(RuntimeError, match="operator"):
            security.standing_check(("admin", "operator"))

    def test_the_door_asks_for_a_standing_the_vocabulary_has(self) -> None:
        assert set(knowledge_router.INGEST_STANDING) <= set(security.ROLES)

    def test_the_word_forbidden_is_not_an_answer_this_platform_gives(self) -> None:
        offenders = [name for name, text in _module_sources().items() if '"code": "forbidden"' in text or "'code': 'forbidden'" in text]
        assert offenders == [], f"{offenders} still answer 403 with a code no tier registers"

    def test_the_registrable_roles_differ_from_the_vocabulary_by_exactly_admin(self) -> None:
        """`RegisterIn.role` and `ROLES` are two homes for one fact, and this is the drift check.

        The schema is a `Literal` because that is what publishes the enum in the contract; `ROLES` is the tuple
        the rest of the code reads. They differ by exactly one value, `admin`, and that difference is a policy:
        the platform's highest standing is not something you sign up for. Asserting the difference rather than
        equality keeps the policy visible; a seventh registrable role or a silently dropped one fails here.
        """
        registrable = {str(item) for item in get_args(RegisterIn.model_fields["role"].annotation)}
        assert registrable <= set(security.ROLES), f"the register door offers standings the vocabulary does not have: {sorted(registrable - set(security.ROLES))}"
        assert set(security.ROLES) - registrable == {"admin"}, f"the gap between what an account can sign up as and what it can be is a policy, and it moved: {sorted(set(security.ROLES) - registrable)}"


class TestTheAdminStandingIsReachableSomewhere:
    def test_an_admin_reaches_the_door_that_refuses_everyone_else(self, client: TestClient) -> None:
        """The first time this platform's highest standing has been measured passing a door.

        Nothing in the suite mentioned `admin` before this file, so `ownership_or_admin`'s admin branch and
        `/knowledge/ingest`'s allow-list were both unexercised. The account is written straight to the database
        because that is the only way one exists: the register door's `Literal` refuses `admin`, by design.
        """
        session = SessionLocal()
        try:
            row = User(
                id=security.new_public_id("usr"),
                email=f"admin-census-{security.new_public_id('x')}@example.test",
                password_hash=security.hash_password("strong-pass-1234"),
                display_name="Census Admin",
                role="admin",
                is_active=True,
            )
            session.add(row)
            session.commit()
            user_id = row.id
        finally:
            session.close()
        token = security.create_access_token(user_id, "admin")
        response = client.post("/api/v1/knowledge/ingest", json={}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True and body["report"]["documents_seen"] >= 12, "the door ran, so the figure it returns has to be the corpus's"
        assert body["audit_id"].startswith("aud_"), "an ingest that is allowed must still leave the §60 audit row"
