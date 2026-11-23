"""The boot fast path must skip unchanged work without hiding real catalogue edits."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import NewsArticleLink, SyncCheckpoint, TacticalSystem, Team
from app.services.tactics.plan import SYSTEM_COUNT
from app.services.tactics.sync import sync_tactics, tactics_recipe
from app.services.world.builder import WorldSizes
from app.services.world.plan import world_id
from app.services.world.sync import sync_world, world_recipe


@pytest.fixture()
def session() -> Iterator[Session]:
    store = SessionLocal()
    try:
        yield store
    finally:
        store.close()


def _without_checkpoint(session: Session, scope: str) -> None:
    session.execute(delete(SyncCheckpoint).where(SyncCheckpoint.scope == scope))
    session.commit()


def test_world_second_sync_uses_the_receipt_without_walking_the_plan(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_checkpoint(session, "world")
    first = sync_world(session)
    assert first.ok and not first.fast_path, first.errors[:5]

    import app.services.world.sync as sync_module

    def unexpected_upsert(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("an unchanged database must not load or upsert the world")

    monkeypatch.setattr(sync_module, "_upsert", unexpected_upsert)
    checkpoint = session.get(SyncCheckpoint, "world")
    assert checkpoint is not None
    database_hash, counts = sync_module._world_database_fingerprint(session)
    assert checkpoint.database_hash == database_hash, (checkpoint.database_hash, database_hash)
    assert checkpoint.row_counts == counts, (checkpoint.row_counts, counts)
    second = sync_world(session)
    assert second.ok and second.fast_path, second.errors[:5]
    assert second.changed == 0
    assert second.unchanged == first.rows
    assert second.fingerprint == first.fingerprint
    assert set(second.per_collection) == set(first.per_collection)


def test_world_receipt_detects_a_same_count_hash_edit_and_repairs_it(session: Session) -> None:
    sync_world(session)
    team = session.scalars(select(Team).order_by(Team.slug)).first()
    assert team is not None
    wanted = team.content_hash
    count = session.scalar(select(func.count()).select_from(Team))
    team.content_hash = "tampered-without-changing-the-row-count"
    session.commit()

    repaired = sync_world(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.updated >= 1
    assert session.scalar(select(func.count()).select_from(Team)) == count
    assert session.get(Team, team.id).content_hash == wanted


def test_world_receipt_detects_delete_plus_replacement_even_when_counts_match(session: Session) -> None:
    sync_world(session)
    old = session.scalars(select(NewsArticleLink)).first()
    assert old is not None
    count = session.scalar(select(func.count()).select_from(NewsArticleLink))
    replacement = NewsArticleLink(
        id=world_id("article_link", "checkpoint-tamper"),
        article_id=old.article_id,
        entity_type=old.entity_type,
        entity_slug="not-a-generated-link",
        entity_id=old.entity_id,
        data_origin=old.data_origin,
        is_demo_data=old.is_demo_data,
    )
    session.delete(old)
    session.add(replacement)
    session.commit()
    assert session.scalar(select(func.count()).select_from(NewsArticleLink)) == count

    repaired = sync_world(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.created >= 1 and repaired.removed >= 1
    assert session.scalar(select(func.count()).select_from(NewsArticleLink)) == count


def test_world_force_and_missing_receipt_both_take_the_full_path(session: Session) -> None:
    sync_world(session)
    forced = sync_world(session, force=True)
    assert forced.ok and not forced.fast_path
    assert forced.updated == forced.rows

    _without_checkpoint(session, "world")
    missing = sync_world(session)
    assert missing.ok and not missing.fast_path
    assert missing.changed == 0


def test_world_recipe_covers_seed_sizes_and_generator_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.world.sync as sync_module

    source = tmp_path / "builder.py"
    source.write_text("WORLD_VERSION = 'one'\n", encoding="utf-8")
    monkeypatch.setattr(sync_module, "WORLD_SOURCE_FILES", (source,))
    baseline = world_recipe(3, WorldSizes())
    assert baseline is not None
    assert world_recipe(4, WorldSizes()) != baseline
    assert world_recipe(3, WorldSizes(movement_slots=0)) != baseline

    source.write_text("WORLD_VERSION = 'two'\n", encoding="utf-8")
    assert world_recipe(3, WorldSizes()) != baseline
    source.write_bytes(b"WORLD_VERSION = 'one'\r\n")
    assert world_recipe(3, WorldSizes()) == baseline
    source.unlink()
    assert world_recipe(3, WorldSizes()) is None


def test_tactics_recipe_covers_generator_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.tactics.sync as sync_module

    source = tmp_path / "plan.py"
    source.write_text("SYSTEM_COUNT = 50\n", encoding="utf-8")
    monkeypatch.setattr(sync_module, "TACTICS_SOURCE_FILES", (source,))
    baseline = tactics_recipe()
    assert baseline is not None
    source.write_text("SYSTEM_COUNT = 51\n", encoding="utf-8")
    assert tactics_recipe() != baseline
    source.unlink()
    assert tactics_recipe() is None


def test_tactics_second_sync_uses_the_receipt_without_building_planned_rows(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_checkpoint(session, "tactics")
    first = sync_tactics(session)
    assert first.ok and not first.fast_path, first.errors[:5]

    import app.services.tactics.sync as sync_module

    def unexpected_plan() -> list[Any]:
        raise AssertionError("an unchanged catalogue must not rebuild its planned rows")

    monkeypatch.setattr(sync_module, "planned_rows", unexpected_plan)
    monkeypatch.setattr(sync_module, "fingerprint", unexpected_plan)
    second = sync_tactics(session)
    assert second.ok and second.fast_path, second.errors[:5]
    assert second.changed == 0 and second.unchanged == SYSTEM_COUNT
    assert second.fingerprint == first.fingerprint


def test_tactics_receipt_detects_a_same_count_hash_edit_and_repairs_it(session: Session) -> None:
    sync_tactics(session)
    system = session.scalars(select(TacticalSystem).order_by(TacticalSystem.slug)).first()
    assert system is not None
    wanted = system.content_hash
    count = session.scalar(select(func.count()).select_from(TacticalSystem))
    system.content_hash = "tampered-without-changing-the-row-count"
    session.commit()

    repaired = sync_tactics(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.updated >= 1
    assert session.scalar(select(func.count()).select_from(TacticalSystem)) == count
    assert session.get(TacticalSystem, system.id).content_hash == wanted


def test_tactics_receipt_detects_delete_plus_replacement_even_when_counts_match(session: Session) -> None:
    sync_tactics(session)
    old = session.scalars(select(TacticalSystem).order_by(TacticalSystem.slug)).first()
    assert old is not None
    count = session.scalar(select(func.count()).select_from(TacticalSystem))
    replacement = TacticalSystem(
        id=world_id("tactical_system", "checkpoint-tamper"),
        slug="checkpoint-tamper",
        name=old.name,
        formation=old.formation,
        temperament_key=old.temperament_key,
        press_line_y=old.press_line_y,
        block_depth=old.block_depth,
        defensive_narrowing=old.defensive_narrowing,
        board=old.board,
        content_hash="tampered",
        data_origin=old.data_origin,
        is_demo_data=old.is_demo_data,
    )
    session.delete(old)
    session.add(replacement)
    session.commit()
    assert session.scalar(select(func.count()).select_from(TacticalSystem)) == count

    repaired = sync_tactics(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.created >= 1 and repaired.removed >= 1
    assert session.scalar(select(func.count()).select_from(TacticalSystem)) == count


def test_tactics_force_and_missing_receipt_both_take_the_full_path(session: Session) -> None:
    sync_tactics(session)
    forced = sync_tactics(session, force=True)
    assert forced.ok and not forced.fast_path
    assert forced.updated == SYSTEM_COUNT

    _without_checkpoint(session, "tactics")
    missing = sync_tactics(session)
    assert missing.ok and not missing.fast_path
    assert missing.changed == 0
