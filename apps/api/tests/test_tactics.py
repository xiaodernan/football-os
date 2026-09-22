"""M4 Tactical Lab: the geometry is right, the catalogue is complete, and every claim cites its number.

This layer is pure — metres in, numbers out, no database and no clock — so the interesting tests are
the ones that check the *meaning* of a measurement (does a low block really defend closer to its own
goal than a high press?) rather than only that a function returns a float.
"""

from __future__ import annotations

import math
import re

import pytest

from app.services.tactics.analysis import CHANGES, analyse, apply_change, in_possession, metrics_of, out_of_possession
from app.services.tactics.pitch import (
    HALF_WIDTH,
    PITCH_LENGTH,
    PITCH_WIDTH,
    Point,
    centroid,
    clamp_point,
    distance,
    lane_of,
    nearest_neighbour_distances,
    out_of_bounds,
    third_of,
    zone_of,
)
from app.services.tactics.plan import PROVENANCE, SYSTEM_COUNT, fingerprint, planned_rows, system_by_slug, tactical_problems, tactical_systems
from app.services.tactics.roles import BANDS, ROLES, TACTICAL_ATTRIBUTES
from app.services.tactics.shapes import FORMATION_SHAPES, TEMPERAMENTS, Slot, _shape
from app.services.world.plan import content_hash

SAFE_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
METRIC_KEYS = {"width", "depth", "coverage", "balance", "spacing", "isolation", "line_separation", "space_behind"}


def y_span(points: tuple[Point, ...]) -> float:
    ys = [point.y for point in points]
    return max(ys) - min(ys)


class TestGeometry:
    def test_a_point_that_is_not_a_number_cannot_enter_the_model(self) -> None:
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="non-finite"):
                Point(bad, 10.0)

    @pytest.mark.parametrize(("x", "y"), [(-HALF_WIDTH, 0.0), (HALF_WIDTH, PITCH_LENGTH), (0.0, 52.5)])
    def test_the_corner_cases_of_the_pitch_are_inside_it(self, x: float, y: float) -> None:
        assert out_of_bounds(Point(x, y)) == []

    def test_off_the_grass_is_named_not_silently_clamped(self) -> None:
        problems = out_of_bounds(Point(80.0, -3.0))
        assert len(problems) == 2
        assert any("x=80.0" in problem for problem in problems)
        clamped = clamp_point(Point(80.0, -3.0))
        assert clamped.x == HALF_WIDTH and clamped.y == 0.0

    def test_a_translation_is_clamped_back_inside_the_pitch(self) -> None:
        assert Point(30.0, 100.0).scaled(10.0, 10.0) == Point(HALF_WIDTH, PITCH_LENGTH)

    def test_three_points_50_metres_from_the_own_goal_are_the_middle_third(self) -> None:
        assert third_of(Point(0.0, 50.0)) == "middle"
        assert third_of(Point(0.0, 20.0)) == "defensive"
        assert third_of(Point(0.0, 95.0)) == "attacking"

    @pytest.mark.parametrize(("x", "lane"), [(-30.0, "LW"), (-12.0, "LC"), (0.0, "C"), (12.0, "RC"), (30.0, "RW")])
    def test_the_five_channels_tile_the_width(self, x: float, lane: str) -> None:
        assert lane_of(Point(x, 50.0)) == lane

    def test_a_zone_is_third_and_channel_together(self) -> None:
        assert zone_of(Point(30.0, 80.0)) == "attacking-RW"

    def test_nearest_teammate_distance_for_a_known_line_of_three(self) -> None:
        points = [Point(-5.0, 40.0), Point(0.0, 40.0), Point(9.0, 40.0)]
        assert [round(value, 2) for value in nearest_neighbour_distances(points)] == [5.0, 5.0, 9.0]

    def test_centroid_of_nothing_is_an_error_not_a_zero(self) -> None:
        with pytest.raises(ValueError, match="undefined"):
            centroid([])

    def test_distance_is_symmetric_and_euclidean(self) -> None:
        a, b = Point(-10.0, 20.0), Point(20.0, 60.0)
        assert distance(a, b) == distance(b, a) == math.hypot(30.0, 40.0)


