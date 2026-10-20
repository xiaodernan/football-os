#!/usr/bin/env python
"""Create (or re-create) a throwaway Postgres database for a browser walk, and print its URL.

Why a walk needs its own database: the API builds a schema with `init_db()`, which is `create_all` — it creates
what is missing and alters nothing. A long-lived development database therefore keeps whatever column widths the
code had on the day each table was first made (see `scripts/schema_drift.py`), so a walk run against it is testing
a schema no fresh installation has. A walk run against a database this script just made is testing the one
`init_db()` produces from today's models — and it cannot leave tenant rows, members or usage events behind in a
database somebody else is reading.

The name is checked before anything is dropped, and the database named by the API's own `DATABASE_URL` is refused,
so the worst this script can do is delete its own scratch space.

Usage: `export DATABASE_URL=$(python scripts/qa_db.py)`

`--assert-scratch NAME` answers one question — would this script be willing to drop and re-create NAME? — and
touches nothing. `scripts/restore_db.sh` runs it, so a disaster-recovery script that has to refuse a real
database holds the refusal once instead of typing a copy of this file's pattern into bash.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import NullPool, create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402

#: A scratch name says what it is: nothing matching these patterns is a real database, and anything that does not
#: match is refused before a DROP is ever considered.
SCRATCH = re.compile(r"^(?:football_os_)?(?:qa|walk|scratch)[a-z0-9_]*$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def scratch_refusal(name: str) -> str | None:
    """Return the reason ``name`` is not a database this script may drop, or ``None`` when it is one."""
    if not IDENTIFIER.fullmatch(name):
        return (
            f"{name!r} is not a plain lower-case SQL identifier (a-z, digits, underscore, at most 63 characters)"
        )
    if not SCRATCH.fullmatch(name):
        return (
            f"{name!r} does not start with qa/walk/scratch (optionally after a football_os_ prefix), "
            "so nothing about it says throwaway — e.g. football_os_qa"
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--name",
        default="football_os_qa",
        help="the scratch database to create (must be recognisably scratch)",
    )
    parser.add_argument(
        "--assert-scratch",
        metavar="NAME",
        help="print whether NAME would be a legal --name and exit 1 if it would not, without touching a server",
    )
    args: Any = parser.parse_args()

    if args.assert_scratch is not None:
        # The name-only leg, for `scripts/restore_db.sh`: it must decide before a `pg_dump` is on the command line
        # and it must not need a running server to answer, because the answer is what arms the refusal.
        reason = scratch_refusal(args.assert_scratch)
        if reason is None:
            print(f"scratch: {args.assert_scratch} is a database this script may drop and re-create")
            return 0
        print(f"REFUSED: {reason}", file=sys.stderr)
        return 1

    reason = scratch_refusal(args.name)
    if reason is not None:
        raise SystemExit(f"refusing to touch {args.name!r}: {reason}")
    source = make_url(settings.database_url)
    if source.drivername.startswith("sqlite"):
        raise SystemExit(
            "the API is pointed at SQLite, so there is no server to create a database on; name a Postgres DATABASE_URL"
        )
    if source.database == args.name:
        raise SystemExit(
            f"refusing to drop {args.name!r}: the API's own DATABASE_URL names it, and that is not a scratch database"
        )

    maintenance = create_engine(
        source.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    with maintenance.connect() as connection:
        # `WITH (FORCE)` and the terminate above are both load-bearing: a pool from a previous run, or the API
        # this script is being run for, holds the database open and a plain DROP would block forever.
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": args.name},
        )
        connection.execute(text(f"DROP DATABASE IF EXISTS {args.name} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {args.name}"))
    maintenance.dispose()

    fresh = create_engine(
        source.set(database=args.name), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    with fresh.connect() as connection:
        # `vector` is not in `template1` on this server — it is installed per database — so without this the app's
        # own `init_db()` fails at `knowledge_chunks.embedding` before the walk can open a page.
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    fresh.dispose()
    print(source.set(database=args.name).render_as_string(hide_password=False))
    print(
        f"-- created {args.name}; the schema is the app's to build at startup",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
