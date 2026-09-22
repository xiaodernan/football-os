"""M4 user boards: a saved arrangement is validated on write and measured on read, and only its owner sees it.

The interesting assertions here are the ones about ownership and about *change*: a board that moved a
player must show different numbers afterwards (otherwise the metrics are decoration), and a second
account must not be able to tell whether a board exists at all.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import TacticBoard
from app.services.tactics.boards import problems_with
from app.services.tactics.plan import tactical_systems

API = "/api/v1/boards"


def _positions(slug: str, phase: str = "phase_in") -> list[dict[str, object]]:
    system = next(item for item in tactical_systems() if item.slug == slug)
    shape = system.phase_in if phase == "phase_in" else system.phase_out
    return shape.as_dict()


def _create(client, name: str = "My 4-3-3", slug: str = "4-3-3-press-high", **extra: object) -> dict:
    payload = {"name": name, "origin_system": slug, "phase_in": _positions(slug), "phase_out": _positions(slug, "phase_out"), **extra}
    response = client.post(API, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestCreateAndMeasure:
    def test_a_board_starts_from_an_authored_system_and_keeps_its_numbers(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client)
        authored = auth_client.get("/api/v1/tactics/4-3-3-press-high").json()
        assert board["data_origin"] == "user" and board["is_demo_data"] is False
        assert board["visibility"] == "private" and board["share_url"] is None
        assert {row["role"] for row in board["phase_in"]} == {row["role"] for row in authored["phase_in"]}
        assert {m["key"]: m["value"] for m in board["metrics_in"]} == {m["key"]: m["value"] for m in authored["metrics_in"]}
        assert "arranged by a FOOTBALL OS user" in board["disclaimer"]

    def test_moving_a_player_changes_the_measured_numbers(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        before = _create(auth_client)
        # Raise the whole defensive line, which is the one edit whose effect on `space_behind` is
        # exact: the measure is the *deepest* defender, so lifting one of the two centre-backs alone
        # would prove nothing.
        positions = [dict(row) for row in before["phase_in"]]
        for row in positions:
            if row["role"] in {"RB", "LB", "DCB"}:
                row["y"] = float(row["y"]) + 10.0
        after = auth_client.patch(f"{API}/{before['slug']}", json={"phase_in": positions})
        assert after.status_code == 200, after.text
        body = after.json()
        space_before = next(m for m in before["metrics_in"] if m["key"] == "space_behind")["value"]
        space_after = next(m for m in body["metrics_in"] if m["key"] == "space_behind")["value"]
        assert space_after == pytest.approx(space_before + 10.0), "raising the back line must move the number"
        assert body["updated_at"] != before["updated_at"]

    def test_the_block_can_be_derived_by_the_same_transform_the_catalogue_uses(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(
            API,
            json={"name": "Derived block", "phase_in": _positions("4-4-2-control-possession"), "derive_block": True, "block": {"press_line_y": 60.0, "block_depth": 32.0, "defensive_narrowing": 0.9}},
        )
        assert response.status_code == 201, response.text
        board = response.json()
        ys = [row["y"] for row in board["phase_out"] if row["role"] != "GK"]
        assert round(max(ys), 1) == 60.0
        assert round(max(ys) - min(ys), 1) == pytest.approx(32.0, abs=0.1)
        assert {row["role"] for row in board["phase_out"]} == {row["role"] for row in board["phase_in"]}

    def test_an_eleven_that_is_not_eleven_players_is_never_stored(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        short = [dict(row) for row in _positions("4-3-3-press-high")][:10]
        response = auth_client.post(API, json={"name": "Ten players", "phase_in": short, "phase_out": short})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_board"
        assert "expected 11" in detail["message"]
        assert auth_client.get(API).json()["total"] == 0

    @pytest.mark.parametrize(  # type: ignore[no-untyped-def]
        ("mutation", "needle"),
        [({"role": "WINGER"}, "unknown role"), ({"x": 900.0}, "off a"), ({"y": -5.0}, "off a")],
    )
    def test_each_kind_of_impossible_coordinate_is_named_not_silently_clamped(self, auth_client, mutation: dict[str, object], needle: str) -> None:  # type: ignore[no-untyped-def]
        positions = [dict(row) for row in _positions("4-3-3-press-high")]
        positions[3] = {**positions[3], **mutation}
        response = auth_client.post(API, json={"name": "Impossible", "phase_in": positions, "phase_out": _positions("4-3-3-press-high", "phase_out")})
        assert response.status_code == 422
        assert needle in response.json()["detail"]["message"], response.json()["detail"]

    def test_a_non_finite_coordinate_is_refused_even_though_json_can_carry_it(self) -> None:
        """NaN and Infinity are Python-JSON extensions, and `Point` would reject them too late.

        Tested at the service boundary because no correct client can send them: the point of the
        guard is that a hand-built request cannot store a position that poisons every average.
        """
        rows = _positions("4-3-3-press-high")
        for bad in (float("nan"), float("inf")):
            mutated = [dict(row) for row in rows]
            mutated[5] = {**mutated[5], "x": bad}
            problems = problems_with(mutated, label="phase_in")
            assert any("finite metres" in problem for problem in problems), (bad, problems)

    def test_an_origin_that_does_not_exist_is_refused(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(
            API,
            json={"name": "Fake origin", "origin_system": "4-3-3-not-a-temperament", "phase_in": _positions("4-3-3-press-high"), "phase_out": _positions("4-3-3-press-high", "phase_out")},
        )
        assert response.status_code == 422
        assert "not a stored tactical system" in response.json()["detail"]["message"]


class TestOwnership:
    def test_another_account_cannot_tell_whether_the_board_exists(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Private work")
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as stranger:
            register = stranger.post(
                "/api/v1/auth/register",
                json={"email": "board-stranger@example.test", "password": "strong-pass-1234", "display_name": "Stranger", "role": "coach", "accepts_data_policy": True},
            )
            assert register.status_code == 201, register.text
            stranger.headers.update({"Authorization": f"Bearer {register.json()['access_token']}"})
            assert stranger.get(API).json()["total"] == 0
            for response in (
                stranger.get(f"{API}/{board['slug']}"),
                stranger.patch(f"{API}/{board['slug']}", json={"name": "hijacked"}),
                stranger.post(f"{API}/{board['slug']}/share"),
                stranger.delete(f"{API}/{board['slug']}"),
            ):
                assert response.status_code == 404, response.text
        # and it really is still the first account's, unchanged
        assert auth_client.get(f"{API}/{board['slug']}").json()["name"] == "Private work"

    def test_deleting_removes_the_row_and_the_share_with_it(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Temporary")
        shared = auth_client.post(f"{API}/{board['id']}/share").json()
        token = shared["share_token"]
        assert auth_client.get(f"{API}/shared/{token}").status_code == 200
        assert auth_client.delete(f"{API}/{board['id']}").status_code == 204
        assert auth_client.get(f"{API}/shared/{token}").status_code == 404
        with SessionLocal() as session:
            assert session.scalar(select(TacticBoard).where(TacticBoard.id == board["id"])) is None

    def test_the_per_account_ceiling_is_a_real_number_and_says_so(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        for index in range(24):
            response = auth_client.post(
                API,
                json={"name": f"Board {index:02d}", "phase_in": _positions("4-3-3-press-high"), "phase_out": _positions("4-3-3-press-high", "phase_out")},
            )
            assert response.status_code == 201, (index, response.text)
        overflow = auth_client.post(API, json={"name": "Board 24", "phase_in": _positions("4-3-3-press-high"), "phase_out": _positions("4-3-3-press-high", "phase_out")})
        assert overflow.status_code == 409
        assert overflow.json()["detail"]["code"] == "board_limit"


class TestSharing:
    def test_boards_need_a_session_at_every_door(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(API).status_code == 401
        assert client.post(API, json={"name": "nope", "phase_in": [], "phase_out": []}).status_code == 401
        assert client.get(f"{API}/shared/whatever").status_code == 404

    def test_a_shared_board_is_readable_by_anyone_and_reveals_no_owner(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Shared shape")
        shared = auth_client.post(f"{API}/{board['slug']}/share").json()
        assert shared["visibility"] == "shared" and shared["share_url"] == f"/tactics/shared/{shared['share_token']}"
        assert shared["share_url"].startswith("/tactics/shared/"), "a share link must not sit behind the login wall"

        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as visitor:
            response = visitor.get(f"{API}/shared/{shared['share_token']}")
            assert response.status_code == 200
            body = response.json()
            assert body["name"] == "Shared shape"
            assert body["data_origin"] == "user"
            leaked = [key for key in ("email", "owner_id", "share_token") if key in body]
            assert leaked == [], f"the shared view exposes {leaked}"
            assert body["owner"] == {"name": "a FOOTBALL OS account", "id": None}
            assert "note" in body, "the owner's own annotation is part of what they chose to share"
            assert len(body["metrics_in"]) == 8

    def test_revoking_kills_the_link_and_leaves_the_board(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Revoke me")
        token = auth_client.post(f"{API}/{board['slug']}/share").json()["share_token"]
        revoked = auth_client.post(f"{API}/{board['slug']}/revoke").json()
        assert revoked["visibility"] == "private" and revoked["share_url"] is None
        assert auth_client.get(f"{API}/shared/{token}").status_code == 404
        assert auth_client.get(f"{API}/{board['slug']}").status_code == 200

    def test_sharing_twice_keeps_one_working_link(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Stable link")
        first = auth_client.post(f"{API}/{board['slug']}/share").json()["share_token"]
        second = auth_client.post(f"{API}/{board['slug']}/share").json()["share_token"]
        assert first == second, "re-sharing must not break a link already sent out"

    def test_a_share_token_is_not_guessable_from_the_board_id(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        board = _create(auth_client, name="Opaque")
        shared = auth_client.post(f"{API}/{board['slug']}/share").json()
        token = shared["share_token"]
        assert len(token) == 32 and board["id"] not in token and token.isalnum()
        with SessionLocal() as session:
            stored = session.scalar(select(TacticBoard).where(TacticBoard.id == board["id"]))
            assert stored is not None and stored.share_token == token and stored.visibility == "shared"
