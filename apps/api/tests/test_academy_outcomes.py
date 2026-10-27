"""The career academy's outcomes: the class is judged by the engine's own selection, not by opinion.

The claims worth pinning:

* the projection is the development curve applied to the stored overall — the same arithmetic the
  `development` block applies per attribute, so the two can never disagree about a player;
* the verdicts come from the engine's own `select_starting_xi` over the career's current squad, so a
  `selected` trainee is one the next round would actually hand a shirt to;
* the block is recomputed from the rows on every read: two reads agree, and the figures can be
  re-derived from `career_appearances` and the world's training sessions by the test itself.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import CAREER_PHLOSOPHIES, Career, CareerAppearance, RealPlayer, Team, User
from app.services.simulation import career as career_service
from app.services.simulation.academy import YOUTH_AGE_MAX, academy_class
from app.services.simulation.carry_over import training_loads
from app.services.simulation.development import TRAINING_MINUTES_PER_UNIT, developed_attributes, developed_overall
from app.services.simulation.profile import band_of_position, select_starting_xi, split_formation
from app.services.simulation.squad import current_squad
from app.services.world import sync_world


def test_zero_minutes_leaves_the_overall_unchanged() -> None:
    assert developed_overall(63.0, potential=80, minutes_played=0) == 63.0


def test_the_overall_projection_is_deterministic_and_saturating() -> None:
    low = developed_overall(58.0, potential=82, minutes_played=900)
    mid = developed_overall(58.0, potential=82, minutes_played=3000)
    high = developed_overall(58.0, potential=82, minutes_played=12000)
    assert low < mid < high, f"the projection must rise with minutes: {low}, {mid}, {high}"
    assert high < 82.0, f"the curve never crosses potential: saw {high}"
    again = developed_overall(58.0, potential=82, minutes_played=3000)
    assert mid == again, "the same minutes must project the same overall"


def test_no_growth_when_already_at_potential() -> None:
    assert developed_overall(80.0, potential=80, minutes_played=5000) == 80.0
    assert developed_overall(85.0, potential=80, minutes_played=5000) == 85.0


def test_the_overall_projection_matches_the_attribute_curve() -> None:
    for minutes in (0, 1500, 3000, 9000):
        expected = developed_attributes(minutes, potential=80, attributes={"finishing": 55})["finishing"]
        assert round(developed_overall(55, potential=80, minutes_played=minutes)) == expected, f"the scalar projection and the attribute curve disagree at {minutes} minutes"


def _player(pid: str, position: str, *, age: int, overall: int, potential: int = 85) -> RealPlayer:
    return RealPlayer(id=pid, slug=pid, name=pid.upper(), position=position, age=age, overall=overall, potential=potential)


def _eleven(squad: list[RealPlayer], formation: str) -> tuple[set[str], dict[str, int]]:
    defenders, midfielders, attackers = split_formation(formation)
    bands = select_starting_xi(squad, defenders, midfielders, attackers)
    eleven = [player for group in bands.values() for player in group]
    seats: dict[str, int] = {}
    for player in eleven:
        band = band_of_position(player.position)
        seats[band] = seats.get(band, 0) + 1
    return {player.id for player in eleven}, seats


def test_an_adult_only_squad_is_an_empty_class() -> None:
    squad = [_player("old-1", "CB", age=29, overall=70), _player("old-2", "ST", age=31, overall=68)]
    selected, seats = _eleven(squad, "4-4-2")
    rows = academy_class(squad, selected_ids=selected, seats_per_band=seats, loads={})
    assert rows == [], "a squad with no under-21 players has no youth class to report"


def test_the_best_young_attacker_is_selected_by_the_engine_s_own_eleven() -> None:
    squad = [
        _player("gk-1", "GK", age=30, overall=72),
        _player("df-1", "CB", age=28, overall=71),
        _player("df-2", "CB", age=26, overall=69),
        _player("df-3", "CB", age=27, overall=68),
        _player("df-4", "CB", age=25, overall=67),
        _player("df-5", "CB", age=24, overall=66),
        _player("mf-1", "CM", age=29, overall=70),
        _player("mf-2", "CM", age=28, overall=69),
        _player("mf-3", "CM", age=27, overall=68),
        _player("mf-4", "CM", age=26, overall=67),
        _player("kid-st", "ST", age=19, overall=74),
        _player("st-1", "ST", age=28, overall=72),
        _player("st-2", "ST", age=30, overall=70),
        _player("kid-cb", "CB", age=18, overall=60),
    ]
    selected, seats = _eleven(squad, "4-4-2")
    rows = academy_class(squad, selected_ids=selected, seats_per_band=seats, loads={})
    by_id = {row["player_id"]: row for row in rows}
    assert set(by_id) == {"kid-st", "kid-cb"}, f"exactly the two under-21 players form the class, got {sorted(by_id)}"
    assert by_id["kid-st"]["verdict"] == "selected", "the class's best attacker must be in the engine's own eleven"
    assert by_id["kid-cb"]["verdict"] == "off_the_pace"
    assert by_id["kid-cb"]["band_rank"] == 6, "the young defender is sixth of six defenders, behind the adult reserve too"
    assert by_id["kid-cb"]["seats_in_band"] == 4
    assert by_id["kid-cb"]["gap_to_last_seat"] == round(67.0 - 60.0, 1), "the gap is the last defender seat's stored overall minus his"


def test_the_first_reserve_of_a_band_is_next_in_line() -> None:
    squad = [
        _player("gk-1", "GK", age=30, overall=72),
        _player("df-1", "CB", age=28, overall=71),
        _player("df-2", "CB", age=26, overall=69),
        _player("df-3", "CB", age=27, overall=68),
        _player("df-4", "CB", age=25, overall=67),
        _player("mf-1", "CM", age=29, overall=70),
        _player("mf-2", "CM", age=28, overall=69),
        _player("mf-3", "CM", age=27, overall=68),
        _player("mf-4", "CM", age=26, overall=67),
        _player("mf-5", "CM", age=25, overall=66),
        _player("kid-mf", "CM", age=20, overall=66),
        _player("st-1", "ST", age=28, overall=72),
        _player("st-2", "ST", age=30, overall=70),
    ]
    selected, seats = _eleven(squad, "4-4-2")
    rows = academy_class(squad, selected_ids=selected, seats_per_band=seats, loads={})
    by_id = {row["player_id"]: row for row in rows}
    # Level on overall with mf-5, the trainee still wins the slug tiebreak ("kid-mf" < "mf-5"), so he
    # is the band's fifth name: the first the shape would reach for beyond its four midfield seats.
    assert by_id["kid-mf"]["verdict"] == "next_in_line"
    assert by_id["kid-mf"]["band_rank"] == 5 and by_id["kid-mf"]["seats_in_band"] == 4


def test_the_projection_reads_the_load_the_caller_handed_in() -> None:
    squad = [_player("kid-st", "ST", age=19, overall=64, potential=84)]
    selected, seats = _eleven(squad, "4-4-2")
    rows = academy_class(squad, selected_ids=selected, seats_per_band=seats, loads={"kid-st": (1200, 400)})
    row = rows[0]
    assert row["minutes"] == 1200 and row["training_units"] == 400
    assert row["effective_minutes"] == 1200 + int(round(TRAINING_MINUTES_PER_UNIT * 400))
    expected = round(developed_overall(64, potential=84, minutes_played=row["effective_minutes"]), 1)
    assert row["projected_overall"] == expected
    assert row["potential_headroom"] == round(max(0.0, 84 - expected), 1)


@pytest.fixture(scope="module")
def world() -> dict[str, object]:
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.slug).limit(1)).one()
    owner = User(
        id=new_public_id("usr"),
        email=f"academy-{club.slug[:8]}@example.test",
        password_hash=hash_password("academy-outcomes-test"),
        display_name="Academy Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, object] = {"club_id": club.id, "owner_id": owner.id}
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _career(session: Session, world: dict[str, object]) -> Career:
    return career_service.create_career(
        session,
        owner_id=str(world["owner_id"]),
        club=career_service.resolve_club(session, str(world["club_id"])),
        manager_name="Academy Test",
        philosophy=CAREER_PHLOSOPHIES[0],
        system_slug="",
        budget=1_000_000,
        objectives=[{"kind": "wins", "target": 1}],
        season="2026",
    )


class TestAcademyBlock:
    def test_the_class_is_the_squad_s_under_21_players_judged_by_the_engine_s_eleven(self, session: Session, world: dict[str, object]) -> None:
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        block = career_service.career_view(session, career)["academy"]
        squad, _account = current_squad(session, career)
        expected_class = [player.id for player in squad if int(player.age) <= YOUTH_AGE_MAX]
        assert block["available"] is True
        assert block["class_size"] == len(expected_class), f"the class is every under-21 squad player: expected {len(expected_class)}"
        assert block["youth_age_max"] == YOUTH_AGE_MAX and block["formation"]
        if not expected_class:
            assert block["trainees"] == [] and "age ceiling" in block["reason"]
            return
        defenders, midfielders, attackers = split_formation(str(block["formation"]))
        bands = select_starting_xi(squad, defenders, midfielders, attackers)
        eleven_ids = {player.id for group in bands.values() for player in group}
        verdicts = set()
        for row in block["trainees"]:
            verdicts.add(row["verdict"])
            assert row["verdict"] in ("selected", "next_in_line", "off_the_pace")
            if row["verdict"] == "selected":
                assert row["player_id"] in eleven_ids, f"{row['player_name']} is `selected` but not in the engine's own eleven"
            assert row["band_rank"] is not None and row["seats_in_band"] >= 0
        assert verdicts <= {"selected", "next_in_line", "off_the_pace"}

    def test_the_block_is_recomputed_from_the_rows_on_every_read(self, session: Session, world: dict[str, object]) -> None:
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        first = career_service.career_view(session, career)["academy"]
        second = career_service.career_view(session, career)["academy"]
        assert first == second, "two reads of the same rows must publish the same class"

    def test_each_trainee_s_figures_rederive_from_the_career_s_own_rows(self, session: Session, world: dict[str, object]) -> None:
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        view = career_service.career_view(session, career)
        block = view["academy"]
        if not block["available"] or not block["trainees"]:
            pytest.skip("the fixture's club has no under-21 squad players to audit")
        minutes: dict[str, int] = {}
        for row in session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id)).all():
            minutes[str(row.player_id)] = minutes.get(str(row.player_id), 0) + int(row.minutes)
        training = training_loads(session, sorted(minutes))
        players = {player.id: player for player in session.scalars(select(RealPlayer).where(RealPlayer.team_id == str(world["club_id"]))).all()}
        for trainee in block["trainees"]:
            player = players[trainee["player_id"]]
            played = minutes.get(player.id, 0)
            units = int(training.get(player.id, 0))
            effective = played + int(round(TRAINING_MINUTES_PER_UNIT * units))
            expected = round(developed_overall(player.overall, potential=player.potential, minutes_played=effective), 1)
            assert trainee["minutes"] == played, f"{player.name}: the block's minutes must be the appearance rows' sum"
            assert trainee["effective_minutes"] == effective
            assert trainee["projected_overall"] == expected, f"{player.name}: the projection must re-derive from the rows"
            assert trainee["stored_overall"] == int(player.overall) and trainee["stored_potential"] == int(player.potential)
