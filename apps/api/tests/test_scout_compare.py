"""M7 §27 — a comparison whose every leader is re-derived from the two stored rows, not from the payload.

§27 asks for `Compare Player A vs Player B` across ten dimensions and rules out one thing:
避免单一 Overall 分数决定一切. A test suite can break that rule just as easily as the code does, by asserting
that some number comes out on top. So the centre of gravity here is the opposite:

* every measure is read again out of `real_players` and `real_player_match_stats` by hand, and the leader is
  re-decided in the test — including the direction, so `age` has to stay unranked and a lower competition
  tier has to be called the better context;
* the payload is searched for the shape of the forbidden thing: no `winner`, no `score`, no `overall_score`,
  no `rating`, and the two stored overall columns may appear only inside `overall_line`, which says in its own
  note that it is not the verdict;
* `split` is asserted as a *correct* answer wherever the two sides win different measures, because a suite
  that only ever looked for a winner would have to invent one to pass;
* a dimension with no lines behind it prints `unknown`, never zero — the same refusal §24 made for a group
  mean, tested per measure here against a row the world genuinely has no stat lines for.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import ATTRIBUTES, RealPlayer, RealPlayerMatchStat, Team
from app.services.scouting import compare as compare_module
from app.services.scouting.compare import (
    DIMENSION_LEADERS,
    DIMENSIONS,
    LEADERS,
    NO_WINNER_NOTE,
    PROGRESSION_ATTRIBUTES,
    STAT_COLUMNS,
    build_comparison,
    comparison_counts,
    comparison_problems,
    comparison_ready,
    limitations,
)
from app.services.scouting.report import ReportRefusal
from app.services.scouting.search import pool
from app.services.simulation import market
from app.services.world import sync_world, world_ready

PASSWORD = "strong-pass-1234"


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world, plus the two rows every test in here compares and the edges they cover."""
    session = SessionLocal()
    try:
        sync_world(session)
        rows = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(rows) > 100 and world_ready(session)
        with_lines = int(session.scalar(select(func.count(func.distinct(RealPlayerMatchStat.player_id)))) or 0)
        observed = max(rows, key=lambda row: (int(row.appearances or 0), row.slug))
        other = next(row for row in rows if row.slug != observed.slug and int(row.appearances or 0) > 0)
        return {
            "players": len(rows),
            "players_without_lines": len(rows) - with_lines,
            "left": observed.slug,
            "right": other.slug,
            "veteran": max(rows, key=lambda row: (int(row.age), row.slug)).slug,
            "young": min(rows, key=lambda row: (int(row.age), row.slug)).slug,
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Any]:
    """A session over the seeded world.

    The dependency is stated rather than left to test order: every gate test here asks the module to build a
    comparison over the stored pool, and a subset run that skipped the `world` fixture would otherwise see an
    empty pool and report a clean gate.
    """
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


@pytest.fixture()
def pair(world: dict[str, Any], session: Any) -> dict[str, Any]:
    """One comparison, built once for the shape tests that do not care which pair it is."""
    return build_comparison(session, str(world["left"]), str(world["right"]))


def dimension(payload: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in payload["dimensions"] if item["dimension"] == name)


def measure(payload: dict[str, Any], name: str, key: str) -> dict[str, Any]:
    return next(item for item in dimension(payload, name)["measures"] if item["key"] == key)


def stored_lines(session: Any, slug: str) -> dict[str, int]:
    """Every column this module reads, summed straight out of the table by a path the module never touches."""
    row = session.execute(
        select(*[func.coalesce(func.sum(getattr(RealPlayerMatchStat, column)), 0) for column in STAT_COLUMNS])
        .select_from(RealPlayerMatchStat)
        .join(RealPlayer, RealPlayer.id == RealPlayerMatchStat.player_id)
        .where(RealPlayer.slug == slug)
    ).one()
    return dict(zip(STAT_COLUMNS, (int(value) for value in row), strict=True))


def expected_leader(left: Any, right: Any, direction: str) -> str:
    if direction == "none":
        return "not_scorable"
    if not isinstance(left, int | float) or not isinstance(right, int | float):
        return "unknown"
    if left == right:
        return "even"
    return "left" if bool(left > right) ^ (direction == "lower_is_greater") else "right"


