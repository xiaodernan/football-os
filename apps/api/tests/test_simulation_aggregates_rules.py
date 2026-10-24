"""#145 — the simulation-aggregates rules door publishes only figures it derives.

The body used to carry six clause-census fields (`spec_verbs_declined`, `refusal_answers`,
`public_clauses`, `clauses_with_a_verb`, `clauses_declined`, `private_tables_excluded`) filled with
invented zeros, three knowledge-graph ceilings (`max_depth`/`max_edges`/`max_nodes`) this tier has no
traversal to enforce, and `world_ready: true` written by hand — under a docstring that claimed
"Nothing here is typed by hand". The clause census belongs to `/graph/rules`, where it is measured
from live metadata; none of these fields had a reader in `apps/web`.

These cases pin the door to what it can actually derive: the tier's own two verbs and two node kinds,
this router's own doors, the aggregate service's constants, and a readiness measured on the caller's
database.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_db
from app.main import app
from app.services.simulation import aggregates as aggregate_service
from app.services.world import sync_world

RULES = "/api/v1/simulation/aggregates/rules"

DERIVED_KEYS = {
    "node_kinds",
    "edge_verbs",
    "routes",
    "world_ready",
    "caps",
    "formulas",
    "disclaimer",
}


def test_the_rules_door_publishes_only_the_vocabulary_it_can_derive(client) -> None:  # type: ignore[no-untyped-def]
    body = client.get(RULES).json()
    invented = sorted(set(body) - DERIVED_KEYS)
    missing = sorted(DERIVED_KEYS - set(body))
    assert not invented and not missing, (
        f"the rules door publishes {invented} with nothing behind them and omits {missing}; "
        f"the body's keys are {sorted(body)}"
    )
    assert "public_clauses" not in body and "refusal_answers" not in body, (
        "the clause census is the graph tier's, measured from live metadata at /graph/rules; "
        f"this door has no scan to put behind it, yet still publishes {sorted(set(body) & {'public_clauses', 'refusal_answers'})}"
    )


def test_the_caps_and_formulas_are_the_service_constants(client) -> None:  # type: ignore[no-untyped-def]
    body = client.get(RULES).json()
    assert body["caps"] == {
        "ledger_limit": aggregate_service.LEDGER_LIMIT,
        "chance_types": list(aggregate_service._CHANCE_TYPES),
        "ledger_types": list(aggregate_service._LEDGER_TYPES),
    }, f"the door printed caps the aggregate service does not guard with: {body['caps']}"
    assert body["formulas"] == {
        "ledger": aggregate_service.LEDGER_FORMULA,
        "consistency": aggregate_service.CONSISTENCY_FORMULA,
        "attribution": aggregate_service.ATTRIBUTION_FORMULA,
    }, f"the door printed a formula the service does not use: {body['formulas']}"


def test_each_published_route_is_a_door_the_app_answers(client) -> None:  # type: ignore[no-untyped-def]
    body = client.get(RULES).json()
    published = {(row["method"], f"/api/v1{row['path']}") for row in body["routes"]}
    live: set[tuple[str, str]] = set()
    for route in app.routes:
        path = str(getattr(route, "path", ""))
        if path.startswith("/api/v1/simulation/aggregates") and path != RULES:
            live |= {(method, path) for method in set(getattr(route, "methods", ()) or ()) - {"HEAD", "OPTIONS"}}
    assert published == live, f"published but not answered: {sorted(published - live)}; answered but not published: {sorted(live - published)}"


@pytest.fixture()
def empty_database() -> Iterator[None]:
    """Serve this request off a database with no tables at all."""
    engine = create_engine("sqlite://")
    sessions = sessionmaker(bind=engine)

    def override() -> Iterator[Session]:
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_world_readiness_is_measured_on_the_caller_s_database(empty_database) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as served:
        response = served.get(RULES)
    assert response.status_code == 200, response.text
    assert response.json()["world_ready"] is False, (
        "a database with no world tables at all was reported ready; readiness is a measurement, not a constant"
    )


def test_world_readiness_is_true_once_the_world_is_on_that_database(client) -> None:  # type: ignore[no-untyped-def]
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        result = sync_world(session)
        assert result.ok, result.errors[:5]
    finally:
        session.close()
    assert client.get(RULES).json()["world_ready"] is True, (
        "a database the sync just filled with the full world was reported unready"
    )


def test_the_contract_description_does_not_claim_what_the_body_cannot_keep() -> None:
    description = app.openapi()["paths"][RULES]["get"].get("description", "")
    assert "Nothing here is typed by hand" not in description, (
        "the published description still claims no figure is typed by hand; the door cannot keep that for the "
        "clause census it used to invent"
    )
    assert "world_ready" in description, (
        "the description does not say where world_ready comes from, which is the field that used to be a constant"
    )
