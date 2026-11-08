"""Cup ties earn a gate and leave appearance minutes (M13 Phase 9 item 34)

A cup tie is played on a real ground in front of a real crowd, and the eleven that plays it is the
career's eleven — but neither fact reached the ledger or the development curve, because both were keyed
by the league round. A tie played after round 7 shares round 7, so the one-gate-per-round and
one-trace-per-player-per-round uniques refused it.

This migration gives both tables a nullable ``tie_id``, names the tie in the uniqueness rule, and turns
the league rules into partial indexes over ``tie_id IS NULL``. A league round keeps exactly one gate and
one trace per player; a cup tie keeps one gate and one trace per player of its own. ``career_gate_receipts``
follows ``fixture_id`` in using SET NULL, because losing the tie must not delete money the balance already
counted; ``career_appearances`` cascades, because a deleted tie's minutes are not a league round.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

_LEAGUE_GATE = "uq_career_gate_round"
_LEAGUE_TRACE = "uq_career_appearance_round_player"


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("career_gate_receipts", recreate="always") as batch:
            batch.add_column(sa.Column("tie_id", sa.String(length=40), nullable=True))
            batch.drop_constraint(_LEAGUE_GATE, type_="unique")
            batch.create_foreign_key("fk_gate_receipt_tie", "career_cup_ties", ["tie_id"], ["id"], ondelete="SET NULL")
        with op.batch_alter_table("career_appearances", recreate="always") as batch:
            batch.add_column(sa.Column("tie_id", sa.String(length=40), nullable=True))
            batch.drop_constraint(_LEAGUE_TRACE, type_="unique")
            batch.create_foreign_key("fk_appearance_tie", "career_cup_ties", ["tie_id"], ["id"], ondelete="CASCADE")
    else:
        op.add_column("career_gate_receipts", sa.Column("tie_id", sa.String(length=40), nullable=True))
        op.create_foreign_key(
            "fk_gate_receipt_tie", "career_gate_receipts", "career_cup_ties", ["tie_id"], ["id"], ondelete="SET NULL"
        )
        op.drop_constraint(_LEAGUE_GATE, "career_gate_receipts", type_="unique")
        op.add_column("career_appearances", sa.Column("tie_id", sa.String(length=40), nullable=True))
        op.create_foreign_key(
            "fk_appearance_tie", "career_appearances", "career_cup_ties", ["tie_id"], ["id"], ondelete="CASCADE"
        )
        op.drop_constraint(_LEAGUE_TRACE, "career_appearances", type_="unique")
    op.create_index(
        _LEAGUE_GATE,
        "career_gate_receipts",
        ["career_id", "round_index"],
        unique=True,
        sqlite_where=sa.text("tie_id IS NULL"),
        postgresql_where=sa.text("tie_id IS NULL"),
    )
    op.create_index("uq_career_gate_tie", "career_gate_receipts", ["tie_id"], unique=True)
    op.create_index(
        _LEAGUE_TRACE,
        "career_appearances",
        ["career_id", "round_index", "player_id"],
        unique=True,
        sqlite_where=sa.text("tie_id IS NULL"),
        postgresql_where=sa.text("tie_id IS NULL"),
    )
    op.create_index(
        "uq_career_appearance_tie_player",
        "career_appearances",
        ["career_id", "tie_id", "player_id"],
        unique=True,
        sqlite_where=sa.text("tie_id IS NOT NULL"),
        postgresql_where=sa.text("tie_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_career_appearance_tie_player", table_name="career_appearances")
    op.drop_index(_LEAGUE_TRACE, table_name="career_appearances")
    op.drop_index("uq_career_gate_tie", table_name="career_gate_receipts")
    op.drop_index(_LEAGUE_GATE, table_name="career_gate_receipts")
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("career_appearances", recreate="always") as batch:
            batch.drop_constraint("fk_appearance_tie", type_="foreignkey")
            batch.create_unique_constraint(_LEAGUE_TRACE, ["career_id", "round_index", "player_id"])
            batch.drop_column("tie_id")
        with op.batch_alter_table("career_gate_receipts", recreate="always") as batch:
            batch.drop_constraint("fk_gate_receipt_tie", type_="foreignkey")
            batch.create_unique_constraint(_LEAGUE_GATE, ["career_id", "round_index"])
            batch.drop_column("tie_id")
    else:
        op.drop_constraint("fk_appearance_tie", "career_appearances", type_="foreignkey")
        op.create_unique_constraint(_LEAGUE_TRACE, "career_appearances", ["career_id", "round_index", "player_id"])
        op.drop_column("career_appearances", "tie_id")
        op.drop_constraint("fk_gate_receipt_tie", "career_gate_receipts", type_="foreignkey")
        op.create_unique_constraint(_LEAGUE_GATE, "career_gate_receipts", ["career_id", "round_index"])
        op.drop_column("career_gate_receipts", "tie_id")
