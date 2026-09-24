"""M7 §23 AI Scout: what a sentence becomes, what a filter costs, and what may not be said quietly.

Three claims hold this module up, and each is tested from the other side rather than from itself:

* **Nothing in a request is dropped.** A phrase either becomes a filter, becomes a refusal carrying its
  reason, or is a listed connector. The parser's own `unaccounted` field is the seam: no code path writes
  to it, so a test that finds it empty on fifteen sentences proves the sweep covers them all.
* **A published cut is a real cut.** `rows_in`/`rows_out` are re-derived here — the age and foot steps
  against a SQL `COUNT`, the rest against the stored rows behind the returned slugs — so a waterfall that
  printed a flattering number without filtering anything would fail rather than merely look plausible.
* **A figure beside a candidate is the project's own arithmetic.** The fee is `market.valuation` on that
  row and the ranking is the published formula re-applied here, so the scout cannot invent a second
  pricing model the transfer market disagrees with.

The wall is §61 again: the vocabulary and the arithmetic are public, a search that reads the whole player
table or points at a career is not, and a foreign career answers 404 rather than confirming it exists.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Career, RealPlayer, Team
from app.services.attributes import ALL_ATTRIBUTES
from app.services.scouting import search as search_module
from app.services.scouting.requirements import (
    BAND_NAMES_READ_AS_POSITIONS,
    FILTER_KINDS,
    OVERLAPPING_ROLE_KEYS,
    ROLE_POSITIONS,
    SAMPLE_REQUIREMENTS,
    SORTS,
    STAFFED_POSITIONS,
    UNSTAFFED_POSITIONS,
    Parsed,
    Requirement,
    RequirementError,
    parse_requirements,
    scout_rules,
    stated_requirements,
    vocabulary_problems,
)
from app.services.scouting.search import (
    MAX_LIMIT,
    SORT_KEYS,
    SearchRefusal,
    scout_counts,
    scout_ready,
    search,
    search_problems,
    world_account,
)
from app.services.simulation import market
from app.services.tactics.roles import BANDS as BOARD_BANDS
from app.services.tactics.roles import ROLES
from app.services.world import sync_world, world_ready

SCOUT = "/api/v1/scout"
CAREERS = "/api/v1/careers"
PASSWORD = "strong-pass-1234"

#: §23's own worked example, verbatim: three of its four claims are filters and one is not in this build.
SPEC_REQUEST = "找一个 22 岁以下、左脚、能踢 Inverted Fullback、预算 €20m 的球员"

#: Sentence → (filters as (kind, value), sort, refused phrases). Each tuple was read off the parser's own
#: answer before being written down, so a vocabulary change has to change this table deliberately.
SENTENCES: dict[str, tuple[list[tuple[str, Any]], str, list[str]]] = {
    SPEC_REQUEST: ([("age_max", 22), ("foot", "left"), ("fee_max", 20_000_000)], "overall", ["Inverted Fullback"]),
    "find me a left-footed under-22 who can play inverted full-back, budget €20m": ([("foot", "left"), ("age_max", 22), ("fee_max", 20_000_000)], "overall", ["inverted full-back"]),
    "under 21 left back with stamina at least 70, cheapest": ([("age_max", 21), ("position", "LB"), ("attribute_min", 70)], "cheapest", []),
    "goalkeeper over 30": ([("position", "GK"), ("age_min", 30)], "overall", []),
    "attackers with dribble at least 70": ([("band", "attack")], "overall", ["dribble at least 70"]),
    "can play 6": ([], "overall", ["6"]),
    "highest rated holding midfielder under 25": ([("position", "CDM"), ("age_max", 25)], "overall", []),
    "右边锋 21岁以下 预算 3000万": ([("position", "RW"), ("age_max", 21), ("fee_max", 30_000_000)], "overall", []),
    "find a central midfielder": ([("position", "CM")], "overall", []),
    "sweeper keeper": ([("position", "GK")], "overall", []),
    "wing-back under 24": ([("age_max", 24)], "overall", ["wing-back"]),
    "an RWB under 25": ([("role", "RWB"), ("age_max", 25)], "overall", []),
    "best player under 20 with speed at least 80": ([("age_max", 20), ("attribute_min", 80)], "overall", []),
    "找个右脚的中场，预算不超过 500万": ([("foot", "right"), ("band", "midfield"), ("fee_max", 5_000_000)], "overall", []),
    "defender, right footed, highest potential": ([("band", "defence"), ("foot", "right")], "potential", []),
    "a keeper who prefers left, under 28": ([("position", "GK"), ("foot", "left"), ("age_max", 28)], "overall", []),
}


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world for the search to read: the generator's 20 clubs and the players they hold."""
    session = SessionLocal()
    try:
        sync_world(session)
        players = int(session.scalar(select(func.count(RealPlayer.id))) or 0)
        club = str(session.scalars(select(Team.id).order_by(Team.overall, Team.slug).limit(1)).one())
        assert players > 100 and world_ready(session)
        return {"players": players, "club_id": club}
    finally:
        session.close()


