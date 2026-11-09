"""§59-family claims against `/capabilities` — the flags the product renders as Live / Not built.

`m9_community` shipped as a hardcoded `False` beside a tier that was fully built: the tables, the five
verbs, the refusal codes, the entitlement doors, and a 252/252 browser walk. Every account's Settings
feature map told it the community does not exist. `m9_community` is now measured from the tier's own
five tables — the same predicate its doors use — and these cases pin that it can never be a literal
again: the value must equal `community_tables_present(db)` on the database serving the request, and on
a migrated database (the suite always runs one) it must be `True`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.community.posts import community_tables_present


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_m9_community_is_measured_not_a_literal(client, db: Session) -> None:  # type: ignore[no-untyped-def]
    body = client.get("/api/v1/capabilities").json()
    assert body["m9_community"] == community_tables_present(db), (
        "/capabilities claims m9_community against a value nothing measured — the Settings page and the "
        "feature map render this as Live vs Not built, and the tier shipped 2026-09-28"
    )


def test_m9_community_is_live_on_a_migrated_database(client) -> None:  # type: ignore[no-untyped-def]
    body = client.get("/api/v1/capabilities").json()
    assert body["m9_community"] is True, (
        "a database carrying the five community tables must answer true — otherwise the shipped tier is "
        "invisible to every reader"
    )
