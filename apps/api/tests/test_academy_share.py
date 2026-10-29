"""M13 Phase 5 item 18, second half — §40's plan behind a link, and what a stranger may see of it.

The claim this file measures is the one the tier makes: the link stores a *question* — this tenant, this plan —
and never a figure. So the checks are of four kinds.

* **The public page is compared with the private read of the same plan.** `progress` has to be the same object
  field by field, because both are `progress_of()` over the same rows on the same request; a review filed after
  the link was minted is on the next public read, which is the proof nothing was copied at mint time.
* **The child is not in the payload.** The player's name and slug are asserted absent from the raw response
  text, no key anywhere names an age, a position, a team, a coach or a free-text note, and the coach's own words
  planted in a review and in feedback never appear.
* **The gate is the private read's gate plus §40's minors' gate.** A stranger in the tenant's own records but
  not on its plans is answered 403; a parent of a different child is answered as a plan that does not exist;
  a minor whose consent was withdrawn cannot have a link minted even by staff.
* **The token is a capability.** Unknown, closed and somebody else's answer one 404; the ceiling is exercised by
  moving it with `monkeypatch`, so the refusal names both figures without the suite minting twenty links.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import _response_cache, response_cache_key
from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.main import app
from app.models import AcademyPlanShare, Organization, RealPlayer, User, VideoAsset
from app.services.club import academy as edu
from app.services.club import sharing as sharing_module
from app.services.world import sync_world, world_ready

CLUB = "/api/v1/club"
ACADEMY = f"{CLUB}/academy"
SHARES = f"{ACADEMY}/shares"
CAPABILITIES = f"{ACADEMY}/capabilities"
PASSWORD = "strong-pass-1234"
#: Keys that would mean the child is in a public payload. `organization` legitimately carries the tenant's name,
#: so the comparison is exact key names rather than every appearance of a word.
PRIVATE_KEYS = frozenset({"player", "player_id", "age", "age_at_open", "is_minor", "position", "overall", "potential", "team", "team_id", "author", "coach", "user_id", "email", "display_name", "strengths", "areas", "next_focus", "feedback_text", "video"})
FULL_RATINGS = {"technique": 61, "tactics": 40, "physical": 55, "mental": 70, "competition_readiness": 33}


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    try:
        sync_world(session)
        players = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(players) > 20 and world_ready(session)
        minors = [row.slug for row in players if int(row.age) < edu.MINOR_AGE]
        adults = [row.slug for row in players if int(row.age) >= edu.MINOR_AGE]
        assert len(minors) >= 2 and len(adults) >= 2
        names = {row.slug: row.name for row in players}
        return {"minors": minors, "adults": adults, "names": names}
    finally:
        session.close()


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(name: str = "Plan Sharer") -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"plan-share-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "coach", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _email_of(client: TestClient) -> str:
    return str(client.get("/api/v1/auth/me").json()["email"])


def _tenant(name: str = "North Bank Academy", owner: str = "Academy Lead") -> tuple[TestClient, str]:
    client = _account(owner)
    opened = client.post(CLUB, json={"name": name, "kind": "academy", "country": "en"})
    assert opened.status_code == 200, opened.text
    return client, str(opened.json()["organization"]["slug"])


def _joined(owner: TestClient, ident: str, role: str, name: str) -> TestClient:
    guest = _account(name)
    assert owner.post(f"{CLUB}/{ident}/invites", json={"email": _email_of(guest), "role": role}).status_code == 200
    assert guest.post(f"{CLUB}/{ident}/accept").status_code == 200
    return guest


def _grant(guardian: TestClient, ident: str, slug: str, scopes: list[str] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"player": slug}
    if scopes is not None:
        body["scopes"] = scopes
    response = guardian.post(f"{ACADEMY}/{ident}/consents", json=body)
    assert response.status_code == 200, response.text
    return response.json()["consent"]


def _sheet(client: TestClient, ident: str, slug: str) -> None:
    """Put one player on this tenant's sheet, creating its squad on first use: a plan is about a listed child."""
    team = client.post(f"{CLUB}/{ident}/teams", json={"name": "Squad", "age_group": "open", "stage": "youth"})
    if team.status_code == 200:
        team_id = str(team.json()["team"]["id"])
    else:
        tenant = client.get(f"{CLUB}/{ident}")
        assert tenant.status_code == 200, tenant.text
        team_id = str(tenant.json()["teams"][0]["id"])
    added = client.post(f"{CLUB}/{ident}/teams/{team_id}/players", json={"player": slug, "note": ""})
    if added.status_code != 200:
        assert _detail(added)["code"] == "already_on_team", added.text


