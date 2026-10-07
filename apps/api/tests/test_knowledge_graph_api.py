"""`/graph` — the doors, the ceilings and the privacy claim of the §30 tier, measured against stored rows.

Four things are held here, and each is a claim a caller can check without reading the code:

* **Every declared edge answers through a real door.** The population is `verbs.EDGES` itself: for each
  edge one carrier row is drawn from its own table, and the door that reads that row's source node must
  print the verb *from that row*. An edge that exists only in the declaration table — because the
  projection builds a query the dialect refuses, or joins the wrong way round — is invisible here, and
  two of those were exactly what the first run of this file found (an ambiguous join left side, and a
  column edge whose carrier is also its own other side).
* **The printed ceilings are the ceilings in force.** `/graph/rules` publishes `max_depth` and
  `max_edges`, and the walk is asked past each of them: the refusal must name the same figure the page
  printed, and the `graph_too_broad` case must be reachable through the real world rather than only by
  mutating a constant.
* **Evidence is not decoration.** Every edge prints the carrier table, row and column it was read from.
  Each one is re-resolved here and compared against the stored row, so a printed relation cannot be a
  guess about which row produced it.
* **Nothing private is reachable** (spec §60, §61). `/graph` answers with no credentials at all, which
  is only defensible while every carrier it reads is a world table. The carriers it prints are checked
  against the privacy closure, and a signed-in user's own member row is shown to be unaddressable.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.models import (
    WORLD_DISCLAIMER,
    Competition,
    NewsArticle,
    NewsArticleLink,
    RealMatch,
    RealPlayer,
    Team,
    TrainingDrill,
)
from app.services.club import answers
from app.services.knowledge_graph import verbs
from app.services.world.plan import web_path

GRAPH = "/api/v1/graph"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    """The engine the app under test runs on, so the world the door reads is the world checked here."""
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _first(session, model: Any, **filters: Any) -> Any:
    """One stored row of a kind, ordered so the pick is the same row on every plane."""
    stmt = select(model).order_by(model.slug)
    for name, value in filters.items():
        stmt = stmt.where(getattr(model, name) == value)
    row = session.scalars(stmt).first()
    assert row is not None, f"the synced world stores no {model.__tablename__} row matching {filters}"
    return row


def _from_edge(links: list[dict[str, Any]], edge: Any, direction: str) -> list[dict[str, Any]]:
    """The links a door printed that came from one declaration.

    A verb name cannot pick them out on its own: `mentions` is carried by four edges (one per linked
    kind) and `plays_for` / `played_for` are two different carriers of the same player-to-team reading.
    The evidence columns separate them, because the projection prints the carrier column it read.
    """
    column = edge.target_column if direction == "out" else edge.source_column
    other_kind = edge.target_kind if direction == "out" else edge.source_kind
    name = edge.verb if direction == "out" else edge.reverse
    return [
        link
        for link in links
        if link["verb"] == name
        and link["evidence"]["carrier"] == edge.carrier
        and link["evidence"]["column"] == column
        and link["other"]["kind"] == other_kind
    ]


def _carrier(session, edge: Any) -> Any:
    """One stored row that carries this edge — the row both doors must then agree about."""
    model = verbs.EDGE_MODEL_BY_TABLE[edge.carrier]
    stmt = select(model).order_by(model.id)
    if edge.type_column:
        stmt = stmt.where(getattr(model, edge.type_column) == edge.type_value)
    row = session.scalars(stmt).first()
    assert row is not None, f"no {edge.carrier} row carries {edge.type_value!r}; the edge prints nothing"
    return row


class TestRulesDoor:
    def test_the_published_ceiling_is_the_one_the_walk_refuses_with(self, client) -> None:  # type: ignore[no-untyped-def]
        printed = client.get(f"{GRAPH}/rules").json()["max_depth"]
        refused = client.get(f"{GRAPH}/nodes/team/whatever/neighborhood?depth={printed + 1}")
        assert refused.status_code == 422, refused.text
        detail = refused.json()["detail"]
        assert detail["code"] == "graph_depth_not_supported"
        assert detail["max_depth"] == printed, "the page promises a ceiling the walk does not use"
        assert detail["asked"] == printed + 1

    def test_the_clause_counts_partition_in_the_printed_body(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{GRAPH}/rules").json()
        assert body["public_clauses"] == body["clauses_with_a_verb"] + body["clauses_declined"]
        assert body["public_clauses"] > 0 and body["clauses_with_a_verb"] > 0
        assert body["private_tables_excluded"] > 0, "a graph with no private half excluded proves nothing was excluded"

    def test_every_verb_the_spec_names_is_printed_or_declined(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{GRAPH}/rules").json()
        published = set(body["edge_verbs"]) | set(body["edge_verbs_reverse"])
        declined = set(body["spec_verbs_declined"])
        for spec_verb, names in verbs.SPEC_VERBS.items():
            if names:
                assert set(names) <= published, f"§30's {spec_verb} is recorded as landed but the page never prints it"
            else:
                assert spec_verb in declined, f"§30's {spec_verb} is neither printed nor declined"

    def test_the_refusal_answers_are_the_statuses_the_doors_earn(self, client, session) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{GRAPH}/rules").json()
        printed = body["refusal_answers"]
        assert printed == answers.published(verbs.REFUSALS)
        assert set(printed) == set(verbs.REFUSALS), (
            "the page prints an answer for a code the tier never registers"
        )
        absent = client.get(f"{GRAPH}/nodes/player/no-such-slug-anywhere")
        assert absent.status_code == printed["no_such_node"]
        bad_kind = client.get(f"{GRAPH}/nodes/coach/any")
        assert bad_kind.status_code == printed["unknown_node_kind"]

    def test_the_doors_answer_without_credentials(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        assert client.get(f"{GRAPH}/rules").status_code == 200
        assert client.get(f"{GRAPH}/nodes/team/{team.slug}").status_code == 200
        assert client.get(f"{GRAPH}/nodes/team/{team.slug}/neighborhood").status_code == 200

    def test_every_door_carries_the_provenance_envelope(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        bodies = [
            client.get(f"{GRAPH}/rules").json(),
            client.get(f"{GRAPH}/nodes/team/{team.slug}").json(),
            client.get(f"{GRAPH}/nodes/team/{team.slug}/neighborhood").json(),
        ]
        for body in bodies:
            assert body["data_origin"] == "synthetic"
            assert body["is_demo_data"] is True
            assert body["disclaimer"] == WORLD_DISCLAIMER


class TestNodeDoor:
    def test_the_door_answers_for_every_declared_edge(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """Each edge in the declaration table is driven through its own door, from a carrier row."""
        models = {spec.kind: spec.model for spec in verbs.NODES}
        for edge in verbs.EDGES:
            carrier_model = verbs.EDGE_MODEL_BY_TABLE[edge.carrier]
            stmt = select(carrier_model).order_by(carrier_model.id)
            if edge.type_column:
                stmt = stmt.where(getattr(carrier_model, edge.type_column) == edge.type_value)
            carrier_row = session.scalars(stmt).first()
            assert carrier_row is not None, f"no {edge.carrier} row carries {edge.type_value!r}; the edge prints nothing"
            source = session.get(models[edge.source_kind], getattr(carrier_row, edge.source_column))
            assert source is not None, f"{edge.verb}: its carrier names a {edge.source_kind} that is not stored"
            response = client.get(f"{GRAPH}/nodes/{edge.source_kind}/{source.slug}?verb={edge.verb}&direction=out")
            assert response.status_code == 200, f"{edge.verb}: {response.text}"
            # `mentions` is one verb over four target kinds, so a filter that stops at the verb gathers
            # every reading of it at once: measured, an article's own door answers `mentions` with
            # players, teams, matches and competitions in one list (30 links, four kinds). The edge under
            # test is one of those readings and the target kind is what names it, so the kind belongs in
            # the filter — this assertion compared four readings against one edge and read as a defect.
            printed = [
                link
                for link in response.json()["edges"]
                if link["verb"] == edge.verb and link["other"]["kind"] == edge.target_kind
            ]
            assert printed, (
                f"{edge.verb} -> {edge.target_kind} prints nothing through its own door, though {edge.carrier} has rows"
            )
            assert any(link["evidence"]["row"] == str(carrier_row.id) for link in printed), (
                f"{edge.verb}: the door answers, but not from carrier row {carrier_row.id} that was picked for it"
            )
            assert {link["evidence"]["carrier"] for link in printed} == {edge.carrier}, (
                f"{edge.verb} is declared on {edge.carrier} but prints evidence carried by another table"
            )

    def test_one_edge_is_named_differently_from_each_side(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """Direction is printable: the same relation reads as two words, one per side, sharing none.

        Two relations join a player to a team — the squad clause (`plays_for`/`has_player`) and the
        appearance link (`played_for`/`had_player_appearance`) — so "the player's team" is four printed
        words over two relations. Measured: this case first expected one pair and read four names, which
        is the world's shape rather than a defect. The claim that does hold is that neither relation
        borrows the other side's word.
        """
        player = session.scalars(
            select(RealPlayer).where(RealPlayer.team_id.is_not(None)).order_by(RealPlayer.slug)
        ).first()
        assert player is not None, "no world player carries a team, so no relation has two readings here"
        team = session.get(Team, player.team_id)
        forward = client.get(f"{GRAPH}/nodes/player/{player.slug}?direction=out").json()
        onward = [
            link
            for link in forward["edges"]
            if link["other"]["kind"] == "team" and link["other"]["slug"] == team.slug
        ]
        assert onward, f"the player's door does not print their own team {team.slug}"
        back = client.get(f"{GRAPH}/nodes/team/{team.slug}?direction=in").json()
        backward = [link for link in back["edges"] if link["other"]["slug"] == player.slug]
        assert backward, f"the team's door does not print {player.slug}, though the player's door prints it"
        forward_words = {link["verb"] for link in onward}
        backward_words = {link["verb"] for link in backward}
        assert forward_words == {"plays_for", "played_for"}, (
            f"the player's door reads their own team as {sorted(forward_words)}, not as the two relations stored"
        )
        assert backward_words == {"has_player", "had_player_appearance"}, (
            f"the team's door reads that same player as {sorted(backward_words)}, not as the two reverse readings"
        )
        shared = forward_words & backward_words
        assert not shared, f"a relation reads as {sorted(shared)} from both sides, so direction is not printable"
        assert {link["direction"] for link in onward} == {"out"}
        assert {link["direction"] for link in backward} == {"in"}

    def test_direction_narrows_what_a_node_prints(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        both = client.get(f"{GRAPH}/nodes/team/{team.slug}").json()
        outgoing = client.get(f"{GRAPH}/nodes/team/{team.slug}?direction=out").json()
        incoming = client.get(f"{GRAPH}/nodes/team/{team.slug}?direction=in").json()
        assert both["edges"], "a team node with no edges narrows nothing"
        assert both["outgoing_count"] > 0 and both["incoming_count"] > 0, (
            f"the team door reads {both['outgoing_count']} out / {both['incoming_count']} in; "
            "a kind that only ever reads one way cannot test direction"
        )
        assert len(both["edges"]) == both["outgoing_count"] + both["incoming_count"]
        assert len(outgoing["edges"]) == both["outgoing_count"] and outgoing["incoming_count"] == 0
        assert len(incoming["edges"]) == both["incoming_count"] and incoming["outgoing_count"] == 0

    def test_a_link_row_is_read_as_the_kind_it_records(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """`news_article_links.entity_type` decides which table a row addresses, not the id's shape.

        The join already drops every cross-kind row in the shipped world, because world ids carry their
        kind in their prefix — which is why a planted-defect probe found this narrowing removable with
        no case going red. This case removes the luck instead of trusting it: one stored link row whose
        `entity_type` says team while its `entity_id` is a real player's id, with a real team slug beside
        it so the row is inconsistent only in the column the graph reads. The player must not be printed
        as mentioned by that article, and the row must print no edge under any kind.
        """
        team = _first(session, Team)
        player = _first(session, RealPlayer)
        linked_teams = select(NewsArticleLink.article_id).where(
            NewsArticleLink.entity_type == "team", NewsArticleLink.entity_slug == team.slug
        )
        article = session.scalars(
            select(NewsArticle).where(NewsArticle.id.notin_(linked_teams)).order_by(NewsArticle.slug)
        ).first()
        assert article is not None, f"every stored article already links {team.slug}, so no row can be planted"
        planted = NewsArticleLink(
            id=new_public_id("wlnk"),
            article_id=article.id,
            entity_type="team",
            entity_slug=team.slug,
            entity_id=player.id,
        )
        session.add(planted)
        session.commit()
        try:
            body = client.get(f"{GRAPH}/nodes/article/{article.slug}?verb=mentions&direction=out").json()
            printed_players = {link["other"]["slug"] for link in body["edges"] if link["other"]["kind"] == "player"}
            assert player.slug not in printed_players, (
                f"article/{article.slug} prints {player.slug} as mentioned, read from a link row whose "
                "entity_type says team: the kind filter is what makes a reading the row's own"
            )
            assert all(link["evidence"]["row"] != planted.id for link in body["edges"]), (
                "the inconsistent row printed an edge under a kind it does not record"
            )
        finally:
            session.delete(planted)
            session.commit()

    def test_every_edge_prints_a_carrier_row_that_proves_it(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """The evidence a caller reads resolves against the table it names."""
        models = {spec.kind: spec.model for spec in verbs.NODES}
        by_column: dict[tuple[str, str], verbs.Edge] = {}
        for edge in verbs.EDGES:
            by_column[(edge.carrier, edge.target_column)] = edge
            by_column[(edge.carrier, edge.source_column)] = edge
        checked = 0
        for kind in ("player", "team", "match", "article"):
            body = client.get(f"{GRAPH}/nodes/{kind}/{_first(session, models[kind]).slug}").json()
            for link in body["edges"][:20]:
                evidence = link["evidence"]
                row = session.get(verbs.EDGE_MODEL_BY_TABLE[evidence["carrier"]], evidence["row"])
                assert row is not None, f"evidence names {evidence['carrier']} row {evidence['row']}, which is not stored"
                edge = by_column[(evidence["carrier"], evidence["column"])]
                key = edge.target_key_column if link["direction"] == "out" else "id"
                other_model = models[link["other"]["kind"]]
                value = getattr(row, evidence["column"])
                other = session.scalars(select(other_model).where(getattr(other_model, key) == value)).first()
                assert other is not None, (
                    f"{link['verb']}: evidence says {evidence['carrier']}.{evidence['column']}={value!r} "
                    f"addresses a {link['other']['kind']} by {key}, and no such row is stored"
                )
                assert str(other.slug) == link["other"]["slug"], (
                    f"{link['verb']}: the printed node is not the row the printed evidence column addresses"
                )
                checked += 1
        assert checked >= 8, f"only {checked} edges were re-resolved against their tables; the sample proved nothing"

    def test_facts_are_the_carrier_columns_the_edge_declares(self, client, session) -> None:  # type: ignore[no-untyped-def]
        from app.models import RealPlayerMatchStat

        edge = next(e for e in verbs.EDGES if e.verb == "participated_in")
        stat = session.scalars(select(RealPlayerMatchStat).order_by(RealPlayerMatchStat.id)).first()
        assert stat is not None, "the world stores no appearance rows, so the facts have no carrier"
        player = session.get(RealPlayer, stat.player_id)
        body = client.get(f"{GRAPH}/nodes/player/{player.slug}?verb=participated_in").json()
        link = next((item for item in body["edges"] if item["evidence"]["row"] == str(stat.id)), None)
        assert link is not None, "the appearance row that exists is not printed by the player's door"
        assert set(link["facts"]) == set(edge.facts)
        assert {name: getattr(stat, name) for name in edge.facts} == link["facts"]

    def test_a_completed_match_prints_its_score_and_a_fixture_does_not(self, client, session) -> None:  # type: ignore[no-untyped-def]
        played = _first(session, RealMatch, status="completed")
        upcoming = _first(session, RealMatch, status="scheduled")
        played_body = client.get(f"{GRAPH}/nodes/match/{played.slug}").json()
        fixture_body = client.get(f"{GRAPH}/nodes/match/{upcoming.slug}").json()
        assert played_body["node"]["label"] == f"{played.round_label} · {played.home_goals}-{played.away_goals}"
        # §50: an unplayed fixture is not given a score it does not have, and does not borrow one either.
        assert fixture_body["node"]["label"] == f"{upcoming.round_label} · not played"
        assert [link["verb"] for link in played_body["edges"]].count("home_team_is") == 1
        assert [link["verb"] for link in played_body["edges"]].count("away_team_is") == 1

    def test_the_label_builder_knows_every_stored_match_status(self, session) -> None:
        """The tail of `_label`'s chain is a refusal, so no stored status may reach it."""
        stored = {row[0] for row in session.execute(select(RealMatch.status).distinct())}
        assert stored, "the world stores no matches, so this compares an empty set"
        assert stored <= {"completed", "scheduled"}, (
            f"stored match statuses {sorted(stored - {'completed', 'scheduled'})} have no label branch; "
            "the door would answer 400 for a node that exists"
        )

    def test_a_node_carries_the_canonical_public_path(self, client, session) -> None:  # type: ignore[no-untyped-def]
        for kind, model in (("player", RealPlayer), ("team", Team), ("competition", Competition), ("drill", TrainingDrill)):
            row = _first(session, model)
            body = client.get(f"{GRAPH}/nodes/{kind}/{row.slug}").json()
            assert body["node"]["path"] == web_path(kind, row.slug), (
                f"a {kind} node prints {body['node']['path']}, not the §80 route the world routes hand out"
            )

    def test_a_missing_node_answers_with_the_tiers_code(self, client) -> None:  # type: ignore[no-untyped-def]
        refused = client.get(f"{GRAPH}/nodes/player/there-is-no-such-player")
        assert refused.status_code == 404
        detail = refused.json()["detail"]
        assert detail["code"] == "no_such_node"
        assert detail["slug"] == "there-is-no-such-player"

    def test_an_unknown_kind_names_the_kinds_it_does_have(self, client) -> None:  # type: ignore[no-untyped-def]
        refused = client.get(f"{GRAPH}/nodes/coach/some-coach")
        assert refused.status_code == 422
        detail = refused.json()["detail"]
        assert detail["code"] == "unknown_node_kind"
        assert detail["known"] == sorted(verbs.NODE_KINDS)

    def test_an_unknown_verb_is_refused_with_the_vocabulary(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        refused = client.get(f"{GRAPH}/nodes/team/{team.slug}?verb=scored")
        assert refused.status_code == 422
        detail = refused.json()["detail"]
        assert detail["code"] == "unknown_edge_verb"
        # scored is now a landed verb (mapped to participated_in), so it should NOT be in declined
        rules = client.get(f"{GRAPH}/rules").json()
        assert "scored" not in rules["spec_verbs_declined"], (
            "scored is now a landed verb (mapped to participated_in), should not be in declined"
        )

    def test_an_unknown_direction_refuses_instead_of_answering_both(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        refused = client.get(f"{GRAPH}/nodes/team/{team.slug}?direction=asi")
        assert refused.status_code == 422
        assert refused.json()["detail"]["code"] == "unknown_direction"


class TestNeighborhoodDoor:
    def test_a_depth_one_walk_prints_only_its_roots_neighbours(self, client, session) -> None:  # type: ignore[no-untyped-def]
        team = _first(session, Team)
        body = client.get(f"{GRAPH}/nodes/team/{team.slug}/neighborhood").json()
        assert body["node"]["slug"] == team.slug
        assert body["depth"] == 1
        assert body["node_count"] == len(body["nodes"]) and body["edge_count"] == len(body["edges"])
        assert {edge["hop"] for edge in body["edges"]} == {1}
        slugs = {node["slug"] for node in body["nodes"]}
        assert slugs >= {team.slug, *(edge["other"]["slug"] for edge in body["edges"])}

    def test_the_walk_holds_its_word_at_the_ceiling(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """At MAX_DEPTH a walk answers inside the published caps, or refuses naming them — never more.

        A depth-2 walk over this world is broad, so the answering path has to be measured where the
        stored rows make it narrow: the articles carrying the fewest links. This case first walked the
        lowest-slug article and asked for 200; measured, that article's two-hop walk is thousands of
        edges and the door refuses it — correctly, and the sibling case below holds that side. What the
        ceiling has to be is a ceiling rather than a wall, so the claim here is that the narrowest roots
        answer, and that **every** trial obeys the figures `/graph/rules` publishes.
        """
        published = client.get(f"{GRAPH}/rules").json()
        narrowest = session.execute(
            select(NewsArticleLink.article_id, func.count(NewsArticleLink.id).label("links"))
            .group_by(NewsArticleLink.article_id)
            .order_by(func.count(NewsArticleLink.id).asc(), NewsArticleLink.article_id)
            .limit(5)
        ).all()
        assert narrowest, "the world stores no article links, so no root can be measured here"
        answered = 0
        for article_id, links in narrowest:
            article = session.get(NewsArticle, article_id)
            assert article is not None, f"a stored article link names article {article_id!r}, which is not stored"
            response = client.get(f"{GRAPH}/nodes/article/{article.slug}/neighborhood?depth={verbs.MAX_DEPTH}")
            assert response.status_code in (200, 422), response.text
            if response.status_code == 422:
                detail = response.json()["detail"]
                assert detail["code"] == "graph_too_broad", (
                    f"a {links}-link article refuses a depth-{verbs.MAX_DEPTH} walk with {detail['code']!r}, "
                    "not with the ceiling it breached"
                )
                assert detail["max_edges"] == published["max_edges"]
                continue
            body = response.json()
            assert body["edge_count"] == len(body["edges"]), "the printed edge count is not the list it counts"
            assert body["node_count"] == len(body["nodes"]), "the printed node count is not the list it counts"
            assert body["edge_count"] <= published["max_edges"], f"{body['edge_count']} edges over {published['max_edges']}"
            assert body["node_count"] <= published["max_nodes"], f"{body['node_count']} nodes over {published['max_nodes']}"
            assert {edge["hop"] for edge in body["edges"]} <= set(range(1, published["max_depth"] + 1))
            answered += 1
        assert answered, (
            f"none of the {len(narrowest)} narrowest articles answers a depth-{verbs.MAX_DEPTH} walk; "
            "the published ceiling is then a wall rather than a ceiling"
        )

    def test_a_walk_that_breaches_the_edge_ceiling_refuses_rather_than_trimming(self, client, session) -> None:  # type: ignore[no-untyped-def]
        """Reachable through stored data, not by editing a constant: the busiest squad's two-hop walk."""
        rows = session.execute(
            select(RealPlayer.team_id, func.count(RealPlayer.id).label("squad"))
            .where(RealPlayer.team_id.is_not(None))
            .group_by(RealPlayer.team_id)
            .order_by(func.count(RealPlayer.id).desc(), RealPlayer.team_id)
        ).all()
        assert rows, "no world player carries a team, so no walk can be broad"
        broadest = session.get(Team, rows[0][0])
        assert broadest is not None, f"the busiest squad belongs to team id {rows[0][0]!r}, which is not stored"
        published = client.get(f"{GRAPH}/rules").json()["max_edges"]
        breach = client.get(f"{GRAPH}/nodes/team/{broadest.slug}/neighborhood?depth=2")
        assert breach.status_code == 422, (
            f"the broadest squad in the world walks depth 2 without breaching: {breach.text[:200]} — "
            f"the ceiling of {published} is then no longer a promise a caller can plan around"
        )
        detail = breach.json()["detail"]
        assert detail["code"] == "graph_too_broad"
        assert detail["max_edges"] == published

    def test_a_walk_names_no_node_the_door_cannot_answer(self, client, session) -> None:  # type: ignore[no-untyped-def]
        article = _first(session, NewsArticle)
        body = client.get(f"{GRAPH}/nodes/article/{article.slug}/neighborhood").json()
        for node in body["nodes"][:12]:
            answered = client.get(f"{GRAPH}/nodes/{node['kind']}/{node['slug']}")
            assert answered.status_code == 200, f"a walk named {node['kind']}/{node['slug']}, which its own door refuses"


class TestPrivacyDoor:
    def test_no_printed_edge_is_carried_by_a_private_table(self, client, session) -> None:  # type: ignore[no-untyped-def]
        private = verbs.private_tables()
        models = {spec.kind: spec.model for spec in verbs.NODES}
        seen = 0
        for kind in ("player", "team", "match", "article", "competition", "drill"):
            row = _first(session, models[kind])
            for source in (f"{GRAPH}/nodes/{kind}/{row.slug}", f"{GRAPH}/nodes/{kind}/{row.slug}/neighborhood"):
                body = client.get(source).json()
                for link in body["edges"]:
                    assert link["evidence"]["carrier"] not in private, (
                        f"{source} printed an edge carried by {link['evidence']['carrier']}, which reaches a user"
                    )
                    seen += 1
        assert seen > 0, "no edge was printed anywhere, so nothing was excluded"

    def test_a_signed_in_users_own_rows_are_not_addressable(self, client, auth_client, player_id, session) -> None:  # type: ignore[no-untyped-def]
        """A member row lives in `players`, and the graph addresses `real_players` — by slug."""
        refused = client.get(f"{GRAPH}/nodes/player/{player_id}")
        assert refused.status_code == 404
        assert refused.json()["detail"]["code"] == "no_such_node"
        # And the public door still answers for the world node that shares nothing with that row.
        team_edges = client.get(f"{GRAPH}/nodes/team/{_first(session, Team).slug}").json()["edges"]
        assert player_id not in {edge["other"]["slug"] for edge in team_edges}


def test_a_declined_clause_is_printed_as_an_object_a_caller_can_read(client) -> None:  # type: ignore[no-untyped-def]
    """The door owns the declines as well as the verbs, and prints why each clause is not walked."""
    body = client.get(f"{GRAPH}/rules").json()
    printed = body["declined_clauses"]
    assert {item["clause"] for item in printed} == {
        f"{table}.{column} -> {target}" for (table, column, target) in verbs.DECLINED_CLAUSES
    }
    assert body["clauses_declined"] == len(printed)
    for item in printed:
        assert len(item["reason"].split()) >= 8, f"the decline of {item['clause']} is printed as {item['reason']!r}"
