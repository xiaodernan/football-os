"""End-to-end API tests for the M1 vertical slice: the first real FOOTBALL OS loop."""

from __future__ import annotations


def test_health_reports_demo_mode(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["providers"]["demo_mode"] is True
    assert any("DEMO MODE" in note for note in body["notes"])


def test_register_login_refresh_and_me(auth_client, client) -> None:  # type: ignore[no-untyped-def]
    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "player"
    assert me.json()["streak_days"] == 0
    assert client.post("/api/v1/auth/login", json={"email": me.json()["email"], "password": "wrong-password-123"}).status_code == 401
    refreshed = auth_client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


def test_duplicate_email_is_rejected(client) -> None:  # type: ignore[no-untyped-def]
    payload = {"email": "dup@example.test", "password": "strong-pass-1234", "display_name": "Dup", "role": "player", "accepts_data_policy": True}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_weak_password_and_missing_consent_are_rejected(client) -> None:  # type: ignore[no-untyped-def]
    short = client.post("/api/v1/auth/register", json={"email": "weak@example.test", "password": "123", "display_name": "W", "accepts_data_policy": True})
    assert short.status_code == 422
    no_consent = client.post(
        "/api/v1/auth/register", json={"email": "nc@example.test", "password": "strong-pass-1234", "display_name": "NC", "accepts_data_policy": False}
    )
    assert no_consent.status_code == 422
    assert no_consent.json()["error"]["code"] == "validation_error"


def test_routes_require_authentication(client) -> None:  # type: ignore[no-untyped-def]
    for path in ["/api/v1/players", "/api/v1/coach/today", "/api/v1/progress/overview", "/api/v1/trainings/drills"]:
        assert client.get(path).status_code == 401, path


def test_player_creation_returns_explainable_profile(auth_client) -> None:  # type: ignore[no-untyped-def]
    response = auth_client.post(
        "/api/v1/players",
        json={"name": "Playmaker", "position": "CAM", "age": 19, "level": "advanced", "preferred_foot": "left", "goal": "become_playmaker", "height_cm": 176},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["overall"] > 30
    assert body["archetype"] in {"Advanced Playmaker", "Complete Forward", "Inverted Winger", "Box-to-Box", "Deep-Lying Playmaker"}
    assert len(body["derivation_reasons"]) >= 4
    assert set(body["attributes"]) >= {"first_touch", "vision", "stamina"}
    assert body["is_demo_data"] is False


def test_invalid_position_is_rejected(auth_client) -> None:  # type: ignore[no-untyped-def]
    response = auth_client.post(
        "/api/v1/players", json={"name": "Bad", "position": "STR", "age": 22, "level": "advanced", "preferred_foot": "right", "goal": "improve_passing"}
    )
    assert response.status_code == 422


def test_training_loop_awards_xp_and_explains_every_change(auth_client, player_id) -> None:  # type: ignore[no-untyped-def]
    drills = auth_client.get("/api/v1/trainings/drills").json()
    assert len(drills) >= 20
    assert all(drill["is_demo_data"] for drill in drills)

    today = auth_client.get(f"/api/v1/coach/today?player_id={player_id}&available_minutes=30")
    assert today.status_code == 200
    recommendation = today.json()
    assert recommendation["demo_mode"] is True
    assert recommendation["reasons"]
    assert recommendation["disclaimer"]
    slug = recommendation["recommendation"]["slug"]

    drill_rows = {d["slug"]: d for d in drills}
    drill_id = drill_rows[slug]["id"]
    planned = auth_client.post("/api/v1/trainings/sessions", json={"drill_id": drill_id, "available_minutes": 30, "has_pitch": True})
    assert planned.status_code == 201
    session_id = planned.json()["session_id"]

    completed = auth_client.post(f"/api/v1/trainings/sessions/{session_id}/complete", json={"execution": 5, "focus": 4, "difficulty_experience": 4, "self_notes": "Felt sharp"})
    assert completed.status_code == 200
    result = completed.json()
    assert result["xp_awarded"] > 0
    assert "base" in result["xp_formula"]
    assert result["coach_feedback"]["content"]
    assert any("first-session" == a for a in result["new_achievements"]) or result["new_achievements"]
    assert all(change["delta"] == 1 and change["reason"] for change in result["attribute_changes"])

    sessions = auth_client.get("/api/v1/trainings/sessions").json()["items"]
    logged = [row for row in sessions if row["id"] == session_id]
    assert logged and logged[0]["self_notes"] == "Felt sharp", "a note typed by the user must be stored verbatim"

    repeat = auth_client.post(f"/api/v1/trainings/sessions/{session_id}/complete", json={"execution": 5, "focus": 5, "difficulty_experience": 5})
    assert repeat.status_code == 409

    overview = auth_client.get("/api/v1/progress/overview").json()
    assert overview["xp"]["total"] == result["player"]["xp"]
    assert overview["training"]["sessions_completed"] == 1
    assert overview["training"]["streak_days"] == 1
    assert overview["empty_state"] is False

    timeline = auth_client.get("/api/v1/progress/timeline").json()
    assert timeline["xp_events"] and timeline["xp_events"][0]["formula"]
    assert timeline["sessions"][0]["status"] == "completed"

    history = auth_client.get("/api/v1/coach/history").json()
    assert any(item["kind"].startswith("answer") or item["kind"] == "post_session" for item in history["items"])
    assert history["memory"]["sessions_total"] == 1
    assert history["disclaimer"]


def _complete(auth_client, drill_id: str) -> dict:  # type: ignore[no-untyped-def]
    planned = auth_client.post("/api/v1/trainings/sessions", json={"drill_id": drill_id, "available_minutes": 30, "has_pitch": True})
    session_id = planned.json()["session_id"]
    response = auth_client.post(f"/api/v1/trainings/sessions/{session_id}/complete", json={"execution": 5, "focus": 5, "difficulty_experience": 5})
    assert response.status_code == 200, response.text
    return response.json()


def test_skill_points_bank_until_an_attribute_moves(auth_client, player_id) -> None:  # type: ignore[no-untyped-def]
    """One session cannot move an attribute (100 points per point) — the ledger must still explain it."""
    drills = {d["slug"]: d for d in auth_client.get("/api/v1/trainings/drills").json()}
    slug = auth_client.get(f"/api/v1/coach/today?player_id={player_id}&available_minutes=30").json()["recommendation"]["slug"]
    drill_id = drills[slug]["id"]

    first = _complete(auth_client, drill_id)
    assert first["xp_awarded"] > 0
    assert first["attribute_changes"] == []
    assert first["skill_progress"], "every targeted attribute needs a banking row"
    assert all(row["banked"] > 0 and row["needed"] == 100 and row["ceiling"] == "" for row in first["skill_progress"])

    gained: list[dict] = []
    for _ in range(6):
        gained.extend(_complete(auth_client, drill_id)["attribute_changes"])
    assert gained, "repeated sessions must eventually raise an attribute"
    assert all(change["delta"] == 1 and change["reason"] for change in gained)

    timeline = auth_client.get("/api/v1/progress/timeline").json()
    assert timeline["attribute_series"], "a stored attribute change must surface on the timeline"


def test_coach_recommendation_is_fresh_and_goal_aligned(auth_client, player_id) -> None:  # type: ignore[no-untyped-def]
    first = auth_client.get(f"/api/v1/coach/today?player_id={player_id}").json()["recommendation"]["slug"]
    second = auth_client.get(f"/api/v1/coach/today?player_id={player_id}").json()["recommendation"]["slug"]
    assert first and second
    asks = auth_client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "What should I train today?"})
    assert asks.status_code == 200
    assert asks.json()["reasons"]
    match = auth_client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "Analyze my last match"}).json()
    assert "Data unavailable" in match["message"]
    plan = auth_client.post(f"/api/v1/coach/plan?player_id={player_id}", json={"horizon_days": 7, "available_minutes": 25, "days_per_week": 4}).json()
    assert len(plan["days"]) == 7
    assert any(day["type"] == "recovery" for day in plan["days"])
    assert any(day["sessions"] for day in plan["days"])


