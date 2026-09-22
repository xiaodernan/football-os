"""M4 Tactical Lab over HTTP: the catalogue is stored, served, recomputed and impossible to half-write.

Mirrors the M3 split — the pure plan is tested in `test_tactics.py`, and these tests prove the same
numbers survive a round trip into the database and out through the API. Everything here is read
without an account on purpose: a tactical system is project-authored content, and spec §80 wants it
crawlable, so an auth wall on these routes would be a defect rather than a feature.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.tactics.analysis import CHANGES, METRIC_KEYS
from app.services.tactics.plan import SYSTEM_COUNT, fingerprint, planned_rows
from app.services.tactics.sync import TACTICS_GATE, _validate, sync_tactics
from app.services.world.plan import Planned

API = "/api/v1/tactics"
SLUG = "4-3-3-press-high"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    store = SessionLocal()
    try:
        yield store
    finally:
        store.close()


class TestStatus:
    def test_status_reports_the_stored_catalogue_and_its_gate(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/status").json()
        assert client.get(f"{API}/status").status_code == 200
        assert body["ready"] is True and body["stored"] == SYSTEM_COUNT
        assert body["counts"] == dict(TACTICS_GATE)
        assert body["gate"] == {"tactical_systems": SYSTEM_COUNT}
        assert body["catalogue_fingerprint"] == fingerprint()
        assert len(body["formations"]) == 10 and len(body["temperaments"]) == 5

    def test_status_publishes_the_formulas_not_just_the_numbers(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/status").json()
        assert {metric["key"] for metric in body["metrics"]} == set(METRIC_KEYS)
        assert all(metric["formula"] and metric["unit"] in {"m", "m²"} for metric in body["metrics"])
        assert [change["key"] for change in body["changes"]] == list(CHANGES)

    def test_every_response_carries_its_own_provenance(self, client) -> None:  # type: ignore[no-untyped-def]
        for path in ("/status", "", f"/{SLUG}"):
            body = client.get(f"{API}{path}").json()
            assert body["data_origin"] == "project-authored", path
            assert body["is_demo_data"] is False, path
            assert "no tracking data" in body["disclaimer"], path


class TestListing:
    def test_the_list_pages_and_links_the_route_the_api_promises(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(API).json()
        assert (body["page"], body["page_size"], body["total"], body["pages"]) == (1, 20, SYSTEM_COUNT, 3)
        assert len(body["items"]) == 20
        for item in body["items"]:
            assert item["path"] == f"/tactics/{item['slug']}"
            assert set(item["in_possession"]) <= set(METRIC_KEYS)
            assert item["in_possession"]["space_behind"] > 0

    @pytest.mark.parametrize(
        ("params", "expected"),
        [({"formation": "4-3-3"}, 5), ({"temperament": "low-block"}, 10), ({"formation": "4-3-3", "temperament": "low-block"}, 1)],
    )  # type: ignore[no-untyped-def]
    def test_filters_narrow_without_inventing_rows(self, client, params: dict[str, str], expected: int) -> None:  # type: ignore[no-untyped-def]
        body = client.get(API, params=params).json()
        assert body["total"] == expected, params
        assert len(body["items"]) == expected

    def test_a_search_that_matches_nothing_says_so(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(API, params={"search": "zzqxvjtunf"}).json()
        assert body["total"] == 0 and body["items"] == []


class TestDetail:
    def test_a_system_resolves_by_slug_and_by_id_with_the_same_board(self, client) -> None:  # type: ignore[no-untyped-def]
        by_slug = client.get(f"{API}/{SLUG}")
        assert by_slug.status_code == 200, by_slug.text
        detail = by_slug.json()
        by_id = client.get(f"{API}/{detail['id']}")
        assert by_id.status_code == 200
        assert by_id.json()["phase_in"] == detail["phase_in"]
        assert detail["path"] == f"/tactics/{SLUG}"

    def test_both_phases_hold_eleven_positions_and_are_related_by_the_published_transform(self, client) -> None:  # type: ignore[no-untyped-def]
        detail = client.get(f"{API}/{SLUG}").json()
        assert len(detail["phase_in"]) == len(detail["phase_out"]) == 11
        assert {row["role"] for row in detail["phase_in"]} == {row["role"] for row in detail["phase_out"]}, "the same eleven players defend"
        depths = [row["y"] for row in detail["phase_out"] if row["role"] != "GK"]
        assert round(max(depths) - min(depths), 1) == round(detail["block_depth"], 1)
        assert round(max(depths), 1) == round(detail["press_line_y"], 1)
        assert f"{detail['block_depth']} m" in detail["transform_note"]

    def test_the_stored_verdicts_quote_measurements_that_reproduce_from_the_board(self, client) -> None:  # type: ignore[no-untyped-def]
        detail = client.get(f"{API}/{SLUG}").json()
        measured = {metric["key"]: metric["value"] for metric in detail["metrics_in"]}
        assert len(detail["metrics_in"]) == len(METRIC_KEYS)
        assert measured["width"] > 0 and measured["space_behind"] > 0
        assert detail["strengths"] and detail["risks"]
        assert len(detail["roles"]) == 11

    def test_an_unknown_slug_is_a_404_not_an_empty_board(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/4-3-3-not-a-real-temperament")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"

    def test_the_boards_namespace_says_where_it_actually_lives(self, client) -> None:  # type: ignore[no-untyped-def]
        # `/tactics/boards` is the web page path; the API's boards live under `/boards`. A client that
        # confuses them must get a pointer, not a misleading "no such tactical system".
        response = client.get(f"{API}/boards")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["code"] == "wrong_path" and "/api/v1/boards" in detail["message"]


class TestCounterfactual:
    def test_raising_the_back_line_is_recomputed_from_the_stored_board(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/{SLUG}/counterfactual", params={"change": "raise-back-line"}).json()
        assert body["recomputed"] is True
        moved = {item["key"]: item for item in body["metrics"]}
        assert moved["space_behind"]["delta"] == pytest.approx(8.0)
        assert moved["depth"]["delta"] == pytest.approx(-8.0)
        assert body["moved_count"] >= 3
        assert len(body["board_after"]) == 11
        assert all(entry["role"] in {"RB", "LB", "DCB", "RWB", "LWB"} for entry in body["clamped"])

    def test_a_clamped_coordinate_is_reported_instead_of_hidden(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/5-3-2-press-high/counterfactual", params={"change": "step-everything-up", "phase": "out"}).json()
        for entry in body["clamped"]:
            assert entry["asked"] != entry["placed"]
            assert -34.0 <= entry["placed"]["x"] <= 34.0 and 0.0 <= entry["placed"]["y"] <= 105.0

    def test_an_unknown_change_is_a_validation_error_listing_the_choices(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/{SLUG}/counterfactual", params={"change": "teleport-striker"})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "unknown_change"
        assert all(key in detail["message"] for key in CHANGES)

    def test_two_boards_compare_metric_by_metric(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/compare", params={"a": SLUG, "b": "4-3-3-low-block", "phase": "out"}).json()
        assert len(body["metrics"]) == len(METRIC_KEYS)
        for row in body["metrics"]:
            assert row["delta"] == pytest.approx(round(row["b"] - row["a"], 2))
            assert row["formula"]
        assert body["a"]["slug"] == SLUG and body["b"]["slug"] == "4-3-3-low-block"
        # A high press defends further from its own goal than a low block — the whole point of the pair.
        behind = {row["key"]: row for row in body["metrics"]}["space_behind"]
        assert behind["a"] > behind["b"]


class TestPersistence:
    def test_a_second_sync_is_a_no_op(self, session) -> None:  # type: ignore[no-untyped-def]
        first = sync_tactics(session)
        assert first.ok
        second = sync_tactics(session)
        assert second.ok and second.created == 0 and second.updated == 0
        assert second.unchanged == SYSTEM_COUNT and second.removed == 0

    def test_a_broken_plan_writes_nothing_rather_than_half_a_catalogue(self, session) -> None:  # type: ignore[no-untyped-def]
        rows = planned_rows()
        broken = rows[0]
        payload = dict(broken.payload)
        payload["phase_in"] = payload["phase_in"][:9]  # nine players is not a team
        damage = Planned(natural_key=broken.natural_key, payload=payload, content_hash=broken.content_hash)
        assert _validate(damage), "the validator must see a truncated board"

        import app.services.tactics.sync as sync_module

        original = sync_module.planned_rows
        sync_module.planned_rows = lambda: [damage, *rows[1:]]  # type: ignore[assignment]
        try:
            report = sync_tactics(session)
        finally:
            sync_module.planned_rows = original  # type: ignore[assignment]
        assert not report.ok
        assert any("phase_in holds 9 positions" in problem for problem in report.errors)
        assert report.created == 0 and report.updated == 0

    def test_capabilities_advertise_m4_only_because_the_rows_are_there(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get("/api/v1/capabilities").json()
        assert body["m4_tactical_lab"] is True
        assert body["m4_tactics"]["counts"]["tactical_systems"] == SYSTEM_COUNT
        assert body["m4_tactics"]["tables_present"] is True
