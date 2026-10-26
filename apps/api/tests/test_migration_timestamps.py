"""No migration may declare a naive timestamp, and the repair must walk the model's columns.

The first database CI ever built from scratch failed `alembic check`: `0021`–`0025` created
`created_at`/`updated_at`/`revoked_at` as `sa.DateTime()`, the models declare
`DateTime(timezone=True)`, and PostgreSQL keeps those as two different column types. SQLite stores
both as `DATETIME`, which is why every local leg was blind to it.

The scanner is lexical on purpose: it reads the declaration sites in the migration population, and
the self-test below feeds it the spellings it must refuse, so "no naive declaration" cannot pass by
matching nothing.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import sqlalchemy as sa

from app.models import Base

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REPAIR_MIGRATION = VERSIONS / "0040_timestamp_timezone_repair.py"
TIMESTAMP_NAMES = ("created_at", "updated_at", "revoked_at")


def _is_sa_datetime(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "DateTime"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sa"
    )


def _naive_declarations(source: str) -> list[str]:
    """Every timestamp declaration in `upgrade` that does not ask for a timezone.

    The unit is the `upgrade` body: a `downgrade` deliberately restores the old shape. A call passed
    as `existing_type=` describes the type being replaced, not a column being created, so it is not
    charged either — a repair has to be able to name what it removes.
    """
    tree = ast.parse(source)
    upgrade = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"),
        None,
    )
    assert upgrade is not None, "a migration has no upgrade() to inspect"
    calls = {
        id(node.func): node
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and _is_sa_datetime(node.func)
    }
    replaced = {
        id(keyword.value)
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "existing_type" and isinstance(keyword.value, ast.Call)
    }
    found: list[str] = []
    for node in ast.walk(upgrade):
        if not _is_sa_datetime(node):
            continue
        call = calls.get(id(node))
        if call is None:
            found.append("bare sa.DateTime")
            continue
        if id(call) in replaced:
            continue
        aware = any(
            keyword.arg == "timezone" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
            for keyword in call.keywords
        )
        if not aware:
            found.append(ast.unparse(call))
    return sorted(found)


def _migration_texts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))}


def _repair_module():
    spec = importlib.util.spec_from_file_location("migration_0040", REPAIR_MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_migration_declares_a_naive_timestamp() -> None:
    texts = _migration_texts()
    assert texts, "the migration population is empty; the scan would pass without reading anything"
    offenders = {name: shapes for name, text in texts.items() if (shapes := _naive_declarations(text))}
    aware = sum(text.count("sa.DateTime(timezone=True)") for text in texts.values())
    assert not offenders, f"naive timestamp declarations: {offenders!r}"
    assert aware >= 27, f"expected the 27 repaired declarations to stay timezone-aware, found {aware}"


def test_the_scanner_refuses_a_naive_declaration_and_accepts_an_aware_one() -> None:
    assert _naive_declarations('def upgrade():\n    op.add_column("t", sa.Column("t", sa.DateTime()))\n') == ["sa.DateTime()"]
    assert (
        _naive_declarations('def upgrade():\n    op.add_column("t", sa.Column("t", sa.DateTime(timezone=False)))\n')
        == ["sa.DateTime(timezone=False)"]
    )
    assert _naive_declarations('def upgrade():\n    op.alter_column("t", "c", type_=sa.DateTime)\n') == [
        "bare sa.DateTime"
    ]
    assert (
        _naive_declarations('def upgrade():\n    op.add_column("t", sa.Column("t", sa.DateTime(timezone=True)))\n')
        == []
    )
    repair = 'def upgrade():\n    op.alter_column("t", "c", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())\n'
    assert _naive_declarations(repair) == []
    fresh = 'def upgrade():\n    op.alter_column("t", "c", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))\n'
    assert _naive_declarations(fresh) == ["sa.DateTime()"]
    undo = 'def upgrade():\n    pass\n\ndef downgrade():\n    op.alter_column("t", "c", type_=sa.DateTime())\n'
    assert _naive_declarations(undo) == []


def test_the_repair_walks_every_timestamp_the_models_call_timezone_aware() -> None:
    repair = _repair_module().REPAIR
    wrong_type: list[str] = []
    for table_name, columns in repair.items():
        table = Base.metadata.tables[table_name]
        modelled = {column.name for column in table.columns if column.name in TIMESTAMP_NAMES}
        assert set(columns) == modelled, f"{table_name}: repaired {sorted(columns)!r}, model has {sorted(modelled)!r}"
        for name in columns:
            column_type = table.columns[name].type
            if not isinstance(column_type, sa.DateTime) or not column_type.timezone:
                wrong_type.append(f"{table_name}.{name}={column_type!r}")
    assert not wrong_type, f"repair targets a column the model does not call timezone-aware: {wrong_type!r}"
    assert len(repair) == 13, f"the repair names {len(repair)} tables; the class was 13"
    assert sum(len(columns) for columns in repair.values()) == 27, "the repair covers 27 columns, not the class"


def test_the_repair_skips_sqlite_in_both_directions() -> None:
    source = REPAIR_MIGRATION.read_text(encoding="utf-8")
    assert source.count('if _engine_name() != "postgresql":') == 2, "both directions must skip SQLite"
