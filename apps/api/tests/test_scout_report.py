"""M7 §24 — a scouting report whose every line is checked against the row it claims to read.

The spec's constraint on this module is 不要输出没有依据的"天赋" — no unevidenced talent. So each figure
is re-read here by a *different* mechanism than the one that printed it:

* the four group means are recomputed in plain Python over `app.models.ATTRIBUTES` and the row's own
  `attributes` dict, and a missing key has to show up in `missing` rather than pull the mean down;
* `current_level.recomputed` is re-derived from `OVERALL_WEIGHTS` by hand (including the 40 that
  `compute_overall` substitutes for a key a row lacks), and `percentile` is a SQL `COUNT` taken here;
* `role_fit` and `team_fit` are checked against `ROLES[...].demands` and `market.tactical_fit` called
  directly on the row, so no report can hold a fit figure the search or the market disagrees with;
* `cost` is `market.valuation` for that row, field by field;
* `risk` is re-derived from the stored age, appearances and wage-to-fee share, and the two factor lists are
  compared for equality rather than subset;
* `recommendation.verdict` is re-derived by walking `RECOMMENDATION_RULE`'s ladder over the figures the
  report itself published — a verdict that did not follow from its own numbers is the failure mode §24
  forbids, and a test that only re-ran the module would never see it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import ATTRIBUTES, Career, RealPlayer, Team
from app.services.attributes import OVERALL_WEIGHTS, compute_overall
from app.services.scouting import report as report_module
from app.services.scouting.report import COMPANION_FIELDS, REPORT_FIELDS, VERDICTS, GroupScore, ReportRefusal, build_report, group_score, limitations, report_counts, report_problems, report_ready
from app.services.scouting.requirements import ROLE_POSITIONS
from app.services.scouting.search import Candidate, pool
from app.services.simulation import market
from app.services.simulation.profile import band_of_position
from app.services.tactics.roles import ROLES
from app.services.world import sync_world, world_ready

CAREERS = "/api/v1/careers"
PASSWORD = "strong-pass-1234"


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world to report on, plus the rows this module has to handle at each edge."""
    session = SessionLocal()
    try:
        sync_world(session)
        rows = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(rows) > 100 and world_ready(session)
        club = str(session.scalars(select(Team.id).order_by(Team.overall, Team.slug).limit(1)).one())
        quietest = min(rows, key=lambda row: (int(row.appearances or 0), row.slug))
        observed = max(rows, key=lambda row: (int(row.appearances or 0), row.slug))
        veteran = max(rows, key=lambda row: (int(row.age), row.slug))
        second = next(row.slug for row in rows if row.slug != observed.slug and row.position == observed.position)
        return {
            "players": len(rows),
            "club_id": club,
            "quietest": quietest.slug,
            "quietest_appearances": int(quietest.appearances or 0),
            "observed": observed.slug,
            "veteran": veteran.slug,
            "veteran_age": int(veteran.age),
            "second": second,
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Any]:
    """A session over the seeded world, so any subset of this file builds reports over rows rather than silence."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _row(slug: str) -> RealPlayer:
    """A player read on its own session and detached, so the ORM cannot affect a test's arithmetic."""
    session = SessionLocal()
    try:
        player = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
        assert player is not None, slug
        session.expunge(player)
        return player
    finally:
        session.close()


def _candidate(slug: str) -> Candidate:
    session = SessionLocal()
    try:
        return next(item for item in pool(session) if item.player.slug == slug)
    finally:
        session.close()


