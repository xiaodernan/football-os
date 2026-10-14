"""M6 item 10 open item: cross-career and league-wide aggregates over sim_events.

These tests verify the new aggregate endpoints that span multiple careers.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import CareerAppearance, RealPlayer, Team, User
from app.services.simulation import career as career_service
from app.services.world import sync_world

API = "/api/v1/simulation/aggregates"
BUDGET = 2_000_000


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """Seed the world and return a few teams for simulations."""
    session = SessionLocal()
    try:
        result = sync_world(session)
        assert result.ok, result.errors[:5]
        teams = list(session.scalars(select(Team).order_by(Team.name).limit(4)).all())
        for team in teams:
            _ = team.competition
        session.close()
        return {"home": teams[0], "away": teams[1], "spare": teams[2]}
    finally:
        session.close()


def _career_slugs(session: Session) -> set[str]:
    """Every slug the aggregate door's own resolution would find."""
    return {str(row) for row in session.scalars(select(CareerAppearance.player_slug).distinct()).all()}


def _slug_with_no_season(session: Session) -> str:
    """A player the world serves who has never appeared in a played round.

    Defined by the query the door uses rather than by a hand-picked slug, so the case cannot quietly
    stop testing anything when the world grows appearances.
    """
    played = _career_slugs(session)
    for slug in session.scalars(select(RealPlayer.slug).order_by(RealPlayer.slug)):
        if str(slug) not in played:
            return str(slug)
    raise AssertionError("every world player already has an appearance row: the career-less ledger has no subject")


@pytest.fixture(scope="module")
def season() -> Iterator[dict[str, Any]]:
    """One real season, played through the engine, so the door has an appearance row to find.

    This is the path §20 traces — `create_career` then `play_round` — and not a hand-written row: an
    appearance with no fixture behind it is a state the application cannot produce, and a ledger read
    against it would prove nothing about a ledger produced by play.
    """
    session = SessionLocal()
    try:
        assert sync_world(session).ok
        club = session.scalars(select(Team).where(Team.competition_id.is_not(None)).order_by(Team.overall, Team.slug).limit(1)).one()
        owner = User(
            id=new_public_id("usr"),
            email=f"agg-{club.slug[:8]}@example.test",
            password_hash=hash_password("aggregate-season-test"),
            display_name="Aggregate Owner",
            role="player",
        )
        session.add(owner)
        session.commit()
        career = career_service.create_career(
            session,
            owner_id=owner.id,
            club=career_service.resolve_club(session, club.id),
            manager_name="Aggregate Manager",
            philosophy="balanced",
            system_slug="",
            budget=BUDGET,
            objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
            season="2026",
        )
        career_service.play_round(session, career)
        row = session.scalars(
            select(CareerAppearance).where(CareerAppearance.career_id == career.id).order_by(CareerAppearance.player_slug)
        ).first()
        assert row is not None, "a played round must leave a trace for the door to find"
        data: dict[str, Any] = {"player_slug": str(row.player_slug), "career_id": career.id, "club_id": club.id}
        session.close()
        yield data
    finally:
        session.close()