def _plan(client: TestClient, ident: str, slug: str, **body: Any) -> dict[str, Any]:
    _sheet(client, ident, slug)
    response = client.post(f"{ACADEMY}/{ident}/plans", json={"player": slug, **body})
    assert response.status_code == 200, response.text
    return response.json()["plan"]


def _review(client: TestClient, ident: str, plan_id: str, day: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"{ACADEMY}/{ident}/plans/{plan_id}/assessments", json={"assessed_on": day, "ratings": FULL_RATINGS, **body})
    assert response.status_code == 200, response.text
    return response.json()["assessment"]


def _share(client: TestClient, ident: str, plan_id: str) -> dict[str, Any]:
    response = client.post(f"{ACADEMY}/{ident}/plans/{plan_id}/share")
    assert response.status_code == 200, response.text
    return response.json()


def _detail(response: Any) -> dict[str, Any]:
    body = response.json()
    assert "detail" in body, body
    return dict(body["detail"])


def _clip_of(client: TestClient, session: Session, duration: float = 40.0) -> str:
    """An M5 upload owned by this account; §40 cites footage, it does not take one."""
    owner = session.scalar(select(User).where(User.email == _email_of(client)))
    assert owner is not None
    now = datetime.now(UTC)
    asset = VideoAsset(
        id=new_public_id("vid"),
        owner_id=owner.id,
        title="share sweep probe",
        filename="clip.mp4",
        storage_key=f"share-sweep/{uuid4().hex}.mp4",
        content_type="video/mp4",
        size_bytes=4096,
        duration_s=duration,
        width=1280,
        height=720,
        fps=25.0,
        codec="h264",
        created_at=now,
        updated_at=now,
    )
    session.add(asset)
    session.commit()
    return str(asset.id)


def _warm(path: str) -> str:
    """Put one anonymous answer in the cache under a public path, as `cached_response_for` would."""
    key = response_cache_key(path, "")
    _response_cache.set(key, {"body": "{}", "status_code": 200, "headers": [], "media_type": "application/json"})
    assert _response_cache.get(key) is not None, "the fixture has to start warm"
    return key