def _career_slug(world: dict[str, Any]) -> str:
    """An owned career, opened through the route a manager uses."""
    with TestClient(_app()) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": f"scout-report-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Report Manager", "role": "player", "accepts_data_policy": True},
        )
        assert registered.status_code == 201, registered.text
        client.headers.update({"Authorization": f"Bearer {registered.json()['access_token']}"})
        created = client.post(
            CAREERS,
            json={"club": world["club_id"], "manager_name": "Report Manager", "philosophy": "balanced", "budget": 4_000_000, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
        )
        assert created.status_code == 200, created.text
        return str(created.json()["career"]["slug"])


def _app() -> Any:
    from app.main import app

    return app


def _career_row(slug: str) -> Career:
    session = SessionLocal()
    try:
        career = session.scalar(select(Career).where(Career.slug == slug))
        assert career is not None, slug
        session.expunge(career)
        return career
    finally:
        session.close()


def _mean_over_keys(attributes: dict[str, int], keys: tuple[str, ...]) -> tuple[float, list[str]]:
    """A second, deliberately dumb reading of a group mean: the keys that are there, and no other."""
    have = [int(attributes[key]) for key in keys if key in attributes]
    missing = [key for key in keys if key not in attributes]
    return (round(sum(have) / len(have), 2) if have else 0.0), missing


def _clamp(value: float) -> int:
    """`app.services.attributes._clamp`, re-typed here so the test does not borrow the code under test."""
    return int(max(1, min(99, round(value))))


class TestGroupScores:
    """§24's Technical / Physical / Mental / Tactical lines are means over the model's own grouping."""

    def test_the_four_groups_are_the_ones_the_model_writes_rows_in(self) -> None:
        assert list(ATTRIBUTES) == ["technical", "physical", "mental", "tactical"]
        assert [group for group in REPORT_FIELDS if group in ATTRIBUTES] == list(ATTRIBUTES)

    def test_a_group_mean_equals_the_same_mean_taken_in_this_test(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        stored = dict(_row(slug).attributes or {})
        candidate = _candidate(slug)
        for group in ATTRIBUTES:
            expected, missing = _mean_over_keys(stored, ATTRIBUTES[group])
            score = group_score(candidate, group)
            assert score.mean == expected, group
            assert score.measured == len(ATTRIBUTES[group]) - len(missing)
            assert score.missing == missing
            assert set(score.attributes) == {key for key in ATTRIBUTES[group] if key in stored}

    def test_the_strongest_and_weakest_keys_answer_their_names(self, world: dict[str, Any]) -> None:
        candidate = _candidate(str(world["observed"]))
        for group in ATTRIBUTES:
            score = group_score(candidate, group)
            values = {key: int(value) for key, value in (candidate.player.attributes or {}).items() if key in ATTRIBUTES[group]}
            assert int(score.attributes[score.strongest]) == max(values.values())
            assert int(score.attributes[score.weakest]) == min(values.values())

    def test_a_key_the_row_does_not_carry_is_named_rather_than_averaged_as_zero(self) -> None:
        """An in-memory row with gaps: the mean is over what exists and the gap is printed beside it."""
        partial = RealPlayer(id="p-partial", slug="partial-row", name="Partial Row", position="CM", age=24, attributes={"passing": 80, "dribbling": 60})
        candidate = Candidate(
            player=partial,
            club_name="",
            club_slug="",
            valuation={"asking_fee": 100, "weekly_wage": 1, "release_clause": 150, "contract_years": 2, "quality_points": 1, "headroom_points": 1, "age_curve": 1.0},
        )
        score = group_score(candidate, "technical")
        assert score.mean == 70.0
        assert score.measured == 2
        assert sorted(score.missing) == sorted(key for key in ATTRIBUTES["technical"] if key not in ("passing", "dribbling"))
        assert isinstance(score, GroupScore)

    def test_a_group_line_publishes_the_rule_that_made_it(self, world: dict[str, Any]) -> None:
        row = group_score(_candidate(str(world["observed"])), "mental").to_dict()
        assert row["rule"] == report_module.GROUP_RULE
        assert "not averaged as zero" in row["rule"]


class TestCurrentLevel:
    """The level line carries the stored figure and the derivation from the same attributes."""

    def test_the_stored_overall_is_the_rows_own_column(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        assert build_report(session, slug)["current_level"]["overall"] == int(_row(slug).overall)

    def test_the_recomputed_level_is_the_weight_mean_taken_by_hand(self, world: dict[str, Any], session: Any) -> None:
        player = _row(str(world["observed"]))
        keys = OVERALL_WEIGHTS.get(player.position, ())
        assert keys, f"no published weighting for {player.position}"
        expected = _clamp(sum(int((player.attributes or {}).get(key, 40)) for key in keys) / len(keys))
        level = build_report(session, str(world["observed"]))["current_level"]
        assert level["recomputed"] == expected == compute_overall(player.position, dict(player.attributes or {}))

    def test_a_generated_row_agrees_with_its_own_derivation_and_says_so(self, world: dict[str, Any], session: Any) -> None:
        level = build_report(session, str(world["observed"]))["current_level"]
        assert level["agrees_with_stored"] is True
        assert level["rule"] == report_module.LEVEL_RULE

    def test_the_percentile_is_a_count_taken_from_the_database(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        player = _row(slug)
        level = build_report(session, slug)["current_level"]
        total = int(session.scalar(select(func.count(RealPlayer.id))) or 0)
        at_or_below = int(session.scalar(select(func.count(RealPlayer.id)).where(RealPlayer.overall <= int(player.overall))) or 0)
        assert level["players_in_pool"] == total == world["players"]
        assert level["at_or_below"] == at_or_below
        assert level["share_of_pool"] == round(at_or_below / total, 3)
        assert level["band"] == band_of_position(player.position)

    def test_the_highest_row_in_the_pool_is_not_reported_as_the_median(self, world: dict[str, Any], session: Any) -> None:
        best = max(pool(session), key=lambda item: (int(item.player.overall), item.player.slug))
        level = build_report(session, best.player.slug)["current_level"]
        assert level["share_of_pool"] > 0.9
        assert level["share_of_band"] > 0.9


class TestPotentialAndCost:
    """The ceiling and the price are the same arithmetic §22 already published."""

    def test_headroom_is_the_rows_own_two_columns_apart(self, world: dict[str, Any], session: Any) -> None:
        player = _row(str(world["observed"]))
        row = build_report(session, str(world["observed"]))["potential"]
        assert row["headroom"] == int(player.potential) - int(player.overall)
        assert row["potential"] == int(player.potential)
        assert row["age_curve"] == market.age_curve(int(player.age))
        assert row["years_past_peak"] == max(0, int(player.age) - market.PEAK_AGE_END)
        assert row["rule"] == report_module.POTENTIAL_RULE

    def test_the_cost_line_is_the_markets_valuation_of_that_row(self, world: dict[str, Any], session: Any) -> None:
        player = _row(str(world["observed"]))
        valuation = market.valuation(player)
        cost = build_report(session, str(world["observed"]))["cost"]
        for key in ("asking_fee", "weekly_wage", "release_clause", "contract_years"):
            assert cost[key] == int(valuation[key]), key
        assert cost["formula"] == market.VALUATION_FORMULA
        assert cost["season_wage"] == int(valuation["weekly_wage"]) * 52
        assert cost["wage_share_of_fee"] == pytest.approx(int(valuation["weekly_wage"]) * 52 / max(int(valuation["asking_fee"]), 1), abs=1e-4)

    def test_the_fee_says_it_is_a_valuation_rather_than_an_offer(self, world: dict[str, Any], session: Any) -> None:
        cost = build_report(session, str(world["observed"]))["cost"]
        assert "not an offer" in cost["note"]
        assert "against_career_budget" not in cost


class TestRiskFactors:
    """§24's Risk line names factors, and every factor names the figure that raised it."""

    def test_the_factor_list_equals_the_same_ladder_walked_in_this_test(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        candidate = _candidate(slug)
        factors = {item["factor"] for item in build_report(session, slug)["risk"]}
        expected: set[str] = set()
        if int(candidate.player.appearances or 0) == 0:
            expected.add("unobserved_season")
        if market.age_curve(int(candidate.player.age)) < 1.0:
            expected.add("below_full_value_age")
        headroom = candidate.headroom()
        if headroom <= 0:
            expected.add("no_headroom")
        elif headroom >= 10:
            expected.add("wide_headroom")
        if candidate.valuation["weekly_wage"] * 52 / max(candidate.asking_fee, 1) > 0.5:
            expected.add("wage_heavy")
        assert factors == expected

    def test_the_crowded_band_factor_turns_on_at_four_rows_in_the_band(self, world: dict[str, Any]) -> None:
        """Swept, not sampled, because a threshold is a number the report can be wrong about.

        A mutation probe moved this rule from four to nine and every sampled report went on passing: no
        sampled club held between four and eight of its own rows in the band the career needs, so the factor
        simply vanished where nothing was looking. The sentence the factor prints says *at least four*, which
        makes four the claim under test rather than whatever the dev world happens to hold.
        """
        candidate = _candidate(str(world["observed"]))
        fired = [count for count in range(0, 9) if any(item["factor"] == "band_is_already_crowded" for item in report_module._risk(candidate, team_fit={"club_stores_in_band": count}))]
        assert fired == [4, 5, 6, 7, 8]
        named = [item for item in report_module._risk(candidate, team_fit={"club_stores_in_band": 4}) if item["factor"] == "band_is_already_crowded"]
        assert named[0]["value"] == 4, "the factor has to name the count that raised it"
        assert "four" in named[0]["rule"], named[0]["rule"]
        assert not any(item["factor"] == "band_is_already_crowded" for item in report_module._risk(candidate, team_fit=None)), "no team fit asked for, no crowded band claimed"

    def test_a_row_with_no_appearances_is_flagged_for_the_absence(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["quietest"])
        report = build_report(session, slug)
        assert report["player"]["observed"] is (world["quietest_appearances"] > 0)
        assert any(item["factor"] == "unobserved_season" for item in report["risk"]) is (world["quietest_appearances"] == 0)

    def test_the_oldest_row_raises_the_age_factor_and_says_what_the_curve_costs(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["veteran"])
        off_peak = [item for item in build_report(session, slug)["risk"] if item["factor"] == "below_full_value_age"]
        assert off_peak, f"age {world['veteran_age']} should sit off the curve's plateau"
        assert off_peak[0]["value"] == int(_row(slug).age)
        assert str(market.age_curve(int(_row(slug).age))) in off_peak[0]["rule"]

    def test_no_risk_line_rests_on_an_unmeasured_quality(self, world: dict[str, Any], session: Any) -> None:
        allowed = {"unobserved_season", "below_full_value_age", "no_headroom", "wide_headroom", "wage_heavy", "band_is_already_crowded"}
        for slug in (str(world["observed"]), str(world["veteran"]), str(world["quietest"])):
            for item in build_report(session, slug)["risk"]:
                assert item["factor"] in allowed
                assert item["rule"] and item["value"] is not None


class TestRoleAndTeamFit:
    """Fit is borrowed from §23 and §22 rather than recomputed a third way."""

    def test_no_role_means_no_role_fit_rather_than_a_zero_one(self, world: dict[str, Any], session: Any) -> None:
        assert build_report(session, str(world["observed"]))["role_fit"] is None

    def test_a_role_fit_is_that_roles_demands_against_the_stored_attributes(self, world: dict[str, Any], session: Any) -> None:
        candidate = _candidate(str(world["observed"]))
        role = "RWB"
        fit = build_report(session, str(world["observed"]), role=role)["role_fit"]
        assert fit is not None and fit["role"] == role
        assert fit["occupiable_by"] == list(ROLE_POSITIONS[role])
        assert fit["label"] == ROLES[role].label and fit["board_band"] == ROLES[role].band
        for row in fit["rows"]:
            assert row["attribute"] in ROLES[role].demands
            assert row["have"] == int((candidate.player.attributes or {}).get(row["attribute"], 0))
            assert row["demanded"] == int(ROLES[role].demands[row["attribute"]])
            assert row["gap"] == row["have"] - row["demanded"]
        assert fit["mean_gap"] == pytest.approx(sum(row["gap"] for row in fit["rows"]) / len(fit["rows"]), abs=0.01)

    def test_an_unknown_role_is_refused_with_the_roles_that_exist(self, world: dict[str, Any], session: Any) -> None:
        with pytest.raises(ReportRefusal) as raised:
            build_report(session, str(world["observed"]), role="Libero")
        assert raised.value.code == "unknown_role"
        assert "RWB" in raised.value.extra["roles"]

    def test_team_fit_needs_a_career_and_says_so_without_one(self, world: dict[str, Any], session: Any) -> None:
        assert build_report(session, str(world["observed"]))["team_fit"] is None

    def test_a_careers_need_and_fit_are_the_markets_own_figures(self, world: dict[str, Any]) -> None:
        slug = _career_slug(world)
        career = _career_row(slug)
        player = _row(str(world["observed"]))
        session = SessionLocal()
        try:
            need = market.club_need(session, career, round_index=int(career.rounds_played))
            fit = build_report(session, str(world["observed"]), career=career)["team_fit"]
        finally:
            session.close()
        assert fit is not None
        assert fit["career"] == slug
        assert fit["needed_band"] == need["needed_band"]
        assert fit["bands"] == need["bands"]
        assert fit["positions_in_band"] == need["positions_in_band"]
        assert fit["fit"] == market.tactical_fit(player, str(need["needed_band"]))["fit"]
        assert fit["formula"] == market.FIT_FORMULA
        assert fit["candidate_already_lists_there"] is (player.team_id == career.club_id)

    def test_the_band_count_beside_team_fit_counts_that_clubs_own_rows(self, world: dict[str, Any]) -> None:
        career = _career_row(_career_slug(world))
        session = SessionLocal()
        try:
            fit = build_report(session, str(world["observed"]), career=career)["team_fit"]
            squad = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)).all())
        finally:
            session.close()
        assert fit is not None
        assert fit["club_stores_in_band"] == sum(1 for row in squad if band_of_position(row.position) == str(fit["needed_band"]))
        assert fit["club_stores_in_band"] <= len(squad)

    def test_a_career_adds_the_budget_line_and_only_a_career_does(self, world: dict[str, Any]) -> None:
        career = _career_row(_career_slug(world))
        session = SessionLocal()
        try:
            cost = build_report(session, str(world["observed"]), career=career)["cost"]
        finally:
            session.close()
        budget = cost["against_career_budget"]
        assert budget["budget"] == int(career.budget)
        assert budget["units"] == career.budget_units
        assert budget["fits_without_selling"] is (int(cost["asking_fee"]) <= int(career.budget))
        assert budget["share_of_budget"] == round(int(cost["asking_fee"]) / int(career.budget), 4)


class TestComparison:
    """§24's Comparison line refuses to compare a player with nobody."""

    def test_no_comparator_leaves_the_line_empty_rather_than_self_referential(self, world: dict[str, Any], session: Any) -> None:
        assert build_report(session, str(world["observed"]))["comparison"] is None

    def test_the_deltas_are_this_minus_other_for_every_group(self, world: dict[str, Any], session: Any) -> None:
        this, other = str(world["observed"]), str(world["second"])
        row_a, row_b = _row(this), _row(other)
        comparison = build_report(session, this, compare_to=other)["comparison"]
        assert comparison is not None
        assert comparison["other"]["slug"] == other
        for group in ATTRIBUTES:
            mine, _ = _mean_over_keys(dict(row_a.attributes or {}), ATTRIBUTES[group])
            theirs, _ = _mean_over_keys(dict(row_b.attributes or {}), ATTRIBUTES[group])
            assert comparison["groups"][group] == pytest.approx(mine - theirs, abs=0.02)
        assert comparison["overall"] == int(row_a.overall) - int(row_b.overall)
        assert comparison["headroom"] == (int(row_a.potential) - int(row_a.overall)) - (int(row_b.potential) - int(row_b.overall))
        assert comparison["rule"] == report_module.COMPARISON_RULE

    def test_comparing_a_player_with_themselves_answers_with_zeroes(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        comparison = build_report(session, slug, compare_to=slug)["comparison"]
        assert comparison is not None
        assert comparison["overall"] == 0 and comparison["asking_fee"] == 0 and comparison["value_for_money"] == 0.0
        assert set(comparison["groups"].values()) == {0.0}

    def test_an_unknown_comparator_is_refused_by_name(self, world: dict[str, Any], session: Any) -> None:
        with pytest.raises(ReportRefusal) as raised:
            build_report(session, str(world["observed"]), compare_to="nobody-here")
        assert raised.value.code == "no_such_player"


class TestRecommendation:
    """The verdict is a ladder over this report's own figures, and the test walks it again."""

    @pytest.mark.parametrize("key", ["observed", "quietest", "veteran"])
    def test_the_verdict_follows_from_the_figures_this_report_published(self, world: dict[str, Any], session: Any, key: str) -> None:
        report = build_report(session, str(world[key]))
        level, potential = report["current_level"], report["potential"]
        fit = float(report["role_fit"]["mean_gap"]) if report["role_fit"] is not None else (float(report["team_fit"]["fit"]) if report["team_fit"] is not None else None)
        above_median = float(level["share_of_band"]) >= 0.5
        if above_median and (fit is None or fit >= 0):
            expected = "sign now"
        elif int(potential["headroom"]) >= 5 and float(potential["age_curve"]) >= 1.0:
            expected = "develop"
        elif fit is not None and fit < 0 and above_median:
            expected = "monitor"
        else:
            expected = "pass"
        assert report["recommendation"]["verdict"] == expected
        assert len(report["recommendation"]["decided_by"]) == 2
        assert report["recommendation"]["rule"] == report_module.RECOMMENDATION_RULE

    def test_a_player_short_for_the_role_asked_is_not_told_to_sign_now(self, world: dict[str, Any], session: Any) -> None:
        """The rule, not the code: a negative `role_fit.mean_gap` is a shortfall and must read as one.

        An earlier version negated the gap on its way into the ladder, so a player short in two of three
        role demands was reported as a positive fit — and the same response carried `mean_gap: -16.0` next
        to `decided_by: ["fit 16.0"]`, contradicting itself in one payload.
        """
        slug = str(world["observed"])
        report = build_report(session, slug, role="RWB")
        gap = float(report["role_fit"]["mean_gap"])
        assert gap < 0, "RWB demands are above this row's tactical attributes, which is the case this test is about"
        assert report["recommendation"]["verdict"] != "sign now"
        for item in report["recommendation"]["decided_by"]:
            if "mean_gap" in item:
                assert item.endswith(str(round(gap, 3)))

    @pytest.mark.parametrize("role", ["RWB", "AM"])
    def test_no_row_in_the_pool_is_told_to_sign_now_while_short_for_the_role_asked(self, world: dict[str, Any], session: Any, role: str) -> None:
        """A universal over the stored pool, sampled every twentieth row, because a single case proves one case.

        The gap between this test and the one above is the difference between checking an example and
        checking a rule: the negated `mean_gap` had to be caught somewhere, and a rule that only fires on
        the row a probe happened to pick is not a rule.
        """
        short = 0
        for candidate in pool(session)[::20]:
            report = build_report(session, str(candidate.player.slug), role=role)
            gap = float(report["role_fit"]["mean_gap"])
            if gap < 0:
                short += 1
                assert report["recommendation"]["verdict"] != "sign now", candidate.player.slug
        assert short >= 3, f"the sample produced {short} short rows, which cannot prove a rule about short rows"

    def test_the_ladder_answers_across_the_pool_rather_than_with_one_verdict(self, world: dict[str, Any], session: Any) -> None:
        """A ladder that fires one rung 300 times is a sentence about the pool, not a judgement per player."""
        verdicts = [build_report(session, str(candidate.player.slug))["recommendation"]["verdict"] for candidate in pool(session)[::20]]
        assert len(verdicts) >= 10
        assert len(set(verdicts)) >= 2, verdicts
        assert max(verdicts.count(item) for item in set(verdicts)) < len(verdicts)
        assert set(verdicts) <= set(VERDICTS)

    def test_the_verdict_says_no_model_wrote_it(self, world: dict[str, Any], session: Any) -> None:
        report = build_report(session, str(world["observed"]))
        assert "No model was asked what it thinks" in report["recommendation"]["note"]
        assert report["recommendation"]["risk_factors_named"] == len(report["risk"])

    def test_the_verdict_moves_when_the_level_it_reads_moves(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """The ladder is the whole report: replace the level line and the answer has to change with it."""
        slug = str(world["observed"])
        baseline = build_report(session, slug)["current_level"]

        def a_level_at(share: float) -> Any:
            def fake(_session: Any, _candidate: Candidate, _candidates: list[Candidate]) -> dict[str, Any]:
                return {**baseline, "share_of_band": share}

            return fake

        monkeypatch.setattr(report_module, "_percentile", a_level_at(0.0))
        low = build_report(session, slug)["recommendation"]["verdict"]
        monkeypatch.setattr(report_module, "_percentile", a_level_at(1.0))
        high = build_report(session, slug)["recommendation"]["verdict"]
        assert high == "sign now"
        assert low != high


class TestReportShapeAndHonesty:
    """§24's structure, and the lines that keep a report from over-claiming."""

    def test_the_report_carries_the_thirteen_fields_in_the_order_the_spec_prints_them(self, world: dict[str, Any], session: Any) -> None:
        report = build_report(session, str(world["observed"]))
        assert list(report)[: len(REPORT_FIELDS)] == list(REPORT_FIELDS)
        assert len(REPORT_FIELDS) == 13
        assert report["fields"] == list(REPORT_FIELDS)

    def test_an_unknown_player_is_refused_rather_than_returned_as_an_empty_report(self, world: dict[str, Any], session: Any) -> None:
        with pytest.raises(ReportRefusal) as raised:
            build_report(session, "who-is-this")
        assert raised.value.code == "no_such_player"
        assert raised.value.to_dict()["ident"] == "who-is-this"

    def test_reading_a_report_writes_nothing_back(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        role = sorted(ROLES)[0]
        first = build_report(session, slug, role=role)
        session.flush()
        second = build_report(session, slug, role=role)
        assert first == second
        assert not session.new and not session.dirty and not session.deleted

    def test_the_limitations_are_six_sentences_and_travel_with_the_report(self, world: dict[str, Any], session: Any) -> None:
        lines = limitations()
        assert len(lines) == 6
        assert any("potential is the generated row's ceiling" in line for line in lines)
        assert any("no model call" in line.lower() for line in lines)
        assert build_report(session, str(world["observed"]))["limitations"] == lines

    def test_a_report_is_only_ready_where_there_are_players_to_read(self, world: dict[str, Any], session: Any) -> None:
        assert report_ready(session) is True
        counts = report_counts(session)
        assert counts["players_in_pool"] == world["players"]
        assert counts["groups"] == {group: len(keys) for group, keys in ATTRIBUTES.items()}

    def test_the_report_is_fiction_about_generated_rows_and_says_so(self, world: dict[str, Any], session: Any) -> None:
        slug = str(world["observed"])
        report = build_report(session, slug)
        assert report["is_demo_data"] is True
        assert report["data_origin"] == _row(slug).data_origin
        assert report["world"]["players_stored"] == world["players"]


class TestReportIntegrityGate:
    """`report_problems` is the claim a reader of `/scout/rules` has to be able to trust, so it is tested by breaking it."""

    def test_the_gate_is_clean_over_the_seeded_world(self, world: dict[str, Any], session: Any) -> None:
        assert report_problems(session) == []

    def test_the_gate_names_a_field_that_stopped_being_answered(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(report_module, "REPORT_FIELDS", (*REPORT_FIELDS, "career_history"))
        problems = report_problems(session)
        assert len(problems) == 1
        assert "career_history" in problems[0]
        assert "absent from a built report" in problems[0]

    def test_the_gate_sees_a_group_mean_that_drifted_from_the_attributes_it_prints(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        real = report_module.group_score

        def inflated(candidate: Candidate, group: str) -> GroupScore:
            line = real(candidate, group)
            return GroupScore(line.group, line.attributes, round(line.mean + 5, 2), line.strongest, line.weakest, line.measured, line.missing)

        monkeypatch.setattr(report_module, "group_score", inflated)
        problems = report_problems(session)
        assert len(problems) == 4
        assert {problem.split("`")[1] for problem in problems} == set(ATTRIBUTES)
        assert all("mean is" in problem for problem in problems)

    def test_the_gate_refuses_a_verdict_outside_the_ladder_it_publishes(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        assert VERDICTS == ("sign now", "develop", "monitor", "pass")
        monkeypatch.setattr(report_module, "VERDICTS", ())
        problems = report_problems(session)
        assert len(problems) == 1
        assert "RECOMMENDATION_RULE does not list" in problems[0]

    def test_the_gate_says_so_when_there_is_no_pool_to_report_on(self, world: dict[str, Any], session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(report_module, "pool", lambda other: [])
        assert report_problems(session) == ["the stored player pool is empty, so no report can be answered here"]


def _own_career(auth_client: TestClient, club_id: str) -> str:
    """A career the account behind `auth_client` actually owns, opened through the route a manager uses."""
    created = auth_client.post(
        CAREERS,
        json={"club": club_id, "manager_name": "Report Manager", "philosophy": "balanced", "budget": 4_000_000, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["career"]["slug"])


class TestReportRoute:
    """§24's door: the route adds an account, a lookup and a status code, and re-derives nothing."""

    def test_the_report_needs_an_account(self, client: TestClient, world: dict[str, Any]) -> None:
        response = client.post("/api/v1/scout/report", json={"player": str(world["observed"])})
        assert response.status_code == 401

    def test_the_route_answers_the_thirteen_fields_and_says_who_was_asked(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        slug = str(world["observed"])
        response = auth_client.post("/api/v1/scout/report", json={"player": slug, "role": sorted(ROLES)[0]})
        assert response.status_code == 200, response.text
        body = response.json()
        assert list(body)[: len(REPORT_FIELDS)] == list(REPORT_FIELDS)
        assert body["role_fit"]["role"] == sorted(ROLES)[0]
        assert body["asked_for"] == {"player": slug, "role": sorted(ROLES)[0], "career": None, "compare_to": None, "round_index": None}
        assert body["demo_data"] is True

    def test_the_route_and_the_service_answer_the_same_report(self, auth_client: TestClient, session: Any, world: dict[str, Any]) -> None:
        slug = str(world["observed"])
        response = auth_client.post("/api/v1/scout/report", json={"player": slug, "role": "AM", "compare_to": str(world["second"])})
        assert response.status_code == 200, response.text
        direct = build_report(session, slug, role="AM", compare_to=str(world["second"]))
        body = response.json()
        for key in (*REPORT_FIELDS, "fields", "groups", "world", "limitations", "data_origin", "is_demo_data"):
            assert body[key] == direct[key], key
        assert set(body) - set(direct) == {"asked_for", "demo_data"}

    def test_an_unknown_player_is_a_404_rather_than_an_empty_report(self, auth_client: TestClient) -> None:
        response = auth_client.post("/api/v1/scout/report", json={"player": "no-such-row"})
        assert response.status_code == 404, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "no_such_player"
        assert detail["ident"] == "no-such-row"
        assert "no stored player" in detail["message"]

    def test_an_unknown_role_is_a_422_carrying_the_roles_that_exist(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        response = auth_client.post("/api/v1/scout/report", json={"player": str(world["observed"]), "role": "False Nine"})
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "unknown_role"
        assert detail["roles"] == sorted(ROLES)
        assert {"GK", "AM", "ST"} <= set(detail["roles"])

    def test_the_player_is_judged_before_the_role_so_a_wrong_slug_wins(self, auth_client: TestClient) -> None:
        response = auth_client.post("/api/v1/scout/report", json={"player": "no-such-row", "role": "False Nine"})
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "no_such_player"

    def test_a_player_field_the_schema_rejects_never_reaches_the_pool(self, auth_client: TestClient) -> None:
        response = auth_client.post("/api/v1/scout/report", json={"player": "x" * 200})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert any("player" in str(item.get("loc", "")) for item in error["details"])

    def test_a_foreign_career_is_a_404_that_never_names_its_owner(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        foreign = _career_slug(world)
        response = auth_client.post("/api/v1/scout/report", json={"player": str(world["observed"]), "career": foreign})
        assert response.status_code == 404, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "not_found"
        assert "Report Manager" not in str(detail)

    def test_an_owned_career_adds_a_team_fit_line_and_its_absence_leaves_it_null(self, auth_client: TestClient, world: dict[str, Any]) -> None:
        slug = str(world["observed"])
        own = _own_career(auth_client, str(world["club_id"]))
        with_career = auth_client.post("/api/v1/scout/report", json={"player": slug, "career": own})
        assert with_career.status_code == 200, with_career.text
        fit = with_career.json()["team_fit"]
        assert fit["career"] == own
        assert fit["needed_band"] in {"attack", "midfield", "defence", "keeper"}
        assert fit["formula"] == market.FIT_FORMULA
        assert with_career.json()["cost"]["against_career_budget"]["budget"] == 4_000_000
        without = auth_client.post("/api/v1/scout/report", json={"player": slug})
        assert without.status_code == 200, without.text
        assert without.json()["team_fit"] is None
        assert "against_career_budget" not in without.json()["cost"]

    def test_the_rules_route_publishes_the_report_structure_and_its_own_gate(self, client: TestClient, world: dict[str, Any], session: Any) -> None:
        response = client.get("/api/v1/scout/rules")
        assert response.status_code == 200, response.text
        body = response.json()
        block = body["report"]
        assert block["fields"] == list(REPORT_FIELDS)
        assert block["companion_fields"] == list(COMPANION_FIELDS)
        assert block["verdicts"] == list(VERDICTS)
        assert block["ready"] is True
        assert block["counts"] == report_counts(session)
        assert block["limitations"] == limitations()
        assert set(block["refusals"]) == {"no_such_player", "unknown_role"}
        assert body["routes"]["report"] == "POST /api/v1/scout/report — needs an account; §24's structured report for one stored player"
        assert body["integrity"]["problems"] == []

    def test_capabilities_publishes_the_report_alongside_the_search(self, client: TestClient, world: dict[str, Any], session: Any) -> None:
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200, response.text
        block = response.json()["m7_scout_report"]
        assert block["ready"] == report_ready(session)
        assert block["fields"] == list(REPORT_FIELDS)
        assert block["counts"]["players_in_pool"] == world["players"]
