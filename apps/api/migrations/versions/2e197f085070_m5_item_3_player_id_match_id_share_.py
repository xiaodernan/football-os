"""M5 item 3: player_id, match_id, share_token on video_assets

Revision ID: 2e197f085070
Revises: 0025
Create Date: 2026-09-30 12:03:23.868379

Rewritten by hand after `alembic upgrade head` failed on SQLite, which is the leg every local run and
`scripts/check.sh` use. It arrived as unadjusted autogenerate — the `### commands auto generated ###` markers were
still in place — produced against PostgreSQL, where `ALTER COLUMN … TYPE` and `ADD CONSTRAINT` are ordinary
statements. SQLite has neither: it has no `ALTER COLUMN` at all, and it cannot add a foreign key or a unique
constraint to an existing table. Alembic's batch mode rebuilds the table instead, and `migrations/env.py` already
sets `render_as_batch=_is_sqlite()` for exactly this reason — the flag only applies to autogenerate, so a
migration generated on one engine and committed unadjusted still fails on the other.

Two things were also wrong beyond the dialect:

* **Each new column was indexed twice.** `player_id` and `match_id` carry `index=True` on the column *and* an
  `Index(...)` row in `__table_args__`, which is two indexes on one column. The model has been corrected to
  declare one, and this migration creates one.
* **`downgrade()` could not run on any engine.** It called `op.drop_constraint(None, ...)` three times — an
  unnamed constraint cannot be dropped by name — so the revision was one-way in practice. Dropping the columns
  removes the constraints that hang off them on both engines, so that is what it does now.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '2e197f085070'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `period_key` widens from 7 to 10 characters. On SQLite this is a table rebuild; on PostgreSQL it is the
    # `ALTER COLUMN … TYPE` it always was. Batch mode picks the right one per dialect.
    with op.batch_alter_table("usage_events") as batch:
        batch.alter_column("period_key", existing_type=sa.VARCHAR(length=7), type_=sa.String(length=10), existing_nullable=False)

    op.add_column("video_assets", sa.Column("player_id", sa.String(length=40), nullable=True))
    op.add_column("video_assets", sa.Column("match_id", sa.String(length=40), nullable=True))
    op.add_column("video_assets", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.add_column("video_assets", sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True))
    # Nullable first, backfilled, then made NOT NULL — the three steps SQLite's `ALTER TABLE` cannot do in one.
    # No `server_default`: the model declares a Python-side `default`, and a server default the model does not
    # know about is exactly what `alembic check` reports as drift.
    op.add_column("video_assets", sa.Column("visibility", sa.String(length=20), nullable=True))
    op.execute("UPDATE video_assets SET visibility = 'private' WHERE visibility IS NULL")

    # The unique constraint and both foreign keys are `ADD CONSTRAINT` forms SQLite does not have, so they go
    # through the same rebuild. On PostgreSQL batch mode emits the plain statements.
    with op.batch_alter_table("video_assets") as batch:
        batch.alter_column("visibility", existing_type=sa.String(length=20), nullable=False)
        batch.create_unique_constraint("uq_video_assets_share_token", ["share_token"])
        batch.create_foreign_key("fk_video_assets_player_id_user_players", "user_players", ["player_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_video_assets_match_id_sim_matches", "sim_matches", ["match_id"], ["id"], ondelete="SET NULL")

    # One index per column, named the way the column's `index=True` names it — not the two the first draft made.
    op.create_index(op.f("ix_video_assets_match_id"), "video_assets", ["match_id"], unique=False)
    op.create_index(op.f("ix_video_assets_player_id"), "video_assets", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_assets_player_id"), table_name="video_assets")
    op.drop_index(op.f("ix_video_assets_match_id"), table_name="video_assets")
    # Dropping the column takes its unique constraint and its foreign key with it on both engines, which is why
    # this does not try to name constraints the first draft left unnamed.
    with op.batch_alter_table("video_assets") as batch:
        batch.drop_column("visibility")
        batch.drop_column("shared_at")
        batch.drop_column("share_token")
        batch.drop_column("match_id")
        batch.drop_column("player_id")
    with op.batch_alter_table("usage_events") as batch:
        batch.alter_column("period_key", existing_type=sa.String(length=10), type_=sa.VARCHAR(length=7), existing_nullable=False)
