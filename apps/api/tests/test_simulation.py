"""M6 Football Simulation, part 1: the pure engine and the profile that feeds it (spec §19, §65).

Three claims are worth testing, and each is tested where it lives:

* **Determinism.** The same two profiles and the same seed must produce a byte-identical report, so a
  saved simulation can be re-derived instead of trusted. The random source is `WorldRng` for exactly
  this reason.
* **The numbers add up.** Goals equal goal events, goals never exceed shots on target, the block rows
  sum to the final line, and every scorer in a side's report came from that side's own eleven.
* **Nothing is invented.** A profile's indices must be computable from the rows the world generator
  wrote, which is what `team_profile` is checked against here — a synced database, not a fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import RealPlayer, Team
from app.services.simulation.engine import (
    SIMULATION_DISCLAIMER,
    MatchInputs,
    _Side,
    _volume_and_quality,
    simulate_match,
)
from app.services.simulation.profile import (
    SideProfile,
    possession_share,
    select_starting_xi,
    split_formation,
    team_profile,
)
from app.services.tactics.plan import tactical_systems
from app.services.world import sync_world


def _profile(
    *,
    team_id: str = "T1",
    name: str = "Northgate United",
    attack: float = 0.5,
    midfield: float = 0.5,
    defence: float = 0.5,
    keeper: float = 0.5,
    press: float = 0.5,
    form: float = 0.5,
    tactics: dict[str, float] | None = None,
    lineup: tuple[tuple[str, str, str], ...] | None = None,
) -> SideProfile:
    return SideProfile(
        team_id=team_id,
        name=name,
        short_name=name.split()[0],
        formation="4-2-3-1",
        system_slug="test",
        system_name="test system",
        attack=attack,
        midfield=midfield,
        defence=defence,
        keeper=keeper,
        press=press,
        form=form,
        overall=0.5,
        tactics=tactics if tactics is not None else {"depth": 30.0, "width": 40.0, "line_separation": 16.0, "space_behind": 12.0, "spacing": 11.0},
        lineup=lineup
        if lineup is not None
        else (
            ("Ana Keeper", "GK", "keeper"),
            ("Bea Doyle", "CB", "defence"),
            ("Cai Marsh", "LB", "defence"),
            ("Dee Allan", "RB", "defence"),
            ("Eli Vance", "CB", "defence"),
            ("Fay Otley", "CDM", "midfield"),
            ("Gus Perry", "CM", "midfield"),
            ("Hal Brodie", "CAM", "midfield"),
            ("Ivo Nash", "LM", "midfield"),
            ("Joy Alden", "RW", "attack"),
            ("Kit Ravel", "ST", "attack"),
        ),
    )


def _inputs(**kwargs: Any) -> MatchInputs:
    values: dict[str, Any] = {"home": _profile(), "away": _profile(team_id="T2", name="Southbank Rovers"), "seed": 7}
    values.update(kwargs)
    return MatchInputs(**values)


class TestFormationSplit:
    def test_a_four_two_three_one_is_four_five_one(self) -> None:
        assert split_formation("4-2-3-1") == (4, 5, 1)

    @pytest.mark.parametrize(
        ("formation", "expected"),
        [("4-4-2", (4, 4, 2)), ("5-3-2", (5, 3, 2)), ("3-4-2-1", (3, 6, 1)), ("4-3-3", (4, 3, 3))],
    )
    def test_first_digit_is_the_back_line_and_last_is_the_front(self, formation: str, expected: tuple[int, int, int]) -> None:
        assert split_formation(formation) == expected

    def test_unreadable_data_falls_back_instead_of_crashing(self) -> None:
        assert split_formation("") == (4, 4, 2)
        assert split_formation("four-two") == (4, 4, 2)


class TestSelection:
    def test_each_band_gets_what_the_formation_asks_for(self) -> None:
        positions = ["GK", "CB", "CB", "LB", "RB", "CM", "CM", "CAM", "ST", "ST", "RW"]
        squad = [_player(f"p{index}", position, 70) for index, position in enumerate(positions)]
        bands = select_starting_xi(squad, defenders=4, midfielders=5, attackers=1)
        counts = (len(bands["keeper"]), len(bands["defence"]), len(bands["midfield"]), len(bands["attack"]))
        assert counts == (1, 4, 5, 1)
        assert len({player.id for band in bands.values() for player in band}) == 11

    def test_a_short_band_borrows_and_nobody_is_picked_twice(self) -> None:
        # Four defenders are wanted from a squad of five with two in the back line: the shortfall must
        # be filled from another band, nobody may appear twice, and the empty bands must read as empty
        # rather than being quietly invented.
        squad = [_player("k", "GK", 70), _player("d1", "CB", 70), _player("d2", "CB", 69), _player("m1", "CM", 72), _player("a1", "ST", 71)]
        bands = select_starting_xi(squad, defenders=4, midfielders=5, attackers=1)
        chosen = [player.id for band in bands.values() for player in band]
        assert len(chosen) == len(set(chosen)) == 5
        assert [player.id for player in bands["defence"]] == ["d1", "d2", "m1", "a1"]
        assert bands["midfield"] == [] and bands["attack"] == []

    def test_the_best_of_a_band_starts(self) -> None:
        squad = [_player("k", "GK", 70), _player("low", "ST", 60), _player("high", "ST", 80)]
        bands = select_starting_xi(squad, defenders=0, midfielders=0, attackers=1)
        assert [player.id for player in bands["attack"]] == ["high"]


def _player(player_id: str, position: str, overall: int) -> RealPlayer:
    player = RealPlayer(id=player_id, slug=player_id, name=player_id.title(), position=position, age=25, overall=overall, form=1.0)
    player.attributes = {key: overall for key in ("finishing", "passing", "tackling", "pressing", "positioning")}
    return player


class TestPossessionShare:
    def test_equal_midfields_split_the_ball_evenly(self) -> None:
        home, away = _profile(), _profile(team_id="T2")
        assert possession_share(home, away, home.tactics, away.tactics) == pytest.approx(0.5)

    def test_the_stronger_midfield_gets_more_until_the_ceiling_holds(self) -> None:
        weak = _profile(midfield=0.0)
        for midfield in (0.2, 0.5, 0.8, 1.0):
            share = possession_share(_profile(midfield=midfield), weak, {}, {})
            assert 0.24 <= share <= 0.76
        # Strictly increasing while the clip is not in play; at the top the share saturates by design,
        # so that no pair of midfields can be modelled into hoarding 90% of the ball.
        assert possession_share(_profile(midfield=0.4), weak, {}, {}) > possession_share(_profile(midfield=0.2), weak, {}, {})
        assert possession_share(_profile(midfield=1.0), weak, {}, {}) == possession_share(_profile(midfield=0.95), weak, {}, {}) == 0.76

    def test_no_home_advantage_is_baked_in(self) -> None:
        home = _profile(midfield=0.7)
        away = _profile(team_id="T2", midfield=0.3)
        forward = possession_share(home, away, home.tactics, away.tactics)
        flipped = possession_share(away, home, away.tactics, home.tactics)
        assert forward == pytest.approx(1.0 - flipped)


class TestDeterminism:
    def test_the_same_seed_and_inputs_replay_identically(self) -> None:
        first = simulate_match(_inputs())
        second = simulate_match(_inputs())
        assert first["digest"] == second["digest"]
        assert first == second

    def test_a_different_seed_is_a_different_match(self) -> None:
        reports = [simulate_match(_inputs(seed=seed)) for seed in (1, 2, 3, 4, 5)]
        digests = {report["digest"] for report in reports}
        assert len(digests) == len(reports)

    def test_changing_one_attribute_changes_the_match(self) -> None:
        base = simulate_match(_inputs())
        shifted = simulate_match(_inputs(away=_profile(team_id="T2", name="Southbank Rovers", defence=0.9)))
        assert base["digest"] != shifted["digest"]

    def test_the_fixture_order_in_a_list_does_not_change_a_report(self) -> None:
        """Each match forks on its own two clubs, so a schedule cannot shuffle results."""
        fixture_a = _inputs(seed=11)
        fixture_b = _inputs(seed=12, away=_profile(team_id="T3", name="Eastvale Athletic"))
        alone = simulate_match(fixture_a)
        with_a_neighbour = [simulate_match(m) for m in (fixture_b, fixture_a)]
        assert alone["digest"] == with_a_neighbour[1]["digest"]

    def test_a_shorter_match_is_its_own_simulation(self) -> None:
        assert simulate_match(_inputs(minutes=30))["digest"] != simulate_match(_inputs(minutes=90))["digest"]


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    """One match, played once for the ledger checks that compare totals against each other."""
    return simulate_match(_inputs(seed=21))


@pytest.fixture(scope="module")
def world_session() -> Iterator[SessionLocal]:  # type: ignore[valid-type]
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    yield session
    session.close()


@pytest.fixture(scope="module")
def world_teams(world_session) -> list[Team]:  # type: ignore[no-untyped-def]
    return list(world_session.scalars(select(Team).order_by(Team.slug).limit(2)))


class TestLedgersAddUp:
    def test_goals_match_goal_events_and_cannot_exceed_shots(self, report: dict[str, Any]) -> None:
        for side in ("home", "away"):
            row = report["sides"][side]
            goal_events = [event for event in report["events"] if event["type"] == "goal" and event["side"] == side]
            assert row["goals"] == len(goal_events) == report["score"][side]
            assert row["goals"] <= row["shots_on_target"] <= row["shots"]
            assert 0 <= row["expected_goals"]
            assert 0 < row["possession_pct"] < 100

    def test_scorers_came_from_their_own_eleven(self, report: dict[str, Any]) -> None:
        for side in ("home", "away"):
            lineup = {player["player"] for player in _lineup(report, side)}
            for event in report["events"]:
                if event["side"] == side:
                    assert event["player"] in lineup, f"{event['player']} is not in {side}'s eleven"

    def test_goal_events_carry_a_running_score_and_the_last_one_is_the_final_line(self, report: dict[str, Any]) -> None:
        goals = [event for event in report["events"] if event["type"] == "goal"]
        assert goals, "this fixture should produce at least one goal"
        assert all("-" in event["score"] for event in goals)
        assert goals[-1]["score"] == f"{report['score']['home']}-{report['score']['away']}"
        for earlier, later in zip(goals, goals[1:], strict=False):
            assert sum(map(int, earlier["score"].split("-"))) <= sum(map(int, later["score"].split("-")))

    def test_blocks_tile_the_match_and_end_on_the_final_score(self, report: dict[str, Any]) -> None:
        blocks = report["blocks"]
        assert len(blocks) == 15
        assert blocks[0]["minute_from"] == 1
        assert blocks[-1]["minute_to"] == 90
        for block, following in zip(blocks, blocks[1:], strict=False):
            assert following["minute_from"] == block["minute_to"] + 1
        assert blocks[-1]["home"]["cumulative"] == f"{report['score']['home']}-{report['score']['away']}"
        for side in ("home", "away"):
            assert sum(block[side]["goals"] for block in blocks) == report["score"][side]
            assert sum(block[side]["shots"] for block in blocks) == report["sides"][side]["shots"]
            # Every block records the multipliers it was played with, so a scoreline is traceable.
            assert {"attack_term", "stretch", "fatigue", "volume", "chance_quality"} <= set(block[side])

    def test_events_are_in_minute_order(self, report: dict[str, Any]) -> None:
        minutes = [event["minute"] for event in report["events"]]
        assert minutes == sorted(minutes)
        assert all(1 <= minute <= 90 for minute in minutes)

    def test_totals_agree_with_the_two_sides(self, report: dict[str, Any]) -> None:
        home, away = report["sides"]["home"], report["sides"]["away"]
        assert report["totals"]["shots"] == home["shots"] + away["shots"]
        assert report["totals"]["passes"] == home["passes"] + away["passes"]
        assert report["totals"]["goal_events"] == report["score"]["home"] + report["score"]["away"]
        assert home["possession_pct"] + away["possession_pct"] == pytest.approx(100.0, abs=0.2)

    def test_pass_accuracy_is_a_rate_of_its_own_attempts(self, report: dict[str, Any]) -> None:
        for side in ("home", "away"):
            row = report["sides"][side]
            assert 0 <= row["pass_completions"] <= row["passes"]
            assert row["pass_accuracy_pct"] == pytest.approx(100 * row["pass_completions"] / max(1, row["passes"]), abs=0.1)


class TestProvenance:
    def test_every_report_is_labelled_fiction_and_says_how_it_was_made(self) -> None:
        report = simulate_match(_inputs(seed=5))
        assert report["provenance"]["disclaimer"] == SIMULATION_DISCLAIMER
        assert report["provenance"]["data_origin"] == "simulation"
        assert report["provenance"]["is_demo_data"] is True
        model = report["model"]
        assert model["calibration"]
        assert model["coefficients"]["xg_big_chance"] > 0
        assert "no real match data" in model["calibration"]
        assert model["what_it_does_not_model"]
        for factor in model["factors"]:
            assert factor["expression"] and factor["reads"], factor
        assert {factor["key"] for factor in model["factors"]} >= {"possession_share", "shot_volume", "chance_quality", "fatigue"}

    def test_goals_and_expected_goals_are_reported_apart(self) -> None:
        report = simulate_match(_inputs(seed=9))
        for side in ("home", "away"):
            assert "expected_goals" in report["sides"][side]
            assert isinstance(report["sides"][side]["goals"], int)


class TestModelledEffects:
    def test_a_man_down_side_makes_fewer_chances_and_concedes_more(self) -> None:
        side = _Side(key="home", profile=_profile(), possession=0.5)
        opponent = _Side(key="away", profile=_profile(team_id="T2"), possession=0.5)
        level_volume, level_quality, _ = _volume_and_quality(side, opponent, 0.5)
        side.red_cards = 1
        down_volume, down_quality, _ = _volume_and_quality(side, opponent, 0.5)
        opponent_again = _Side(key="away", profile=_profile(team_id="T2"), possession=0.5)
        against_down, _, terms = _volume_and_quality(opponent_again, side, 0.5)
        assert down_volume < level_volume
        assert down_quality < level_quality
        assert against_down > level_volume
        assert terms["man_down_concede"] > 1.0

    def test_fatigue_is_crossed_with_late_space_and_form_decides_which_wins(self) -> None:
        """Two opposing drifts are modelled, and their trade-off is a claim worth pinning down.

        A side's own `fatigue` falls as the match runs on, while `late_space` — the gaps a tired
        opponent leaves — rises. For a low-form side fade wins, so its late volume is below its early
        volume; for a side in perfect form the drift wins, so late volume is above. If a coefficient is
        changed without noticing, this test is where it shows.
        """
        opponent = _Side(key="away", profile=_profile(team_id="T2"), possession=0.5)
        fresh = _Side(key="home", profile=_profile(form=1.0), possession=0.5)
        tiring = _Side(key="home", profile=_profile(form=0.0), possession=0.5)
        early_fresh, _, early_terms = _volume_and_quality(fresh, opponent, 0.05)
        late_fresh, _, _ = _volume_and_quality(fresh, opponent, 0.95)
        late_tiring, _, tiring_terms = _volume_and_quality(tiring, opponent, 0.95)
        assert tiring_terms["fatigue"] < early_terms["fatigue"]
        assert late_tiring < early_fresh < late_fresh
        assert late_fresh - early_fresh < 0.05  # the trade-off is a nudge, not a second wind

    def test_a_stretched_shape_makes_more_chances_than_a_deep_one(self) -> None:
        stretched = _Side(key="home", profile=_profile(tactics={"depth": 45.0, "width": 52.0, "line_separation": 16.0, "space_behind": 12.0}), possession=0.5)
        held = _Side(key="home", profile=_profile(tactics={"depth": 22.0, "width": 30.0, "line_separation": 16.0, "space_behind": 12.0}), possession=0.5)
        opponent = _Side(key="away", profile=_profile(team_id="T2"), possession=0.5)
        assert _volume_and_quality(stretched, opponent, 0.5)[0] > _volume_and_quality(held, opponent, 0.5)[0]

    def test_a_side_can_finish_over_or_under_its_expected_goals(self) -> None:
        """Bernoulli finishing means xG is a companion number, never a rounding of the scoreline."""
        gaps = []
        for seed in range(1, 13):
            report = simulate_match(_inputs(seed=seed))
            gaps.append(report["sides"]["home"]["goals"] - report["sides"]["home"]["expected_goals"])
        assert any(gap > 0.4 for gap in gaps) or any(gap < -0.4 for gap in gaps)


class TestSubstitutions:
    """A substitution is modelled as fresh legs — a bounded, deterministic boost to midfield and attack
    from a fixed minute. The default path (substitutions=0) must stay byte-identical to before, so the
    selected eleven still plays on and every existing determinism test still holds.
    """

    def test_default_path_leaves_no_substitution_and_replays_identically(self) -> None:
        first = simulate_match(_inputs(seed=7))
        second = simulate_match(_inputs(seed=7))
        assert first["substitutions"] == []
        assert first["digest"] == second["digest"]

    def test_a_substitution_is_deterministic_and_reported_for_both_sides(self) -> None:
        """The same seed and inputs replay identically, and each side records one fresh-legs sub."""
        first = simulate_match(_inputs(seed=7, substitutions=1))
        second = simulate_match(_inputs(seed=7, substitutions=1))
        assert first["digest"] == second["digest"]
        subs = first["substitutions"]
        assert len(subs) == 2, f"both sides should record a substitution, saw {subs!r}"
        assert {entry["side"] for entry in subs} == {"home", "away"}
        for entry in subs:
            assert entry["minute"] >= 54, f"the sub fires from the fixed minute, saw {entry!r}"
            assert "fresh legs" in entry["detail"]

    def test_a_substitution_changes_the_digest_but_names_no_player(self) -> None:
        """The fresh-legs path is a different match from the default one, and the engine still refuses to
        credit a player it never selected: the substitution event carries an empty player name."""
        default = simulate_match(_inputs(seed=7))
        with_sub = simulate_match(_inputs(seed=7, substitutions=1))
        assert default["digest"] != with_sub["digest"]

        sub_events = [event for event in with_sub["events"] if event["type"] == "substitution"]
        assert len(sub_events) == 2, f"two substitution events expected, saw {len(sub_events)}"
        for event in sub_events:
            assert event["player"] == "", "a substitution names no player — it is an energy effect"
            assert event["type"] == "substitution"

    def test_substitution_fresh_legs_is_a_published_factor(self) -> None:
        report = simulate_match(_inputs(seed=7, substitutions=1))
        assert {"substitution_fresh_legs"}.issubset({factor["key"] for factor in report["model"]["factors"]})


class TestTacticalShift:
    """A tactical shift is a scripted, set-minute push by the side trailing on goals: a bounded midfield and
    attack lift that recomputes possession share and raises chance quality. The default
    (tactical_shift_minute=0) must stay untouched, so the digest is identical to before.
    """

    def test_default_path_leaves_no_shift_and_replays_identically(self) -> None:
        first = simulate_match(_inputs(seed=7))
        second = simulate_match(_inputs(seed=7))
        assert first["tactical_shift"] == []
        assert first["digest"] == second["digest"]

    def _seed_with_a_shift(self, minute: int = 60) -> tuple[int, dict[str, Any]]:
        for seed in range(1, 200):
            report = simulate_match(_inputs(seed=seed, tactical_shift_minute=minute))
            if report["tactical_shift"]:
                return seed, report
        raise AssertionError("no seed in range produced a trailing side at the shift minute")

    def test_a_shift_is_deterministic_names_no_player_and_is_published(self) -> None:
        seed, report = self._seed_with_a_shift()
        again = simulate_match(_inputs(seed=seed, tactical_shift_minute=60))
        assert report["digest"] == again["digest"]
        events = [event for event in report["events"] if event["type"] == "tactical_shift"]
        assert len(events) == 1, f"exactly one shift event expected, saw {events!r}"
        assert events[0]["player"] == "", "a tactical shift names no player — it is a posture change"
        assert events[0]["side"] in {"home", "away"}
        assert {"tactical_shift", "substitution_fresh_legs"}.issubset(
            {factor["key"] for factor in report["model"]["factors"]}
        )

    def test_a_shift_changes_the_digest_when_a_side_is_behind(self) -> None:
        seed, _ = self._seed_with_a_shift()
        default = simulate_match(_inputs(seed=seed))
        shifted = simulate_match(_inputs(seed=seed, tactical_shift_minute=60))
        assert default["digest"] != shifted["digest"]


class TestMomentum:
    """Momentum is a pre-match, per-side authored edge (0..1): a side riding form attacks and presses with
    more conviction from kick-off. Default 0 leaves the profile untouched, so the digest is identical to before.
    """

    def test_default_path_leaves_no_momentum_effect_and_replays_identically(self) -> None:
        first = simulate_match(_inputs(seed=7))
        second = simulate_match(_inputs(seed=7))
        assert first["momentum"] == {"home": 0.0, "away": 0.0}
        assert first["digest"] == second["digest"]

    def test_momentum_is_deterministic_and_changes_the_digest(self) -> None:
        first = simulate_match(_inputs(seed=7, home_momentum=1.0))
        second = simulate_match(_inputs(seed=7, home_momentum=1.0))
        assert first["digest"] == second["digest"]
        default = simulate_match(_inputs(seed=7))
        assert default["digest"] != first["digest"]

    def test_momentum_boosts_only_the_named_side(self) -> None:
        default = simulate_match(_inputs(seed=7))
        with_momentum = simulate_match(_inputs(seed=7, home_momentum=1.0))
        home_default = default["sides"]["home"]["indices"]
        home_boosted = with_momentum["sides"]["home"]["indices"]
        away_default = default["sides"]["away"]["indices"]
        away_boosted = with_momentum["sides"]["away"]["indices"]
        assert home_boosted["attack"] > home_default["attack"], "home momentum should lift home attack"
        assert home_boosted["press"] > home_default["press"], "home momentum should lift home press"
        assert away_boosted["attack"] == away_default["attack"], "away should be untouched by home momentum"
        assert away_boosted["press"] == away_default["press"]

    def test_momentum_is_a_published_factor(self) -> None:
        report = simulate_match(_inputs(seed=7, home_momentum=1.0))
        assert {"momentum"}.issubset({factor["key"] for factor in report["model"]["factors"]})


class TestProfilesFromStoredRows:
    """`team_profile` must compute from the world the generator wrote, not from numbers this test picks."""

    def test_indices_land_in_the_documented_range(self, world_session, world_teams) -> None:  # type: ignore[no-untyped-def]
        for team in world_teams:
            profile = team_profile(world_session, team.id)
            assert len(profile.lineup) == 11
            for value in (profile.attack, profile.midfield, profile.defence, profile.keeper, profile.press, profile.form, profile.overall):
                assert 0.0 <= value <= 1.0
            assert profile.formation == team.formation

    def test_every_index_travels_with_the_formula_that_produced_it(self, world_session, world_teams) -> None:
        profile = team_profile(world_session, world_teams[0].id)
        keys = {metric.key for metric in profile.factors}
        assert {"attack_index", "midfield_index", "defence_index", "keeper_index", "press_index", "form_index", "squad_index"} <= keys
        assert all(metric.formula for metric in profile.factors)
        keeper = next(metric for metric in profile.factors if metric.key == "keeper_index")
        assert "no goalkeeping attribute" in keeper.formula  # honest about the world's missing attribute

    def test_the_shape_selects_the_eleven_so_two_formations_differ(self, world_session, world_teams) -> None:
        """A 4-4-2 and a back three genuinely put different players forward, and the indices move."""
        by_formation: dict[str, Any] = {}
        for system in tactical_systems():
            by_formation.setdefault(system.formation, system)
        first, second = sorted(by_formation)[:2]
        assert first != second, "the authored systems should offer more than one formation"
        team = world_teams[0]
        profile_a = team_profile(world_session, team.id, system_slug=by_formation[first].slug)
        profile_b = team_profile(world_session, team.id, system_slug=by_formation[second].slug)
        assert profile_a.formation == first and profile_b.formation == second
        assert _band_counts(profile_a) != _band_counts(profile_b)
        assert len(profile_a.lineup) == len(profile_b.lineup) == 11
        assert profile_a.tactics and profile_b.tactics
        assert (profile_a.tactics["width"], profile_a.tactics["depth"]) != (profile_b.tactics["width"], profile_b.tactics["depth"])
        for key in ("width", "depth", "line_separation"):
            assert any(metric.key == f"tactics_{key}" for metric in profile_a.factors)

    def test_missing_rows_are_refused_rather_than_invented(self, world_session, world_teams) -> None:
        with pytest.raises(LookupError, match="no team"):
            team_profile(world_session, "team-that-does-not-exist")
        with pytest.raises(LookupError, match="no tactical system"):
            team_profile(world_session, world_teams[0].id, system_slug="not-a-system")

    def test_a_real_fixture_between_two_real_clubs_is_labelled_and_consistent(self, world_session, world_teams) -> None:
        system = tactical_systems()[3].slug
        inputs = MatchInputs(
            home=team_profile(world_session, world_teams[0].id, system_slug=system),
            away=team_profile(world_session, world_teams[1].id, system_slug=tactical_systems()[7].slug),
            seed=101,
        )
        report = simulate_match(inputs)
        assert report["provenance"]["data_origin"] == "simulation"
        assert report["sides"]["home"]["name"] == world_teams[0].name
        assert report["sides"]["home"]["system_slug"] == system
        assert 24.0 <= report["possession_share"]["home"] * 100 <= 76.0
        assert report["score"]["home"] == report["sides"]["home"]["goals"]
        assert simulate_match(inputs)["digest"] == report["digest"]

    def test_indices_recompute_from_the_squad_that_is_actually_stored(self, world_session, world_teams) -> None:
        team = world_teams[0]
        profile = team_profile(world_session, team.id)
        squad = list(world_session.scalars(select(RealPlayer).where(RealPlayer.team_id == team.id)))
        selected = profile.to_dict()["lineup"]
        attack_names = [entry["player"] for entry in selected if entry["band"] == "attack"]
        assert attack_names, "a shape always selects at least one forward"
        assert {entry["player"] for entry in selected} <= {player.name for player in squad}
        # The attack index is the mean of the stored attributes of exactly the forwards named above.
        stored = {player.name: player for player in squad}
        forwards = [stored[name] for name in attack_names]
        keys = ("finishing", "off_ball_movement", "dribbling", "decision_making", "speed", "acceleration")
        values = [player.attributes[key] for player in forwards for key in keys]
        assert profile.attack == pytest.approx(max(0.0, min(1.0, (sum(values) / len(values) - 28.0) / 68.0)), abs=1e-6)

    def test_the_report_names_the_eleven_it_creditied(self, world_session, world_teams) -> None:
        inputs = MatchInputs(
            home=team_profile(world_session, world_teams[0].id),
            away=team_profile(world_session, world_teams[1].id),
            seed=77,
        )
        report = simulate_match(inputs)
        for side in ("home", "away"):
            assert len(_lineup(report, side)) == 11
            assert {entry["player"] for entry in _lineup(report, side)} <= {entry["player"] for entry in (inputs.home if side == "home" else inputs.away).to_dict()["lineup"]}

    def test_the_report_carries_the_measurements_behind_its_indices(self, world_session, world_teams) -> None:
        """A side block ships the metres and the factor formulas it was built from (spec §60)."""
        systems = tactical_systems()
        inputs = MatchInputs(
            home=team_profile(world_session, world_teams[0].id, system_slug=systems[3].slug),
            away=team_profile(world_session, world_teams[1].id, system_slug=systems[11].slug),
            seed=131,
        )
        report = simulate_match(inputs)
        for side, profile in (("home", inputs.home), ("away", inputs.away)):
            measured = report["sides"][side]["inputs"]
            assert set(measured["tactics"]) == set(profile.tactics)
            assert measured["tactics"]["width"] == pytest.approx(profile.tactics["width"], abs=0.01)
            keys = {factor["key"] for factor in measured["factors"]}
            assert {"attack_index", "midfield_index", "defence_index", "press_index", "tactics_width"} <= keys
            assert all(str(factor["formula"]).strip() for factor in measured["factors"])
            values = {factor["key"]: factor["value"] for factor in measured["factors"]}
            assert values["midfield_index"] == round(profile.midfield, 2)
            assert values["tactics_width"] == round(profile.tactics["width"], 2)


def _band_counts(profile: SideProfile) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _name, _position, band in profile.lineup:
        counts[band] = counts.get(band, 0) + 1
    return counts


def _lineup(report: dict[str, Any], side: str) -> list[dict[str, str]]:
    """The eleven the profile selected, carried into the report's side block for the reader to audit."""
    return report["sides"][side]["lineup"]
