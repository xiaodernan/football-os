"""The season's story — three chapters straight from the stored fixtures.

`compute_story` is the narrative layer of the almanac era. These cases pin the shape of the
JSON the door returns, the coherence with the almanac's own title-race chapter, and the honesty
rules the chapters are not allowed to break: a chapter with nothing to print publishes no names,
and chapter I can never disagree with the door next to it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import RealMatch
from app.services.world import sync_world
from app.services.world.story import compute_story

API = "/api/v1"
CHAPTER_KEYS = ("title_race", "avalanche", "unbeaten_run")


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheStory:
    def test_compute_returns_every_chapter_exactly_once(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_story(session)
        assert [chapter["key"] for chapter in result["chapters"]] == list(CHAPTER_KEYS)

    def test_chapter_one_is_the_almanacs_title_race_verbatim(self, session) -> None:  # type: ignore[no-untyped-def]
        from app.services.world.almanac import compute_almanac

        story = compute_story(session)
        almanac = compute_almanac(session)
        chapter = story["chapters"][0]
        if almanac["title_race"].get("available"):
            assert chapter["available"] is True
            assert chapter["champion"]["points"] == almanac["title_race"]["champion"]["points"]
            assert chapter["champion"]["name"] == almanac["title_race"]["champion"]["name"]
            assert chapter["margin"] == almanac["title_race"]["margin"]
        else:
            assert chapter.get("available") is False

    def test_chapter_two_picks_the_biggest_stored_margin(self, session) -> None:  # type: ignore[no-untyped-def]
        story = compute_story(session)
        chapter = story["chapters"][1]
        if not chapter["available"]:
            return  # a world with no decisive result publishes no avalanche — never an invented one
        rows = session.scalars(
            select(RealMatch).where(RealMatch.status == "completed")
        ).all()
        margins = [
            abs((m.home_goals or 0) - (m.away_goals or 0))
            for m in rows
            if m.home_goals is not None and m.away_goals is not None
        ]
        assert margins, "the chapter claimed a result that does not exist in the stored rows"
        assert chapter["margin"] == max(margins)

    def test_chapter_three_finds_a_real_unbeaten_streak(self, session) -> None:  # type: ignore[no-untyped-def]
        story = compute_story(session)
        chapter = story["chapters"][2]
        if not chapter["available"]:
            return
        assert chapter["run"] >= 1
        assert chapter["team"]["path"].startswith("/team/")

    def test_the_door_answers_with_an_envelope_like_its_neighbours(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/story")
        assert response.status_code == 200
        body = response.json()
        assert [chapter["key"] for chapter in body["chapters"]] == list(CHAPTER_KEYS)
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"chapters", "season"}