def _keys(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


class TestThePublishedRulebook:
    def test_the_share_codes_are_published_with_one_status_each(self) -> None:
        body = TestClient(app).get(CAPABILITIES).json()
        assert body["share_refusals"] == {
            "no_such_share": 404,
            "share_subject_gone": 404,
            "share_already_revoked": 409,
            "too_many_shares": 409,
        }
        assert set(body["share_refusals"]) == set(sharing_module.REFUSALS)
        assert not set(sharing_module.REFUSALS) & set(edu.REFUSALS), "a code that meant two things would answer with two statuses"
        assert "14 days" not in sharing_module.LIMITATION and "revocable" in sharing_module.LIMITATION
        assert sharing_module.LIMITATION in body["limitations"]

    def test_the_public_page_lists_every_omission_with_a_reason(self) -> None:
        assert len(sharing_module.REDACTED) == 9
        for field, why in sharing_module.REDACTED:
            assert field and why, "an omission without a reason is indistinguishable from a thin page"
        assert {field for field, _ in sharing_module.REDACTED} == {
            "name",
            "exact_age",
            "position_and_rating",
            "team_name",
            "coach",
            "feedback_text",
            "review_notes",
            "video",
            "account_and_guardian",
        }


class TestThePublicRead:
    def test_a_link_answers_a_stranger_and_agrees_with_the_private_read(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant()
        plan = _plan(coach, ident, world["adults"][0], focus=["first touch"], goals=[{"title": "cleaner first touch", "measure": "two of three reps", "by": "2026-12-01"}])
        _review(coach, ident, plan["id"], "2026-09-01")
        _review(coach, ident, plan["id"], "2026-10-01")
        minted = _share(coach, ident, plan["id"])
        assert minted["created"] is True
        token = str(minted["token"])
        assert len(token) == 32 and all(character in "0123456789abcdef" for character in token)
        private = coach.get(f"{ACADEMY}/{ident}/plans/{plan['id']}").json()
        with TestClient(app) as stranger:
            public = stranger.get(f"{ACADEMY}/shared/{token}")
        assert public.status_code == 200, public.text
        payload = public.json()
        assert payload["progress"] == private["progress"], "the public page and the private read are one arithmetic over one set of rows"
        assert payload["plan"]["status"] == plan["status"]
        assert payload["plan"]["review_weeks"] == plan["review_weeks"]
        assert payload["plan"]["stage"] == "adult"
        assert payload["plan"]["goals"] == [{"title": "cleaner first touch", "measure": "two of three reps", "by": "2026-12-01"}]
        assert payload["shared"]["plan"] == plan["id"]
        assert payload["shared"]["organization"] == {"slug": ident, "name": org_name(ident), "kind": "academy"}
        assert payload["counts"] == {"assessments": 2, "feedback": 0, "feedback_shared_with_guardian": 0, "evidence": 0}
        assert payload["demo_data"] is False
        assert not PRIVATE_KEYS & set(_keys(payload))
        assert world["names"][world["adults"][0]] not in public.text and world["adults"][0] not in public.text

    def test_the_child_name_and_the_coachs_words_never_appear(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("East Dock Academy")
        plan = _plan(coach, ident, world["adults"][1])
        _review(coach, ident, plan["id"], "2026-10-02", strengths="SECRET-STRENGTH", areas="SECRET-AREA", next_focus="SECRET-NEXT")
        filed = coach.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/feedback", json={"message": "SECRET-COACH-NOTE", "shared_with_guardian": True})
        assert filed.status_code == 200, filed.text
        minted = _share(coach, ident, plan["id"])
        with TestClient(app) as stranger:
            public = stranger.get(f"{ACADEMY}/shared/{minted['token']}")
        assert public.status_code == 200, public.text
        for secret in ("SECRET-STRENGTH", "SECRET-AREA", "SECRET-NEXT", "SECRET-COACH-NOTE"):
            assert secret not in public.text, f"{secret} reached a public page"
        assert world["names"][world["adults"][1]] not in public.text
        assert [item["field"] for item in public.json()["redacted"]] == [field for field, _ in sharing_module.REDACTED]
        assert public.json()["counts"]["feedback"] == 1 and public.json()["counts"]["feedback_shared_with_guardian"] == 1
        assert public.json()["assessments"][0]["mean_rating"] == round(sum(FULL_RATINGS.values()) / len(FULL_RATINGS), 1)

    def test_an_unknown_token_is_the_same_absence_and_answers_no_account(self, world: dict[str, Any]) -> None:
        with TestClient(app) as stranger:
            answer = stranger.get(f"{ACADEMY}/shared/" + "0" * 32)
        assert answer.status_code == 404, answer.text
        assert _detail(answer)["code"] == "no_such_share"

    def test_a_minted_link_keeps_ageing_in_the_open(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("West Gate Academy")
        plan = _plan(coach, ident, world["adults"][0])
        minted = _share(coach, ident, plan["id"])
        _review(coach, ident, plan["id"], "2026-10-05")
        with TestClient(app) as stranger:
            public = stranger.get(f"{ACADEMY}/shared/{minted['token']}")
        assert public.status_code == 200, public.text
        assert public.json()["counts"]["assessments"] == 1, "a figure stored at mint time would still be zero here"
        assert public.json()["progress"]["overall_last"] is not None


def org_name(ident: str) -> str:
    session = SessionLocal()
    try:
        row = session.scalar(select(Organization).where(Organization.slug == ident))
        assert row is not None
        return str(row.name)
    finally:
        session.close()


class TestTheGate:
    def test_a_stranger_in_no_tenant_is_answered_as_a_tenant_that_does_not_exist(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("South Pier Academy")
        plan = _plan(coach, ident, world["adults"][0])
        outsider = _account("Uninvited Guest")
        refused = outsider.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/share")
        assert refused.status_code == 404, refused.text
        assert _detail(refused)["code"] == "no_such_organization"

    def test_a_role_without_a_plan_right_is_refused_with_the_matrix(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Harbour View Academy")
        plan = _plan(owner, ident, world["adults"][0])
        scout = _joined(owner, ident, "scout", "Academy Scout")
        refused = scout.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/share")
        assert refused.status_code == 403, refused.text
        assert _detail(refused)["code"] == "insufficient_role"

    def test_a_parent_of_another_child_is_answered_as_a_plan_that_does_not_exist(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Mill Lane Academy")
        parent = _joined(owner, ident, "parent", "Guardian Of One")
        _sheet(owner, ident, world["minors"][0])
        _grant(parent, ident, world["minors"][0])
        own = _plan(owner, ident, world["minors"][0])
        other = _plan(owner, ident, world["adults"][0])
        minted = parent.post(f"{ACADEMY}/{ident}/plans/{own['id']}/share")
        assert minted.status_code == 200, minted.text
        assert minted.json()["consented_by"]["guardian"] is not None
        refused = parent.post(f"{ACADEMY}/{ident}/plans/{other['id']}/share")
        assert refused.status_code == 404, refused.text
        assert _detail(refused)["code"] == "no_such_plan"

    def test_a_withdrawn_consent_stops_a_minors_link_even_for_staff(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Old Foundry Academy")
        parent = _joined(owner, ident, "parent", "Guardian Who Said No")
        _sheet(owner, ident, world["minors"][1])
        _grant(parent, ident, world["minors"][1])
        plan = _plan(owner, ident, world["minors"][1])
        assert parent.delete(f"{ACADEMY}/{ident}/consents/{world['minors'][1]}").status_code == 200
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/share")
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "consent_required"
        assert detail["scope"] == "plan" and detail["threshold"] == edu.MINOR_AGE

    def test_a_scope_set_without_plan_is_not_a_yes_for_a_public_page(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Bell Tower Academy")
        parent = _joined(owner, ident, "parent", "Guardian Of Assessment")
        _sheet(owner, ident, world["minors"][0])
        _grant(parent, ident, world["minors"][0], scopes=["assessment", "feedback"])
        opened = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": world["minors"][0]})
        assert opened.status_code == 422, opened.text
        assert _detail(opened)["code"] == "scope_not_consented"


class TestTheLedger:
    def test_asking_twice_returns_the_same_live_token(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("Ferry Road Academy")
        plan = _plan(coach, ident, world["adults"][0])
        first = _share(coach, ident, plan["id"])
        second = _share(coach, ident, plan["id"])
        assert second["created"] is False
        assert second["token"] == first["token"] and second["opened_at"] == first["opened_at"]
        ledger = coach.get(SHARES)
        assert ledger.status_code == 200, ledger.text
        assert ledger.json()["counts"] == {"opened": 1, "live": 1, "revoked": 0}
        assert ledger.json()["max_live"] == sharing_module.MAX_LIVE
        assert ledger.json()["shares"][0]["token"] == first["token"]

    def test_the_ceiling_refuses_with_both_figures(self, world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sharing_module, "MAX_LIVE", 1)
        coach, ident = _tenant("Lock Keepers Academy")
        first = _plan(coach, ident, world["adults"][0])
        second = _plan(coach, ident, world["adults"][1])
        assert _share(coach, ident, first["id"])["max_live"] == 1
        refused = coach.post(f"{ACADEMY}/{ident}/plans/{second['id']}/share")
        assert refused.status_code == 409, refused.text
        detail = _detail(refused)
        assert detail["code"] == "too_many_shares"
        assert detail["live"] == 1 and detail["max_live"] == 1

    def test_closing_hides_the_token_and_keeps_the_row(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("Quarry Bank Academy")
        plan = _plan(coach, ident, world["adults"][0])
        minted = _share(coach, ident, plan["id"])
        closed = coach.delete(f"{SHARES}/{minted['token']}")
        assert closed.status_code == 200, closed.text
        assert closed.json()["live"] is False and closed.json()["token"] is None
        again = coach.delete(f"{SHARES}/{minted['token']}")
        assert again.status_code == 409, again.text
        assert _detail(again)["code"] == "share_already_revoked"
        ledger = coach.get(SHARES)
        assert ledger.json()["counts"] == {"opened": 1, "live": 0, "revoked": 1}
        row = ledger.json()["shares"][0]
        assert row["token"] is None, "a closed token is a dead key and is not printed"
        assert row["revoked_at"] is not None

    def test_somebody_elses_link_is_not_this_accounts_to_close(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Slate Yard Academy")
        minted = _share(owner, ident, _plan(owner, ident, world["adults"][0])["id"])
        other = _account("Other Sharer")
        refused = other.delete(f"{SHARES}/{minted['token']}")
        assert refused.status_code == 404, refused.text
        assert _detail(refused)["code"] == "no_such_share"
        assert other.get(SHARES).json()["counts"]["opened"] == 0
        closed = owner.delete(f"{SHARES}/{minted['token']}")
        assert closed.status_code == 200, closed.text

    def test_the_ledger_survives_a_membership_ending(self, world: dict[str, Any]) -> None:
        owner, ident = _tenant("Weighbridge Academy")
        guest = _joined(owner, ident, "coach", "Departing Coach")
        _sheet(owner, ident, world["adults"][0])
        plan = _plan(guest, ident, world["adults"][0])
        minted = _share(guest, ident, plan["id"])
        assert owner.delete(f"{CLUB}/{ident}/members/{_email_of(guest)}").status_code in (200, 204), "a member that left is removed by email"
        ledger = guest.get(SHARES)
        assert ledger.status_code == 200, ledger.text
        assert ledger.json()["counts"]["live"] == 1, "the link is the account's, so it outlives the membership that minted it"
        assert guest.delete(f"{SHARES}/{minted['token']}").status_code == 200


class TestTheWriteTellsTheCache:
    """The page is recomputed per request, but the response cache could still hand out a minute-old answer.

    These checks hold the other half of the live-read promise: every plan write drops the cached anonymous
    answer of each open link over that plan, and leaves a sibling plan's answer alone.
    """

    def test_each_plan_write_retires_the_cached_public_answer(self, world: dict[str, Any], session: Session) -> None:
        coach, ident = _tenant("Signal Box Academy")
        plan = _plan(coach, ident, world["adults"][0])
        sibling = _plan(coach, ident, world["adults"][1])
        path = f"{ACADEMY}/shared/{_share(coach, ident, plan['id'])['token']}"
        sibling_path = f"{ACADEMY}/shared/{_share(coach, ident, sibling['id'])['token']}"
        clip = _clip_of(coach, session)
        writes = (
            ("PATCH", f"{ACADEMY}/{ident}/plans/{plan['id']}", {"focus": ["pressing"]}),
            ("POST", f"{ACADEMY}/{ident}/plans/{plan['id']}/assessments", {"assessed_on": "2026-10-06", "ratings": FULL_RATINGS}),
            ("POST", f"{ACADEMY}/{ident}/plans/{plan['id']}/feedback", {"message": "a note for the family", "shared_with_guardian": True}),
            ("POST", f"{ACADEMY}/{ident}/plans/{plan['id']}/evidence", {"clip": clip, "t_start": 0.0, "t_end": 5.0}),
        )
        sibling_key = _warm(sibling_path)
        evidence_id = ""
        for method, url, body in writes:
            key = _warm(path)
            response = coach.request(method, url, json=body)
            assert response.status_code == 200, response.text
            assert _response_cache.get(key) is None, f"{method} {url} left a stale public answer behind"
            assert _response_cache.get(sibling_key) is not None, "a write over one plan must not sweep another plan's page"
            if url.endswith("/evidence"):
                evidence_id = str(response.json()["evidence"]["id"])
        key = _warm(path)
        removed = coach.delete(f"{ACADEMY}/{ident}/plans/{plan['id']}/evidence/{evidence_id}")
        assert removed.status_code == 200, removed.text
        assert _response_cache.get(key) is None, "an un-cited clip changes the public counts, so its answer goes too"
        _response_cache.drop_public_path(sibling_path)

    def test_erasing_the_plan_retires_the_answer_the_rows_take_with_them(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("Coal Drop Academy")
        plan = _plan(coach, ident, world["adults"][0])
        minted = _share(coach, ident, plan["id"])
        path = f"{ACADEMY}/shared/{minted['token']}"
        key = _warm(path)
        erased = coach.delete(f"{ACADEMY}/{ident}/plans/{plan['id']}?confirm=true")
        assert erased.status_code == 200, erased.text
        assert _response_cache.get(key) is None, "the link dies with the plan, so its cached answer must die too"
        with TestClient(app) as stranger:
            public = stranger.get(path)
        assert public.status_code == 404, public.text
        assert _detail(public)["code"] == "no_such_share", "the share row cascaded away with the plan it named"

    def test_erasing_a_childs_rows_retires_every_plan_answer(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("Ash Grove Academy")
        plan = _plan(coach, ident, world["adults"][1])
        path = f"{ACADEMY}/shared/{_share(coach, ident, plan['id'])['token']}"
        key = _warm(path)
        erased = coach.delete(f"{ACADEMY}/{ident}/players/{world['adults'][1]}/data?confirm=true")
        assert erased.status_code == 200, erased.text
        assert _response_cache.get(key) is None, "the rows behind the page are gone, so its cached answer must go first"
        with TestClient(app) as stranger:
            assert stranger.get(path).status_code == 404, "a link whose subject was erased answers as a dead link"


class TestTheSubjectAges:
    def test_a_plan_one_tenant_no_longer_writes_says_the_subject_is_gone(self, world: dict[str, Any], session: Session) -> None:
        owner, ident = _tenant("Tram Shed Academy")
        plan = _plan(owner, ident, world["adults"][0])
        minted = _share(owner, ident, plan["id"])
        elsewhere = _account("Second Tenant Owner")
        other = elsewhere.post(CLUB, json={"name": "Tram Shed Second Side", "kind": "academy", "country": "en"})
        assert other.status_code == 200, other.text
        other_org = str(other.json()["organization"]["slug"])
        row = session.scalar(select(AcademyPlanShare).where(AcademyPlanShare.share_token == str(minted["token"])))
        assert row is not None
        row.organization_id = str(session.scalar(select(Organization.id).where(Organization.slug == other_org)))
        session.commit()
        with TestClient(app) as stranger:
            public = stranger.get(f"{ACADEMY}/shared/{minted['token']}")
        assert public.status_code == 404, public.text
        detail = _detail(public)
        assert detail["code"] == "share_subject_gone" and detail["plan"] == plan["id"]

    def test_closing_a_link_retires_the_public_answer_the_cache_still_holds(self, world: dict[str, Any]) -> None:
        coach, ident = _tenant("Rope Walk Academy")
        minted = _share(coach, ident, _plan(coach, ident, world["adults"][0])["id"])
        token = str(minted["token"])
        path = f"{ACADEMY}/shared/{token}"
        key = response_cache_key(path, "")
        _response_cache.set(key, {"body": "{}", "status_code": 200, "headers": [], "media_type": "application/json"})
        assert _response_cache.get(key) is not None, "the fixture has to start warm"
        closed = coach.delete(f"{SHARES}/{token}")
        assert _response_cache.get(key) is None, "closing the link must retire the anonymous answer the cache holds"
        assert _response_cache.drop_public_path(path) == 0, "and there must be nothing left to sweep"
        assert closed.status_code == 200, closed.text
        with TestClient(app) as stranger:
            public = stranger.get(path)
        assert public.status_code == 404, public.text
