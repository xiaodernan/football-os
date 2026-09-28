"""§38's Football CV (M10): ten sections printed from rows other tiers own, in one read.

The claims this file defends, in the order it attacks them:

* §38's ten sections, in §38's order, under §38's own words — held against the spec's list transcribed here, so a
  renamed section is caught by a test rather than by a reader of the page;
* the tier owns **no table**, asserted over `Base.metadata` and not promised in prose: a stored CV is the copy that
  goes stale, and an assertion is the only form of that promise a reviewer can run;
* every figure is counted at the moment of the read with its expression printed beside it, so completing a training
  session and re-reading the CV shows a different number — the measurement a cached section could never pass;
* the two sections this build cannot fill print the *measurement* instead of a `0`: the rows that would have to
  exist, and the foreign key that says the rows that do exist are about another player
  (`career_appearances.player_id` -> `real_players`, while only four tables in the schema reference `user_players`);
* an account with no player row earns a CV that says so rather than a 404, and the CV door answers 401 before any
  row is read — §35's rule that absence is an answer, applied to a read;
* the rules door is public and holds only the tier's vocabulary, and nothing in either answer is money, because §42
  owns pricing and a CV is not a shop.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import portfolio as portfolio_router
from app.core.db import Base, SessionLocal
from app.main import app
from app.models import AttributeChange, User
from app.services.portfolio import cv as portfolio

CV = "/api/v1/portfolio/cv"
RULES = "/api/v1/portfolio/rules"
PASSWORD = "strong-pass-1234"

#: §38's own list, transcribed: the spec's "Football CV" names Position, Archetype, Skills, Matches, Stats,
#: Training, Videos, Achievements, AI Reports and Development History, in that order.
SPEC_38_TITLES: Final = (
    "Position",
    "Archetype",
    "Skills",
    "Matches",
    "Stats",
    "Training",
    "Videos",
    "Achievements",
    "AI Reports",
    "Development History",
)

#: The four tables in this schema whose rows reference `user_players` — measured below, and the count the `matches`
#: section prints as part of the reason it is empty. A fifth table would have to move both numbers together.
USER_PLAYER_TABLES: Final = ("attribute_changes", "training_plans", "training_sessions", "xp_events")

#: §42 owns pricing. The AI Reports section names the model's provider, which is data origin rather than a vendor,
#: so the words hunted here are the ones that only ever mean money.
MONEY_WORDS: Final = ("price", "pricing", "currency", "checkout", "payment", "stripe", "usd", "amount_paid")


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(db: Session, name: str = "Ada Portfolio") -> User:
    """An account with no player row: the shape a CV has to answer without a 404."""
    tag = uuid4().hex[:8]
    row = User(id=f"usr_{tag}", email=f"portfolio-{tag}@example.test", password_hash="not-a-password-just-a-column", display_name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _client(name: str) -> TestClient:
    """Its own client with its own registered account: every CV here is one account's, so a case needs its own."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"portfolio-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _actor(client: TestClient) -> str:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _player(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/players",
        json={"name": "Test Midfielder", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _complete_a_session(client: TestClient, execution: int = 4) -> tuple[dict[str, Any], dict[str, Any]]:
    """Plan and complete one real session through the academy's own doors; return (drill, completion)."""
    drills = client.get("/api/v1/trainings/drills")
    assert drills.status_code == 200, drills.text
    drill = drills.json()[0]
    planned = client.post("/api/v1/trainings/sessions", json={"drill_id": drill["id"], "available_minutes": 60})
    assert planned.status_code == 201, planned.text
    done = client.post(
        f"/api/v1/trainings/sessions/{planned.json()['session_id']}/complete",
        json={"execution": execution, "focus": 4, "difficulty_experience": 3},
    )
    assert done.status_code == 200, done.text
    return drill, done.json()


def _section(cv: dict[str, Any], key: str) -> dict[str, Any]:
    found = [item for item in cv["sections"] if item["section"] == key]
    assert len(found) == 1, f"a CV prints exactly one {key!r} section"
    return found[0]


def _walk(value: Any) -> Iterator[str]:
    """Every key and leaf of an answer, so a word cannot hide inside a nested figure."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk(item)
    else:
        yield str(value)


class TestTheSectionsAreTheSpecs:
    def test_the_ten_sections_are_spec_38s_ten_in_its_order(self) -> None:
        assert [portfolio.SECTION_TITLES[key] for key in portfolio.SECTIONS] == list(SPEC_38_TITLES)

    def test_every_section_names_the_rows_it_reads(self) -> None:
        for key in portfolio.SECTIONS:
            if key in portfolio.UNFILLED_REASONS:
                assert portfolio.WOULD_READ_FROM.get(key), f"{key!r} is empty without naming the rows that would fill it"
            else:
                assert portfolio.SOURCES.get(key), f"{key!r} would print figures without naming the table behind them"
        assert set(portfolio.UNFILLED_REASONS) == {"matches", "stats"}
        assert set(portfolio.WOULD_READ_FROM) == set(portfolio.UNFILLED_REASONS)

    def test_the_tier_owns_no_table(self) -> None:
        names = {str(name).lower() for name in Base.metadata.tables}
        offenders = sorted(name for name in names if "portfolio" in name or name.endswith("_cv"))
        assert offenders == [], f"a CV is a read of rows that already exist; {offenders} would be the copy that goes stale"

    def test_the_reason_printed_for_matches_counts_the_schema_it_is_read_from(self) -> None:
        referencing = tuple(sorted(table.name for table in Base.metadata.tables.values() if any(fk.target_fullname == "user_players.id" for column in table.columns for fk in column.foreign_keys)))
        assert referencing == USER_PLAYER_TABLES, "the printed sentence counts these tables; a new one moves both"
        sentence = portfolio.UNFILLED_REASONS["matches"]
        assert "four" in sentence, "the sentence counts the tables it found, in words"
        assert all(name in sentence for name in USER_PLAYER_TABLES), "the reason has to name the tables it counted"
        assert "career_appearances.player_id" in sentence
        targets = {fk.target_fullname for column in Base.metadata.tables["career_appearances"].columns for fk in column.foreign_keys}
        assert "real_players.id" in targets and "user_players.id" not in targets


class TestTheReadIsTheRows:
    def test_an_account_with_no_player_earns_a_cv_that_says_so(self, session: Session) -> None:
        account = _account(session)
        cv = portfolio.build_cv(session, account.id)
        assert cv["has_player"] is False and cv["player"] is None
        assert cv["account"] == {"user_id": account.id, "display_name": account.display_name}
        assert cv["counts"]["sections"] == 10 and cv["counts"]["filled"] == 0
        assert cv["counts"]["unfilled"] == list(portfolio.SECTIONS)
        for section in cv["sections"]:
            assert section["available"] is False
            assert section["missing_because"], "an empty section has to say which rows it looked for"
            assert "figures" not in section, "a `0` reads as a measurement; the empty section prints the reason instead"

    def test_the_player_row_is_the_position_the_archetype_and_the_skills(self, session: Session) -> None:
        client = _client("Ada Keeper")
        player = _player(client)
        cv = portfolio.build_cv(session, _actor(client))

        position = _section(cv, "position")
        assert position["available"] is True and position["source"] == portfolio.SOURCES["position"]
        assert position["figures"]["position"] == player["position"] == "CM"
        assert position["figures"]["preferred_foot"] == player["preferred_foot"]
        assert position["figures"]["age"] == player["age"] and position["figures"]["goal"] == player["goal"]

        archetype = _section(cv, "archetype")
        assert archetype["figures"]["archetype"] == player["archetype"]
        assert archetype["items"] == [{"reason": reason} for reason in player["derivation_reasons"]]

        skills = _section(cv, "skills")
        assert skills["figures"]["overall"] == player["overall"] and skills["figures"]["potential"] == player["potential"]
        rated = {name: value for name, value in skills["figures"]["attributes"].items() if not name.startswith("_sp_")}
        assert rated == player["attributes"], "the page the account sees and the CV read one row, not two copies"
        assert skills["items"] == [{"attribute": name, "value": value} for name, value in sorted(skills["figures"]["attributes"].items())]

    def test_completing_a_session_moves_the_training_figures_on_a_reread(self, session: Session) -> None:
        client = _client("Bo Trains")
        _player(client)
        account = _actor(client)
        before = portfolio.build_cv(session, account)
        assert _section(before, "training")["available"] is False
        assert _section(before, "development")["available"] is False

        drill, completion = _complete_a_session(client)

        after = portfolio.build_cv(session, account)
        training = _section(after, "training")
        assert training["available"] is True and training["source"] == portfolio.SOURCES["training"]
        assert training["figures"]["sessions"] == 1
        assert training["figures"]["completed"] == 1 and training["figures"]["planned"] == 0
        assert training["figures"]["minutes"] == drill["duration_min"], "minutes are the drill's own duration, summed over completed sessions"
        assert training["figures"]["mean_execution"] == 4.0
        assert training["figures"]["xp_awarded"] == completion["xp_awarded"]
        assert [item["drill"] for item in training["items"]] == [drill["title"]]

        development = _section(after, "development")
        assert development["available"] is True
        assert development["figures"]["xp_total"] == completion["xp_awarded"], "the CV counts the XP row the completion wrote"
        assert set(development["figures"]["net_change"]) == {change["attribute"] for change in completion["attribute_changes"]}
        assert any(item.get("xp") == completion["xp_awarded"] for item in development["items"])

    def test_an_attribute_change_written_elsewhere_shows_up_on_the_next_read(self, session: Session) -> None:
        """The read that proves nothing is cached: a row another tier writes is on the CV at the next call."""
        client = _client("Fay Change")
        player = _player(client)
        account = _actor(client)
        assert _section(portfolio.build_cv(session, account), "development")["available"] is False

        session.add(
            AttributeChange(
                id=f"ac_{uuid4().hex[:12]}",
                player_id=player["id"],
                attribute="passing",
                delta=1,
                before=60,
                after=61,
                reason="written by a case, read back by the CV",
            )
        )
        session.commit()

        development = _section(portfolio.build_cv(session, account), "development")
        assert development["available"] is True
        assert set(development["figures"]) == {"changes", "net_change", "xp_total", "first_change", "last_change"}
        assert development["figures"]["changes"] == 1
        assert development["figures"]["net_change"] == {"passing": 1}
        assert development["figures"]["xp_total"] == 0, "no XP row was written by this case, and none is invented"
        assert development["figures"]["first_change"] is not None
        assert development["figures"]["last_change"] == development["figures"]["first_change"]
        assert development["items"][0]["attribute"] == "passing" and development["items"][0]["after"] == 61

    def test_the_two_sections_that_cannot_be_filled_print_a_reason_and_no_zero(self, session: Session) -> None:
        account = _account(session)
        cv = portfolio.build_cv(session, account.id)
        for key in ("matches", "stats"):
            section = _section(cv, key)
            assert section["available"] is False and "figures" not in section
            assert section["missing_because"] == portfolio.UNFILLED_REASONS[key]
            assert section["would_be_read_from"] == portfolio.WOULD_READ_FROM[key]
        assert "real_player_match_stats" in portfolio.UNFILLED_REASONS["matches"]
        assert "user_players" in portfolio.UNFILLED_REASONS["matches"]
        assert set(cv["unfilled_reasons"]) == {"matches", "stats"}

    def test_every_filled_section_prints_exactly_its_own_formulas(self, session: Session) -> None:
        client = _client("Cy Formulas")
        _player(client)
        _complete_a_session(client)
        cv = portfolio.build_cv(session, _actor(client))
        for section in cv["sections"]:
            expected = {key.split(".", 1)[1] for key in portfolio.FORMULAS if key.startswith(section["section"] + ".")}
            if section["available"]:
                assert set(section["formulas"]) == expected, f"{section['section']} prints a figure with no expression beside it"
                for name, expression in section["formulas"].items():
                    assert expression == portfolio.FORMULAS[f"{section['section']}.{name}"]
            else:
                assert "formulas" not in section
        assert {key.split(".", 1)[0] for key in portfolio.FORMULAS} <= set(portfolio.SECTIONS)


class TestTheDoors:
    def test_the_guide_names_exactly_the_doors_that_are_routed(self) -> None:
        declared = {(entry["method"], f"/api/v1{entry['path']}") for entry in portfolio_router.ROUTE_GUIDE}
        assert len(declared) == len(portfolio_router.ROUTE_GUIDE), "two entries describe one door"
        live: set[tuple[str, str]] = set()
        for route in app.routes:
            path = str(getattr(route, "path", ""))
            if path.startswith("/api/v1/portfolio"):
                live |= {(method, path) for method in set(getattr(route, "methods", ()) or ()) - {"HEAD", "OPTIONS"}}
        assert declared == live, f"only in the guide: {sorted(declared - live)}; only routed: {sorted(live - declared)}"

    def test_the_rules_door_is_public_and_holds_no_persons_rows(self) -> None:
        response = TestClient(app).get(RULES)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["routes"] == [dict(item) for item in portfolio_router.ROUTE_GUIDE]
        assert [item["title"] for item in body["sections"]] == list(SPEC_38_TITLES)
        assert [item["fillable"] for item in body["sections"]] == [key not in portfolio.UNFILLED_REASONS for key in portfolio.SECTIONS]
        assert body["unfilled"] == {key: portfolio.UNFILLED_REASONS[key] for key in ("matches", "stats")}
        assert body["would_read_from"] == dict(portfolio.WOULD_READ_FROM)
        assert body["formulas"] == dict(portfolio.FORMULAS)
        assert body["public_outputs"] == dict(portfolio.PUBLIC_OUTPUTS)
        assert body["limitation"] == portfolio.LIMITATION
        assert body["refusal_answers"] == {}, "this tier raises no code; one appearing here arrived without its status"
        for key in ("account", "player", "user_id", "sections_filled"):
            assert key not in body

    def test_the_cv_door_answers_401_before_it_reads_a_row(self) -> None:
        assert TestClient(app).get(CV).status_code == 401
        client = _client("Dee Door")
        assert _player(client)["position"] == "CM"
        response = client.get(CV)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["counts"]["sections"] == 10
        assert body["player"]["position"] == "CM"


def test_no_answer_in_this_tier_is_money() -> None:
    client = _client("Eve Money")
    _player(client)
    _complete_a_session(client)
    words = " ".join(_walk([TestClient(app).get(RULES).json(), client.get(CV).json()])).lower()
    assert not [word for word in MONEY_WORDS if word in words], "§42 owns pricing; a CV is not a shop"