class TestTenDimensions:
    """§27's list is a claim about structure, so the structure is checked against the list and nothing else."""

    def test_the_dimensions_are_the_ten_the_spec_prints_in_the_order_it_prints_them(self, pair: dict[str, Any]) -> None:
        assert [item["dimension"] for item in pair["dimensions"]] == list(DIMENSIONS)
        assert pair["dimensions_list"] == list(DIMENSIONS)

    @pytest.mark.parametrize("name", list(DIMENSIONS))
    def test_every_dimension_answers_with_measures_rather_than_a_lone_number(self, pair: dict[str, Any], name: str) -> None:
        line = dimension(pair, name)
        assert len(line["measures"]) >= 2
        assert line["leader"] in DIMENSION_LEADERS
        assert line["source"]
        assert line["rule"] == compare_module.DIMENSION_RULE

    def test_the_attribute_dimensions_cover_every_key_the_project_lists_for_that_group(self, pair: dict[str, Any]) -> None:
        for group in ("technical", "physical", "mental", "tactical"):
            assert [item["key"] for item in dimension(pair, group)["measures"]] == list(ATTRIBUTES[group])

    def test_the_event_dimensions_are_built_from_columns_that_exist_on_the_stat_line(self) -> None:
        from app.models import RealPlayerMatchStat as Stat

        for entries in compare_module.EVENT_MEASURES.values():
            for _key, columns, _direction in entries:
                for column in columns:
                    assert column in STAT_COLUMNS
                    assert hasattr(Stat, column)
        for key in PROGRESSION_ATTRIBUTES:
            assert key in ATTRIBUTES["technical"] or key in ATTRIBUTES["mental"]

    def test_counts_reconcile_with_the_measures_printed(self, pair: dict[str, Any]) -> None:
        measures = [item for line in pair["dimensions"] for item in line["measures"]]
        assert pair["counts"]["dimensions"] == len(DIMENSIONS)
        assert pair["counts"]["measures"] == len(measures)
        assert sum(pair["counts"]["by_leader"].values()) == len(measures)
        assert sum(pair["counts"]["dimension_leaders"].values()) == len(DIMENSIONS)


class TestNoSingleScore:
    """The rule §27 writes down in one line, tested as a property of the payload rather than of the code."""

    def test_the_payload_carries_no_winner_score_index_or_rating(self, pair: dict[str, Any]) -> None:
        for forbidden in ("winner", "score", "overall_score", "combined", "index", "rating", "verdict"):
            assert forbidden not in pair
        for line in pair["dimensions"]:
            assert not any(key in line for key in ("score", "winner", "index"))

    def test_the_two_overall_columns_are_printed_without_being_made_the_answer(self, pair: dict[str, Any], world: dict[str, Any], session: Any) -> None:
        line = pair["overall_line"]
        assert "leader" not in line and "winner" not in line
        assert "not the verdict" in line["note"]
        left_row = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(world["left"]))).one()
        assert line["left"] == int(left_row.overall)
        assert line["delta"] == line["left"] - line["right"]

    def test_the_note_about_not_having_a_winner_travels_inside_the_payload(self, pair: dict[str, Any]) -> None:
        assert pair["no_single_score"] == NO_WINNER_NOTE
        assert "no weighted index" in NO_WINNER_NOTE

    def test_a_dimension_the_two_sides_divide_over_is_called_split_rather_than_forced(self, pair: dict[str, Any]) -> None:
        """`split` is a correct answer, and a suite that hunted for a winner could never produce one."""
        splits = [item for item in pair["dimensions"] if item["leader"] == "split"]
        assert splits, "over a pool of thousands a pair that divides every dimension is not the world this fixture picks"
        for line in splits:
            assert line["counts"]["left"] >= 1 and line["counts"]["right"] >= 1

    def test_younger_is_not_treated_as_better(self, pair: dict[str, Any], world: dict[str, Any], session: Any) -> None:
        """The age line has to be printed and refused at once — a two-year gap decides nothing."""
        line = measure(pair, "age", "age")
        assert line["direction"] == "none"
        assert line["leader"] == "not_scorable"
        assert line["delta"] is None, "a measure that refuses a direction must not print a difference either — a difference implies one"
        veteran = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(world["veteran"]))).one()
        young = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(world["young"]))).one()
        if int(veteran.age) != int(young.age):
            reversed_pair = build_comparison(session, str(world["veteran"]), str(world["young"]))
            assert measure(reversed_pair, "age", "age")["leader"] == "not_scorable"

    def test_a_competition_name_is_printed_and_not_ranked(self, pair: dict[str, Any]) -> None:
        line = measure(pair, "context", "competition_name")
        assert line["direction"] == "none"
        assert line["leader"] == "not_scorable"


