"""§30's graph is a projection over the schema's own clauses, so the clauses are the census (spec §30).

Three things are held here, and none of them is "the code looks right":

* **Every public foreign key answers to a verb or to a written decline.** The population is read from
  live metadata, and the private half is excluded by a closure over the same clauses, so a table a
  later milestone adds is counted without anyone remembering to list it. A public clause that arrives
  with neither would be a relation the graph silently does not have.
* **The privacy predicate has teeth in both directions.** It is checked against tables that must be
  inside it (a career's appearances, a club's fixture, a minor's guardian consent) and tables that must
  be outside (a player, a team), and the import-time validator is asked to refuse two planted
  declarations — an edge aimed at a private carrier, and a public clause whose decline is deleted.
  A guard that has never been made to refuse is a description of intent, not a control.
* **The stored world agrees with the relations the graph claims.** The appearance rows name a team that
  is actually one of the two sides of their match; every world training session names a drill that
  exists; every article link resolves, and only to kinds this graph addresses.

The last group is what makes `real_training_sessions.drill_slug` and `news_article_links.entity_id`
legitimate edges at all: neither is a foreign key, so each is declared beside the test that proves it
resolves for *every* row, and `verbs._validate()` refuses the import if that test does not exist.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import (
    NewsArticleLink,
    RealMatch,
    RealPlayerMatchStat,
    RealTrainingSession,
    TrainingDrill,
)
from app.services.knowledge_graph import verbs
from app.services.world import sync_world


@pytest.fixture(scope="module")
def world() -> Iterator[None]:
    session = SessionLocal()
    try:
        sync_world(session)
    finally:
        session.close()
    yield


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


class TestClauseCensus:
    def test_every_public_clause_has_a_verb_or_a_written_decline(self) -> None:
        public = set(verbs.public_clauses())
        covered = verbs.consumed_clauses() & public
        declined = set(verbs.DECLINED_CLAUSES) & public
        missing = public - covered - declined
        assert public, "the census measured no public foreign keys, so it proved nothing about any of them"
        assert covered, "no public clause is traversed, so the graph has no edges"
        assert not missing, (
            f"{len(missing)} public foreign key(s) answer to neither a verb nor a decline: {sorted(missing)}. "
            "Either give the relation a verb in `EDGES`, or record in `DECLINED_CLAUSES` why the graph must not "
            "traverse it — a clause outside both is a relation the graph does not have and does not say it lacks."
        )
        assert not (covered & declined), (
            f"a clause is both traversed and declined: {sorted(covered & declined)}"
        )
        assert len(public) == len(covered) + len(declined), (
            f"public={len(public)} covered={len(covered)} declined={len(declined)} — the two halves "
            "must add up to the population the same scan measured"
        )

    def test_a_decline_without_a_reason_is_refused(self) -> None:
        empty = [key for key, reason in verbs.DECLINED_CLAUSES.items() if not reason.strip()]
        assert not empty, f"declined clauses with no reason: {empty}"

    def test_each_node_kind_is_reachable_by_at_least_one_edge(self) -> None:
        for spec in verbs.NODES:
            touching = [edge for edge in verbs.EDGES if spec.kind in (edge.source_kind, edge.target_kind)]
            assert touching, (
                f"{spec.kind} is a declared node kind but no edge touches it, so it can only ever be "
                "found by a slug a caller already knows"
            )

    def test_the_two_readings_of_an_edge_are_differently_named(self) -> None:
        collisions: list[tuple[str, str, str]] = []
        seen: dict[tuple[str, str, str], str] = {}
        for edge in verbs.EDGES:
            key = (edge.verb, edge.source_kind, edge.target_kind)
            if key in seen and seen[key] != edge.reverse:
                collisions.append((edge.verb, edge.source_kind, edge.target_kind))
            seen[key] = edge.reverse
        assert not collisions, f"{collisions} read the same way from both ends"

    def test_clauses_that_share_a_table_pair_still_differ_by_column(self) -> None:
        """`real_matches` points at `teams` twice, and a graph that cannot tell the sides apart is wrong."""
        by_pair: dict[tuple[str, str], list[verbs.Edge]] = {}
        for edge in verbs.EDGES:
            by_pair.setdefault((edge.carrier, edge.target_kind), []).append(edge)
        for pair, group in by_pair.items():
            if len(group) > 1:
                columns = {edge.target_column for edge in group}
                assert len(columns) == len(group), (
                    f"{pair}: {len(group)} edges share one column {sorted(columns)}, so the projection "
                    "cannot tell which relation a row carries"
                )
                verbs_out = {edge.verb for edge in group}
                assert len(verbs_out) == len(group), f"{pair}: two clauses of one pair share a verb"


class TestPrivacyPredicate:
    def test_the_closure_catches_a_table_with_no_user_column_of_its_own(self) -> None:
        priv = verbs.private_tables()
        assert {"users", "organizations"} <= priv
        assert "careers" in priv, "a career belongs to a user, and it carries that column directly"
        assert "career_appearances" in priv, (
            "this row has no user column, but it points at a career; the closure is what makes it private"
        )
        for table in ("club_fixtures", "development_plans", "guardian_consents", "sim_matches", "cv_shares"):
            assert table in priv, f"{table} is a tenant's or a person's row and the predicate missed it"

    def test_the_world_stays_outside_it(self) -> None:
        priv = verbs.private_tables()
        for table in ("real_players", "teams", "competitions", "real_matches", "news_articles", "training_drills"):
            assert table not in priv, f"{table} is generated world data, not a tenant's row"

    def test_no_declared_edge_carries_a_private_row(self) -> None:
        priv = verbs.private_tables()
        for edge in verbs.EDGES:
            touched = {edge.carrier, verbs.table_of(edge.source_kind), verbs.table_of(edge.target_kind)}
            assert not (touched & priv), f"{edge.verb}/{edge.reverse} would read {sorted(touched & priv)}"

    def test_a_graph_edge_aimed_at_a_private_carrier_refuses_the_import(self) -> None:
        """The validator's refuse side, planted through the shipped module rather than described."""
        planted = verbs.Edge(
            verb="owns", reverse="owned_by",
            source_kind="player", target_kind="team",
            carrier="career_squad_moves", source_column="player_id", target_column="counterparty_team_id",
        )
        original = verbs.EDGES
        try:
            verbs.EDGES = original + (planted,)
            with pytest.raises(RuntimeError, match="private"):
                verbs._validate()
        finally:
            verbs.EDGES = original
        verbs._validate()  # the accept side: the shipped declarations still pass

    def test_deleting_a_decline_refuses_the_import(self) -> None:
        """A public clause with no verb must not be able to hide by deleting the row that named it."""
        key = next(iter(verbs.DECLINED_CLAUSES))
        original = dict(verbs.DECLINED_CLAUSES)
        try:
            del verbs.DECLINED_CLAUSES[key]
            with pytest.raises(RuntimeError, match="neither a verb nor a decline"):
                verbs._validate()
        finally:
            verbs.DECLINED_CLAUSES.clear()
            verbs.DECLINED_CLAUSES.update(original)
        verbs._validate()

    def test_an_edge_naming_a_column_the_schema_does_not_have_refuses_the_import(self) -> None:
        planted = verbs.Edge(
            verb="invented", reverse="invented_by",
            source_kind="player", target_kind="team",
            carrier="real_players", source_column="id", target_column="club_id",
        )
        original = verbs.EDGES
        try:
            verbs.EDGES = original + (planted,)
            with pytest.raises(RuntimeError, match="club_id"):
                verbs._validate()
        finally:
            verbs.EDGES = original
        verbs._validate()


