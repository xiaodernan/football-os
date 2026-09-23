"""transfer market (spec §22): what the market offered, and what the career did about it

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-24 00:20:00.000000

Before this revision a career carried one budget number and no way to be checked against it: §21 could
publish `budget` on a run, but nothing could spend it, so the figure was a statement rather than a
balance. These two tables are what turns it into an arithmetic.

`transfer_listings` is the market's side: one player a career was offered, priced by the valuation at
the moment of the offer. The fee, clause and wage are copied out of the player row rather than joined
at read time on purpose — an offer that was made, and refused, should not silently reprice because the
demon world was regenerated underneath the career. `asking_fee` therefore stays the price the
valuation printed and `current_price` carries what the seller asks now, so the negotiation a career
did can be checked against the rule the market publishes.

`career_squad_moves` is the career's side: buy, loan, sell or release, each with the balance it left
behind in `budget_after`. Two columns do real work here. `round_index` is the round the move was made
before, which is what lets a stored match be re-derived: the eleven played in round 4 is the squad as
of the moves made before round 4, not as of today. `fee` is signed by direction of travel in the
reader's head, not in the column — the kind tells you whether it left or arrived, so summing stays
honest and one row can be checked against the running total in the next.

Neither table has an AI in it. §22 lists `Tactical Fit` and `Negotiation` as market features; both
land in the service layer as measured arithmetic over stored rows, and both print their formula.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_listings",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("potential", sa.Integer(), nullable=False),
        sa.Column("from_team_id", sa.String(length=40), nullable=True),
        sa.Column("from_team_name", sa.String(length=160), nullable=False),
        sa.Column("asking_fee", sa.Integer(), nullable=False),
        sa.Column("current_price", sa.Integer(), nullable=False),
        sa.Column("release_clause", sa.Integer(), nullable=False),
        sa.Column("contract_years", sa.Integer(), nullable=False),
        sa.Column("weekly_wage", sa.Integer(), nullable=False),
        sa.Column("tactical_fit", sa.Float(), nullable=False),
        sa.Column("needed_band", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("listed_round", sa.Integer(), nullable=False),
        sa.Column("negotiations", sa.Integer(), nullable=False),
        sa.Column("last_offer", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_transfer_listings_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["player_id"], ["real_players.id"], name=op.f("fk_transfer_listings_player_id_real_players"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["from_team_id"], ["teams.id"], name=op.f("fk_transfer_listings_from_team_id_teams"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_listings")),
        sa.UniqueConstraint("career_id", "player_id", name="uq_listing_career_player"),
    )
    op.create_index("ix_listing_career_status", "transfer_listings", ["career_id", "status"], unique=False)

    op.create_table(
        "career_squad_moves",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False),
        sa.Column("fee_units", sa.String(length=40), nullable=False),
        sa.Column("contract_years", sa.Integer(), nullable=False),
        sa.Column("weekly_wage", sa.Integer(), nullable=False),
        sa.Column("loan_until_round", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.String(length=40), nullable=True),
        sa.Column("counterparty_team_id", sa.String(length=40), nullable=True),
        sa.Column("counterparty_name", sa.String(length=160), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_squad_moves_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["player_id"], ["real_players.id"], name=op.f("fk_career_squad_moves_player_id_real_players"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["transfer_listings.id"], name=op.f("fk_career_squad_moves_listing_id_transfer_listings"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["counterparty_team_id"], ["teams.id"], name=op.f("fk_career_squad_moves_counterparty_team_id_teams"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_squad_moves")),
    )
    op.create_index("ix_squad_move_career_round", "career_squad_moves", ["career_id", "round_index"], unique=False)
    op.create_index("ix_squad_move_player", "career_squad_moves", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_squad_move_player", table_name="career_squad_moves")
    op.drop_index("ix_squad_move_career_round", table_name="career_squad_moves")
    op.drop_table("career_squad_moves")
    op.drop_index("ix_listing_career_status", table_name="transfer_listings")
    op.drop_table("transfer_listings")
