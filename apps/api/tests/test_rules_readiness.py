"""#146 — the two public rulebooks promise zeros before the migration, and no door could reach that branch.

`community_counts` and the seven creator `*_counts` functions return zeros when `ready` is false, and their
docstrings say why: a database that has not run the migration is empty, not broken. But both `rules` functions
defaulted `ready` to `True` and both doors passed `ready=True` by hand — so on a database without the tier's
tables, `GET /community/rules` and `GET /creator/rules` answered **500** with
`no such table: creator_profiles`, not the zeros the branch exists for. Every other rulebook door measures its
readiness (`world_ready`, `club_ready`, `academy_ready`, `scout_ready`); these two were the exception.

The fix measures readiness at the door, from the presence of every table the counts read, and publishes it
beside a rule that says what it means. `rules` no longer defaults `ready`, so the value a door prints is the
one it measured.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_db
from app.main import app
from app.models import Base, CommunityPost, CreatorProfile
from app.services.community import posts as com
from app.services.creator import publishing as cre

COMMUNITY = "/api/v1/community/rules"
CREATOR = "/api/v1/creator/rules"

COMMUNITY_COUNTS = {"posts", "comments", "reactions", "reposts", "follows"}
CREATOR_COUNTS = {
    "counts": {"profiles", "guides", "citations"},
    "program_counts": {"programs", "steps"},
    "tactical_counts": {"tactical_guides"},
    "analysis_counts": {"player_analyses"},
    "match_counts": {"match_analyses"},
    "scouting_list_counts": {"scouting_lists", "scouting_entries"},
    "career_challenge_counts": {"career_challenges", "career_attempts"},
}

#: The tables readiness is measured on, named here independently of the tuples under test: deriving this set
#: from `com.COMMUNITY_TABLES` would let an entry dropped from the tuple drop itself from the expectation too.
COMMUNITY_TABLES = {
    "community_posts",
    "community_comments",
    "community_reactions",
    "community_reposts",
    "community_follows",
}
CREATOR_TABLES = {
    "creator_profiles",
    "creator_guides",
    "guide_citations",
    "creator_programs",
    "creator_program_steps",
    "creator_tactical_guides",
    "creator_player_analyses",
    "creator_match_analyses",
    "creator_scouting_lists",
    "creator_scouting_entries",
    "creator_career_challenges",
    "creator_career_attempts",
}


@contextmanager
def served_on(engine: Engine) -> Iterator[TestClient]:
    """A client whose request session is bound to `engine`, and a 500 read as a status."""
    sessions = sessionmaker(bind=engine)

    def override() -> Iterator[Session]:
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app, raise_server_exceptions=False) as served:
            yield served
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.fixture()
def empty_database(tmp_path) -> Iterator[Engine]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    yield engine
    engine.dispose()


def test_the_community_rulebook_answers_an_empty_database_with_five_zeros(
    empty_database: Engine,
) -> None:
    with served_on(empty_database) as served:
        response = served.get(COMMUNITY)
    assert (
        response.status_code == 200
    ), f"a database without the community tables answered {response.status_code}: {response.text[:200]}"
    body = response.json()
    assert (
        body["ready"] is False
    ), "the door claimed readiness on a database that holds none of its five tables"
    assert body["counts"] == {
        name: 0 for name in COMMUNITY_COUNTS
    }, f"the counts were not five true zeros: {body['counts']}"
    assert body[
        "ready_rule"
    ], "the door published readiness without saying what it means"


def test_the_creator_rulebook_answers_an_empty_database_with_twelve_zeros(
    empty_database: Engine,
) -> None:
    with served_on(empty_database) as served:
        response = served.get(CREATOR)
    assert (
        response.status_code == 200
    ), f"a database without the creator tables answered {response.status_code}: {response.text[:200]}"
    body = response.json()
    assert (
        body["ready"] is False
    ), "the door claimed readiness on a database that holds none of its twelve tables"
    for key, names in CREATOR_COUNTS.items():
        assert body[key] == {
            name: 0 for name in names
        }, f"{key} was not a set of true zeros: {body[key]}"
    assert body[
        "ready_rule"
    ], "the door published readiness without saying what it means"


def _create(engine: Engine, names: set[str]) -> None:
    tables = [table for table in Base.metadata.sorted_tables if table.name in names]
    assert {table.name for table in tables} == names, "the metadata lacks a table this gate names"
    for table in tables:
        table.create(engine)


def test_the_community_readiness_needs_every_table_not_just_one(
    empty_database: Engine,
) -> None:
    CommunityPost.__table__.create(empty_database)
    with served_on(empty_database) as served:
        response = served.get(COMMUNITY)
    assert response.status_code == 200, response.text[:200]
    body = response.json()
    assert (
        body["ready"] is False
    ), "one of the five tables was enough to call the tier ready"
    assert (
        body["counts"] == {name: 0 for name in COMMUNITY_COUNTS}
    ), f"a partly migrated database was counted past the missing tables: {body['counts']}"


def test_the_creator_readiness_needs_every_table_not_just_one(
    empty_database: Engine,
) -> None:
    CreatorProfile.__table__.create(empty_database)
    with served_on(empty_database) as served:
        response = served.get(CREATOR)
    assert response.status_code == 200, response.text[:200]
    body = response.json()
    assert (
        body["ready"] is False
    ), "one of the twelve tables was enough to call the tier ready"
    for key, names in CREATOR_COUNTS.items():
        assert body[key] == {
            name: 0 for name in names
        }, f"{key} was counted past the missing tables: {body[key]}"


def test_the_community_readiness_falls_when_the_last_table_is_dropped(
    empty_database: Engine,
) -> None:
    _create(empty_database, COMMUNITY_TABLES)
    with empty_database.begin() as connection:
        connection.execute(text("DROP TABLE community_follows"))
    with served_on(empty_database) as served:
        response = served.get(COMMUNITY)
    assert response.status_code == 200, response.text[:200]
    body = response.json()
    assert (
        body["ready"] is False
    ), "the four remaining tables were enough to call the tier ready after the fifth was dropped"
    assert (
        body["counts"] == {name: 0 for name in COMMUNITY_COUNTS}
    ), f"counts were read past a dropped table: {body['counts']}"


def test_the_creator_readiness_falls_when_the_last_table_is_dropped(
    empty_database: Engine,
) -> None:
    _create(empty_database, CREATOR_TABLES)
    with empty_database.begin() as connection:
        connection.execute(text("DROP TABLE creator_career_attempts"))
    with served_on(empty_database) as served:
        response = served.get(CREATOR)
    assert response.status_code == 200, response.text[:200]
    body = response.json()
    assert (
        body["ready"] is False
    ), "the eleven remaining tables were enough to call the tier ready after the twelfth was dropped"
    for key, names in CREATOR_COUNTS.items():
        assert body[key] == {
            name: 0 for name in names
        }, f"{key} was counted past a dropped table: {body[key]}"


def test_both_rulebooks_are_ready_on_the_migrated_database(client) -> None:  # type: ignore[no-untyped-def]
    for path in (COMMUNITY, CREATOR):
        response = client.get(path)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ready"] is True, f"{path} called a fully migrated database unready"
        assert body["ready_rule"], f"{path} published readiness without a rule"


def test_the_readiness_tuple_is_exactly_the_tables_the_counts_read() -> None:
    assert set(com.COMMUNITY_TABLES) == COMMUNITY_TABLES, com.COMMUNITY_TABLES
    assert len(com.COMMUNITY_TABLES) == len(set(com.COMMUNITY_TABLES))
    assert set(cre.CREATOR_TABLES) == CREATOR_TABLES, cre.CREATOR_TABLES
    assert len(cre.CREATOR_TABLES) == len(set(cre.CREATOR_TABLES))
    assert (
        len({name for group in CREATOR_COUNTS.values() for name in group})
        == len(CREATOR_TABLES)
    ), "the readiness universe and the count keys disagree about how many tables exist"


def test_the_published_contract_says_where_readiness_comes_from() -> None:
    for path in (COMMUNITY, CREATOR):
        description = app.openapi()["paths"][path]["get"].get("description", "")
        assert (
            "ready" in description and "table" in description
        ), f"{path}'s description does not say readiness is measured from the tier's tables: {description!r}"
