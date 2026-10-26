"""No migration's docstring may describe the file as something the chain does not hold.

`apps/api/migrations/versions/0021_club_fixtures.py` opened with "PARKED DRAFT — not in the tree on
purpose … Move to `apps/api/migrations/versions/0021_club_fixtures.py` once the leg is green". The
file was at that path, tracked by `git ls-files`, replayed by every `alembic upgrade head` on a
fresh database, and named by `0022`'s `down_revision`. Its instruction had already been followed;
the paragraph was the note written while the file still lived somewhere else, and nothing read it
again.

That is a claim about the tree that the tree contradicts, which this repository gates rather than
reviews. The scanner reads the module docstring — the first thing a reader of a migration meets —
and refuses:

* a claim that the file is outside the tree: "not in the tree", "not committed", "untracked",
  "parked";
* the word "draft", which in a migration announces a state the chain does not have;
* a path under `migrations/versions/`, which in a docstring is an instruction to move the file
  rather than a description of what it creates (a migration creates tables, not Python files).

Two cases: the real population, and a self-test that feeds the scanner every spelling it must
refuse, so "no drafting residue" cannot pass by matching nothing.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"

DRAFTING = (
    re.compile(r"not\s+in\s+the\s+tree", re.IGNORECASE),
    re.compile(r"not\s+committed", re.IGNORECASE),
    re.compile(r"\buntracked\b", re.IGNORECASE),
    re.compile(r"\bparked\b", re.IGNORECASE),
    re.compile(r"\bdraft\b", re.IGNORECASE),
)

VERSIONS_PATH = re.compile(r"migrations/versions/[\w./-]+\.py")


def _docstring(source: str) -> str:
    doc = ast.get_docstring(ast.parse(source))
    assert doc, "a migration has no module docstring, so there is nothing to inspect"
    return doc


def _residue(doc: str) -> list[str]:
    found = [match.group(0) for pattern in DRAFTING if (match := pattern.search(doc))]
    path = VERSIONS_PATH.search(doc)
    if path is not None:
        found.append(path.group(0))
    return found


def test_no_migration_describes_itself_as_outside_the_tree() -> None:
    migrations = sorted(VERSIONS.glob("*.py"))
    assert len(migrations) >= 40, f"{VERSIONS} holds {len(migrations)} migrations, so this gate reads almost nothing"
    offenders: list[str] = []
    for path in migrations:
        residue = _residue(_docstring(path.read_text(encoding="utf-8")))
        if residue:
            offenders.append(f"{path.name} says {residue}")
    assert not offenders, "a migration's docstring contradicts the tree it is committed in: " + "; ".join(offenders)


def test_the_scanner_refuses_every_drafting_spelling_and_accepts_a_description() -> None:
    refused = (
        '"""A table.\n\nPARKED DRAFT — not in the tree on purpose.\n"""\n',
        '"""A table.\n\nThis file is not committed yet.\n"""\n',
        '"""A table scraped from an untracked scratch copy."""\n',
        '"""A parked table, written but not landed."""\n',
        '"""Two design decisions that the draft makes."""\n',
        '"""Move to `apps/api/migrations/versions/0099_x.py` once the leg is green."""\n',
    )
    for source in refused:
        assert _residue(_docstring(source)), f"the scanner accepted a docstring it must refuse: {source!r}"

    accepted = (
        '"""The rows live with the models in `app/models/__init__.py`."""\n',
        '"""Two design decisions the table\'s shape makes."""\n',
        '"""A fixture is the record of a promise between two sides."""\n',
    )
    for source in accepted:
        assert not _residue(_docstring(source)), f"the scanner refused a plain description: {source!r}"