class TestAuthoredData:
    def test_ten_shapes_and_five_temperaments_make_the_gate(self) -> None:
        assert len(FORMATION_SHAPES) == 10
        assert len(TEMPERAMENTS) == 5
        assert len(FORMATION_SHAPES) * len(TEMPERAMENTS) == SYSTEM_COUNT

    @pytest.mark.parametrize("name", sorted(FORMATION_SHAPES))
    def test_every_shape_is_eleven_players_with_one_keeper_on_the_grass(self, name: str) -> None:
        shape = FORMATION_SHAPES[name]
        assert len(shape) == 11
        assert sum(1 for slot in shape if slot.role == "GK") == 1
        assert all(out_of_bounds(slot.point()) == [] for slot in shape)
        assert all(slot.role in ROLES for slot in shape)

    def test_a_shape_missing_a_player_is_refused_at_import_time(self) -> None:
        with pytest.raises(ValueError, match="11 slots"):
            _shape(*(("DCB", 0.0, 20.0) for _ in range(10)))
        with pytest.raises(ValueError, match="unknown role"):
            _shape(*[(slot.role, slot.x, slot.y) for slot in FORMATION_SHAPES["4-3-3"][:9]], ("WINGER", 20.0, 60.0), ("ST", 0.0, 74.0))
        with pytest.raises(ValueError, match="off the grass"):
            _shape(*[(slot.role, slot.x, slot.y) for slot in FORMATION_SHAPES["4-3-3"][:9]], ("ST", 90.0, 74.0), ("ST", -90.0, 74.0))

    def test_no_role_is_dead_catalogue_weight(self) -> None:
        """A role nothing ever fields is documentation, not data: it cannot be selected or graded."""
        used = {slot.role for shape in FORMATION_SHAPES.values() for slot in shape}
        assert used <= set(ROLES)
        assert set(ROLES) - used == set(), f"roles nothing plays: {sorted(set(ROLES) - used)}"

    @pytest.mark.parametrize("key", sorted(ROLES))
    def test_every_role_describes_both_phases_differently(self, key: str) -> None:
        role = ROLES[key]
        assert role.band in BANDS
        assert role.in_possession != role.out_of_possession
        assert role.instructions and role.risk
        assert set(role.demands) <= set(TACTICAL_ATTRIBUTES)
        assert all(0 < level <= 99 for level in role.demands.values())

    @pytest.mark.parametrize("key", sorted(TEMPERAMENTS))
    def test_a_temperament_describes_a_block_that_fits_the_pitch(self, key: str) -> None:
        temperament = TEMPERAMENTS[key]
        assert 0.0 < temperament.press_line_y - temperament.block_depth < temperament.press_line_y < PITCH_LENGTH
        assert 0.5 < temperament.defensive_narrowing <= 1.0
        assert temperament.in_possession_deltas, "a temperament that changes nothing is not a temperament"
        assert temperament.instructions


class TestTransforms:
    def test_in_possession_applies_the_documented_shift(self) -> None:
        shape = in_possession(FORMATION_SHAPES["4-3-3"], TEMPERAMENTS["press-high"])
        # The base right-back stands at y=24 and the high press pushes full-backs +11 m.
        assert shape.slots[1].role == "RB"
        assert shape.points[1].y == pytest.approx(35.0)
        assert shape.points[1].x == pytest.approx(27.0)
        # A role the temperament says nothing about keeps its authored coordinate exactly.
        assert shape.slots[2].role == "DCB"
        assert shape.points[2] == Point(9.0, 20.0)

    def test_out_of_possession_is_a_rescale_of_the_same_eleven(self) -> None:
        attacking = in_possession(FORMATION_SHAPES["4-4-2"], TEMPERAMENTS["low-block"])
        defending = out_of_possession(attacking, TEMPERAMENTS["low-block"])
        temperament = TEMPERAMENTS["low-block"]
        outfield = defending.outfield()
        assert len(defending.points) == len(attacking.points) == 11
        # The block's vertical span is exactly the authored depth, and its top is the press line.
        assert max(point.y for point in outfield) == pytest.approx(temperament.press_line_y, abs=0.01)
        assert y_span(outfield) == pytest.approx(temperament.block_depth, abs=0.01)
        assert min(point.y for point in defending.points) <= 4.0, "the keeper stays on its line"
        assert all(out_of_bounds(point) == [] for point in defending.points)

    def test_narrowing_shrinks_the_width_and_never_moves_it_across_the_midline(self) -> None:
        attacking = in_possession(FORMATION_SHAPES["3-5-2"], TEMPERAMENTS["low-block"])
        defending = out_of_possession(attacking, TEMPERAMENTS["low-block"])
        before = max(point.x for point in attacking.outfield())
        after = max(point.x for point in defending.outfield())
        assert after == pytest.approx(before * TEMPERAMENTS["low-block"].defensive_narrowing)
        assert (after > 0) == (before > 0)

    @pytest.mark.parametrize("name", sorted(FORMATION_SHAPES))
    def test_every_shape_survives_every_temperament_on_the_grass(self, name: str) -> None:
        for key, temperament in TEMPERAMENTS.items():
            attacking = in_possession(FORMATION_SHAPES[name], temperament)
            defending = out_of_possession(attacking, temperament)
            assert all(out_of_bounds(point) == [] for point in (*attacking.points, *defending.points)), f"{name}/{key}"