@pytest.fixture()
def session() -> Iterator[Any]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


@contextmanager
def _signed_in() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as other:
        response = other.post(
            "/api/v1/auth/register",
            json={"email": f"rival-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Rival Manager", "role": "player", "accepts_data_policy": True},
        )
        assert response.status_code == 201, response.text
        other.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield other


def _career(auth_client: TestClient, club: str) -> str:
    response = auth_client.post(
        CAREERS,
        json={
            "club": club,
            "manager_name": "Scout Manager",
            "philosophy": "balanced",
            "budget": 4_000_000,
            "objectives": [{"kind": "wins", "target": 1, "label": "win once"}],
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["career"]["slug"])


def _rows_by_slug(slugs: list[str]) -> dict[str, RealPlayer]:
    session = SessionLocal()
    try:
        return {row.slug: row for row in session.scalars(select(RealPlayer).where(RealPlayer.slug.in_(slugs))).all()}
    finally:
        session.close()


def _count(*conditions: Any) -> int:
    session = SessionLocal()
    try:
        return int(session.scalar(select(func.count(RealPlayer.id)).where(*conditions)) or 0)
    finally:
        session.close()


def _all_rows() -> list[RealPlayer]:
    """The stored players read straight off the ORM — the pool the waterfall's counts are checked against."""
    session = SessionLocal()
    try:
        return list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
    finally:
        session.close()


def _codes_of(row: RealPlayer) -> set[str]:
    return {str(row.position), *[str(item) for item in row.secondary_positions or []]}


def _plan_of(payload: dict[str, Any]) -> Parsed:
    body = dict(payload)
    for key in ("career_slug", "limit"):
        body.pop(key, None)
    query = str(body.pop("query", ""))
    stated = {key: value for key, value in body.items() if value not in (None, "", {}, [])}
    requirements = stated_requirements(stated)
    if not query:
        return Parsed(text="", requirements=requirements)
    parsed = parse_requirements(query)
    parsed.requirements.extend(requirements)
    return parsed


def _searched(**payload: Any) -> dict[str, Any]:
    """A search run straight through the service, so a test can read the numbers without a wire."""
    career_slug = payload.pop("career_slug", None)
    session = SessionLocal()
    try:
        career = None
        if career_slug:
            career = session.scalar(select(Career).where(Career.slug == str(career_slug)))
            assert career is not None
        return search(session, _plan_of(payload), career=career, limit=int(payload.get("limit", 20)))
    finally:
        session.close()


# --- the vocabulary's own agreement --------------------------------------------------------------------------------


class TestVocabularyIntegrity:
    def test_the_published_vocabulary_agrees_with_itself(self) -> None:
        assert vocabulary_problems() == []

    def test_the_search_answers_every_requirement_kind_the_parser_emits(self, world, session) -> None:  # type: ignore[no-untyped-def]
        assert search_problems(session) == []

    def test_every_filter_kind_reaches_a_probe(self) -> None:
        """`SAMPLE_REQUIREMENTS` is what `search_problems` runs; a kind missing from it is unproven."""
        assert set(FILTER_KINDS) == {item.kind for item in SAMPLE_REQUIREMENTS} - {"sort"}

    def test_every_filter_kind_is_reachable_from_a_sentence_or_a_stated_body(self) -> None:
        from_sentences = {kind for filters, _, _ in SENTENCES.values() for kind, _ in filters}
        from_body = {
            item.kind
            for item in stated_requirements(
                {"max_age": 20, "min_age": 18, "foot": "left", "positions": ["CM"], "bands": ["midfield"], "role": "DM", "attributes": {"stamina": 60}, "max_fee": 5_000_000, "sort": "cheapest"}
            )
        }
        assert set(FILTER_KINDS) <= from_sentences | from_body

    def test_a_probe_with_no_rows_says_so_instead_of_passing(self, world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # The world is loaded for this test on purpose: the patched pool, not an empty database, has to be what empties it.
        monkeypatch.setattr(search_module, "pool", lambda session: [])
        problems = search_problems(SessionLocal())
        assert len(problems) == 1
        assert "no stored player rows" in problems[0] and f"{len(SORT_KEYS)} sortings" in problems[0]

    def test_every_band_word_the_parser_knows_is_one_the_engine_measures(self) -> None:
        rules = scout_rules()
        assert set(rules["bands"]) == {"keeper", "defence", "midfield", "attack"}
        assert set(rules["band_vocabularies"]["board"]["keys"]) == set(BOARD_BANDS)
        # Two vocabularies disagree by name in this project; the response says which is which.
        assert rules["band_vocabularies"]["engine"]["keys"] != rules["band_vocabularies"]["board"]["keys"]

    def test_the_position_catalogue_publishes_the_codes_this_world_never_staffs(self) -> None:
        rules = scout_rules()
        assert set(rules["positions"]) == set(STAFFED_POSITIONS)
        assert set(rules["positions_the_engine_names_and_the_world_does_not_staff"]) == set(UNSTAFFED_POSITIONS)
        assert set(rules["roles_no_stored_position_occupies"]) == {key for key in ROLES if not ROLE_POSITIONS.get(key)}

    def test_a_shared_word_resolves_to_the_narrower_claim_and_says_so(self) -> None:
        rules = scout_rules()
        assert set(rules["role_names_that_read_as_a_position"]) == set(OVERLAPPING_ROLE_KEYS)
        assert set(rules["band_names_that_read_as_a_position"]) == set(BAND_NAMES_READ_AS_POSITIONS)
        # `number ten` names a role and a position; the position wins, and this is the sentence that shows it.
        assert [(item.kind, item.value) for item in parse_requirements("number ten").requirements] == [("position", "CAM")]

    def test_no_connector_is_also_a_filter_word(self) -> None:
        """The bug this guard exists for: a foot word listed as a connector was silently ignored."""
        names = {str(name).lower() for name in scout_rules()["connectors_ignored"]}
        for forbidden in ("left", "right", "both", "foot", "footed", "prefers", "prefer", "preferably", "左脚", "右脚", "双脚"):
            assert forbidden not in names
        assert all(not name.endswith("footed") for name in names)


# --- what a sentence becomes ---------------------------------------------------------------------------------------


class TestSentenceParsing:
    @pytest.mark.parametrize("sentence", sorted(SENTENCES))
    def test_the_request_becomes_these_filters(self, sentence: str) -> None:
        expected_filters, expected_sort, expected_refused = SENTENCES[sentence]
        parsed = parse_requirements(sentence)
        assert [(item.kind, item.value) for item in parsed.filters] == expected_filters
        assert parsed.sort == expected_sort
        assert [item.phrase for item in parsed.refused] == expected_refused

    @pytest.mark.parametrize("sentence", sorted(SENTENCES))
    def test_nothing_in_a_sentence_is_dropped(self, sentence: str) -> None:
        parsed = parse_requirements(sentence)
        assert parsed.unaccounted == []
        assert parsed.to_dict()["unaccounted"] == []
        # Every filter carries the words that produced it, so a shortlist reads back as the request.
        for item in parsed.requirements:
            assert item.phrase and item.phrase in sentence
            assert item.rule and item.source == "parsed"

    def test_an_unknown_word_is_refused_with_the_names_it_is_close_to(self) -> None:
        dribble = parse_requirements("attackers with dribble at least 70").refused[0]
        assert dribble.code == "unknown_attribute" and "dribbling" in dribble.suggestions
        wing = parse_requirements("wing-back under 24").refused[0]
        assert wing.code == "not_in_vocabulary" and "role LWB" in wing.suggestions and "role RWB" in wing.suggestions

    def test_consecutive_unknown_words_are_refused_as_the_phrase_they_were_said_in(self) -> None:
        """`Inverted Fullback` is one claim in one sentence, so it comes back as one refusal."""
        refused = parse_requirements(SPEC_REQUEST).refused
        assert [item.phrase for item in refused] == ["Inverted Fullback"]
        assert "inverted" in refused[0].message.lower() and "nothing was filtered on it" in refused[0].message

    def test_a_fee_says_what_unit_it_was_read_as(self) -> None:
        parsed = parse_requirements(SPEC_REQUEST)
        assert parsed.assumptions and "career credits" in parsed.assumptions[0]
        assert any(item.kind == "fee_max" and item.value == 20_000_000 for item in parsed.filters)

    def test_a_foot_is_a_filter_in_every_shape_it_is_stated(self) -> None:
        for sentence, wanted in (("left-footed", "left"), ("right footed", "right"), ("左脚", "left"), ("右脚", "right"), ("who prefers left", "left"), ("two-footed", "both")):
            parsed = parse_requirements(f"{sentence} defender")
            assert [(item.kind, item.value) for item in parsed.filters if item.kind == "foot"] == [("foot", wanted)], sentence
            assert parsed.refused == [], sentence

    def test_an_ambiguity_between_a_foot_and_a_position_goes_to_the_position(self) -> None:
        """`left back` is a position; reading its first word as a foot would filter the wrong column."""
        parsed = parse_requirements("under 21 left back with stamina at least 70, cheapest")
        kinds = [(item.kind, item.value) for item in parsed.filters]
        assert ("position", "LB") in kinds and "foot" not in [item[0] for item in kinds]

    def test_a_request_of_nothing_filters_nothing_rather_than_everything(self) -> None:
        parsed = parse_requirements("can play 6")
        assert parsed.filters == [] and parsed.sort == "overall"
        assert parsed.refused[0].phrase == "6"


# --- the structured path -------------------------------------------------------------------------------------------


class TestStatedFields:
    def test_a_stated_body_becomes_one_requirement_per_field(self) -> None:
        body = {"max_age": 24, "min_age": 18, "foot": "left", "positions": ["CM"], "bands": ["midfield"], "role": "DM", "attributes": {"stamina": 60}, "max_fee": 5_000_000, "sort": "cheapest"}
        requirements = stated_requirements(body)
        assert [(item.kind, item.value) for item in requirements] == [
            ("age_max", 24),
            ("age_min", 18),
            ("foot", "left"),
            ("position", "CM"),
            ("band", "midfield"),
            ("role", "DM"),
            ("attribute_min", 60),
            ("fee_max", 5_000_000),
            ("sort", "cheapest"),
        ]
        assert all(item.source == "stated" for item in requirements)

    def test_a_body_of_nothing_filters_nothing(self) -> None:
        assert stated_requirements({}) == []

    def test_an_unknown_field_raises_naming_what_is_accepted(self) -> None:
        with pytest.raises(RequirementError) as error:
            stated_requirements({"max_age": 20, "heigth_cm": 190})
        assert error.value.code == "unknown_field"
        assert error.value.detail["fields"] == ["heigth_cm"]
        assert "max_age" in error.value.detail["fields_accepted"]

    def test_an_unknown_foot_band_role_attribute_or_sort_raises(self) -> None:
        for body, code in (
            ({"foot": "switch"}, "unknown_foot"),
            ({"bands": ["half-back"]}, "unknown_band"),
            ({"role": "joker"}, "unknown_role"),
            ({"attributes": {"dribble": 70}}, "unknown_attribute"),
            ({"sort": "vibes"}, "unknown_sort"),
        ):
            with pytest.raises(RequirementError) as error:
                stated_requirements(body)
            assert error.value.code == code, body

    def test_a_position_the_world_never_staffs_is_refused_rather_than_searched(self) -> None:
        for code in ("LM", "RM"):
            with pytest.raises(RequirementError) as error:
                stated_requirements({"positions": [code]})
            assert error.value.code == "unstaffed_position"
            assert set(error.value.detail["staffed"]) == set(STAFFED_POSITIONS)

    def test_a_word_that_names_an_unstaffed_code_and_a_staffed_one_resolves_to_the_staffed_one(self) -> None:
        """`CF` is the engine's code for a centre-forward and the world stores that player as `ST`; the alias says so."""
        requirement = stated_requirements({"positions": ["CF"]})[0]
        assert (requirement.kind, requirement.value) == ("position", "ST")
        assert "cf" in [str(item).lower() for item in scout_rules()["positions"]["ST"]["aliases"]]

    def test_a_board_slot_no_stored_position_occupies_cannot_filter_a_list(self) -> None:
        for key in ("RM", "LM"):
            with pytest.raises(RequirementError) as error:
                stated_requirements({"role": key})
            assert error.value.code == "unstaffed_role"
            assert key not in error.value.detail["staffed_roles"]

    def test_an_attribute_floor_outside_the_stored_range_raises(self) -> None:
        for floor in (0, 100, 500):
            with pytest.raises(RequirementError) as error:
                stated_requirements({"attributes": {"stamina": floor}})
            assert error.value.code == "attribute_out_of_range"

    def test_a_stated_filter_says_it_was_stated_rather_than_parsed(self, world) -> None:  # type: ignore[no-untyped-def]
        """`source` is published on every step, so a body cannot impersonate a sentence about itself."""
        result = _searched(max_age=25, positions=["CM"], bands=["midfield"], role="DM")
        assert [step["source"] for step in result["waterfall"]] == ["stated"] * 4
        assert all(str(item["source"]) == "stated" for item in result["requirements"])
        sentence = _searched(query="under 21 left footed")
        assert [step["source"] for step in sentence["waterfall"]] == ["parsed"] * 2


# --- the waterfall --------------------------------------------------------------------------------------------------


class TestWaterfall:
    def test_the_pool_is_every_stored_player_and_each_step_starts_where_the_last_ended(self, world) -> None:
        result = _searched(query="under 21 left footed, cheapest")
        steps = result["waterfall"]
        assert result["rows_examined"] == world["players"] == _count()
        assert steps[0]["rows_in"] == world["players"]
        for previous, step in zip(steps, steps[1:], strict=False):
            assert step["rows_in"] == previous["rows_out"]
        assert steps[-1]["rows_out"] == result["total_matches"]
        assert all(step["cut"] == step["rows_in"] - step["rows_out"] for step in steps)
        assert any(step["cut"] > 0 for step in steps), "a waterfall that cut nothing proves nothing"

    def test_an_age_and_foot_cut_equals_a_count_taken_in_the_database(self, world) -> None:
        """The step numbers re-derived by a different engine: SQL `COUNT` against the waterfall's scan."""
        result = _searched(max_age=19, foot="left")
        assert result["total_matches"] == _count(RealPlayer.age <= 19, RealPlayer.preferred_foot == "left")
        assert result["waterfall"][-1]["rows_out"] == result["total_matches"]

    def test_a_band_cut_equals_the_codes_the_engine_measures_in_that_band(self, world) -> None:
        from app.services.simulation.profile import BANDS

        result = _searched(bands=["keeper"])
        assert set(BANDS["keeper"]) == {"GK"}
        codes = set(BANDS["keeper"])
        assert result["total_matches"] == sum(1 for row in _all_rows() if codes & _codes_of(row))
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        assert all(codes & _codes_of(rows[str(item["slug"])]) for item in result["candidates"])

    def test_a_filter_that_cannot_match_anyone_empties_the_pool_and_names_the_step(self, world) -> None:
        result = _searched(min_age=59)
        assert result["total_matches"] == 0 and result["candidates"] == [] and result["truncated"] is False
        step = result["waterfall"][0]
        assert step["rows_out"] == 0 and step["cut"] == step["rows_in"] == world["players"]
        assert step["example_of_a_row_dropped"]["stated"] == 59

    def test_every_returned_candidate_answers_every_filter_with_its_own_measurement(self, world) -> None:
        result = _searched(max_age=24, positions=["CM"], attributes={"stamina": 40}, limit=8)
        assert result["candidates"], "an empty shortlist would pass every assertion below it"
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        phrases = {str(step["phrase"]) for step in result["waterfall"]}
        for candidate in result["candidates"]:
            row = rows[str(candidate["slug"])]
            assert {str(item["phrase"]) for item in candidate["answers"]} == phrases
            assert int(row.age) <= 24
            assert "CM" == row.position or "CM" in list(row.secondary_positions or [])
            assert int(row.attributes["stamina"]) >= 40
            for answer in candidate["answers"]:
                assert len(answer) > 2, "an answer has to carry the figure that made it true"

    def test_the_shortlist_pages_without_losing_the_count(self, world) -> None:
        wide = _searched(max_age=24, limit=MAX_LIMIT)
        capped = _searched(max_age=24, limit=3)
        assert wide["total_matches"] > MAX_LIMIT, "a pool this test cannot overflow would prove nothing about paging"
        assert capped["returned"] == 3 and capped["limit"] == 3 and capped["truncated"] is True
        assert capped["total_matches"] == wide["total_matches"]
        assert wide["returned"] == min(wide["total_matches"], MAX_LIMIT) and wide["truncated"] is (wide["total_matches"] > wide["returned"])
        assert [item["slug"] for item in capped["candidates"]] == [item["slug"] for item in wide["candidates"][:3]]

    def test_the_refused_phrase_survives_the_search_that_ignored_it(self, world) -> None:
        """§23's example: the rows are listed *and* the role that was not found says it was not found."""
        result = _searched(query=SPEC_REQUEST)
        assert [item["phrase"] for item in result["refused"]] == ["Inverted Fullback"]
        assert result["candidates"], "the search found players, so the refusal has to ride with them"
        assert result["unaccounted"] == [] and result["assumptions"]
        assert all(item["kind"] in FILTER_KINDS or item["kind"] == "sort" for item in result["requirements"])

    def test_the_same_request_twice_answers_the_same_way(self, world) -> None:
        first = _searched(query="defender, right footed, highest potential", limit=10)
        second = _searched(query="defender, right footed, highest potential", limit=10)
        assert [item["slug"] for item in first["candidates"]] == [item["slug"] for item in second["candidates"]]
        assert first["waterfall"] == second["waterfall"]


# --- the arithmetic beside a candidate ------------------------------------------------------------------------------


class TestPublishedArithmetic:
    def test_a_candidates_fee_is_the_markets_own_valuation_of_that_row(self, world) -> None:
        result = _searched(max_age=23, limit=8)
        assert result["candidates"]
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        priced = market.valuation(rows[str(result["candidates"][0]["slug"])])
        assert set(priced) >= {"asking_fee", "release_clause", "weekly_wage", "contract_years", "quality_points", "headroom_points", "age_curve"}
        for candidate in result["candidates"]:
            row = rows[str(candidate["slug"])]
            figures = market.valuation(row)
            assert candidate["valuation"] == {key: figures[key] for key in candidate["valuation"]}
            assert candidate["value_for_money"] == pytest.approx(int(row.overall) * 1_000_000 / max(int(figures["asking_fee"]), market.CREDIT_ROUND), abs=0.01)
            assert candidate["headroom"] == int(row.potential) - int(row.overall)
            assert candidate["overall"] == int(row.overall) and candidate["potential"] == int(row.potential)

    def test_the_price_carries_its_curve_and_points(self, world) -> None:
        candidate = _searched(limit=1)["candidates"][0]
        assert candidate["valuation"]["age_curve"] and candidate["valuation"]["quality_points"] >= 0

    @pytest.mark.parametrize("sort", sorted(SORT_KEYS))
    def test_each_sorting_orders_the_survivors_by_its_published_key(self, sort: str, world) -> None:
        if sort == "need_fit":
            pytest.skip("need_fit is ranked against a career and tested with one")
        result = _searched(max_age=24, sort=sort, limit=10)
        assert result["candidates"]
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        slugs = [str(item["slug"]) for item in result["candidates"]]
        primary = [_expected_key(sort, rows[slug]) for slug in slugs]
        assert primary == sorted(primary), f"{sort} did not order its own key"
        assert result["sort"]["key"] == sort and result["sort"]["applied_to"] == result["total_matches"]
        for index in range(1, len(primary)):
            if primary[index] == primary[index - 1]:
                assert slugs[index] > slugs[index - 1], "a tie must break on the slug"

    def test_an_unobserved_player_has_no_season_rather_than_a_zero_one(self, world) -> None:
        result = _searched(limit=MAX_LIMIT)
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        observed = 0
        for candidate in result["candidates"]:
            row = rows[str(candidate["slug"])]
            assert candidate["observed"] == (int(row.appearances) > 0)
            if candidate["observed"]:
                observed += 1
                assert candidate["season"]["appearances"] == int(row.appearances) and candidate["season"]["minutes"] == int(row.minutes)
                assert candidate["season"]["rating"] == round(float(row.rating), 2)
            else:
                assert candidate["season"] is None
        assert observed > 0, "a shortlist of nobody observed would only exercise the null branch"
        assert "null" in result["observed_rule"] and "zero" in result["observed_rule"]

    def test_a_candidate_carries_the_paths_a_page_would_link_to(self, world) -> None:
        candidate = _searched(max_age=22, limit=1)["candidates"][0]
        assert candidate["path"] == f"/player/{candidate['slug']}"
        assert candidate["club"]["path"] == f"/team/{candidate['club']['slug']}"
        assert candidate["data_origin"] and candidate["is_demo_data"] is True


def _expected_key(sort: str, row: RealPlayer) -> Any:
    figures = market.valuation(row)
    fee = int(figures["asking_fee"])
    if sort == "overall":
        return -int(row.overall)
    if sort == "potential":
        return -int(row.potential)
    if sort == "headroom":
        return -(int(row.potential) - int(row.overall))
    if sort == "value_for_money":
        return -round(int(row.overall) * 1_000_000 / max(fee, market.CREDIT_ROUND), 3)
    if sort == "cheapest":
        return fee
    if sort == "youth":
        return int(row.age)
    raise AssertionError(f"{sort} is not a sort this helper knows; SORT_KEYS and the test drifted")


# --- a role is ranked, never guessed -------------------------------------------------------------------------------


class TestRoleFit:
    def test_a_role_cuts_on_the_slots_it_can_be_occupied_by(self, world) -> None:
        result = _searched(role="DM", limit=10)
        assert result["candidates"]
        staffed = set(ROLE_POSITIONS["DM"])
        assert staffed, "an empty slot list would make every assertion below vacuous"
        assert result["total_matches"] == sum(1 for row in _all_rows() if staffed & _codes_of(row))
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        for candidate in result["candidates"]:
            assert staffed & _codes_of(rows[str(candidate["slug"])])
            assert set(candidate["role_fit"]["occupiable_by"]) == staffed

    def test_a_roles_fit_is_the_board_demands_against_the_stored_attributes(self, world) -> None:
        result = _searched(query="an RWB under 25 with stamina at least 50", limit=5)
        assert result["candidates"], "the RWB probe needs at least one row to read the fit off"
        role = ROLES["RWB"]
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        for candidate in result["candidates"]:
            fit = candidate["role_fit"]
            assert fit["role"] == "RWB" and fit["label"] == role.label and fit["board_band"] == role.band
            assert fit["risk"] == role.risk and set(fit["occupiable_by"]) == set(ROLE_POSITIONS["RWB"])
            assert [str(line["attribute"]) for line in fit["rows"]] == sorted(role.demands)
            row = rows[str(candidate["slug"])]
            for line in fit["rows"]:
                assert line["demanded"] == role.demands[str(line["attribute"])]
                assert line["have"] == int(row.attributes[str(line["attribute"])])
                assert line["gap"] == line["have"] - line["demanded"]
            assert fit["mean_gap"] == round(sum(int(line["gap"]) for line in fit["rows"]) / len(fit["rows"]), 2)

    def test_a_player_who_is_short_for_the_role_is_still_listed(self, world) -> None:
        """The fit is a ranking, not a filter: nobody was dropped for being bad at the role."""
        result = _searched(role="AM", limit=MAX_LIMIT)
        short = [item for item in result["candidates"] if item["role_fit"]["shortfalls"]]
        assert short, "no candidate is short against this role's demands, which would make the claim vacuous"
        assert all(str(item["role_fit"]["verdict"]).startswith("short in") for item in short)

    def test_a_search_without_a_role_reports_no_fit_rather_than_a_zero_one(self, world) -> None:
        result = _searched(max_age=25, limit=3)
        assert result["candidates"] and all(item["role_fit"] is None for item in result["candidates"])


# --- a search that knows which squad is asking ----------------------------------------------------------------------


class TestCareerNeed:
    def test_ranking_by_need_fit_refuses_without_a_career(self) -> None:
        with pytest.raises(SearchRefusal) as error:
            _searched(sort="need_fit")
        assert error.value.code == "need_fit_needs_career"
        assert error.value.detail["see"] == "/api/v1/scout/rules"

    def test_an_unknown_sorting_is_refused_with_the_published_list(self) -> None:
        plan = Parsed(text="", requirements=[Requirement("sort", "sort", "vibes", "stated sort=vibes", "rule")])
        with pytest.raises(SearchRefusal) as error:
            search(SessionLocal(), plan)
        assert error.value.code == "unknown_sort" and set(error.value.detail["sorts"]) == set(SORT_KEYS)

    def test_a_careers_need_is_measured_and_every_candidate_is_scored_against_it(self, world, auth_client) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, world["club_id"])
        result = _searched(career_slug=slug, sort="need_fit", limit=8)
        need = result["need"]
        assert need["needed_band"] in {"attack", "defence", "midfield", "keeper"}
        assert set(need["bands"]) == {"attack", "defence", "midfield", "keeper"}
        assert need["bands"][need["needed_band"]] == min(need["bands"].values())
        assert result["career"]["slug"] == slug and result["sort"]["career_dependent"] is True
        rows = _rows_by_slug([str(item["slug"]) for item in result["candidates"]])
        fits = [float(item["tactical_fit"]["fit"]) for item in result["candidates"]]
        assert fits == sorted(fits, reverse=True), "need_fit did not rank by the fit it printed"
        for candidate in result["candidates"]:
            measured = market.tactical_fit(rows[str(candidate["slug"])], str(need["needed_band"]))
            assert candidate["tactical_fit"] == {**measured, "formula": market.FIT_FORMULA}

    def test_a_career_that_asks_nothing_about_need_still_gets_a_fit(self, world, auth_client) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, world["club_id"])
        result = _searched(career_slug=slug, max_age=23, limit=4)
        assert result["need"] is not None and result["sort"]["key"] == "overall"
        assert all(item["tactical_fit"]["formula"] == market.FIT_FORMULA for item in result["candidates"])

    def test_the_world_the_scout_reads_is_counted_in_the_database(self, world) -> None:
        session = SessionLocal()
        try:
            account = world_account(session)
        finally:
            session.close()
        assert account["players_stored"] == world["players"]
        assert account["players_at_a_club"] + account["players_with_no_club"] == account["players_stored"]
        assert account["clubs_stored"] >= 20