def test_youth_load_cap_is_applied(client) -> None:  # type: ignore[no-untyped-def]
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "youth@example.test", "password": "strong-pass-1234", "display_name": "Youth", "role": "player", "accepts_data_policy": True},
    )
    client.headers.update({"Authorization": f"Bearer {register.json()['access_token']}"})
    player = client.post(
        "/api/v1/players", json={"name": "Youth Player", "position": "ST", "age": 15, "level": "beginner", "preferred_foot": "right", "goal": "improve_finishing"}
    ).json()
    today = client.get(f"/api/v1/coach/today?player_id={player['id']}").json()
    assert today["recommendation"]["difficulty"] <= 3 or any("under-18" in r or "unsuitable" in r for r in today["reasons"])


def test_export_and_delete_privacy_surfaces(auth_client, player_id) -> None:  # type: ignore[no-untyped-def]
    exported = auth_client.get("/api/v1/progress/export")
    assert exported.status_code == 200
    assert exported.json()["players"][0]["id"] == player_id
    deleted = auth_client.delete("/api/v1/progress/player-data")
    assert deleted.status_code == 200
    assert auth_client.get("/api/v1/players").json() == []


def test_cross_user_access_returns_404(client, auth_client) -> None:  # type: ignore[no-untyped-def]
    other = client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.test", "password": "strong-pass-1234", "display_name": "Intruder", "role": "player", "accepts_data_policy": True},
    )
    token = other.json()["access_token"]
    victim_id = auth_client.post(
        "/api/v1/players", json={"name": "Victim", "position": "CB", "age": 25, "level": "advanced", "preferred_foot": "right", "goal": "improve_defending"}
    ).json()["id"]
    steal = client.get(f"/api/v1/players/{victim_id}", headers={"Authorization": f"Bearer {token}"})
    assert steal.status_code == 404