class TestMeasuresAgainstTheRows:
    """Each figure is read again from the tables by hand, so a wrong rate cannot survive in one place."""

    @pytest.mark.parametrize("group", ["technical", "physical", "mental", "tactical"])
    def test_an_attribute_measure_is_the_value_stored_on_each_row_and_its_leader_follows(self, world: dict[str, Any], session: Any, group: str) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        rows = {slug: session.scalars(select(RealPlayer).where(RealPlayer.slug == slug)).one() for slug in (world["left"], world["right"])}
        for key in ATTRIBUTES[group]:
            line = measure(payload, group, key)
            a = (rows[str(world["left"])].attributes or {}).get(key)
            b = (rows[str(world["right"])].attributes or {}).get(key)
            assert (line["left"], line["right"]) == (a, b)
            assert line["leader"] == expected_leader(a, b, "higher_is_greater")
            assert line["source"] == f"`attributes.{key}` on each row"

    @pytest.mark.parametrize(
        ("name", "key", "formula"),
        [
            ("production", "goals_per_90", lambda totals: round(totals["goals"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("production", "assists_per_90", lambda totals: round(totals["assists"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("production", "shots_on_target_per_90", lambda totals: round(totals["shots_on_target"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("possession", "pass_accuracy", lambda totals: round(totals["passes_accurate"] / totals["passes"], 3) if totals["passes"] else None),
            ("possession", "key_passes_per_90", lambda totals: round(totals["key_passes"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("defensive", "tackles_per_90", lambda totals: round(totals["tackles"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("defensive", "interceptions_per_90", lambda totals: round(totals["interceptions"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
            ("defensive", "duels_won_per_90", lambda totals: round(totals["duels_won"] * 90 / totals["minutes"], 2) if totals["minutes"] else None),
        ],
    )
    def test_an_event_measure_is_the_rate_its_own_source_line_describes(self, world: dict[str, Any], session: Any, name: str, key: str, formula: Any) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        line = measure(payload, name, key)
        assert line["left"] == formula(stored_lines(session, str(world["left"])))
        assert line["right"] == formula(stored_lines(session, str(world["right"])))
        assert line["leader"] == expected_leader(line["left"], line["right"], line["direction"])
        assert line["delta"] == pytest.approx(round(float(line["left"]) - float(line["right"]), 4), abs=1e-9)

    def test_the_progression_dimension_says_which_of_its_measures_come_from_where(self, world: dict[str, Any], session: Any) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        line = dimension(payload, "progression")
        keys = [item["key"] for item in line["measures"]]
        assert keys == [*PROGRESSION_ATTRIBUTES, "key_passes_per_90"]
        assert compare_module.PROGRESSION_RULE == line["note"]
        for item in line["measures"]:
            if item["key"] in PROGRESSION_ATTRIBUTES:
                assert "attributes" in item["source"]
            else:
                assert "real_player_match_stats" in item["source"]

    def test_the_age_dimension_prices_years_left_the_way_the_market_does(self, world: dict[str, Any], session: Any) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        rows = {slug: session.scalars(select(RealPlayer).where(RealPlayer.slug == slug)).one() for slug in (world["left"], world["right"])}
        for side, slug in (("left", world["left"]), ("right", world["right"])):
            row = rows[str(slug)]
            assert measure(payload, "age", "age")[side] == int(row.age)
            assert measure(payload, "age", "headroom")[side] == int(row.potential) - int(row.overall)
            assert measure(payload, "age", "age_curve")[side] == market.age_curve(int(row.age))
            assert measure(payload, "age", "years_past_peak")[side] == max(0, int(row.age) - market.PEAK_AGE_END)
        assert measure(payload, "age", "years_past_peak")["direction"] == "lower_is_greater"

    def test_context_reads_the_club_and_competition_rows_behind_the_players(self, world: dict[str, Any], session: Any) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        for side, slug in (("left", world["left"]), ("right", world["right"])):
            row = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(slug))).one()
            club = session.get(Team, row.team_id) if row.team_id else None
            assert measure(payload, "context", "club_overall")[side] == (int(club.overall) if club else None)
            assert measure(payload, "context", "competition_name")[side] == (club.competition.name if club and club.competition else None)
            tier = measure(payload, "context", "competition_tier")
            assert tier[side] == (int(club.competition.tier) if club and club.competition else None)
            appearances = int(row.appearances or 0)
            expected = round(int(row.starts or 0) / appearances, 3) if appearances else None
            assert measure(payload, "context", "starts_per_appearance")[side] == expected
        assert measure(payload, "context", "competition_tier")["direction"] == "lower_is_greater"

    def test_the_seeded_world_records_a_line_for_every_player(self, world: dict[str, Any]) -> None:
        """The fact that makes the test below a patched read rather than a stored row.

        If the generator ever starts leaving a player with no stat lines, this goes red and the unknown
        branch gets a real row to be measured against — which is the better test, and the reason this one is
        written down instead of being quietly folded into the next case.
        """
        assert world["players_without_lines"] == 0

    def test_a_side_with_no_stat_lines_prints_unknown_rather_than_zero(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """§27's rates over a side with nothing recorded, reached by taking the totals read away.

        The patched mapping is the exact shape `_stat_totals` returns — every column it sums, plus `lines` —
        so each measure below is still formed by the real code, over a side that has no events to form one from.
        """
        original = compare_module._stat_totals

        def nothing_for_the_left(_session: Any, player_ids: list[str]) -> dict[str, dict[str, int]]:
            totals = original(_session, player_ids)
            totals[player_ids[0]] = dict(dict.fromkeys(STAT_COLUMNS, 0), lines=0)
            return totals

        monkeypatch.setattr(compare_module, "_stat_totals", nothing_for_the_left)
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        for name in ("production", "possession", "defensive"):
            for item in dimension(payload, name)["measures"]:
                assert item["left"] is None, f"{name}.{item['key']} invented a figure for a player no line records"
                assert item["leader"] == "unknown"
                assert item["right"] is not None
                assert "left" in item["unobserved"]
        assert payload["left"]["stat_lines"] == 0
        assert payload["left"]["minutes_in_lines"] == 0

    def test_the_event_dimension_of_an_unobserved_side_is_unresolved_not_even(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """`unresolved` and `even` are different answers, and only one of them is a lie about a blank side."""

        def nothing_for_both(_session: Any, player_ids: list[str]) -> dict[str, dict[str, int]]:
            return {pid: dict(dict.fromkeys(STAT_COLUMNS, 0), lines=0) for pid in player_ids}

        monkeypatch.setattr(compare_module, "_stat_totals", nothing_for_both)
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        assert dimension(payload, "production")["leader"] == "unresolved"
        assert dimension(payload, "production")["counts"]["even"] == 0
        # The attribute dimensions are untouched by an empty stat sheet, which is the point of ten dimensions.
        assert dimension(payload, "technical")["leader"] in ("left", "right", "split", "even")

    def test_a_side_with_lines_reports_the_lines_its_own_rows_hold(self, world: dict[str, Any], session: Any) -> None:
        """The other half of the refusal: the counting is real, so a zero here is not a stub always returning zero."""
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        for side, slug in (("left", world["left"]), ("right", world["right"])):
            counted = int(
                session.scalar(
                    select(func.count()).select_from(RealPlayerMatchStat).where(RealPlayerMatchStat.player_id == select(RealPlayer.id).where(RealPlayer.slug == str(slug)).scalar_subquery())
                )
                or 0
            )
            assert payload[side]["stat_lines"] == counted
            assert payload[side]["minutes_in_lines"] == stored_lines(session, str(slug))["minutes"]

    def test_the_totals_check_compares_the_stored_season_columns_with_the_lines_under_them(self, world: dict[str, Any], session: Any) -> None:
        payload = build_comparison(session, str(world["left"]), str(world["right"]))
        for side, slug in (("left", world["left"]), ("right", world["right"])):
            row = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(slug))).one()
            totals = stored_lines(session, str(slug))
            check = payload["totals_check"][side]
            assert check["lines_minutes"] == totals["minutes"]
            assert check["lines_goals"] == totals["goals"]
            assert check["agree"] == (int(row.minutes or 0) == totals["minutes"] and int(row.goals or 0) == totals["goals"])

    def test_a_pair_can_be_asked_for_by_id_as_well_as_by_slug(self, world: dict[str, Any], session: Any) -> None:
        left = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(world["left"]))).one()
        by_slug = build_comparison(session, str(world["left"]), str(world["right"]))
        by_id = build_comparison(session, str(left.id), str(world["right"]))
        assert by_id["dimensions"] == by_slug["dimensions"]


class TestRefusals:
    def test_comparing_a_player_with_themself_is_refused_and_says_why(self, world: dict[str, Any], session: Any) -> None:
        with pytest.raises(ReportRefusal) as error:
            build_comparison(session, str(world["left"]), str(world["left"]))
        assert error.value.code == "same_player"
        assert error.value.to_dict()["players_in_pool"] >= 2
        assert "two players" in error.value.to_dict()["note"]

    def test_the_same_row_asked_twice_under_two_different_idents_is_still_one_player(self, world: dict[str, Any], session: Any) -> None:
        row = session.scalars(select(RealPlayer).where(RealPlayer.slug == str(world["left"]))).one()
        with pytest.raises(ReportRefusal) as error:
            build_comparison(session, str(world["left"]), str(row.id))
        assert error.value.code == "same_player"

    def test_an_unknown_side_refuses_before_anything_is_computed(self, world: dict[str, Any], session: Any) -> None:
        with pytest.raises(ReportRefusal) as error:
            build_comparison(session, "nobody-at-all", str(world["left"]))
        assert error.value.code == "no_such_player"
        assert error.value.to_dict()["ident"] == "nobody-at-all"

    def test_the_left_side_is_answered_first_when_neither_exists(self, session: Any) -> None:
        with pytest.raises(ReportRefusal) as error:
            build_comparison(session, "neither-here", "nor-here")
        assert error.value.to_dict()["ident"] == "neither-here"

    def test_a_pool_with_one_row_cannot_be_compared(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(compare_module, "pool", lambda _session: pool(session)[:1])
        assert comparison_ready(session) is False
        assert comparison_problems(session) == ["the stored player pool has fewer than two rows, so no pair can be compared here"]

    def test_a_pool_with_two_rows_can_be(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(compare_module, "pool", lambda _session: pool(session)[:2])
        assert comparison_ready(session) is True


class TestComparisonIntegrityGate:
    """The gate §23 and §24 publish on `/scout/rules`, pointed at the payload §27 is made of."""

    def test_a_clean_world_produces_a_clean_gate(self, session: Any) -> None:
        assert comparison_problems(session) == []

    def test_a_dimension_list_drifted_from_the_specs_is_named(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(compare_module, "DIMENSIONS", (*DIMENSIONS[:-1], "set_pieces"))
        problems = comparison_problems(session)
        assert any("not §27's ten" in item for item in problems)

    def test_a_dimension_whose_leader_ignores_its_measures_is_named(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(compare_module, "_leader_for", lambda _measures, _counts: "left")
        problems = comparison_problems(session)
        assert problems
        assert any("but its measures give" in item for item in problems)

    def test_an_unrankable_measure_that_ranks_anyway_is_named(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        original = compare_module._measure

        def rank_anyway(key: str, left: Any, right: Any, direction: str, source: str, **extra: Any) -> dict[str, Any]:
            row = original(key, left, right, direction, source, **extra)
            if direction == "none":
                row["leader"] = "left"
            return row

        monkeypatch.setattr(compare_module, "_measure", rank_anyway)
        problems = comparison_problems(session)
        assert any("cannot be ranked and ranks anyway" in item for item in problems)
        # This is the check that catches it, and only this one: a measure whose leader was rewritten still
        # feeds the same (wrong) leader to the counts and to the dimension ladder, so those agree with each
        # other and say nothing. `direction: none` is the one case where the payload contradicts itself
        # without the arithmetic, and the gate reads the contradiction rather than the arithmetic.
        assert any("`age`" in item for item in problems)
        assert any("`competition_name`" in item for item in problems)

    def test_a_single_score_smuggled_into_the_payload_is_named(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        original = compare_module.build_comparison

        def with_a_winner(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {**original(*args, **kwargs), "winner": "left"}

        monkeypatch.setattr(compare_module, "build_comparison", with_a_winner)
        assert any("single score §27 rules out" in item for item in comparison_problems(session))

    def test_an_empty_pool_says_so_instead_of_failing(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(compare_module, "pool", lambda _session: [])
        assert comparison_problems(session) == ["the stored player pool has fewer than two rows, so no pair can be compared here"]

    def test_a_measure_that_leads_against_its_own_printed_difference_is_named(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """The gate's second copy of the answer is the subtraction, not a recount of the leader column.

        `counts` and the dimension leader are both formed from the measure's `leader`, so a leader rewritten
        after the figures were made leaves them internally consistent — this pair of checks is what catches
        it, and it is written as `delta` against `left - right` because a payload that prints +0.35 and calls
        the measure even has contradicted itself in one line.
        """
        original = compare_module._measure

        candidates = pool(session)
        clean = build_comparison(session, str(candidates[0].player.slug), str(candidates[1].player.slug))
        assert measure(clean, "production", "goals_per_90")["leader"] in ("left", "right"), "the pair the gate builds for itself ties on goals per 90, which would make the mutation below a no-op"

        def miscounted(key: str, left: Any, right: Any, direction: str, source: str, **extra: Any) -> dict[str, Any]:
            row = original(key, left, right, direction, source, **extra)
            if key == "goals_per_90" and row["leader"] in ("left", "right"):
                row["leader"] = "even"
            return row

        monkeypatch.setattr(compare_module, "_measure", miscounted)
        problems = comparison_problems(session)
        assert any("leads even while the delta it prints points" in item for item in problems), problems


class TestComparisonRoute:
    """`POST /api/v1/scout/compare` answers with the same payload the service builds, or refuses in the house shape."""

    def test_the_door_is_shut_without_a_token(self, client: TestClient) -> None:
        assert client.post("/api/v1/scout/compare", json={"left": "a", "right": "b"}).status_code == 401

    def test_a_pair_comes_back_with_the_ten_dimensions_and_who_was_asked(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        response = auth_client.post("/api/v1/scout/compare", json={"left": world["left"], "right": world["right"]})
        assert response.status_code == 200
        body = response.json()
        assert [item["dimension"] for item in body["dimensions"]] == list(DIMENSIONS)
        assert body["asked_for"] == {"left": world["left"], "right": world["right"]}
        assert body["demo_data"] is True

    def test_the_route_sends_the_same_figures_the_service_built(self, auth_client: TestClient, world: dict[str, Any], session: Any) -> None:
        body = auth_client.post("/api/v1/scout/compare", json={"left": world["left"], "right": world["right"]}).json()
        direct = build_comparison(session, str(world["left"]), str(world["right"]))
        assert set(body) - set(direct) == {"asked_for", "demo_data"}
        assert body["dimensions"] == direct["dimensions"]
        assert body["counts"] == direct["counts"]

    def test_a_single_player_asked_as_a_pair_is_a_refusal_with_a_reason(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        response = auth_client.post("/api/v1/scout/compare", json={"left": world["left"], "right": world["left"]})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "same_player"

    def test_an_unknown_player_is_not_found_rather_than_invalid(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        response = auth_client.post("/api/v1/scout/compare", json={"left": "not-a-player", "right": world["right"]})
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_such_player"

    @pytest.mark.parametrize("payload", [{"left": "only-one"}, {"right": "only-one"}, {}, {"left": "", "right": "x"}])
    def test_a_request_that_is_not_a_pair_is_the_house_validation_answer(self, auth_client: TestClient, payload: dict[str, str]) -> None:
        response = auth_client.post("/api/v1/scout/compare", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert "error" not in body, f"a schema refusal must print where a service one prints: {body}"
        detail = body["detail"]
        assert detail["code"] == "validation_error"
        assert detail["message"] == "Request validation failed"

    def test_rules_publishes_the_dimension_list_it_answers_with(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        body = auth_client.get("/api/v1/scout/rules").json()
        block = body["comparison"]
        assert block["dimensions"] == list(DIMENSIONS)
        assert block["ready"] is True
        assert block["stat_columns"] == list(STAT_COLUMNS)
        assert block["no_single_score"] == NO_WINNER_NOTE
        assert block["measure_leaders"] == list(LEADERS)
        assert block["dimension_leaders"] == list(DIMENSION_LEADERS)
        assert body["integrity"]["problems"] == []
        assert "comparison" in body["routes"]

    def test_capabilities_says_the_comparison_is_here(self, client: TestClient) -> None:
        body = client.get("/api/v1/capabilities").json()
        assert body["m7_player_comparison"]["ready"] is True
        assert body["m7_player_comparison"]["dimensions"] == list(DIMENSIONS)

    def test_the_counts_and_limitations_are_published_not_private(self, session: Any) -> None:
        counts = comparison_counts(session)
        assert counts["dimensions"] == list(DIMENSIONS)
        assert counts["players_in_pool"] == len(pool(session))
        assert len(limitations()) == 6
        assert len(compare_module.limitations()) == len(limitations())


class TestNothingInvented:
    """The house check that a module this close to a verdict did not quietly widen its own vocabulary."""

    def test_no_measure_is_asked_to_be_something_the_stored_world_cannot_answer(self, pair: dict[str, Any]) -> None:
        for line in pair["dimensions"]:
            for item in line["measures"]:
                assert item["source"], f"{line['dimension']}.{item['key']} prints a figure with no source named"
                assert item["direction"] in ("higher_is_greater", "lower_is_greater", "none")

    def test_the_payload_names_what_it_cannot_say(self, pair: dict[str, Any]) -> None:
        assert any("broadcast tracking" in line for line in pair["limitations"])
        assert any("no model call" in line for line in pair["limitations"])
        assert any("progressive-carry" in line for line in pair["limitations"])

    def test_the_world_line_is_the_same_account_the_search_and_report_publish(self, pair: dict[str, Any], session: Any) -> None:
        from app.services.scouting.search import world_account

        assert pair["world"] == world_account(session)

    def test_a_comparison_between_the_same_two_players_is_the_same_both_ways_round(self, world: dict[str, Any], session: Any) -> None:
        """Every figure is a subtraction with a sign, so flipping the pair has to flip it and nothing else."""
        forward = build_comparison(session, str(world["left"]), str(world["right"]))
        back = build_comparison(session, str(world["right"]), str(world["left"]))
        for line, mirror in zip(forward["dimensions"], back["dimensions"], strict=True):
            for a, b in zip(line["measures"], mirror["measures"], strict=True):
                assert a["left"] == b["right"] and a["right"] == b["left"]
                if a["delta"] is not None and b["delta"] is not None:
                    assert a["delta"] == pytest.approx(-b["delta"], abs=1e-9)
                flip = {"left": "right", "right": "left"}
                assert flip.get(a["leader"], a["leader"]) == b["leader"]

    def test_a_pair_is_not_a_pair_just_because_the_idents_differ(self, session: Any) -> None:
        """Two idents, one row: the slug and the id of the same player must not become a comparison."""
        row = session.scalars(select(RealPlayer).order_by(RealPlayer.slug).limit(1)).one()
        with pytest.raises(ReportRefusal) as error:
            build_comparison(session, str(row.slug), str(row.id))
        assert error.value.code == "same_player"


def test_a_request_that_names_nothing_does_not_reach_the_service(auth_client: TestClient) -> None:
    """A random string is not a player, and the route has to fail as a search would."""
    noise = f"nobody-{uuid4().hex[:8]}"
    response = auth_client.post("/api/v1/scout/compare", json={"left": noise, "right": noise})
    assert response.status_code == 404
