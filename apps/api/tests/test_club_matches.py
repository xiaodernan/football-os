"""§39's Matches: a tenant's fixture list, played through the engine, with its eleven recorded.

DRAFT — parked outside `tests/` while a full test leg runs on this tree; move to
`apps/api/tests/test_club_matches.py` together with the service module, and treat every shape asserted here as
a claim to be checked by the run rather than by reading it.

The rules this file holds:

* a fixture is an arrangement, not a result: the scoreline, the timeline and every counted figure live in
  `sim_matches` / `sim_events`, and this tier stores none of them;
* a tenant's side is its own sheet, not the world club it is bound to — the overlay removes the base squad and
  adds the named players, so a match played by a tenant's eleven cannot silently be a match played by the
  generator's squad;
* a fixture may be played once, and the refusal prints the answer that already exists;
* the appearance rows are written only when the eleven rebuilt from the tenant's rows matches the eleven the
  stored report names;
* erasing a fixture takes its appearance rows with it and leaves the engine's match row standing;
* a role the matrix does not give a match right is answered 403, and a foreign tenant is answered 404.

Cases deliberately not drafted here: the `fixture_limit` ceiling, because proving it means arranging two hundred
fixtures and the cap is already held from both sides by the count the listing prints. Everything else the earlier
note called un-draftable — the cannot-field figures, the capabilities round-trip, the minor's gate — is below,
written against the module rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1 import club as club_router
from app.core.db import SessionLocal
from app.main import app
from app.models import RealPlayer, SimulationMatch, Team, utc_today
from app.services.club import academy as edu
from app.services.club import matches as mat
from tests.test_club_academy import _account, _detail, _grant, _joined, _opened, _sheet, _team, _validation, world, world_child  # noqa: F401

CLUB = "/api/v1/club"
CAPABILITIES = f"{CLUB}/capabilities"
_ANSWERS = club_router._ANSWERS

# The app's own day, not the host's: the door judges `scheduled_on` against `utc_today()`, and a test that read
# `date.today()` disagrees with the code under test for the hours a local-ahead host sits behind UTC.
YESTERDAY = (utc_today() - timedelta(days=1)).isoformat()
TOMORROW = (utc_today() + timedelta(days=1)).isoformat()


@pytest.fixture()
def db(world: dict[str, Any]) -> Iterator[Session]:  # noqa: F811 — pytest requesting §40's seeded-world fixture
    """One session per test, over the world the academy file seeded."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _adults() -> list[str]:
    from tests.test_club_academy import _adults as shared

    return shared()


def _players_with_keeper(count: int = 11) -> list[str]:
    """`count` adults including at least one goalkeeper, by slug, from the shared world.

    Adults on purpose: the sheet this builds feeds a door that gates every minor behind a consent row, and an
    alphabetical pick would trip that gate for reasons that have nothing to do with a fixture. §41's attendance
    tests make the same choice for the same reason, and one case below names a child deliberately.
    """
    session = SessionLocal()
    try:
        pool = _adults()
        keepers = [str(row) for row in session.scalars(select(RealPlayer.slug).where(RealPlayer.position == "GK", RealPlayer.age >= 20).order_by(RealPlayer.slug)).all()]
        others = [slug for slug in pool if slug not in set(keepers)]
    finally:
        session.close()
    assert keepers and len(others) >= count - 1, "the world has to hold an eleven of adults and a keeper among them"
    return [keepers[0], *others[: count - 1]]


def _tenant(name: str) -> tuple[TestClient, str]:
    owner = _account(f"Matches Owner {name}")
    return owner, str(_opened(owner, name, kind="club", country="en")["organization"]["slug"])


def _bind(owner: TestClient, ident: str, name: str, world_team: str, *slugs: str) -> dict[str, Any]:
    """A tenant's team, placed in the world's ladder, its sheet filled from the names given."""
    response = owner.post(f"{CLUB}/{ident}/teams", json={"name": name, "age_group": "open", "stage": "senior", "world_team": world_team})
    assert response.status_code == 200, response.text
    team = response.json()["team"]
    assert (team.get("world_team") or {}).get("slug") == world_team, "the binding the door accepted has to be the one it prints"
    _sheet(owner, ident, team["name"], *slugs)
    return team


