"""The boot fast path must skip unchanged work without hiding real catalogue edits."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import NewsArticleLink, SyncCheckpoint, TacticalSystem, Team
from app.services.tactics.plan import SYSTEM_COUNT
from app.services.tactics.sync import sync_tactics, tactics_recipe
from app.services.world.builder import WorldSizes
from app.services.world.plan import world_id
from app.services.world.sync import sync_world, world_recipe

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _import_sources(entry: Path) -> set[Path]:
    pending = [entry.resolve()]
    sources: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in sources:
            continue
        sources.add(source)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or not node.module or not node.module.startswith("app."):
                continue
            if node.module == "app.core" or node.module.startswith("app.core."):
                continue
            target = APP_ROOT.joinpath(*node.module.split(".")[1:])
            candidate = target.with_suffix(".py")
            if not candidate.is_file():
                candidate = target / "__init__.py"
            if candidate.is_file():
                if node.module == "app.models":
                    sources.add(candidate.resolve())
                else:
                    pending.append(candidate.resolve())
    return sources


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

    def unexpected_plan(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("an unchanged database must not generate the world plan")

    monkeypatch.setattr(sync_module, "_upsert", unexpected_upsert)
    monkeypatch.setattr(sync_module, "plan_world", unexpected_plan)
    checkpoint = session.get(SyncCheckpoint, "world")
    assert checkpoint is not None
    database_hash, counts = sync_module._world_database_fingerprint(session)
    assert checkpoint.database_hash == database_hash, f"world database hash {checkpoint.database_hash!r} != {database_hash!r}"
    assert checkpoint.row_counts == counts, f"world row counts {checkpoint.row_counts!r} != {counts!r}"
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


def test_world_receipt_detects_non_hash_edits_and_repairs_every_generated_column(session: Session) -> None:
    sync_world(session)
    team = session.scalars(select(Team).order_by(Team.slug)).first()
    assert team is not None
    team_id = team.id
    wanted_name = team.name
    wanted_origin = team.data_origin
    team.name = "tampered-name-with-the-original-hash"
    team.data_origin = "real"
    session.commit()

    repaired = sync_world(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.updated >= 1
    stored = session.get(Team, team_id)
    assert stored is not None
    assert stored.name == wanted_name
    assert stored.data_origin == wanted_origin


def test_world_rejects_primary_key_tampering_instead_of_saving_a_false_receipt(session: Session) -> None:
    sync_world(session)
    link = session.scalars(select(NewsArticleLink)).first()
    assert link is not None
    wanted_id = link.id
    receipt = session.get(SyncCheckpoint, "world")
    assert receipt is not None
    wanted_database_hash = receipt.database_hash
    link.id = "tampered-article-link-id"
    session.commit()

    rejected = sync_world(session, force=True)
    assert not rejected.ok and not rejected.fast_path
    assert any("primary key" in error for error in rejected.errors), rejected.errors[:5]
    assert session.get(NewsArticleLink, "tampered-article-link-id") is not None
    assert session.get(NewsArticleLink, wanted_id) is None
    receipt = session.get(SyncCheckpoint, "world")
    assert receipt is not None and receipt.database_hash == wanted_database_hash


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


def test_world_force_and_missing_receipt_both_take_the_full_path(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_world(session)
    forced = sync_world(session, force=True)
    assert forced.ok and not forced.fast_path
    assert forced.updated == forced.rows

    _without_checkpoint(session, "world")
    import app.services.world.sync as sync_module

    original_plan = sync_module.plan_world
    original_upsert = sync_module._upsert
    plans = 0
    upserts = 0

    def observed_plan(*args: Any, **kwargs: Any) -> Any:
        nonlocal plans
        plans += 1
        return original_plan(*args, **kwargs)

    def observed_upsert(*args: Any, **kwargs: Any) -> None:
        nonlocal upserts
        upserts += 1
        original_upsert(*args, **kwargs)

    monkeypatch.setattr(sync_module, "plan_world", observed_plan)
    monkeypatch.setattr(sync_module, "_upsert", observed_upsert)
    missing = sync_world(session)
    assert missing.ok and not missing.fast_path
    assert missing.changed == 0
    assert plans == 1
    assert upserts == len(sync_module.COLLECTIONS)
    checkpoint = session.get(SyncCheckpoint, "world")
    assert checkpoint is not None and checkpoint.recipe_hash
    assert checkpoint.database_hash == sync_module._world_database_fingerprint(session)[0]


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


def test_tactics_receipt_detects_non_hash_edits_and_repairs_every_generated_column(session: Session) -> None:
    sync_tactics(session)
    system = session.scalars(select(TacticalSystem).order_by(TacticalSystem.slug)).first()
    assert system is not None
    system_id = system.id
    wanted_name = system.name
    wanted_board = deepcopy(system.board)
    wanted_origin = system.data_origin
    system.name = "tampered-name-with-the-original-hash"
    system.board = {**system.board, "tampered": True}
    system.data_origin = "user"
    session.commit()

    repaired = sync_tactics(session)
    assert repaired.ok and not repaired.fast_path, repaired.errors[:5]
    assert repaired.updated >= 1
    stored = session.get(TacticalSystem, system_id)
    assert stored is not None
    assert stored.name == wanted_name
    assert stored.board == wanted_board
    assert stored.data_origin == wanted_origin


def test_tactics_rejects_primary_key_tampering_instead_of_saving_a_false_receipt(session: Session) -> None:
    sync_tactics(session)
    system = session.scalars(select(TacticalSystem).order_by(TacticalSystem.slug)).first()
    assert system is not None
    wanted_id = system.id
    receipt = session.get(SyncCheckpoint, "tactics")
    assert receipt is not None
    wanted_database_hash = receipt.database_hash
    system.id = "tampered-tactical-system-id"
    session.commit()

    rejected = sync_tactics(session, force=True)
    assert not rejected.ok and not rejected.fast_path
    assert any("primary key" in error for error in rejected.errors), rejected.errors[:5]
    assert session.get(TacticalSystem, "tampered-tactical-system-id") is not None
    assert session.get(TacticalSystem, wanted_id) is None
    receipt = session.get(SyncCheckpoint, "tactics")
    assert receipt is not None and receipt.database_hash == wanted_database_hash


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


def test_tactics_force_and_missing_receipt_both_take_the_full_path(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_tactics(session)
    forced = sync_tactics(session, force=True)
    assert forced.ok and not forced.fast_path
    assert forced.updated == SYSTEM_COUNT

    _without_checkpoint(session, "tactics")
    import app.services.tactics.sync as sync_module

    original_plan = sync_module.planned_rows
    original_columns = sync_module._columns_for
    plans = 0
    columns = 0

    def observed_plan() -> list[Any]:
        nonlocal plans
        plans += 1
        return original_plan()

    def observed_columns(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal columns
        columns += 1
        return original_columns(*args, **kwargs)

    monkeypatch.setattr(sync_module, "planned_rows", observed_plan)
    monkeypatch.setattr(sync_module, "_columns_for", observed_columns)
    missing = sync_tactics(session)
    assert missing.ok and not missing.fast_path
    assert missing.changed == 0
    assert plans == 1
    assert columns == SYSTEM_COUNT
    checkpoint = session.get(SyncCheckpoint, "tactics")
    assert checkpoint is not None and checkpoint.recipe_hash
    assert checkpoint.database_hash == sync_module._tactics_database_fingerprint(session)[0]


def test_world_recipe_includes_every_output_affecting_dependency() -> None:
    import app.services.world.sync as sync_module

    source = Path(sync_module.__file__).resolve()
    expected = _import_sources(source.parent / "builder.py") | {source}
    assert {source.parent / "names.py", source.parents[1] / "attributes.py"} <= expected, "the import walk did not reach world generator dependencies"
    actual = {path.resolve() for path in sync_module.WORLD_SOURCE_FILES}
    assert expected <= actual, sorted(str(path) for path in expected - actual)


def test_tactics_recipe_includes_every_output_affecting_dependency() -> None:
    import app.services.tactics.sync as sync_module

    source = Path(sync_module.__file__).resolve()
    expected = _import_sources(source.parent / "plan.py") | {source}
    assert {source.parent / "analysis.py", source.parent / "roles.py", source.parent / "shapes.py"} <= expected, "the import walk did not reach tactical generator dependencies"
    actual = {path.resolve() for path in sync_module.TACTICS_SOURCE_FILES}
    assert expected <= actual, sorted(str(path) for path in expected - actual)


def test_checkpoint_fingerprints_cover_every_persisted_generated_column() -> None:
    import app.services.tactics.sync as tactics_module
    import app.services.world.sync as world_module

    for collection in world_module.COLLECTIONS:
        expected = set(collection.model.__table__.columns.keys()) - {"created_at", "updated_at"}
        assert set(world_module.CHECKPOINT_COLUMNS[collection.name]) == expected, collection.name
    expected_tactics = set(TacticalSystem.__table__.columns.keys()) - {"created_at", "updated_at"}
    assert set(tactics_module.CHECKPOINT_COLUMNS) == expected_tactics


def test_world_receipt_read_error_falls_back_to_a_full_sync(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sync_world(session)
    import app.services.world.sync as sync_module

    original = sync_module._world_database_fingerprint
    original_plan = sync_module.plan_world
    calls = 0
    plans = 0

    def fail_once(store: Session) -> tuple[str, dict[str, int]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLAlchemyError("injected receipt read failure")
        return original(store)

    def observed_plan(*args: Any, **kwargs: Any) -> Any:
        nonlocal plans
        plans += 1
        return original_plan(*args, **kwargs)

    monkeypatch.setattr(sync_module, "_world_database_fingerprint", fail_once)
    monkeypatch.setattr(sync_module, "plan_world", observed_plan)
    rebuilt = sync_world(session)
    assert rebuilt.ok and not rebuilt.fast_path, rebuilt.errors[:5]
    assert rebuilt.changed == 0
    assert calls == 2
    assert plans == 1


def test_tactics_receipt_read_error_falls_back_to_a_full_sync(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sync_tactics(session)
    import app.services.tactics.sync as sync_module

    original = sync_module._tactics_database_fingerprint
    original_plan = sync_module.planned_rows
    calls = 0
    plans = 0

    def fail_once(store: Session) -> tuple[str, dict[str, int]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLAlchemyError("injected receipt read failure")
        return original(store)

    def observed_plan() -> list[Any]:
        nonlocal plans
        plans += 1
        return original_plan()

    monkeypatch.setattr(sync_module, "_tactics_database_fingerprint", fail_once)
    monkeypatch.setattr(sync_module, "planned_rows", observed_plan)
    rebuilt = sync_tactics(session)
    assert rebuilt.ok and not rebuilt.fast_path, rebuilt.errors[:5]
    assert rebuilt.changed == 0
    assert calls == 2
    assert plans == 1


def test_world_unreadable_recipe_source_disables_the_fast_path(
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_world(session)
    import app.services.world.sync as sync_module

    original_plan = sync_module.plan_world
    plans = 0

    def observed_plan(*args: Any, **kwargs: Any) -> Any:
        nonlocal plans
        plans += 1
        return original_plan(*args, **kwargs)

    monkeypatch.setattr(sync_module, "WORLD_SOURCE_FILES", (tmp_path / "missing.py",))
    monkeypatch.setattr(sync_module, "plan_world", observed_plan)
    rebuilt = sync_world(session)
    assert rebuilt.ok and not rebuilt.fast_path, rebuilt.errors[:5]
    assert rebuilt.changed == 0
    assert plans == 1


def test_tactics_unreadable_recipe_source_disables_the_fast_path(
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_tactics(session)
    import app.services.tactics.sync as sync_module

    original_plan = sync_module.planned_rows
    plans = 0

    def observed_plan() -> list[Any]:
        nonlocal plans
        plans += 1
        return original_plan()

    monkeypatch.setattr(sync_module, "TACTICS_SOURCE_FILES", (tmp_path / "missing.py",))
    monkeypatch.setattr(sync_module, "planned_rows", observed_plan)
    rebuilt = sync_tactics(session)
    assert rebuilt.ok and not rebuilt.fast_path, rebuilt.errors[:5]
    assert rebuilt.changed == 0
    assert plans == 1


def test_world_receipt_write_failure_rolls_back_catalogue_repairs(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_world(session)
    team = session.scalars(select(Team).order_by(Team.slug)).first()
    assert team is not None
    team_id = team.id
    wanted = team.content_hash
    team.content_hash = "tampered-before-receipt-write-failure"
    session.commit()
    import app.services.world.sync as sync_module

    saves = 0

    def fail_save(*args: Any, **kwargs: Any) -> None:
        nonlocal saves
        saves += 1
        raise SQLAlchemyError("injected receipt write failure")

    monkeypatch.setattr(sync_module, "save_checkpoint", fail_save)
    try:
        report = sync_world(session)
        assert not report.ok and not report.fast_path
        assert report.updated >= 1
        assert saves == 1
        assert session.get(Team, team_id).content_hash == "tampered-before-receipt-write-failure"
    finally:
        session.get(Team, team_id).content_hash = wanted
        session.commit()


def test_tactics_receipt_write_failure_rolls_back_catalogue_repairs(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_tactics(session)
    system = session.scalars(select(TacticalSystem).order_by(TacticalSystem.slug)).first()
    assert system is not None
    system_id = system.id
    wanted = system.content_hash
    system.content_hash = "tampered-before-receipt-write-failure"
    session.commit()
    import app.services.tactics.sync as sync_module

    saves = 0

    def fail_save(*args: Any, **kwargs: Any) -> None:
        nonlocal saves
        saves += 1
        raise SQLAlchemyError("injected receipt write failure")

    monkeypatch.setattr(sync_module, "save_checkpoint", fail_save)
    try:
        report = sync_tactics(session)
        assert not report.ok and not report.fast_path
        assert report.updated >= 1
        assert saves == 1
        assert session.get(TacticalSystem, system_id).content_hash == "tampered-before-receipt-write-failure"
    finally:
        session.get(TacticalSystem, system_id).content_hash = wanted
        session.commit()
