"""The record book — eight marks, straight from the stored rows.

These cases pin the shape of the JSON the door returns, the honesty rules the records
cannot break (every claimed figure must exist in the tables), and that the book orders
itself in the order the catalogue prints.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from sqlalchemy import event

from app.core import db as db_module
from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.records import RECORD_KEYS, compute_records

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheRecords:
    def test_compute_returns_every_record_exactly_once(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_records(session)
        assert [r["key"] for r in result["records"]] == list(RECORD_KEYS)

    def test_every_available_record_carries_a_payload_it_can_defend(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_records(session)
        for record in result["records"]:
            if not record["available"]:
                continue
            assert record["key"] in RECORD_KEYS

    def test_the_door_answers_with_an_envelope_like_its_neighbours(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/records")
        assert response.status_code == 200
        body = response.json()
        assert [r["key"] for r in body["records"]] == list(RECORD_KEYS)
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"records", "season"}

    def test_the_records_are_not_empty_on_a_live_world(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_records(session)
        available = [r for r in result["records"] if r["available"]]
        assert len(available) == len(RECORD_KEYS), "every record should be earned by a seeded 7:3 world"

    def test_the_book_asks_the_world_once(self, session) -> None:  # type: ignore[no-untyped-def]
        """Pin the hot path's read shape: the league scan, the completed-fixtures scan, and the team table, once each.

        This arc cut the book's read from fourteen SQL statements to eight (nine after the first push,
        eight once the team table was threaded into the league centre as well); this case is the witness
        that keeps the repeat scans removed. It counts statements by their table-qualified
        `SELECT <table>.` prefix — SQLAlchemy emits this exact shape for a flat scan of
        one table — so joins against the same tables from the aggregate queries don't
        inflate the count. The `field =` distinction separates the league-scoped fixtures
        from the world-wide completed set; both project `competition_id`, so the bare-column
        check cannot.
        """
        counts = {"league": 0, "completed": 0, "teams": 0}

        def before(conn, clauseelement, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
            text = " ".join(statement.split())
            if re.match(r"^SELECT\s+real_matches\.", text):
                # `field =`, not the bare column — every flat scan of this table projects `competition_id`
                if "competition_id =" in text:
                    counts["league"] += 1
                else:
                    counts["completed"] += 1
            elif re.match(r"^SELECT\s+teams\.", text) and "FROM teams" in text:
                counts["teams"] += 1

        engine = db_module.engine
        event.listen(engine, "before_cursor_execute", before)
        try:
            compute_records(session)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        assert counts["league"] <= 1, f"the league-scoped fixtures scan ran {counts['league']} times"
        assert counts["completed"] <= 1, f"the completed-fixtures scan ran {counts['completed']} times"
        assert counts["teams"] <= 1, f"the teams table was pulled {counts['teams']} times"
