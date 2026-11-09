"""Gamification leaderboard (spec §37). The board exists to motivate, not to shame: an account is
invisible on it until it says so itself, and every rank is plainly computed from stored XP rows.
"""

from __future__ import annotations

import pytest

from app.core.db import SessionLocal, init_db
from app.main import app
from app.models import User, UserPlayer, XpEvent


@pytest.fixture()
def db() -> SessionLocal:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_leaderboard_door_orders_opted_in_accounts_by_xp_and_refuses_unopted(client, auth_client, db) -> None:
    """Ranked by 30-day XP among the opted-in, tie-broken by account creation order; unopted ranks nowhere."""
    # Create two accounts and grant each some XP.
    r1 = client.post("/api/v1/auth/register", json={"email": "lb1@example.test", "password": "strong-password-1", "display_name": "Player One", "role": "player", "accepts_data_policy": True})
    r2 = client.post("/api/v1/auth/register", json={"email": "lb2@example.test", "password": "strong-password-2", "display_name": "Player Two", "role": "player", "accepts_data_policy": True})
    assert r1.status_code == 201 and r2.status_code == 201

    # Player profiles arrive through /players (there is no auto-create on register).
    a = client.post("/api/v1/auth/login", json={"email": "lb1@example.test", "password": "strong-password-1"})
    b = client.post("/api/v1/auth/login", json={"email": "lb2@example.test", "password": "strong-password-2"})
    assert a.status_code == 200 and b.status_code == 200
    tok_a, tok_b = a.json()["access_token"], b.json()["access_token"]

    profile = client.post(
        "/api/v1/players",
        json={"name": "Player One", "position": "CM", "age": 22, "level": "intermediate", "preferred_foot": "right", "goal": "improve_passing", "height_cm": 178},
        headers={"authorization": f"Bearer {tok_a}"},
    )
    assert profile.status_code in (200, 201), profile.text
    profile2 = client.post(
        "/api/v1/players",
        json={"name": "Player Two", "position": "ST", "age": 24, "level": "advanced", "preferred_foot": "left", "goal": "improve_finishing", "height_cm": 182},
        headers={"authorization": f"Bearer {tok_b}"},
    )
    assert profile2.status_code in (200, 201), profile2.text

    for index, (email, amount) in enumerate([("lb1@example.test", 100), ("lb2@example.test", 250)]):
        session = SessionLocal()
        try:
            u = session.query(User).filter(User.email == email).one()
            player_ids = [r[0] for r in session.query(UserPlayer.id).filter(UserPlayer.user_id == u.id).all()]
            session.add(
                XpEvent(
                    id=f"xp_lb_{index}",
                    user_id=u.id,
                    player_id=player_ids[0],
                    amount=amount,
                    reason="test seeds",
                    formula="test",
                    source_type="manual",
                )
            )
            session.commit()
        finally:
            session.close()

    res = auth_client.get("/api/v1/leaderboard")
    assert res.status_code == 200

    # Opt both in; rank by XP descending; both must appear after opting in.
    r = client.post("/api/v1/leaderboard", json={"enabled": True}, headers={"authorization": f"Bearer {tok_a}"})
    r2 = client.post("/api/v1/leaderboard", json={"enabled": True}, headers={"authorization": f"Bearer {tok_b}"})
    assert r.status_code == 200 and r2.status_code == 200

    top = client.get("/api/v1/leaderboard", headers={"authorization": f"Bearer {tok_a}"}).json()
    assert len(top["leaders"]) == 2
    assert top["leaders"][0]["name"] == "Player Two"
    assert top["leaders"][0]["xp"] == 250
    assert top["leaders"][1]["name"] == "Player One"
    assert top["leaders"][1]["xp"] == 100
    # Opting one out removes them from the board.
    r3 = client.post("/api/v1/leaderboard", json={"enabled": False}, headers={"authorization": f"Bearer {tok_b}"})
    assert r3.status_code == 200
    after = client.get("/api/v1/leaderboard", headers={"authorization": f"Bearer {tok_a}"}).json()
    assert len(after["leaders"]) == 1
    assert after["leaders"][0]["name"] == "Player One"
    assert after["me"]["visible"] is True
    assert after["me"]["xp"] == 100


def test_the_board_reads_without_a_credential_and_the_contract_says_public(client) -> None:
    """Anyone may read the opted-in board; only the opt-in switch is private.

    This is the shape the security gate knocks: an operation the contract calls secured must answer 401
    without a credential. The read carries an optional bearer, which FastAPI would otherwise publish as
    a security requirement — so the route declares `security: []` and this case binds the artifact, the
    anonymous answer and the private switch together.
    """
    assert client.get("/api/v1/leaderboard").status_code == 200

    paths = app.openapi()["paths"]["/api/v1/leaderboard"]
    assert paths["get"].get("security", []) == []
    assert paths["post"].get("security"), "the opt-in switch must stay private"