class TestSimulationAggregates:
    """M6 item 10: cross-career and league-wide aggregates."""

    def test_league_ledger_requires_valid_competition(self, client) -> None:
        r = client.get(f"{API}/league/non-existent-slug")
        assert r.status_code == 404

    def test_league_ledger_returns_structured_data(self, client, world) -> None:
        comp_slug = world["home"].competition.slug
        r = client.get(f"{API}/league/{comp_slug}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["competition"]["slug"] == comp_slug
        assert "players" in body
        assert "totals" in body
        assert "fixtures_played" in body
        assert "consistency" in body
        assert body["source"] in ("sim_events rows", "no traced fixture")

    def test_player_aggregate_requires_valid_player(self, client) -> None:
        """The refusal is about the player, not about their season: no world row, no ledger."""
        r = client.get(f"{API}/player/non-existent-slug")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "not_found"

    def test_player_aggregate_answers_zeros_for_a_world_player_with_no_season(self, client, world) -> None:
        """A player the world serves is not a 404 for having played nobody's season.

        The sibling door above promises this behaviour in prose — the index page says a competition
        with no events "still answers … rather than pretending the season never happened" — and the
        player door used to refuse 278 of the world's 300 players instead.
        """
        session = SessionLocal()
        try:
            slug = _slug_with_no_season(session)
        finally:
            session.close()
        r = client.get(f"{API}/player/{slug}")
        assert r.status_code == 200, f"the world has {slug} and the ledger refused to say so: {r.status_code} {r.text}"
        body = r.json()
        assert body["player"]["slug"] == slug
        assert body["careers"] == []
        assert body["fixtures_played"] == 0
        assert body["fixtures_traced"] == 0
        assert body["totals"]["events"] == 0 and body["totals"]["goals"] == 0
        assert body["by_type"] == {}
        assert body["source"] == "no traced fixture"
        assert "sum over no rows" in body["consistency"], body["consistency"]
        assert slug in body["career_notice"], "the empty ledger has to say why it is empty"

    def test_player_aggregate_names_the_world_player_when_no_season_says(self, client, world) -> None:
        """With no appearance row to copy from, the name and position come from `real_players`."""
        session = SessionLocal()
        try:
            slug = _slug_with_no_season(session)
            player = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
            assert player is not None, "the career-less slug this case asks about is not a world player"
            name, position = str(player.name), str(player.position)
        finally:
            session.close()
        body = client.get(f"{API}/player/{slug}").json()
        assert body["player"]["name"] == name, "a ledger that prints a slug where the world prints a name disagrees with the world"
        assert body["player"]["position"] == position

    def test_player_aggregate_notice_is_blank_once_a_career_has_played(self, client, season) -> None:
        """The sole-witness for the other branch: a played season leaves no notice behind.

        The career set is read from `career_appearances` rather than assumed to be this fixture's own,
        because the suite shares one database: other modules play rounds whose squads contain the same
        world player, and a door that sums every career naming the slug is correct to list them all.
        """
        r = client.get(f"{API}/player/{season['player_slug']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["career_notice"] == "", body["career_notice"]
        session = SessionLocal()
        try:
            traced = {str(row) for row in session.scalars(
                select(CareerAppearance.career_id).where(CareerAppearance.player_slug == season["player_slug"]).distinct()
            ).all()}
        finally:
            session.close()
        assert season["career_id"] in traced, "the round this fixture played left no appearance row naming the player"
        assert {str(c["id"]) for c in body["careers"]} == traced, (
            "the door's career list is exactly the set of careers with an appearance row naming this slug; "
            f"door {sorted(str(c['id']) for c in body['careers'])} vs rows {sorted(traced)}"
        )
        assert body["fixtures_played"] >= 1
        assert all(row["slug"] == season["player_slug"] for row in body["players"]), "the table is cut to the player the door was asked about"

    def test_a_player_the_world_serves_is_never_refused_a_ledger(self, client, world) -> None:
        """The two doors may not disagree about whether a player exists.

        Read as a pair on purpose: this is the agreement the walk's stopping point broke, over the
        whole 20-player sample the live read used rather than one hand-picked slug.
        """
        session = SessionLocal()
        try:
            slugs = [str(slug) for slug in session.scalars(select(RealPlayer.slug).order_by(RealPlayer.slug).limit(20)).all()]
        finally:
            session.close()
        assert slugs, "the world has no players, so this agreement test has no population"
        disagreements: list[str] = []
        for slug in slugs:
            served = client.get(f"/api/v1/world/players/{slug}").status_code
            ledger = client.get(f"{API}/player/{slug}").status_code
            if served == 200 and ledger == 404:
                disagreements.append(slug)
        assert not disagreements, f"the world serves these at 200 while the ledger refuses them: {disagreements}"
        assert len(slugs) == 20, f"the sample was smaller than the claim: {len(slugs)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
