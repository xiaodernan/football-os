"""the shortlist (spec §23's 建立 shortlist): a list that stores membership, not figures

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-25 10:20:00.000000

§23 asks the scout for a shortlist, and the obvious schema is a table of players with the numbers that
recommended them copied in. This migration refuses that shape, and the reason is a difference between a
shortlist and the one table in this project that *does* snapshot prices.

`transfer_listings` stores the asking fee, the release clause and the fit score as they read at listing
time, because a listing is the record of something that happened: an offer was made at that number and a
seller answered it. Rewriting the row when the world moves would falsify a negotiation. A shortlist is the
opposite kind of object — not a record of an act but a live question, *who am I watching* — and a rating
frozen at add-time keeps answering long after the row behind it has been regenerated, scored a season, or
had its asking fee repriced by §22's own valuation formula. A stale number on a live question is the exact
failure mode §24's whole report exists to avoid.

So these two tables store four things about a player: that he is on the list, in what order, and the
manager's own words about him. Every figure a shortlist prints — age, band, foot, overall, potential,
headroom, asking fee, the club he is at now, the fit against the career's need band — is read again from
`real_players` and §23's own candidate projection on the request that shows it, by the same code path a
search uses. Nothing in this schema can go stale, because nothing in it is a claim about the player.

`career_id` is the one link that does carry meaning beyond membership: a list built against a career is
read against that career's *current* need, which is itself recomputed each time from the career's own
squad rows and the round it has reached. It is `SET NULL` rather than `DELETE CASCADE` on purpose: a
deleted career must not delete the list a manager was using, it must only stop the list being able to say
whose need it answers.

What this tier does not claim: no scores are stored, so no score can be exported or shared as a promise
about a player's future; no rank is stored beyond insertion order, so the list cannot become a ranking the
world later agrees with by accident; and nothing here observes a player — a row on a list says somebody
typed his name, which is a fact about the account, not about the footballer.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scout_shortlists",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("query", sa.String(length=400), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_scout_shortlists_owner_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_scout_shortlists_career_id_careers"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scout_shortlists")),
        sa.UniqueConstraint("owner_id", "name", name=op.f("uq_shortlist_owner_name")),
    )
    op.create_index("ix_shortlist_owner", "scout_shortlists", ["owner_id"], unique=False)

    op.create_table(
        "scout_shortlist_items",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("shortlist_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["shortlist_id"],
            ["scout_shortlists.id"],
            name=op.f("fk_scout_shortlist_items_shortlist_id_scout_shortlists"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["real_players.id"],
            name=op.f("fk_scout_shortlist_items_player_id_real_players"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scout_shortlist_items")),
        sa.UniqueConstraint("shortlist_id", "player_id", name=op.f("uq_shortlist_player")),
    )
    op.create_index("ix_shortlist_item_order", "scout_shortlist_items", ["shortlist_id", "position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shortlist_item_order", table_name="scout_shortlist_items")
    op.drop_table("scout_shortlist_items")
    op.drop_index("ix_shortlist_owner", table_name="scout_shortlists")
    op.drop_table("scout_shortlists")
