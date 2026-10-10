"""Drop the video_assets legacy index aliases the restore drill surfaced

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-11 03:05:00

`2e197f085070`'s docstring records the defect: `player_id` and `match_id` were indexed twice —
`index=True` on the column *and* an `Index(...)` in `__table_args__` — and the model plus this
migration were corrected to create one each (`ix_video_assets_player_id`, `ix_video_assets_match_id`).
Fresh databases replay the corrected history and `alembic check` is clean everywhere the gate runs.

What the correction could not reach was a database that already existed. This project's own
PostgreSQL container was created before the fix, still carries the original aliases
(`ix_video_match`, `ix_video_player`), and `alembic check` against it therefore reported two
`remove_index` operations — found, not by a gate, but by executing the M12 restore drill and
running `alembic check` against the *restored* copy, which is the drill doing its job: proving
the backup is byte-faithful, drift and all.

This revision drops the two aliases where they exist. On a fresh database — either engine — both
`DROP INDEX IF EXISTS` statements are no-ops, so the gate's fresh-database legs are unchanged; on
the long-lived container they converge its schema with what the models declare. `downgrade`
recreates them, because a reversible repair to a live database is worth more than a tidy history.
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

LEGACY_ALIASES = ("ix_video_match", "ix_video_player")


def upgrade() -> None:
    for index_name in LEGACY_ALIASES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")


def downgrade() -> None:
    for index_name in LEGACY_ALIASES:
        column = "match_id" if index_name == "ix_video_match" else "player_id"
        op.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON video_assets ({column})")
