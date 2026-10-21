"""A census of the rows an account erasure has to decide about (spec §61, M12).

The schema cascades every row whose foreign key points at `users.id`, so the only rows an erasure has to
decide about are the ones with **no** foreign key — jobs, model calls, RAG queries, usage events, audit
logs, revoked tokens. That list is a literal in the service, and a literal in a service is a contract that
rots the day a table is added: a new account-linked table would join an account, survive the erasure, and
the inventory would never have said so.

This file holds the two together:

* every column that **looks** like an account id, in a table with no foreign key to `users.id`, is named
  in the erasure's contract with its fate;
* every row the contract names is a real column of a real table;
* every foreign key to `users.id` says what the database does with the row — `CASCADE` (the row goes with
  the account) or `SET NULL` (the row stays and loses the account id). A key that says neither would
  leave the account's row behind *and* refuse the delete.
"""

from __future__ import annotations

from app.core.db import Base
from app.services.account_deletion import (
    ACCOUNT_ID_COLUMN_NAMES,
    NO_FOREIGN_KEY_ACCOUNT_ROWS,
)


def _account_foreign_key_columns() -> list[tuple[str, str]]:
    """Every column that points at `users.id`, with what the database does with the row."""
    found: list[tuple[str, str]] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                if foreign_key.target_fullname == "users.id":
                    found.append((f"{table.name}.{column.name}", str(foreign_key.ondelete).upper()))
    return found


def test_every_account_linked_table_without_a_foreign_key_is_named_in_the_erasure() -> None:
    """A table that holds an account's row and cannot be cascaded must say what happens to it."""
    named = {name.split(".", 1)[0] for name in NO_FOREIGN_KEY_ACCOUNT_ROWS}
    candidates: set[str] = set()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if column.name not in ACCOUNT_ID_COLUMN_NAMES:
                continue
            if any(foreign_key.target_fullname == "users.id" for foreign_key in column.foreign_keys):
                continue
            candidates.add(table.name)
    missing = sorted(candidates - named)
    assert not missing, (
        "these tables hold an account's row and have no foreign key to `users.id`, so the erasure "
        f"cannot cascade them and must name them: {missing}. Add each to "
        "NO_FOREIGN_KEY_ACCOUNT_ROWS with its fate."
    )


def test_every_row_the_erasure_names_is_a_real_column() -> None:
    """A contract that names a table the schema does not have is a contract that lies."""
    for name in NO_FOREIGN_KEY_ACCOUNT_ROWS:
        table_name, _, column_name = name.partition(".")
        table = Base.metadata.tables.get(table_name)
        assert table is not None, f"{name} is named in the erasure's contract, and the schema has no {table_name}"
        assert column_name in table.columns, f"{name} is named in the erasure's contract, and {table_name} has no {column_name}"


def test_every_account_foreign_key_says_what_the_database_does_with_the_row() -> None:
    """A key that says neither CASCADE nor SET NULL would leave the row behind and refuse the delete."""
    undecided = [name for name, ondelete in _account_foreign_key_columns() if ondelete not in {"CASCADE", "SET NULL"}]
    assert not undecided, (
        "these columns point at `users.id` and say nothing about the row, so an account's row would "
        f"survive the erasure and the delete would fail: {sorted(undecided)}"
    )


def test_the_census_can_see_a_table_it_has_never_been_told_about() -> None:
    """The check has to be able to fail, or it is a sentence rather than a gate."""
    candidates = {
        table.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name in ACCOUNT_ID_COLUMN_NAMES
        and not any(foreign_key.target_fullname == "users.id" for foreign_key in column.foreign_keys)
    }
    assert candidates, "the census sees no account-linked table at all, so it is looking for nothing"
    named = {name.split(".", 1)[0] for name in NO_FOREIGN_KEY_ACCOUNT_ROWS}
    assert candidates & named, "the census's candidates and the contract do not meet, so one of them is wrong"
