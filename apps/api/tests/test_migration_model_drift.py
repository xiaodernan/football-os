"""The committed migration chain and the committed models must describe one schema.

`21bbf86` is why this file exists. The commit before it, `c0d376c`, landed a plane older than `0cf34c1`: twenty
paths answered HEAD's item-36 bytes with pre-item-36 text, so `CareerBudgetAward` stopped declaring `stage` and
`uq_career_award_stage` — while `migrations/versions/0049_objective_bonuses.py`, which adds exactly those, was
not in the reverted set and stayed. A tree can hold a revision that builds a column no model writes and a unique
key no model names, and the suite cannot see it: every test that builds its schema with `create_all` gets the
model's schema, every test that runs the chain gets the revision's, and nothing ever asked the two to agree. The
two gates that did red on that commit (`test_spec_audit_currency`'s migration count and `test_locale_claims`'s
README row) red because a *figure* disagreed with a *file*; neither reads the schema.

The probe runs the chain to head on a temporary SQLite file in a subprocess — its own `DATABASE_URL`, so the
checkout's `.env` and the suite's test database are both out of the picture — and asks alembic's own
`compare_metadata` what would have to change to move the migrated schema to `Base.metadata`. Four cases read the
same result and each fails on its own kind of difference, so the first red names the shape: a column the chain
builds and no model declares is a reverted unit, a column a model declares and no chain builds is an unwritten
revision, a table missing on either side is the same defect one level up, and anything left over is the catch-all.

What is deliberately not compared: column *types and widths*. That drift is `scripts/schema_drift.py`'s job
against a live database, and `autogenerate` on SQLite reports reflection noise the moment `compare_type` is on.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
MIGRATIONS_DIR = "apps/api/migrations/versions"

PROBE = r"""
import json, os, sys, tempfile
from pathlib import Path

API = sys.argv[1]
DB = sys.argv[2]
os.environ["DATABASE_URL"] = "sqlite:///" + Path(DB).as_posix()
os.environ.pop("FOOTBALL_OS_TEST_DATABASE_URL", None)
sys.path.insert(0, API)

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

config = Config(os.path.join(API, "alembic.ini"))
config.set_main_option("script_location", os.path.join(API, "migrations"))
command.upgrade(config, "head")

import app.models  # noqa: F401 -- importing the models is what populates Base.metadata
from app.core.db import Base

engine = sa.create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)


def table_of(entry):
    kind = entry[0]
    if kind.endswith("_table"):
        return entry[1].name
    if kind.endswith("_column"):
        return entry[2]
    return getattr(getattr(entry[1], "table", None), "name", None)


def name_of(entry):
    kind = entry[0]
    if kind.endswith("_table"):
        return entry[1].name
    if kind.endswith("_column"):
        return entry[3].name
    return getattr(entry[1], "name", None) or str(entry[1])


print("DRIFT-JSON:" + json.dumps({
    "diffs": [
        {"kind": entry[0], "table": table_of(entry), "name": name_of(entry), "raw": repr(entry)[:240]}
        for entry in diffs
    ],
}))
"""


def _git(args: list[str]) -> bytes:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, timeout=120)
    assert done.returncode == 0, f"`git {' '.join(args)}` failed rc={done.returncode}: {done.stderr.decode('utf-8', 'replace')[:300]}"
    return done.stdout


@cache
def _committed_text(rel: str) -> str:
    """The file as the commit holds it — the tree this file grades, not whatever the run has checked out."""
    if (ROOT / ".git").exists():
        return _git(["show", f"HEAD:{rel}"]).decode("utf-8")
    return (ROOT / rel).read_text(encoding="utf-8")


@cache
def _revisions() -> dict[str, str]:
    if (ROOT / ".git").exists():
        listing = _git(["ls-tree", "-r", "--name-only", "HEAD", "--", MIGRATIONS_DIR]).decode("utf-8")
        rels = [line for line in listing.splitlines() if line.endswith(".py")]
    else:
        rels = sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / MIGRATIONS_DIR).glob("*.py"))
    return {rel: _committed_text(rel) for rel in rels}


def _adding_revisions(table: str, name: str) -> list[str]:
    """The revisions whose own source names both this table and this column — who shipped it, and so who was reverted."""
    hits = []
    for rel, source in sorted(_revisions().items()):
        if f'"{table}"' in source and (f'"{name}"' in source or f"'{name}'" in source):
            hits.append(Path(rel).name)
    return hits


@cache
def probe() -> list[dict[str, str]]:
    """Run the committed chain to head on a temporary database and report alembic's own diff against the models."""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.py"
        script.write_text(PROBE, encoding="utf-8")
        db = Path(tmp) / "chain.db"
        done = subprocess.run(
            [sys.executable, str(script), str(API), str(db)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(API),
            timeout=900,
        )
    assert done.returncode == 0, f"the committed chain did not upgrade a fresh SQLite database (rc={done.returncode}): {done.stderr[-500:]}"
    marker = "DRIFT-JSON:"
    assert marker in done.stdout, f"the probe printed no verdict: {done.stdout[-400:]}{done.stderr[-400:]}"
    return json.loads(done.stdout.split(marker, 1)[1])["diffs"]


def _of(kind: str) -> list[dict[str, str]]:
    return [entry for entry in probe() if entry["kind"] == kind]


def test_no_revision_builds_a_column_the_models_have_stopped_declaring() -> None:
    # The `c0d376c` shape: the unit's migration survived its landing and the unit's model did not.
    drifted = _of("remove_column")
    assert not drifted, (
        f"{len(drifted)} column(s) the committed chain builds are declared by no committed model: "
        f"{[(entry['table'], entry['name']) for entry in drifted[:8]]}. Each one names the revision that added it "
        f"{[(entry['name'], _adding_revisions(entry['table'], entry['name'])) for entry in drifted[:4]]} — a landing "
        "that reverted the model without reverting the migration."
    )


def test_every_column_a_model_declares_is_built_by_the_chain() -> None:
    drifted = _of("add_column")
    assert not drifted, (
        f"{len(drifted)} column(s) the models declare are built by no revision: "
        f"{[(entry['table'], entry['name']) for entry in drifted[:8]]}. `create_all` hides this in tests and the "
        "first `alembic upgrade head` shows it in a deployment — write the migration."
    )


def test_the_models_declare_every_table_the_chain_builds_and_the_chain_builds_every_one_they_do() -> None:
    extra = _of("remove_table")
    missing = _of("add_table")
    assert not extra and not missing, (
        f"the chain builds {len(extra)} table(s) no model declares {[entry['table'] for entry in extra[:6]]} and "
        f"no revision builds {len(missing)} table(s) the models declare {[entry['table'] for entry in missing[:6]]}"
    )


def test_alembic_sees_no_other_difference_between_the_migrated_schema_and_the_models() -> None:
    # Constraints, indexes and anything autogenerate can name that the three cases above do not read.
    named = {"remove_column", "add_column", "remove_table", "add_table"}
    others = [entry for entry in probe() if entry["kind"] not in named]
    assert not others, (
        f"{len(others)} schema difference(s) between `alembic upgrade head` and `Base.metadata` beyond columns and "
        f"tables: {[(entry['kind'], entry['table'], entry['name']) for entry in others[:8]]}. In `c0d376c` the "
        "revert moved here too — `uq_career_award_stage` out, `uq_career_award_season` back."
    )
