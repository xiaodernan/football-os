"""0025 — §38's share output: one revocable token over a CV that stores no figures (M10, spec §38, §40).

`cv_shares` holds only what `build_cv` cannot derive: the token, the section names its owner chose, and the two
timestamps that say when the link opened and when it closed. Every figure a public reader sees is counted from the
rows §38's published formulas name at the moment of the read, which is why a link minted before a training session
was completed shows that session the next time somebody opens it.

There is no `player_id` column, and that is a decision rather than an omission. A link that stored which player row
it pointed at would need either an ownership check on a caller-supplied id — which §35's reach rule forbids, because
the refusal for "that id exists but is not yours" confirms existence — or a second copy of §38's player-resolution
rule, which §50 forbids. So a link points at an account, and the read resolves the player through the one reader the
owner's own door uses. The `ondelete` follows §36's argument for a publication that is its author's own: the
account's erasure right (§40) takes its links down with it.

`revoked_at` rather than §17's nulled token. `tactic_boards` sets `share_token = None`, which stops the old link
resolving and loses the fact that a link ever existed; a CV link is the kind of thing its owner later asks when it
closed, so the row keeps both timestamps and the doors read the live ones.

Nothing dialect-specific: every constraint is named through `op.f()` so both engines in the test matrix accept the
DDL as written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cv_shares",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_cv_shares_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cv_shares")),
        sa.UniqueConstraint("share_token", name=op.f("uq_cv_share_token")),
    )
    op.create_index("ix_cv_share_owner_live", "cv_shares", ["user_id", "revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_cv_share_owner_live", table_name="cv_shares")
    op.drop_table("cv_shares")