class TestMetrics:
    def test_the_eight_metrics_are_all_measured_in_metres_or_square_metres(self) -> None:
        shape = in_possession(FORMATION_SHAPES["4-2-3-1"], TEMPERAMENTS["control-possession"])
        metrics = metrics_of(shape)
        assert {metric.key for metric in metrics} == METRIC_KEYS
        assert all(metric.unit in {"m", "m²"} for metric in metrics)
        assert all(metric.formula for metric in metrics)

    def test_no_measurement_can_exceed_the_pitch(self) -> None:
        for system in tactical_systems():
            for phase in ("in", "out"):
                values = {metric.key: metric.value for metric in system.metrics(phase)}
                assert 0.0 <= values["width"] <= PITCH_WIDTH
                assert 0.0 <= values["depth"] <= PITCH_LENGTH
                assert values["coverage"] <= PITCH_WIDTH * PITCH_LENGTH
                assert math.isfinite(values["spacing"]) and values["isolation"] >= values["spacing"]

    def test_a_low_block_defends_closer_to_its_own_goal_than_a_high_press(self) -> None:
        """The ordering the vocabulary promises, checked in the numbers rather than asserted in prose."""
        press = system_by_slug("4-3-3-press-high")
        block = system_by_slug("4-3-3-low-block")
        behind = {phase: {metric.key: metric.value for metric in system.metrics(phase)}["space_behind"] for system, phase in ((press, "out"), (block, "out"))}
        assert behind["out"] > 0
        assert {metric.key: metric.value for metric in block.metrics("out")}["space_behind"] < {metric.key: metric.value for metric in press.metrics("out")}["space_behind"]
        assert {metric.key: metric.value for metric in block.metrics("out")}["spacing"] < {metric.key: metric.value for metric in press.metrics("out")}["spacing"]


class TestCounterfactuals:
    def test_every_change_is_offered_for_every_shape(self) -> None:
        shape = in_possession(FORMATION_SHAPES["4-1-4-1"], TEMPERAMENTS["direct-transition"])
        assert {diff.change.key for diff in analyse(shape)} == set(CHANGES)

    def test_a_change_moves_exactly_the_slots_it_names_and_no_others(self) -> None:
        shape = in_possession(FORMATION_SHAPES["3-5-2"], TEMPERAMENTS["press-high"])
        after = apply_change(shape, CHANGES["narrow-midfield"])
        for slot, before, moved in zip(shape.slots, shape.points, after.points, strict=True):
            change = CHANGES["narrow-midfield"]
            expected = clamp_point(Point(before.x * change.scale_x, before.y)) if change.matches(slot) else before
            assert moved == expected, f"{slot.role} moved to {moved}, not the documented {expected}"
            if not change.matches(slot):
                assert moved == before, f"{slot.role} was touched by a change that does not name it"
        outfield_bands = {"defensive", "midfield", "attacking"}
        for slot in shape.slots:
            band = ROLES[slot.role].band
            reachable = any(change.matches(slot) for change in CHANGES.values())
            assert reachable == (band in outfield_bands), f"{slot.role} ({band}) reachable by a change: {reachable}"
        assert CHANGES["narrow-midfield"].target, "a change must say who it moves"

    def test_raising_the_back_line_costs_exactly_the_metres_it_buys(self) -> None:
        shape = in_possession(FORMATION_SHAPES["4-3-3"], TEMPERAMENTS["control-possession"])
        diff = next(item for item in analyse(shape) if item.change.key == "raise-back-line")
        moved = {before.key: (before.value, after.value, delta) for before, after, delta in diff.moved}
        assert moved["space_behind"][2] == pytest.approx(8.0)
        assert moved["depth"][2] == pytest.approx(-8.0), "the same team, 8 m taller and 8 m shorter at once"
        assert moved["coverage"][2] < 0
        assert moved["line_separation"][2] < 0

    def test_a_counterfactual_never_invents_a_movement(self) -> None:
        """`widen-front` scales x only: no y may move, so the panel cannot claim a height change."""
        shape = in_possession(FORMATION_SHAPES["3-4-3"], TEMPERAMENTS["press-high"])
        after = apply_change(shape, CHANGES["widen-front"])
        for before_point, after_point, slot in zip(shape.points, after.points, shape.slots, strict=True):
            assert before_point.y == after_point.y
            if ROLES[slot.role].band != "attacking":
                assert before_point.x == after_point.x

    def test_a_change_cannot_walk_a_player_off_the_pitch(self) -> None:
        shape = in_possession(FORMATION_SHAPES["5-3-2"], TEMPERAMENTS["press-high"])
        for change in CHANGES.values():
            moved = apply_change(shape, change)
            assert all(out_of_bounds(point) == [] for point in moved.points), change.key

    def test_only_moved_metrics_are_reported(self) -> None:
        shape = in_possession(FORMATION_SHAPES["4-4-2"], TEMPERAMENTS["low-block"])
        for diff in analyse(shape):
            assert {metric.key for metric in diff.before} == {metric.key for metric in diff.after}
            for before, after, delta in diff.moved:
                assert abs(after.value - before.value) == pytest.approx(abs(delta))
                assert abs(delta) >= 0.05, f"{diff.change.key} reported {before.key} as moved by {delta}"
            reported = {before.key for before, _, _ in diff.moved}
            recomputed = {before.key for before, after in zip(diff.before, diff.after, strict=True) if abs(after.value - before.value) >= 0.05}
            assert reported == recomputed