# --- over the wire --------------------------------------------------------------------------------------------------


class TestScoutRoutes:
    def test_the_rules_are_public_and_clean(self, client, world) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{SCOUT}/rules", headers={"Authorization": ""})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["integrity"]["clean"] is True and body["integrity"]["problems"] == []
        assert body["integrity"]["ready"] is True
        assert body["integrity"]["counts"]["positions"] == len(STAFFED_POSITIONS)
        assert body["integrity"]["counts"]["players_stored"] == world["players"]
        assert set(body["search"]["sorts"]) == set(SORT_KEYS)
        assert body["search"]["max_limit"] == MAX_LIMIT
        assert len(body["search"]["limits"]) >= 5 and body["disclaimer"]
        assert body["example_parse"]["refused"][0]["phrase"] == "Inverted Fullback"
        assert body["example_parse"]["filters_applied"] == 3

    def test_parsing_a_sentence_needs_no_account_and_reads_no_rows(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.post(f"{SCOUT}/parse", json={"query": SPEC_REQUEST}, headers={"Authorization": ""})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["request"] == SPEC_REQUEST
        assert body["filters_applied"] == 3 and body["sort"] == "overall"
        assert [item["phrase"] for item in body["refused"]] == ["Inverted Fullback"]
        assert body["search_would_apply"] == 3 and "nothing was searched here" in body["note"]
        assert "candidates" not in body

    def test_a_sentence_that_filters_nothing_says_the_pool_would_only_be_ranked(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.post(f"{SCOUT}/parse", json={"query": "can play 6"}).json()
        assert body["filters_applied"] == 0 and "would rank the whole stored pool" in body["note"]

    def test_a_search_needs_an_account(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.post(f"{SCOUT}/search", json={"query": "under 21"}).status_code == 401

    def test_a_search_answers_with_the_waterfall_and_the_refusal_together(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(f"{SCOUT}/search", json={"query": SPEC_REQUEST, "limit": 3})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["returned"] == 3 and body["limit"] == 3 and body["max_limit"] == MAX_LIMIT
        assert [step["phrase"] for step in body["waterfall"]] == ["22 岁以下", "左脚", "预算 €20m"]
        assert body["refused"][0]["suggestions"], "a refusal has to carry the names it is close to"
        assert body["asked_for"] == {"query": SPEC_REQUEST, "stated": None, "career": None, "limit": 3}
        assert body["demo_data"] is True and body["data_origin"] == "simulation"

    def test_a_stated_field_and_a_sentence_both_cut_and_say_so(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        alone = auth_client.post(f"{SCOUT}/search", json={"max_age": 22}).json()
        both = auth_client.post(f"{SCOUT}/search", json={"query": "under 25 left footed", "max_age": 22}).json()
        assert [step["kind"] for step in both["waterfall"]] == ["age_max", "foot", "age_max"]
        assert both["total_matches"] <= min(alone["total_matches"], both["waterfall"][1]["rows_out"])
        assert [str(item["kind"]) for item in both["duplicate_fields"]] == ["age_max"]
        assert "both cuts apply" in both["duplicate_fields"][0]["rule"]
        assert len(both["duplicate_fields"][0]["phrases"]) == 2

    def test_a_stated_field_the_vocabulary_does_not_hold_is_a_422(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(f"{SCOUT}/search", json={"positions": ["LM"]})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "unstaffed_position"

    def test_a_search_ranked_on_need_without_a_career_is_a_422(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(f"{SCOUT}/search", json={"sort": "need_fit"})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "need_fit_needs_career"

    def test_the_limit_is_a_range_rather_than_a_suggestion(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        assert auth_client.post(f"{SCOUT}/search", json={"limit": MAX_LIMIT + 1}).status_code == 422
        assert auth_client.post(f"{SCOUT}/search", json={"limit": 0}).status_code == 422
        assert auth_client.post(f"{SCOUT}/parse", json={"query": "x" * 401}).status_code == 422

    def test_another_accounts_career_is_not_there_for_this_one(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, world["club_id"])
        with _signed_in() as other:
            response = other.post(f"{SCOUT}/search", json={"max_age": 22, "career": slug})
            assert response.status_code == 404, response.text
            assert response.json()["detail"]["code"] == "not_found"
            assert "candidates" not in response.json()

    def test_an_unknown_career_is_a_404_and_a_real_one_answers_for_its_owner(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        assert auth_client.post(f"{SCOUT}/search", json={"career": "no-such-career"}).status_code == 404
        slug = _career(auth_client, world["club_id"])
        body = auth_client.post(f"{SCOUT}/search", json={"sort": "need_fit", "career": slug, "limit": 2}).json()
        assert body["career"]["slug"] == slug and body["need"]["needed_band"]

    def test_the_capability_flag_reports_the_scout_as_it_measures(self, client, world) -> None:  # type: ignore[no-untyped-def]
        body = client.get("/api/v1/capabilities").json()
        assert body["m7_scouting"] is True
        assert body["m7_scout"]["problems"] == []
        assert body["m7_scout"]["counts"]["players_stored"] == world["players"]
        assert body["m7_scout"]["disclaimer"]
        session = SessionLocal()
        try:
            assert scout_ready(session) is True
            assert scout_counts(session)["sortings"] == len(SORT_KEYS)
        finally:
            session.close()


# --- what the feature says it cannot do -----------------------------------------------------------------------------


class TestHonestySurface:
    def test_the_limitations_are_published_on_every_read(self, world) -> None:
        rules = scout_rules()
        body = _searched(max_age=24, limit=2)
        assert all(len(str(item)) > 30 for item in body["limitations"])
        assert any("valuation" in str(item) for item in body["limitations"])
        assert any("no model call" in str(item) for item in body["limitations"])
        assert set(body["rules"]) == {"money", "feet", "bands", "rank", "valuation"}
        assert body["rules"]["valuation"] == market.VALUATION_FORMULA
        assert "not an index" in body["scan_note"]
        assert body["waterfall_rule"] == search_module.WATERFALL_RULE
        assert set(rules["attributes"]) == set(ALL_ATTRIBUTES)
        assert set(rules["sorts"]) == set(SORTS) == set(SORT_KEYS)

    def test_no_candidate_claims_an_answer_it_did_not_measure(self, world) -> None:
        """`answers` is the only place a candidate says why it is here; a filter with no answer is a lie."""
        body = _searched(query="under 23 midfielders with stamina at least 50, cheapest")
        assert body["candidates"]
        for candidate in body["candidates"]:
            assert {str(item["phrase"]) for item in candidate["answers"]} == {str(step["phrase"]) for step in body["waterfall"]}
            assert {str(item["kind"]) for item in candidate["answers"]} == {"age_max", "band", "attribute_min"}

    def test_a_candidate_list_cannot_be_built_without_the_refusals_that_came_with_it(self) -> None:
        """`search` takes the whole `Parsed`: there is no argument left that drops a refusal on the floor."""
        with pytest.raises(TypeError):
            search(SessionLocal(), requirements=[], refused=[])  # type: ignore[call-arg]

    def test_the_disclaimer_and_origin_travel_with_every_answer(self, world) -> None:
        body = _searched(max_age=24, limit=1)
        assert body["disclaimer"] and body["is_demo_data"] is True and body["data_origin"] == "simulation"
        assert body["suggestion_formula"] and body["match_rule"] and body["valuation_note"]
