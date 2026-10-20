"""§36's first kind of content: a training program a learner can walk.

The creator tier published guides, and its own verification record said what a guide is not:
"Nothing here is a runnable program: no row carries a schedule, a dose or a progression."

This file defends the three things that sentence names:

* a **schedule** - the steps, in order, one row each, and the order is unique per program;
* a **dose** - the minutes each step asks for, and the total the program asks for;
* a **progression** - the position, which is the order the learner walks the steps in.

and the rule that makes a program runnable rather than merely well-formed: **a step names a drill from
the training catalogue, and a step naming a drill the catalogue does not hold is refused at
publication**, not at the learner's first session. A plan that cannot be walked is not a plan.

Starting a program plans the caller's own training sessions — the training tier's rows, so completing
one of them is the same act as completing any other session.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import CreatorProgram, CreatorProgramStep, TrainingDrill, TrainingSession, UserPlayer

PASSWORD = "TestPass1234!"


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _client(tag: str = "") -> TestClient:
    client = TestClient(app)
    email = f"program-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Program Tester {uuid4().hex[:6]}",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"registration failed: {response.text}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _drills(db: Session, count: int = 2) -> list[TrainingDrill]:
    """Two catalogue drills to name, written the way the catalogue writes them."""
    rows = db.scalars(select(TrainingDrill).order_by(TrainingDrill.slug).limit(count)).all()
    if len(rows) >= count:
        return list(rows)
    made: list[TrainingDrill] = []
    for index in range(count):
        slug = f"program-drill-{uuid4().hex[:8]}-{index}"
        row = TrainingDrill(
            id=f"drill-{uuid4().hex[:16]}",
            slug=slug,
            title=f"Program Drill {index}",
            category="technical",
            objective="a program step",
            setup="a program step",
            instructions="do the thing",
            coaching_points="point one",
            common_mistakes="mistake one",
            difficulty=1,
            duration_min=20,
            positions=["CM"],
            target_attributes=["passing"],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        made.append(row)
    return made


def _player(db: Session, user_id: str) -> UserPlayer:
    row = UserPlayer(
        id=f"plr_{uuid4().hex[:16]}",
        user_id=user_id,
        name="Program Player",
        position="CM",
        age=24,
        level="intermediate",
        preferred_foot="right",
        goal="become_box_to_box",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestTheProgramObject:
    def test_a_program_carries_its_schedule_its_dose_and_its_progression(self, session: Session) -> None:
        client = _client()
        drills = _drills(session, 2)
        response = client.post(
            "/api/v1/creator/programs",
            json={
                "title": "First touch and passing",
                "summary": "Two drills, in the order they build on each other.",
                "visibility": "public",
                "steps": [
                    {"drill": drills[0].slug, "minutes": 25, "note": "start here"},
                    {"drill": drills[1].slug, "minutes": 35},
                ],
            },
        )
        assert response.status_code == 201, response.text
        program = response.json()

        assert program["title"] == "First touch and passing"
        assert [step["position"] for step in program["steps"]] == [1, 2], "the progression is the order"
        assert [step["drill"] for step in program["steps"]] == [drills[0].slug, drills[1].slug]
        assert program["figures"]["steps"] == 2
        assert program["figures"]["minutes"] == 60, "the dose is the sum of the steps' minutes"

    def test_a_step_naming_a_drill_the_catalogue_does_not_hold_is_refused_at_publication(
        self, session: Session
    ) -> None:
        client = _client()
        response = client.post(
            "/api/v1/creator/programs",
            json={
                "title": "A program that cannot be walked",
                "steps": [{"drill": "no-such-drill-anywhere", "minutes": 20}],
            },
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "no_such_drill"

    def test_a_program_with_no_steps_is_refused(self) -> None:
        client = _client()
        response = client.post(
            "/api/v1/creator/programs",
            json={"title": "An empty plan", "steps": []},
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "program_steps"

    def test_a_step_asking_for_impossible_minutes_is_refused(self, session: Session) -> None:
        client = _client()
        drill = _drills(session, 1)[0]
        response = client.post(
            "/api/v1/creator/programs",
            json={
                "title": "A step that asks for a whole afternoon",
                "steps": [{"drill": drill.slug, "minutes": 600}],
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "step_minutes"

    def test_the_shelf_reads_the_programs_it_holds(self, session: Session) -> None:
        client = _client()
        drill = _drills(session, 1)[0]
        published = client.post(
            "/api/v1/creator/programs",
            json={"title": "A program on the shelf", "steps": [{"drill": drill.slug, "minutes": 20}]},
        )
        assert published.status_code == 201, published.text
        program_id = published.json()["id"]

        shelf = client.get("/api/v1/creator/programs")
        assert shelf.status_code == 200, shelf.text
        ids = [row["id"] for row in shelf.json()["programs"]]
        assert program_id in ids

    def test_the_rules_door_publishes_the_programs_own_vocabulary(self) -> None:
        client = _client()
        rules = client.get("/api/v1/creator/rules")
        assert rules.status_code == 200, rules.text
        body = rules.json()
        assert "program_caps" in body, "the rulebook does not publish the program's ceilings"
        assert body["program_caps"]["program_steps_max"] >= 1
        assert "program_rule" in body
        assert any(route["path"] == "/creator/programs" for route in body["routes"])
        assert body["refusal_answers"]["no_such_program"] == 404


class TestStartingAProgram:
    def test_starting_a_program_plans_the_callers_own_sessions_in_order(self, session: Session) -> None:
        client = _client()
        drills = _drills(session, 2)
        _player(session, _user_id_of(client))
        published = client.post(
            "/api/v1/creator/programs",
            json={
                "title": "A program to walk",
                "steps": [
                    {"drill": drills[0].slug, "minutes": 20},
                    {"drill": drills[1].slug, "minutes": 30},
                ],
            },
        )
        assert published.status_code == 201, published.text
        program_id = published.json()["id"]

        started = client.post(f"/api/v1/creator/programs/{program_id}/start")
        assert started.status_code == 201, started.text
        body = started.json()
        assert len(body["sessions"]) == 2
        assert body["minutes"] == 50

        with SessionLocal() as db:
            rows = db.scalars(
                select(TrainingSession).where(TrainingSession.program_id == program_id).order_by(TrainingSession.id)
            ).all()
        assert len(rows) == 2
        assert all(row.program_id == program_id for row in rows)
        assert any("Step 1" in " ".join(row.recommendation_reasons) for row in rows)

    def test_starting_a_program_without_a_player_is_refused(self, session: Session) -> None:
        client = _client()
        drill = _drills(session, 1)[0]
        published = client.post(
            "/api/v1/creator/programs",
            json={"title": "A program nobody can walk", "steps": [{"drill": drill.slug, "minutes": 20}]},
        )
        assert published.status_code == 201, published.text

        started = client.post(f"/api/v1/creator/programs/{published.json()['id']}/start")
        assert started.status_code == 409, started.text
        assert started.json()["detail"]["code"] == "no_player"

    def test_another_accounts_program_answers_as_absence(self, session: Session) -> None:
        owner = _client("owner-")
        drill = _drills(session, 1)[0]
        published = owner.post(
            "/api/v1/creator/programs",
            json={"title": "A private program", "visibility": "unlisted", "steps": [{"drill": drill.slug, "minutes": 20}]},
        )
        assert published.status_code == 201, published.text
        program_id = published.json()["id"]

        stranger = _client("stranger-")
        read = stranger.get(f"/api/v1/creator/programs/{program_id}")
        assert read.status_code in (200, 404), read.text
        erase = stranger.delete(f"/api/v1/creator/programs/{program_id}")
        assert erase.status_code == 404, erase.text
        assert erase.json()["detail"]["code"] == "no_such_program"


class TestErasingAProgram:
    def test_erasing_a_program_erases_the_sessions_it_planned(self, session: Session) -> None:
        client = _client()
        drills = _drills(session, 1)
        _player(session, _user_id_of(client))
        published = client.post(
            "/api/v1/creator/programs",
            json={"title": "A program to erase", "steps": [{"drill": drills[0].slug, "minutes": 20}]},
        )
        assert published.status_code == 201, published.text
        program_id = published.json()["id"]
        started = client.post(f"/api/v1/creator/programs/{program_id}/start")
        assert started.status_code == 201, started.text

        erased = client.delete(f"/api/v1/creator/programs/{program_id}")
        assert erased.status_code == 200, erased.text
        assert erased.json()["sessions_erased"] == 1

        with SessionLocal() as db:
            assert db.get(CreatorProgram, program_id) is None
            steps = db.scalars(select(CreatorProgramStep).where(CreatorProgramStep.program_id == program_id)).all()
            assert not steps
            sessions = db.scalars(select(TrainingSession).where(TrainingSession.program_id == program_id)).all()
            assert not sessions


def _user_id_of(client: TestClient) -> str:
    """The account behind an authenticated client."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return str(body["id"])
