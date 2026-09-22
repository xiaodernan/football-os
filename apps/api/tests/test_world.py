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
from app.models import NewsArticle, NewsArticleLink, RealMatch, RealPlayer, RealTrainingSession, Team
from app.services.world import search_world, sync_world, web_path, world_counts, world_ready
from app.services.world.builder import TRAINING_RPE, WorldSizes, plan_world
from app.services.world.names import slugify
from app.services.world.plan import WorldPlan, duplicate_keys
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


class TestPlan:
    def test_same_seed_rebuilds_the_identical_world(self, plan: WorldPlan, rebuilt_plan: WorldPlan) -> None:
        assert plan.fingerprint() == rebuilt_plan.fingerprint()

    def test_a_different_seed_is_a_different_world(self, plan: WorldPlan) -> None:
        assert plan_world(4).fingerprint() != plan.fingerprint()

    def test_plan_clears_the_gate_without_colliding(self, plan: WorldPlan) -> None:
        assert plan_problems(plan) == []

    def test_default_sizes_are_the_documented_gate(self, plan: WorldPlan) -> None:
        sizes = WorldSizes()
        assert (sizes.teams, sizes.squad_size, sizes.competitions) == (20, 15, 10)
        assert sizes.played_matches >= 100
        counts = plan.counts()
        assert counts["players"] == sizes.players == 300
        assert counts["competitions"] == sizes.competitions
        assert counts["matches"] >= 100

    @pytest.mark.parametrize("collection", ["competitions", "teams", "players", "matches", "articles"])
    def test_public_slugs_are_url_safe(self, plan: WorldPlan, collection: str) -> None:
        keys = [row.natural_key for row in plan.collections[collection]]
        assert all(SAFE_SLUG.match(key) for key in keys), [key for key in keys if not SAFE_SLUG.match(key)][:3]
        assert all(key == slugify(key) and len(key) <= 200 for key in keys)

    def test_article_urls_survive_a_percent_round_trip(self, plan: WorldPlan) -> None:
        assert len(plan.collections["articles"]) == 500
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
        assert session.scalar(select(func.count()).select_from(NewsArticle)) == 500

    def test_a_squad_and_its_fixtures_agree_with_the_club_row(self, session) -> None:
        team = session.scalars(select(Team).order_by(Team.slug).limit(1)).one()
        squad = session.scalars(select(RealPlayer).where(RealPlayer.team_id == team.id)).all()
        assert len(squad) == team.squad_size == 15
        fixtures = session.scalars(select(RealMatch).where((RealMatch.home_team_id == team.id) | (RealMatch.away_team_id == team.id))).all()
        assert fixtures
        for match in fixtures:
            played = match.status == "completed"
            assert (match.home_goals is not None) is played


class TestReads:
    """The world is public fiction: readable without an account, never without its labels."""

    def test_status_reports_counts_gate_and_seed(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/status").json()
        assert body["is_demo_data"] is True and body["data_origin"] == "synthetic"
        assert body["counts"]["teams"] >= GATE["teams"] and body["counts"]["articles"] >= GATE["articles"]
        assert body["counts"]["training_sessions"] >= GATE["training_sessions"]
        assert body["gate"] == dict(GATE)
        assert isinstance(body["seed"], int)
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
        assert all(item["team_count"] > 0 for item in listed), [item["team_count"] for item in listed]

        league = client.get(f"{API}/competitions/{by_kind['league']['slug']}").json()
        assert league["competition"]["path"] == web_path("competition", by_kind["league"]["slug"])
        assert league["teams"] and league["standings"]
        assert league["completed"] + league["scheduled"] == len(league["fixtures"])

        cup = client.get(f"{API}/competitions/{by_kind['cup']['slug']}").json()
        assert cup["fixtures"], "a cup with no drawn ties is not a cup"
        assert cup["standings"] == [], "a knockout does not have a league table"
        assert all(fixture["home"] and fixture["away"] for fixture in cup["fixtures"]), cup["fixtures"][0]
        assert {team["id"] for team in cup["teams"]} == {fixture["home"]["id"] for fixture in cup["fixtures"]} | {fixture["away"]["id"] for fixture in cup["fixtures"]}

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
                assert candidate.startswith(("/player/", "/team/", "/match/", "/competition/", "/news/", "/training/")), (path, candidate)
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
