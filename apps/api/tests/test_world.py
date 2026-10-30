"""M3 Football World: the plan is deterministic, the sync is idempotent, and every read says demo (spec §65, §80).

Two layers are covered separately on purpose. The pure plan needs no database, so its invariants
(slug safety, gate floors, no score before kick-off) are checked once cheaply; the sync and the HTTP
reads then prove the same world survives a round trip to SQLite or Postgres and reaches a client with
its provenance flags and canonical paths attached.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import quote, unquote

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Competition, NewsArticle, NewsArticleLink, RealMatch, RealPlayer, RealTrainingSession, Team
from app.services.world import search_world, sync_world, web_path, world_counts, world_ready
from app.services.world.builder import TRAINING_RPE, WorldSizes, plan_world
from app.services.world.names import slugify
from app.services.world.plan import WorldPlan, duplicate_keys, world_id
from app.services.world.sync import COLLECTIONS, GATE, plan_problems

SAFE_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
API = "/api/v1/world"


@pytest.fixture(scope="module")
def plan() -> WorldPlan:
    return plan_world(3)


@pytest.fixture(scope="module")
def rebuilt_plan() -> WorldPlan:
    """The same seed built again after clearing the cache — a determinism witness, not a second world."""
    plan_world.cache_clear()
    fresh = plan_world(3)
    plan_world.cache_clear()
    return fresh


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _item(client, path: str):  # type: ignore[no-untyped-def]
    """First row of a list endpoint, which every detail test needs as both a slug and an id."""
    return client.get(f"{API}{path}", params={"page_size": 1}).json()["items"][0]


def _played_leagues(plan: WorldPlan) -> dict[str, set[str]]:
    """Team id -> the league ids it played its completed 2026 fixtures in."""
    league_ids = {world_id("competition", row.natural_key) for row in plan.collections["competitions"] if row.payload["kind"] == "league"}
    played: dict[str, set[str]] = {}
    for row in plan.collections["matches"]:
        payload = row.payload
        if payload["season"] != "2026" or payload["competition_id"] not in league_ids:
            continue
        for team_id in (payload["home_team_id"], payload["away_team_id"]):
            played.setdefault(str(team_id), set()).add(str(payload["competition_id"]))
    return played


def _moved_clubs(plan: WorldPlan) -> list[str]:
    """Clubs whose registered league is not the league their 2026 fixtures were played in."""
    played = _played_leagues(plan)
    moved = []
    for row in plan.collections["teams"]:
        team_id = world_id("team", row.natural_key)
        registered = str(row.payload["competition_id"])
        if played.get(team_id, set()) != {registered}:
            moved.append(row.natural_key)
    return moved


def _stored_table(session, competition_id: str, season: str = "2026") -> list[Team]:  # type: ignore[no-untyped-def]
    """The table recomputed in the test from stored fixtures: points, goal difference, goals for, slug."""
    totals: dict[str, dict[str, int]] = {}
    for match in session.scalars(select(RealMatch).where(RealMatch.competition_id == competition_id, RealMatch.season == season)).all():
        if match.status != "completed" or match.home_goals is None or match.away_goals is None:
            continue
        home = totals.setdefault(match.home_team_id, {"points": 0, "scored": 0, "conceded": 0})
        away = totals.setdefault(match.away_team_id, {"points": 0, "scored": 0, "conceded": 0})
        home["scored"] += match.home_goals
        home["conceded"] += match.away_goals
        away["scored"] += match.away_goals
        away["conceded"] += match.home_goals
        if match.home_goals == match.away_goals:
            home["points"] += 1
            away["points"] += 1
        elif match.home_goals > match.away_goals:
            home["points"] += 3
        else:
            away["points"] += 3
    teams = {team.id: team for team in session.scalars(select(Team).where(Team.id.in_(totals))).all()}
    order = sorted(
        totals,
        key=lambda team_id: (
            -totals[team_id]["points"],
            -(totals[team_id]["scored"] - totals[team_id]["conceded"]),
            -totals[team_id]["scored"],
            teams[team_id].slug,
        ),
    )
    return [teams[team_id] for team_id in order]


class TestPlan:
    def test_same_seed_rebuilds_the_identical_world(self, plan: WorldPlan, rebuilt_plan: WorldPlan) -> None:
        assert plan.fingerprint() == rebuilt_plan.fingerprint()

    def test_a_different_seed_is_a_different_world(self, plan: WorldPlan) -> None:
        assert plan_world(4).fingerprint() != plan.fingerprint()

    def test_plan_clears_the_gate_without_colliding(self, plan: WorldPlan) -> None:
        assert plan_problems(plan) == []

    def test_default_sizes_are_the_documented_gate(self, plan: WorldPlan) -> None:
        sizes = WorldSizes()
        assert sizes.tiers == (2, 2), "two top-flight leagues over two second-division leagues"
        assert (sizes.teams, sizes.squad_size, sizes.competitions) == (32, 15, 12)
        assert sizes.played_matches >= 100
        counts = plan.counts()
        assert counts["players"] == sizes.players == 480
        assert counts["competitions"] == sizes.competitions
        assert counts["matches"] == sizes.played_matches + sizes.scheduled_matches
        assert counts["matches"] >= 100

    def test_the_leagues_form_a_two_tier_pyramid(self, plan: WorldPlan) -> None:
        """A second division exists, cups sit outside it, and every league is a full slate."""
        sizes = WorldSizes()
        leagues = [row for row in plan.collections["competitions"] if row.payload["kind"] == "league"]
        assert [row.payload["tier"] for row in leagues] == [1, 1, 2, 2]
        assert [row.payload["tier"] for row in plan.collections["competitions"] if row.payload["kind"] == "cup"] == [0] * sizes.cups
        membership: dict[str, int] = {}
        for row in plan.collections["teams"]:
            key = str(row.payload["competition_id"])
            membership[key] = membership.get(key, 0) + 1
        for league in leagues:
            assert membership[world_id("competition", league.natural_key)] == sizes.teams_per_league

    def test_the_season_boundary_moves_one_club_per_pairing(self, plan: WorldPlan) -> None:
        """Two tier-1/tier-2 pairings, one club down and one up in each, at the default one slot."""
        moved = _moved_clubs(plan)
        assert len(moved) == 4, moved
        played = _played_leagues(plan)
        registered = {world_id("team", row.natural_key): str(row.payload["competition_id"]) for row in plan.collections["teams"]}
        for club in moved:
            team_id = world_id("team", club)
            assert played[team_id], f"{club} was registered somewhere it never played"
            assert registered[team_id] not in played[team_id], f"{club} is registered in the league it already played"

    def test_the_boundary_can_be_switched_off(self) -> None:
        """`movement_slots = 0` leaves every club in the league it played, which is what the switch promises."""
        assert _moved_clubs(plan_world(13, WorldSizes(movement_slots=0))) == []

    def test_next_seasons_fixtures_are_drawn_from_the_new_membership(self, plan: WorldPlan) -> None:
        registered = {world_id("team", row.natural_key): str(row.payload["competition_id"]) for row in plan.collections["teams"]}
        fixtures = [row.payload for row in plan.collections["matches"] if row.payload["season"] == "2027"]
        assert fixtures, "the next season has an opening round on the calendar"
        for fixture in fixtures:
            for team_id in (fixture["home_team_id"], fixture["away_team_id"]):
                assert registered[team_id] == fixture["competition_id"], (
                    f"{fixture['slug']} names {team_id}, which is registered in {registered[team_id]} rather than in {fixture['competition_id']}"
                )

    @pytest.mark.parametrize("collection", ["competitions", "teams", "players", "matches", "articles"])
    def test_public_slugs_are_url_safe(self, plan: WorldPlan, collection: str) -> None:
        keys = [row.natural_key for row in plan.collections[collection]]
        assert all(SAFE_SLUG.match(key) for key in keys), [key for key in keys if not SAFE_SLUG.match(key)][:3]
        assert all(key == slugify(key) and len(key) <= 200 for key in keys)

    def test_article_urls_survive_a_percent_round_trip(self, plan: WorldPlan) -> None:
        assert len(plan.collections["articles"]) >= 500, "the feed clears the spec's 500-article floor"
        for row in plan.collections["articles"]:
            url = web_path("article", row.natural_key)
            assert unquote(quote(url, safe="/")) == url

    def test_no_fixture_has_a_score_before_kickoff(self, plan: WorldPlan) -> None:
        unplayed = [row for row in plan.collections["matches"] if row.payload["status"] != "completed"]
        assert unplayed, "the schedule should contain fixtures that have not been played"
        for row in unplayed:
            assert row.payload["home_goals"] is None and row.payload["away_goals"] is None

    def test_every_row_the_sync_writes_is_marked_synthetic(self, plan: WorldPlan) -> None:
        for collection in COLLECTIONS:
            row = collection.columns_for(plan.collections[collection.name][0])
            assert row["data_origin"] == "synthetic" and row["is_demo_data"] is True

    def test_duplicate_key_detector_is_not_a_no_op(self, plan: WorldPlan) -> None:
        rows = plan.collections["matches"]
        assert duplicate_keys(rows) == []
        assert duplicate_keys([rows[0], rows[0]]) == [rows[0].natural_key]

    def test_training_log_clears_the_last_gate_item_and_quotes_only_the_catalogue(self, plan: WorldPlan) -> None:
        """Spec §65's 100 Training Sessions: demo history, but every field traceable to a row.

        The drills are the project-authored catalogue, the durations and difficulties are copied
        from it, and load is the session-RPE product — so nothing on a session row is invented for
        the page, which is the difference between demo data and a fake measurement.
        """
        from app.services.training_catalog import DRILLS

        rows = plan.collections["training_sessions"]
        assert len(rows) >= GATE["training_sessions"]
        by_slug = {str(drill["slug"]): drill for drill in DRILLS}
        players = {row.natural_key for row in plan.collections["players"]}
        for row in rows:
            payload = row.payload
            drill = by_slug.get(payload["drill_slug"])
            assert drill is not None, f"{payload['drill_slug']} is not in the catalogue"
            assert payload["player_slug"] in players
            assert payload["drill_title"] == drill["title"] and payload["category"] == drill["category"]
            assert payload["difficulty"] == drill["difficulty"]
            assert payload["duration_min"] == drill["duration_min"]
            assert payload["load_units"] == payload["duration_min"] * payload["rpe"]
            assert TRAINING_RPE[0] <= payload["rpe"] <= TRAINING_RPE[1]
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", payload["session_date"]), payload["session_date"]
        assert len({row.natural_key for row in rows}) == len(rows)
        # Spread across the squad rather than one player's diary: the draw is weighted by minutes
        # played, so a floor on distinct players is what tells those two stories apart.
        assert len({row.payload["player_slug"] for row in rows}) >= 40, plan.counts()
        assert len({row.payload["drill_slug"] for row in rows}) >= 10


class TestSync:
    def test_second_sync_changes_nothing(self, session) -> None:  # type: ignore[no-untyped-def]
        first = sync_world(session)
        assert first.ok, first.errors[:5]
        second = sync_world(session)
        assert second.changed == 0, second.summary_line()
        assert second.unchanged == first.rows

    def test_counts_clear_every_gate_floor(self, session) -> None:
        counts = world_counts(session)
        for name, floor in GATE.items():
            assert counts[name] >= floor, f"{name}: {counts[name]} < {floor}"
        assert world_ready(session) is True

    def test_stat_lines_only_reference_players_that_exist(self, session) -> None:
        from app.models import RealPlayerMatchStat

        dangling = session.scalar(select(func.count()).select_from(RealPlayerMatchStat).where(RealPlayerMatchStat.player_id.not_in(select(RealPlayer.id))))
        assert dangling == 0

    def test_world_training_rows_reference_players_that_exist(self, session) -> None:  # type: ignore[no-untyped-def]
        """`drill_slug` is checked against the catalogue in the plan tests; `player_id` is a FK, so
        the round trip through the database is what proves the row still points at a real club member."""
        sync_world(session)
        dangling = session.scalar(select(func.count()).select_from(RealTrainingSession).where(RealTrainingSession.player_id.not_in(select(RealPlayer.id))))
        assert dangling == 0
        assert session.scalar(select(func.count()).select_from(RealTrainingSession)) >= GATE["training_sessions"]

    def test_article_links_never_point_at_a_deleted_article(self, session) -> None:
        orphans = session.scalar(select(func.count()).select_from(NewsArticleLink).where(NewsArticleLink.article_id.not_in(select(NewsArticle.id))))
        assert orphans == 0
        assert session.scalar(select(func.count()).select_from(NewsArticle)) >= GATE["articles"]

    def test_a_squad_and_its_fixtures_agree_with_the_club_row(self, session) -> None:
        team = session.scalars(select(Team).order_by(Team.slug).limit(1)).one()
        squad = session.scalars(select(RealPlayer).where(RealPlayer.team_id == team.id)).all()
        assert len(squad) == team.squad_size == 15
        fixtures = session.scalars(select(RealMatch).where((RealMatch.home_team_id == team.id) | (RealMatch.away_team_id == team.id))).all()
        assert fixtures
        for match in fixtures:
            played = match.status == "completed"
            assert (match.home_goals is not None) is played

    def test_the_league_boundary_is_computed_from_the_stored_table(self, session) -> None:  # type: ignore[no-untyped-def]
        """The relegated club is the last row of the table the fixtures aggregate to, not a seeded pick."""
        top = session.scalars(select(Competition).where(Competition.kind == "league", Competition.tier == 1).order_by(Competition.slug)).first()
        assert top is not None
        table = _stored_table(session, top.id)
        assert len(table) == 8
        bottom, above = table[-1], table[-2]
        assert bottom.competition_id != top.id, f"{bottom.slug} finished last but was not relegated"
        lower = session.get(Competition, bottom.competition_id)
        assert lower is not None and (lower.kind, lower.tier) == ("league", 2)
        assert above.competition_id == top.id, "the club above the bottom did not stay up"
        promoted = [team for team in session.scalars(select(Team).where(Team.competition_id == top.id)).all() if team.id not in {row.id for row in table}]
        assert len(promoted) == 1, (
            f"{len(promoted)} club(s) joined {top.slug} besides the clubs the completed season tabled: "
            + ", ".join(team.slug for team in promoted)
        )
        assert _stored_table(session, lower.id)[0].id == promoted[0].id, "the club that came up was not top of the league below"

    def test_every_club_is_registered_in_exactly_one_league(self, session) -> None:  # type: ignore[no-untyped-def]
        leagues = session.scalars(select(Competition).where(Competition.kind == "league")).all()
        counts = {league.id: 0 for league in leagues}
        for team in session.scalars(select(Team)).all():
            assert team.competition_id in counts, f"{team.slug} is registered outside the pyramid"
            counts[team.competition_id] += 1
        assert sum(counts.values()) == 32 and set(counts.values()) == {8}

    def test_next_seasons_fixtures_name_only_the_new_membership(self, session) -> None:  # type: ignore[no-untyped-def]
        leagues = session.scalars(select(Competition).where(Competition.kind == "league")).all()
        for league in leagues:
            registered = {team.id for team in session.scalars(select(Team).where(Team.competition_id == league.id)).all()}
            fixtures = session.scalars(select(RealMatch).where(RealMatch.competition_id == league.id, RealMatch.season == "2027")).all()
            assert fixtures, league.slug
            named = {match.home_team_id for match in fixtures} | {match.away_team_id for match in fixtures}
            assert named <= registered, (
                f"{league.slug}'s 2027 fixtures name {sorted(named - registered)}, which the league's membership does not hold"
            )


class TestReads:
    """The world is public fiction: readable without an account, never without its labels."""

    def test_status_reports_counts_gate_and_seed(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/status").json()
        assert body["is_demo_data"] is True and body["data_origin"] == "synthetic"
        assert body["counts"]["teams"] >= GATE["teams"] and body["counts"]["articles"] >= GATE["articles"]
        assert body["counts"]["training_sessions"] >= GATE["training_sessions"]
        assert body["gate"] == dict(GATE)
        assert isinstance(body["seed"], int)
        # The cache-key contract: a client keys a cache on (version, seed), so both must be on the wire.
        assert isinstance(body["version"], str) and body["version"], "the world publishes its version for cache keying"
        assert body["disclaimer"]

    @pytest.mark.parametrize("path", ["/competitions", "/teams", "/players", "/matches", "/news"])
    def test_list_endpoints_page_and_carry_paths(self, client, path: str) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}{path}", params={"page_size": 5}).json()
        assert (body["page"], body["page_size"]) == (1, 5)
        assert len(body["items"]) == 5 and body["total"] >= 5 and body["pages"] >= 1
        for item in body["items"]:
            assert SAFE_SLUG.match(item["path"].rsplit("/", 1)[-1]), item["path"]
            assert item.get("is_demo_data", True) is True

    @pytest.mark.parametrize(("path", "key"), [("/teams", "team"), ("/players", "player"), ("/matches", "match"), ("/news", "article")])
    def test_detail_resolves_by_slug_and_by_id(self, client, path: str, key: str) -> None:  # type: ignore[no-untyped-def]
        item = _item(client, path)
        by_slug = client.get(f"{API}{path}/{item['slug']}")
        by_id = client.get(f"{API}{path}/{item['id']}")
        assert by_slug.status_code == 200, by_slug.text
        assert by_id.status_code == 200
        assert by_slug.json()[key]["id"] == item["id"]
        assert by_id.json()[key] == by_slug.json()[key], path
        assert by_slug.json()["is_demo_data"] is True

    def test_league_detail_has_a_table_and_cup_detail_has_entrants(self, client) -> None:  # type: ignore[no-untyped-def]
        listed = client.get(f"{API}/competitions").json()["items"]
        by_kind = {item["kind"]: item for item in listed}
        assert {"league", "cup"} <= set(by_kind), sorted(by_kind)
        assert all(item["team_count"] > 0 for item in listed), f"a listed entry carried no teams: {[item['team_count'] for item in listed]!r}"

        league = client.get(f"{API}/competitions/{by_kind['league']['slug']}").json()
        assert league["competition"]["path"] == web_path("competition", by_kind["league"]["slug"])
        assert league["teams"] and league["standings"]
        assert league["completed"] + league["scheduled"] == len(league["fixtures"])

        cup = client.get(f"{API}/competitions/{by_kind['cup']['slug']}").json()
        assert cup["fixtures"], "a cup with no drawn ties is not a cup"
        assert cup["standings"] == [], "a knockout does not have a league table"
        assert all(fixture["home"] and fixture["away"] for fixture in cup["fixtures"]), cup["fixtures"][0]
        assert {team["id"] for team in cup["teams"]} == {fixture["home"]["id"] for fixture in cup["fixtures"]} | {fixture["away"]["id"] for fixture in cup["fixtures"]}

    def test_the_competitions_list_counts_membership_not_every_club_that_ever_played(self, client) -> None:  # type: ignore[no-untyped-def]
        """A tier-2 league lost one club and gained one at the boundary; its count is still eight."""
        listed = client.get(f"{API}/competitions", params={"page_size": 50}).json()["items"]
        leagues = [item for item in listed if item["kind"] == "league"]
        assert leagues, "the world lists no league, so there is no membership to count"
        wrong = []
        for item in leagues:
            page = client.get(f"{API}/competitions/{item['slug']}").json()
            registered = {team["id"] for team in page["teams"]}
            if item["team_count"] != len(registered):
                wrong.append((item["slug"], item["team_count"], len(registered)))
        assert not wrong, f"the list counts a club that played here last season as a member: {wrong}"

    def _league_pages(self, client):  # type: ignore[no-untyped-def]
        listed = client.get(f"{API}/competitions", params={"page_size": 50}).json()["items"]
        return [client.get(f"{API}/competitions/{item['slug']}").json() for item in listed if item["kind"] == "league"]

    def test_a_league_page_names_the_clubs_that_played_not_just_the_ones_left(self, client) -> None:  # type: ignore[no-untyped-def]
        """A relegated club is still a row of the table it earned, and the direction follows the club."""
        page = next((body for body in self._league_pages(client) if body["movement"]), None)
        assert page is not None, "no league page published its boundary move"
        competition_id = page["competition"]["id"]
        promoted, relegated = page["movement"]["promoted"], page["movement"]["relegated"]
        assert len(promoted) == len(relegated) == 1, page["movement"]

        def tier(slug: str) -> int:
            return client.get(f"{API}/competitions/{slug}").json()["competition"]["tier"]

        errors = []
        for entry in relegated:
            assert entry["from"]["id"] != entry["to"]["id"]
            if tier(entry["to"]["slug"]) <= tier(entry["from"]["slug"]):
                errors.append(("relegated", entry["from"]["name"], entry["to"]["name"]))
        for entry in promoted:
            assert entry["from"]["id"] != entry["to"]["id"]
            if tier(entry["to"]["slug"]) >= tier(entry["from"]["slug"]):
                errors.append(("promoted", entry["from"]["name"], entry["to"]["name"]))
        assert not errors, f"tier 1 is the top flight, so these directions are inverted: {errors}"
        table = {row["team_id"] for row in page["standings"]}
        leaving = next((entry for entry in (*relegated, *promoted) if entry["from"]["id"] == competition_id), None)
        arriving = next((entry for entry in (*relegated, *promoted) if entry["to"]["id"] == competition_id), None)
        assert leaving is not None and arriving is not None, "the page does not show both sides of its boundary"
        assert leaving["team"]["id"] in table, "the club that left this league vanished from the table it earned"
        assert arriving["team"]["id"] not in table
        assert all(row["team"] is not None and row["name"] != "Data unavailable" for row in page["standings"])
        assert {team["id"] for team in page["teams"]} == table
        assert all(fixture["home"] and fixture["away"] for fixture in page["fixtures"]), "a fixture lost a side after the move"

    def test_a_future_season_page_lists_the_membership_registered_for_it(self, client) -> None:  # type: ignore[no-untyped-def]
        """No results to table yet, so the page shows the field registered for the season, not the last one's entrants."""
        page = next((body for body in self._league_pages(client) if body["movement"]), None)
        assert page is not None
        competition_id = page["competition"]["id"]
        entrants = {team["id"] for team in page["teams"]}
        moves = [*page["movement"]["promoted"], *page["movement"]["relegated"]]
        leaving = next(entry for entry in moves if entry["from"]["id"] == competition_id)
        arriving = next(entry for entry in moves if entry["to"]["id"] == competition_id)
        membership = (entrants - {leaving["team"]["id"]}) | {arriving["team"]["id"]}
        slug = page["competition"]["slug"]
        future = client.get(f"{API}/competitions/{slug}", params={"season": "2027"}).json()
        assert future["movement"] is None, "a season with no stored results has no boundary to publish"
        assert {team["id"] for team in future["teams"]} == membership
        named = {fixture["home"]["id"] for fixture in future["fixtures"]} | {fixture["away"]["id"] for fixture in future["fixtures"]}
        assert named and named <= membership

    def test_a_cup_publishes_no_tier_movement(self, client) -> None:  # type: ignore[no-untyped-def]
        cup = next(item for item in client.get(f"{API}/competitions", params={"page_size": 50}).json()["items"] if item["kind"] == "cup")
        assert client.get(f"{API}/competitions/{cup['slug']}").json()["movement"] is None

    def test_unknown_ident_is_a_404_not_an_empty_page(self, client) -> None:  # type: ignore[no-untyped-def]
        for path in ("/competitions", "/teams", "/players", "/matches", "/news"):
            response = client.get(f"{API}{path}/no-such-record")
            assert response.status_code == 404, path
            assert response.json()["detail"]["code"] == "not_found"

    def test_unplayed_fixture_reports_no_score(self, client) -> None:  # type: ignore[no-untyped-def]
        scheduled = [item for item in client.get(f"{API}/matches", params={"page_size": 200}).json()["items"] if item["status"] != "completed"]
        assert scheduled
        body = client.get(f"{API}/matches/{scheduled[0]['slug']}").json()
        assert body["available"] is False
        assert body["match"]["home_goals"] is None and body["match"]["away_goals"] is None
        assert body["stat_lines"] == []

    def test_team_detail_squad_is_full_and_linkable(self, client) -> None:  # type: ignore[no-untyped-def]
        team = _item(client, "/teams")
        body = client.get(f"{API}/teams/{team['slug']}").json()
        assert len(body["squad"]) == 15
        assert body["squad"][0]["path"].startswith("/player/")
        assert any("demo data" in note for note in body["squad_notes"])

    def test_search_returns_typed_hits_with_paths_and_reasons(self, client) -> None:  # type: ignore[no-untyped-def]
        team = _item(client, "/teams")
        body = client.get(f"{API}/search", params={"q": team["name"]}).json()
        assert body["results"], team["name"]
        top = body["results"][0]
        assert top["type"] == "team" and top["path"] == team["path"]
        assert top["reasons"] and body["is_demo_data"] is True

    def test_search_type_filter_only_returns_that_type(self, client) -> None:  # type: ignore[no-untyped-def]
        player = _item(client, "/players")
        body = client.get(f"{API}/search", params={"q": player["name"], "types": "players"}).json()
        assert {hit["type"] for hit in body["results"]} <= {"player"}
        assert body["results"][0]["slug"] == player["slug"]

    def test_news_detail_links_entities_without_inventing_urls(self, client) -> None:  # type: ignore[no-untyped-def]
        item = _item(client, "/news")
        body = client.get(f"{API}/news/{item['slug']}").json()
        article = body["article"]
        assert article["url"] == web_path("article", item["slug"])
        assert article["source_name"] == "synthetic-world"
        assert body["body"].startswith("Fact about this generated world:")
        for link in body["related"]:
            assert link["path"].startswith(("/player/", "/team/", "/competition/", "/match/"))

    def test_every_path_in_a_detail_payload_is_a_seo_route(self, client) -> None:  # type: ignore[no-untyped-def]
        """The web tier links straight from these fields instead of building URLs itself, so a wrong
        prefix here becomes a 404 for a crawler. Walk every string that claims to be a path."""

        def walk(node: object) -> Iterator[str]:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.endswith("path") and isinstance(value, str):
                        yield value
                    else:
                        yield from walk(value)
            elif isinstance(node, list):
                for value in node:
                    yield from walk(value)

        checked = 0
        for path in ("/competitions", "/teams", "/players", "/matches", "/news"):
            item = _item(client, path)
            body = client.get(f"{API}{path}/{item['slug']}").json()
            for candidate in walk(body):
                assert candidate.startswith(("/player/", "/team/", "/match/", "/competition/", "/news/", "/training/")), f"{candidate!r} is not a page route the world publishes for {path!r}"
                assert SAFE_SLUG.match(candidate.rsplit("/", 1)[-1]), candidate
                checked += 1
        assert checked > 25, checked

    def test_training_log_is_public_and_its_load_is_arithmetic(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/training").json()
        assert body["is_demo_data"] is True and body["data_origin"] == "synthetic" and body["disclaimer"]
        assert body["total"] >= GATE["training_sessions"]
        assert body["gate"] == {"training_sessions": GATE["training_sessions"]}
        assert body["page_totals"]["sessions"] == len(body["items"]) > 0
        for item in body["items"]:
            assert item["load_units"] == item["duration_min"] * item["rpe"]
            assert item["player_path"] == web_path("player", item["player_slug"])
            assert item["drill_path"] == web_path("drill", item["drill_slug"])
            assert "records no real person" in item["summary"]

    def test_training_log_filters_narrow_to_the_player_or_club_asked_for(self, client) -> None:  # type: ignore[no-untyped-def]
        item = client.get(f"{API}/training").json()["items"][0]
        by_player = client.get(f"{API}/training", params={"player": item["player_slug"], "page_size": 100}).json()
        assert by_player["total"] >= 1 and {row["player_slug"] for row in by_player["items"]} == {item["player_slug"]}
        club = client.get(f"{API}/players/{item['player_slug']}").json()["player"]["club"]["slug"]
        by_club = client.get(f"{API}/training", params={"team": club, "page_size": 100}).json()
        assert by_club["total"] >= by_player["total"]
        assert client.get(f"{API}/training", params={"player": "no-such-player"}).status_code == 404

    def test_player_detail_and_the_log_agree_on_the_same_rows(self, client) -> None:  # type: ignore[no-untyped-def]
        """Two read paths, one set of rows: a total on the player page that the list cannot reproduce
        would be exactly the kind of stored-and-derived mismatch the rest of M3 refuses to ship."""
        slug = client.get(f"{API}/training").json()["items"][0]["player_slug"]
        log = client.get(f"{API}/players/{slug}").json()["training_log"]
        listed = client.get(f"{API}/training", params={"player": slug, "page_size": 100}).json()
        assert log["sessions"] == listed["total"] == len(log["items"])
        assert {row["id"] for row in log["items"]} == {row["id"] for row in listed["items"]}
        assert log["total_load"] == sum(row["load_units"] for row in listed["items"])
        assert log["total_minutes"] == sum(row["duration_min"] for row in listed["items"]) > 0
        assert log["load_formula"] == "load_units = duration_min x rpe"

    def test_a_player_with_no_session_reports_an_empty_log_not_a_zeroed_average(self, client) -> None:  # type: ignore[no-untyped-def]
        """Most generated players were never picked by the 100 sessions, and their page has to say *none*
        rather than render the arithmetic identity `mean of nothing = 0` as a measured average."""
        trained = {row["player_slug"] for row in client.get(f"{API}/training", params={"page_size": 200}).json()["items"]}
        listed = [p["slug"] for page in (1, 2) for p in client.get(f"{API}/players", params={"page": page, "page_size": 200}).json()["items"]]
        untrained = next((slug for slug in listed if slug not in trained), None)
        assert untrained is not None, f"{len(listed)} players cannot all be covered by {len(trained)} trained slugs"
        log = client.get(f"{API}/players/{untrained}").json()["training_log"]
        assert log["sessions"] == 0 and log["items"] == [] and log["total_load"] == 0 and log["total_minutes"] == 0
        assert log["categories"] == [] and log["drills"] == []
        assert log["mean_rpe"] == 0, "the page renders this as no data, not as an RPE of nil"

    def test_stat_lines_carry_the_match_path_too(self, client) -> None:  # type: ignore[no-untyped-def]        """A line without its fixture's path would force the client to rebuild `/match/{slug}`."""
        played = client.get(f"{API}/matches", params={"status": "completed", "page_size": 1}).json()["items"][0]
        detail = client.get(f"{API}/matches/{played['slug']}").json()
        assert detail["stat_lines"], "a completed fixture must carry its lines"
        for line in detail["stat_lines"][:5]:
            assert line["match_path"] == web_path("match", played["slug"])
            assert line["player"]["path"] == web_path("player", line["player"]["slug"])

    def test_capabilities_advertise_the_world_with_real_counts(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get("/api/v1/capabilities").json()
        assert body["m3_football_world"] is True
        assert body["m3_world"]["tables_present"] is True
        assert body["m3_world"]["counts"]["articles"] >= GATE["articles"]


class TestSearchService:
    def test_ranking_prefers_the_exact_club_name(self, session) -> None:
        sync_world(session)
        team = session.scalars(select(Team).order_by(Team.name).limit(1)).one()
        hits = search_world(session, team.name, limit=10)
        assert hits[0].type == "team"
        assert hits[0].path == web_path("team", team.slug)

    def test_nonsense_query_returns_no_rows_instead_of_a_guess(self, session) -> None:
        sync_world(session)
        assert search_world(session, "zzqxvjtunf", limit=10) == []

    def test_every_hit_carries_its_provenance(self, session) -> None:
        sync_world(session)
        hits = search_world(session, "league", limit=25)
        assert hits
        for hit in hits:
            assert any("synthetic" in reason for reason in hit.to_dict()["reasons"]), hit
            assert hit.path.startswith("/")