class TestCatalogue:
    def test_the_gate_is_fifty_systems_with_no_problems(self) -> None:
        systems = tactical_systems()
        assert len(systems) == SYSTEM_COUNT
        assert tactical_problems(systems) == []

    def test_the_plan_is_reproducible_across_a_cold_start(self) -> None:
        first = fingerprint()
        tactical_systems.cache_clear()
        assert fingerprint() == first
        tactical_systems.cache_clear()

    def test_keys_and_slugs_are_unique_and_url_safe(self) -> None:
        systems = tactical_systems()
        assert len({system.key for system in systems}) == SYSTEM_COUNT
        for system in systems:
            assert SAFE_SLUG.match(system.slug), system.slug
            assert len(system.slug) <= 160
            assert system.path() == f"/tactics/{system.slug}"

    def test_a_row_carries_both_phases_and_the_provenance_of_both(self) -> None:
        row = system_by_slug("4-2-3-1-press-high").payload()
        assert len(row["phase_in"]) == 11 and len(row["phase_out"]) == 11
        assert row["data_origin"] == PROVENANCE["data_origin"]
        assert row["is_demo_data"] is False
        assert "no tracking data" in row["disclaimer"]
        assert row["counterfactuals"], "the board needs something to ask"
        assert all(slot["band"] in BANDS for slot in row["phase_in"])

    def test_every_verdict_quotes_the_number_it_was_decided_from(self) -> None:
        fallbacks = ("shows no extreme measurement", "sits in an extreme quartile")
        computed = 0
        for system in tactical_systems():
            for sentence in (*system.strengths, *system.risks):
                if any(marker in sentence for marker in fallbacks):
                    continue
                computed += 1
                assert re.search(r"\d+\.\d m", sentence), f"{system.key}: {sentence}"
                assert re.search(r"\d+(st|nd|rd|th) percentile, (lowest quartile|highest quartile|middle half)", sentence), sentence
        assert computed >= SYSTEM_COUNT, "the catalogue is graded against itself, so most systems should have a measured verdict"

    def test_the_catalogue_separates_the_temperaments_it_claims_to(self) -> None:
        """If 'high press' and 'low block' measured the same geometry, the words would be decoration."""
        by_phase: dict[str, list[float]] = {"press-high": [], "low-block": []}
        for system in tactical_systems():
            if system.temperament_key in by_phase:
                by_phase[system.temperament_key].append({metric.key: metric.value for metric in system.metrics("out")}["space_behind"])
        assert min(by_phase["press-high"]) > max(by_phase["low-block"])

    def test_planned_rows_are_one_per_system_and_hash_stable(self) -> None:
        rows = planned_rows()
        assert len(rows) == SYSTEM_COUNT
        assert len({row.natural_key for row in rows}) == SYSTEM_COUNT
        for row in rows:
            assert row.content_hash == content_hash(row.payload)
        assert all(row.payload["natural_key"] == row.natural_key for row in rows)

    def test_an_unknown_slug_is_not_a_system(self) -> None:
        assert system_by_slug("4-4-2-tiki-taka") is None

    def test_a_slot_without_a_label_still_renders(self) -> None:
        slot = Slot("ST", 0.0, 70.0)
        assert slot.point() == Point(0.0, 70.0)
        assert ROLES[slot.role].label