def _arranged(owner: TestClient, ident: str, body: dict[str, Any]) -> dict[str, Any]:
    response = owner.post(f"{CLUB}/{ident}/fixtures", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _played(owner: TestClient, ident: str, fixture: str, body: dict[str, Any] | None = None) -> Any:
    return owner.post(f"{CLUB}/{ident}/fixtures/{fixture}/play", json=body or {})


@pytest.fixture()
def side(db: Session) -> dict[str, Any]:
    """Two world clubs with squads apiece, and an eleven that belongs to neither of them."""
    pools = dict(db.execute(select(RealPlayer.team_id, func.count()).group_by(RealPlayer.team_id)).all())
    playable = [row for row in db.execute(select(Team.id, Team.slug, Team.name).order_by(Team.slug)).all() if pools.get(row[0], 0) >= 11]
    assert len(playable) >= 2, "the world has to hold two clubs a tenant can be placed in and against"
    home, away = playable[0], playable[1]
    base = [str(row) for row in db.scalars(select(RealPlayer.slug).where(RealPlayer.team_id == home[0]).order_by(RealPlayer.slug)).all()]
    return {
        "world_team": str(home[1]),
        "base": base,
        "opponent_slug": str(away[1]),
        "opponent_name": str(away[2]),
        "eleven": _players_with_keeper(11),
    }


class TestArranging:
    def test_a_fixture_names_its_side_the_date_and_an_opponent(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Riverside Matchday")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        answer = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "competition": "County Cup", "note": ""})
        row = answer["fixture"]
        assert row["team"]["name"] == "First Team"
        assert row["status"] == "scheduled"
        assert (row["opponent"] or {}).get("slug") == side["opponent_slug"]
        # The engine's numbers cannot be on a fixture that has not been played.
        assert row["match"] is None and row["appearances"] == 0

    def test_a_date_that_has_not_happened_is_refused_not_accepted_as_a_plan(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Tomorrow Club")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": TOMORROW})
        assert refused.status_code == 422
        detail = _detail(refused)
        assert detail["code"] == "date_in_future"
        assert detail["scheduled_on"] == TOMORROW
        assert detail["today"] == utc_today().isoformat()

    def test_an_opponent_not_in_the_ladder_names_what_was_sent(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("No Such Cup")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": "united-of-nowhere", "scheduled_on": YESTERDAY})
        # 404, not the 422 the draft expected: `no_such_world_club` is §39's code and the team door registers
        # it as an absence, so the fixtures door cannot answer the same sentence a second way. `assemble()`
        # raised at import until the claim was dropped.
        assert refused.status_code == 404
        detail = _detail(refused)
        assert detail["code"] == "no_such_world_club"
        assert detail["world_team"] == "united-of-nowhere"

    def test_a_team_nobody_placed_in_the_world_cannot_be_played(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Unbound Athletic")
        team = _team(owner, ident, "Reserves")  # §39's team door allows a sheet with no world binding
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        played = _played(owner, ident, arranged["fixture"]["id"])
        assert played.status_code == 422
        detail = _detail(played)
        assert detail["code"] == "no_world_side"
        assert detail["team"] == "Reserves"
        # Arranging stayed legal: a fixture is a promise, and the missing binding is about playing it.
        assert arranged["fixture"]["status"] == "scheduled"

    def test_one_side_cannot_be_at_home_twice_on_one_date(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Double Home")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        body = {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "side": "home"}
        _arranged(owner, ident, body)
        again = owner.post(f"{CLUB}/{ident}/fixtures", json=body)
        assert again.status_code == 409
        detail = _detail(again)
        assert detail["code"] == "side_taken"
        assert detail["side"] == "home" and detail["scheduled_on"] == YESTERDAY and detail["team"] == "First Team"
        # The other side of the same tie, on the same date, is a different fixture and stays legal.
        assert owner.post(f"{CLUB}/{ident}/fixtures", json={**body, "side": "away"}).status_code == 200

    def test_a_side_is_one_of_two_words_and_the_answer_says_which(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Third Side")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "side": "neutral"})
        assert refused.status_code == 422
        detail = _detail(refused)
        assert detail["code"] == "side_shape"
        assert detail["sides"] == list(mat.SIDES)
        assert detail["sent"] == "neutral"

    def test_an_unknown_field_is_refused_before_the_service_reads_it(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Extra Field")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "medical_note": "a knee"})
        assert refused.status_code == 422
        assert "medical_note" in str(_validation(refused))


class TestPlaying:
    def test_playing_reads_the_result_through_the_engines_row(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Played Once")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        played = _played(owner, ident, arranged["fixture"]["id"], {"seed": 7})
        assert played.status_code == 200, played.text
        answer = played.json()
        row = answer["fixture"]
        assert row["status"] == "played"
        assert row["match"]["slug"] == answer["match_slug"]
        assert row["match"]["digest"] == answer["digest"]
        assert row["appearances"] == 11
        # Nothing about the scoreline is a column of this tier's: the fixture row carries a pointer and a digest.
        for forbidden in ("home_goals", "away_goals", "score", "possession"):
            assert forbidden not in row, f"`{forbidden}` would be a stored copy of a figure the engine owns"

    def test_the_eleven_that_played_is_the_tenants_sheet(self, side: dict[str, Any], db: Session) -> None:
        owner, ident = _tenant("Own Eleven")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        played = _played(owner, ident, arranged["fixture"]["id"], {"seed": 3})
        assert played.status_code == 200, played.text
        named = set(side["eleven"])
        base = set(side["base"])
        assert named.isdisjoint(base), "the fixture's own premise: the tenant's players are not this club's world squad"
        rows = list(
            db.execute(
                select(mat.ClubMatchAppearance.player_slug, mat.ClubMatchAppearance.position)
                .where(mat.ClubMatchAppearance.fixture_id == arranged["fixture"]["id"])
                .order_by(mat.ClubMatchAppearance.player_slug)
            ).all()
        )
        assert len(rows) == 11
        assert {row[0] for row in rows} <= named, "an appearance row for a player nobody on the tenant's sheet named"
        # The keeper is judged from the door's own printed figure, not from the engine's position label: the
        # sheet holds exactly one adult goalkeeper and `_can_field` counts the player rows, so the arithmetic is
        # this tier's claim to test. What the engine calls a position in its report is the sim tier's vocabulary.
        assert played.json()["fielding"]["keepers"] == 1 and played.json()["fielding"]["ok"] is True
        assert {row[1] for row in rows} & {"GK", "Goalkeeper"}, "the eleven that played had no keeper in it at all"

    def test_a_fixture_answers_once_and_the_refusal_prints_the_first_answer(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Twice Played")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        first = _played(owner, ident, arranged["fixture"]["id"], {"seed": 11})
        assert first.status_code == 200, first.text
        again = _played(owner, ident, arranged["fixture"]["id"], {"seed": 12})
        assert again.status_code == 409
        detail = _detail(again)
        assert detail["code"] == "fixture_played"
        assert detail["match_slug"] == first.json()["match_slug"]

    def test_a_seed_the_caller_chose_replays_identically_in_another_tenant(self, side: dict[str, Any]) -> None:
        digests = []
        for label in ("Seed Left", "Seed Right"):
            owner, ident = _tenant(label)
            team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
            arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
            played = _played(owner, ident, arranged["fixture"]["id"], {"seed": 2026})
            assert played.status_code == 200, played.text
            digests.append(played.json()["digest"])
        assert digests[0] == digests[1], "the engine's determinism has to survive a change of tenant"


class TestErasing:
    def test_erasing_takes_the_appearances_and_leaves_the_engine_row(self, side: dict[str, Any], db: Session) -> None:
        owner, ident = _tenant("Erased Fixture")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        played = _played(owner, ident, arranged["fixture"]["id"], {"seed": 5})
        assert played.status_code == 200, played.text
        slug = played.json()["match_slug"]
        ident_row = arranged["fixture"]["id"]
        gone = owner.delete(f"{CLUB}/{ident}/fixtures/{ident_row}")
        assert gone.status_code == 200, gone.text
        assert owner.get(f"{CLUB}/{ident}/fixtures/{ident_row}").status_code == 404
        assert db.scalar(select(func.count()).select_from(SimulationMatch).where(SimulationMatch.slug == slug)) == 1, "the match the engine played outlives the tenant's record of it"
        assert db.scalar(select(func.count()).select_from(mat.ClubMatchAppearance).where(mat.ClubMatchAppearance.fixture_id == ident_row)) == 0

    def test_another_tenant_cannot_read_a_fixture_it_was_not_arranged_in(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Owner A Fixtures")
        other, other_ident = _tenant("Owner B Fixtures")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        stolen = other.get(f"{CLUB}/{other_ident}/fixtures/{arranged['fixture']['id']}")
        assert stolen.status_code == 404
        detail = _detail(stolen)
        assert detail["code"] == "no_such_fixture"
        assert detail["fixture"] == arranged["fixture"]["id"], "the caller's own string comes back, unresolved"


class TestRoles:
    def test_a_role_the_matrix_gives_no_match_right_is_answered_403(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Scout Watch")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        for role in ("scout", "parent"):
            guest = _joined(owner, ident, role, f"{role.title()} Of Nobody")
            refused = guest.get(f"{CLUB}/{ident}/fixtures")
            assert refused.status_code == 403, f"{role} holds no match right and should be refused before the rows are read"
            assert _detail(refused)["code"] == "insufficient_role"

    def test_an_analyst_reads_the_list_and_cannot_arrange_it(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Analyst Desk")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        guest = _joined(owner, ident, "analyst", "Match Analyst")
        listed = guest.get(f"{CLUB}/{ident}/fixtures")
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["role"] == "analyst"
        assert guest.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY}).status_code == 403


class TestFielding:
    """The four figures that decide whether a side can be played, and the refusals that print them."""

    def test_a_side_too_small_to_field_is_refused_with_the_counts_that_decided_it(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Five A Side")
        team = _bind(owner, ident, "Colts", side["world_team"], *side["eleven"][:5])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        # Arranging is not fielding: the promise stands, and the answer says in figures what it would take.
        assert arranged["fielding"]["ok"] is False
        assert arranged["fielding"]["players"] == 5 and arranged["fielding"]["needs_players"] == mat.CAPS["needs_players"]
        played = _played(owner, ident, arranged["fixture"]["id"])
        assert played.status_code == 422, played.text
        detail = _detail(played)
        assert detail["code"] == "can_not_field"
        assert detail["players"] == 5 and detail["needs_players"] == 11 and detail["needs_keepers"] == 1
        assert detail["rule"].startswith("a side is fielded only while"), "the tier's own sentence, not the career's"

    def test_a_name_that_is_not_on_the_sheet_cannot_be_walked_onto_a_fixture(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Crash Party")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        outsider = _adults()[-1]
        assert outsider not in side["eleven"], "the point of the case: a player the world holds and this sheet does not"
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "named": [outsider]})
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "not_on_sheet" and detail["player"] == outsider
        assert detail["on_sheet"] == len(side["eleven"])

    def test_naming_more_players_than_the_cap_is_refused_with_both_figures(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Whole Village")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        too_many = _adults()[: mat.NAMED_MAX + 1]
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "named": too_many})
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "named_limit"
        assert detail["named"] == mat.NAMED_MAX + 1 and detail["max"] == mat.NAMED_MAX

    def test_a_block_length_the_engine_does_not_play_is_refused_with_its_choices(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Forty Five Minutes")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        arranged = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        played = _played(owner, ident, arranged["fixture"]["id"], {"minutes": 45})
        assert played.status_code == 422, played.text
        detail = _detail(played)
        # The club tier does not draw its own band around the engine's input: the choices printed here are the
        # choices `/simulate/options` publishes, so a caller can play what this door accepts, no more.
        assert detail["code"] == "minutes_choice" and detail["minutes"] == 45
        assert detail["choices"] == list(mat.CAPS["minute_choices"])

    def test_a_tenant_cannot_be_arranged_against_the_club_it_is_placed_as(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Mirror Game")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["world_team"], "scheduled_on": YESTERDAY})
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "opponent_is_own_club" and detail["team"] == "First Team"
        assert detail["world_team"] == side["world_team"], "the answer names the binding that made this self-play"


class TestTheChildsGate:
    """A fixture about a child sits behind the same yes that opens their plan — §40's scope, not a fifth word."""

    def test_a_minor_on_the_default_selection_stops_the_arrangement_until_a_guardian_answers(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Consented Matchday")
        adults = side["eleven"]
        team = _bind(owner, ident, "First Team", side["world_team"], *adults)
        child = world_child(ident, owner, team["name"], 0)
        # Empty `named` means the whole sheet, and the sheet now holds a child: the default selection is refused
        # rather than quietly recording a minor who has no consent on file.
        refused = owner.post(f"{CLUB}/{ident}/fixtures", json={"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY})
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "consent_required" and detail["scope"] == "plan"
        assert detail["threshold"] == edu.MINOR_AGE
        # Naming only the adults is a selection with no minor in it, and it needs no consent at all.
        held = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "named": adults})
        assert [row["slug"] for row in held["fixture"]["named"]] == adults
        guardian = _joined(owner, ident, "parent", "Guardian Of The Match Child")
        assert guardian.get(f"{CLUB}/{ident}/fixtures").status_code == 403, "a parent holds no match right; the consent opens the row, not the door"
        _grant(guardian, ident, child)
        after = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "side": "away"})
        assert any(row["slug"] == child for row in after["fixture"]["named"]), "with the yes on file the child is on the arrangement"
        assert any(row["is_minor"] for row in after["fixture"]["named"])


class TestTheCalendar:
    def test_every_figure_the_listing_prints_is_counted_from_the_rows_it_names(self, side: dict[str, Any]) -> None:
        owner, ident = _tenant("Fixture Book")
        team = _bind(owner, ident, "First Team", side["world_team"], *side["eleven"])
        reserves = _team(owner, ident, "Reserves")
        _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": YESTERDAY, "competition": "County Cup"})
        played = _arranged(owner, ident, {"team": team["name"], "opponent": side["opponent_slug"], "scheduled_on": (utc_today() - timedelta(days=8)).isoformat(), "side": "away"})
        _played(owner, ident, played["fixture"]["id"], {"seed": 99})
        _arranged(owner, ident, {"team": reserves["name"], "opponent": side["opponent_slug"], "scheduled_on": (utc_today() - timedelta(days=15)).isoformat()})
        listed = owner.get(f"{CLUB}/{ident}/fixtures")
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 3 and body["played"] == 1 and body["unplayed"] == 2
        assert body["appearances"] == 11, "the played fixture's eleven, summed over the rows on this page"
        assert body["by_competition"] == {"County Cup": 1, "uncupplied": 2}
        assert body["fixtures_held"] == 3 and body["limit"] == mat.MAX_FIXTURES_PER_ORGANIZATION
        assert body["role"] == "owner" and body["read_through"] == "match.read"
        assert set(body["formulas"]) == set(mat.FORMULAS), "the page prints the tier's formulas, not a paraphrase of them"
        # One filter per coordinate, and each answer is a subset of the same rows.
        assert owner.get(f"{CLUB}/{ident}/fixtures?team=First+Team").json()["total"] == 2
        assert owner.get(f"{CLUB}/{ident}/fixtures?status=played").json()["total"] == 1
        assert owner.get(f"{CLUB}/{ident}/fixtures?since={utc_today() - timedelta(days=9)}").json()["total"] == 2


class TestThePublishedRulebook:
    def test_the_capabilities_door_publishes_the_fixture_tiers_own_figures(self) -> None:
        body = TestClient(app).get(CAPABILITIES).json()
        assert body["fixture_caps"] == dict(mat.CAPS)
        published = body["fixture_refusals"]
        assert set(mat.PUBLISHED) <= set(published) and set(mat.REFUSALS) <= set(_ANSWERS)
        # One code, one answer, at this door too — the table §51 assembled is the only thing that decides.
        assert published["no_such_fixture"] == 404 and published["fixture_played"] == 409 and published["side_shape"] == 422
        assert "insufficient_role" not in mat.FORBIDDEN_CODES and not mat.FORBIDDEN_CODES
        assert body["fixture_limitation"].startswith("a fixture is arranged against a club")
        assert any("no fatigue" in line for line in [body["fixture_limitation"]]), "the tier says out loud what a club fixture does not carry"

    def test_the_tier_no_longer_claims_that_no_match_exists_here(self) -> None:
        body = TestClient(app).get(CAPABILITIES).json()
        for line in body["limitations"]:
            assert not line.startswith(
                "no match report or message exists in this tier"
            ), "§39's Matches row has landed, so the rulebook's own sentence about it is now a lie: rewrite it, do not delete it"
