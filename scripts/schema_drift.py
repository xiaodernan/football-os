#!/usr/bin/env python
"""Compare each `String(n)` the models declare against the width the database actually holds.

Why this exists: the app creates a fresh schema with `init_db()`, but `create_all` never *alters* a table that
already exists. So a column widened in code — §42's `usage_events.period_key`, `YYYY-MM` (7) to `YYYY-MM-DD` (10)
— stays narrow in every long-lived database that was created before the change, and only the engine that enforces
widths notices. SQLite stores what it is given and passes; Postgres raises `StringDataRightTruncation` at the
first daily usage row, which is how a browser walk met a 500 no test had produced.

Read-only: it SELECTs from the catalog and writes nothing. Exit 1 names a column the database cannot hold, so a
gate can fail on it. Usage: `python scripts/schema_drift.py` (the API's own DATABASE_URL) or pass a URL.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

warnings.filterwarnings("ignore", message="Did not recognize type")

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402
from app import models  # noqa: E402,F401 — importing the models is what populates Base.metadata


def declared() -> dict[str, dict[str, int]]:
    """Every fixed-width text column the code says a table has."""
    return {
        table.name: {
            str(column.name): int(column.type.length)
            for column in table.columns
            if getattr(column.type, "length", None)
        }
        for table in Base.metadata.sorted_tables
    }


def held(engine: Engine) -> dict[str, dict[str, int | None]]:
    """Every fixed-width text column the database says it has, `None` for a type with no width."""
    inspector = inspect(engine)
    return {
        str(table): {
            str(row["name"]): (
                int(row["type"].length)
                if getattr(row["type"], "length", None)
                else None
            )
            for row in inspector.get_columns(str(table))
        }
        for table in inspector.get_table_names()
    }


def compare(url: str) -> tuple[list[str], list[str], list[str]]:
    engine = create_engine(url)
    want, have = declared(), held(engine)
    missing_tables = [table for table in want if table not in have]
    narrow = [
        f"{table}.{column}: the database holds {have[table][column]} characters, the model writes up to {width}"
        for table, columns in sorted(want.items())
        for column, width in sorted(columns.items())
        if isinstance(have.get(table, {}).get(column), int)
        and have[table][column] < width
    ]
    wider = [
        f"{table}.{column}: the database holds {have[table][column]} characters, the model declares {width}"
        for table, columns in sorted(want.items())
        for column, width in sorted(columns.items())
        if isinstance(have.get(table, {}).get(column), int)
        and have[table][column] > width
    ]
    return narrow, wider, missing_tables


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="database URL; defaults to the API's own DATABASE_URL",
    )
    args: Any = parser.parse_args()
    url = args.url or settings.database_url
    # Never print the credential the URL carries — the point of this probe is a schema, not a password.
    print(f"== {url.rsplit('@', 1)[-1] if '@' in url else url}")
    narrow, wider, missing_tables = compare(url)
    total = sum(len(columns) for columns in declared().values())
    print(
        f"{total} fixed-width text columns declared; {len(narrow)} narrower in the database than in the model, {len(wider)} wider, {len(missing_tables)} tables absent"
    )
    for line in missing_tables:
        print(f"ABSENT {line}")
    for line in narrow:
        print(f"NARROW {line}")
    for line in wider:
        print(f"WIDER  {line}")
    if narrow:
        print(
            "A narrower column is a write that SQLite accepts and Postgres refuses: recreate this database (or run the migration that widens it)."
        )
    return 1 if narrow else 0


if __name__ == "__main__":
    raise SystemExit(main())
