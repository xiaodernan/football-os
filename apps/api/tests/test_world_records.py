"""The record book — eight marks, straight from the stored rows.

These cases pin the shape of the JSON the door returns, the honesty rules the records
cannot break (every claimed figure must exist in the tables), and that the book orders
itself in the order the catalogue prints.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

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