class TestSpecVerbsAreAccountedFor:
    def test_every_verb_the_spec_names_is_landed_or_declined(self) -> None:
        shipped = verbs.verb_names()
        landed = {name for name, names in verbs.SPEC_VERBS.items() if names}
        declined = set(verbs.DECLINED_SPEC_VERBS)
        assert landed | declined == set(verbs.SPEC_VERBS), (
            f"a §30 verb is neither landed nor declined: {sorted(set(verbs.SPEC_VERBS) - landed - declined)}"
        )
        for name, carriers in verbs.SPEC_VERBS.items():
            assert set(carriers) <= shipped, f"{name} is answered by verbs the graph does not carry"
        assert landed == {"plays_for", "played_for", "participated_in", "competes_in", "plays", "has_role", "scored"}, (
            f"the landed set moved to {sorted(landed)}; §30's own list is what this case pins"
        )

    def test_a_decline_names_the_measurement_that_forced_it(self) -> None:
        thin = {name: reason for name, reason in verbs.DECLINED_SPEC_VERBS.items() if len(reason) < 40}
        assert not thin, f"declines with no measurement behind them: {sorted(thin)}"


class TestDeclaredNonForeignKeyRelations:
    def test_every_world_training_session_names_a_drill_that_exists(self, world: None, session) -> None:  # type: ignore[no-untyped-def]
        total = session.scalar(select(func.count(RealTrainingSession.id)))
        assert total, "no world training sessions were synced, so this resolves nothing"
        unmatched = session.scalar(
            select(func.count(RealTrainingSession.id))
            .where(RealTrainingSession.drill_slug.notin_(select(TrainingDrill.slug)))
        )
        assert unmatched == 0, (
            f"{unmatched} of {total} training sessions name a drill slug that no drill carries; the graph "
            "resolves that relation by slug, so an unmatched row is a lost edge rather than a refused one"
        )

    def test_article_links_only_name_kinds_this_graph_addresses(self, world: None, session) -> None:
        declared = set(verbs.POLYMORPHIC_RELATIONS[("news_article_links", "entity_id")])
        stored = {row[0] for row in session.execute(select(NewsArticleLink.entity_type).distinct())}
        assert stored, "no article links were synced, so this compares two empty sets"
        assert stored <= declared, (
            f"the world links to {sorted(stored - declared)}, which the graph declares no edge for; "
            "those rows are invisible to a caller who trusts `/graph/rules`"
        )

    def test_every_article_link_resolves_to_a_real_row(self, world: None, session) -> None:
        """One set-based query per declared kind, not one per stored link.

        The first draft looped over the links and asked for each row's target; measured, that was the
        slowest case in this file by an order of magnitude (18.57s of a 45.25s run), and a suite cost
        that buys no extra evidence is a suite cost the next milestone pays without noticing.
        """
        declared = {spec.kind: spec.model for spec in verbs.NODES}
        dangling: list[tuple[str, str]] = []
        unaddressed = session.execute(
            select(NewsArticleLink.entity_type, NewsArticleLink.entity_slug).where(
                NewsArticleLink.entity_type.notin_(tuple(declared))
            )
        ).all()
        dangling.extend((str(kind), str(slug)) for kind, slug in unaddressed)
        for kind, model in declared.items():
            rows = session.execute(
                select(NewsArticleLink.entity_slug)
                .where(NewsArticleLink.entity_type == kind)
                .where(NewsArticleLink.entity_slug.notin_(select(model.slug)))
            ).all()
            dangling.extend((kind, str(slug)) for (slug,) in rows)
        assert not dangling, f"article links name rows that are not in the world: {dangling[:5]}"

    def test_an_appearance_never_names_a_team_outside_its_own_match(self, world: None, session) -> None:
        """The `played_for` edge is read from the appearance row's team, so that team must be a side."""
        rows = session.execute(
            select(
                RealPlayerMatchStat.id,
                RealPlayerMatchStat.team_id,
                RealMatch.home_team_id,
                RealMatch.away_team_id,
            ).join(RealMatch, RealMatch.id == RealPlayerMatchStat.match_id)
        ).all()
        assert rows, "no appearance rows were synced, so this compares nothing"
        unmatched = {
            str(row.id)
            for row in rows
            if row.team_id not in (row.home_team_id, row.away_team_id)
        }
        assert not unmatched, (
            f"{len(unmatched)} of {len(rows)} appearance rows name a team that is not one of the match's two "
            f"sides (e.g. {sorted(unmatched)[:3]}); `played_for` is read off that column, so the graph would "
            "print a player at a club they never appeared for"
        )
        orphaned = session.scalar(
            select(func.count(RealPlayerMatchStat.id)).where(
                RealPlayerMatchStat.match_id.notin_(select(RealMatch.id))
            )
        )
        assert orphaned == 0, f"{orphaned} appearance rows name no stored match at all"
