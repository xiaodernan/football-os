"""the wage bill (spec §22): a played round now costs the career what it agreed to pay

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-24 04:05:00.000000

§22 asks for *Contract* in the transfer market, and 0011 stored one beside every deal: a weekly wage and
a length of years. What it did not do was charge anyone. A career could sign five players at 60,000 a
week and finish the season with the same balance it opened with, so the published
`wage_committed_per_week` was a rate nobody paid, and `limitations()["wages"]` had to say so on the page.

This table is the payment: one row per round the engine plays, whose `fee` is the sum of the weekly
wages of the deals that career holds at the start of that round, with the names it was charged for in
`detail` and the balance it left behind in `budget_after` — the same running-total discipline
`career_squad_moves` was built on, so the two tables read together as one ledger.

Why a second table rather than a fifth `kind` in `career_squad_moves`: that table's `player_id` is a
foreign key to `real_players` and not nullable, because every row in it is about a person — and the
eleven is composed out of those rows, so a row with no player would either break the constraint or have
to be filtered out of squad maths everywhere it is read. Wages move money and no player. Keeping them
apart is what lets each table mean exactly one thing.

Nothing here is an economy. There is no sponsorship, no appearance bonus and no default: a career that
cannot pay its wage bill is not punished beyond the balance going negative, which the market page prints
and the buy route then refuses to spend from.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_wage_charges",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False),
        sa.Column("fee_units", sa.String(length=40), nullable=False),
        sa.Column("players", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_wage_charges_career_id_careers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_wage_charges")),
    )
    op.create_index("ix_wage_charge_career_round", "career_wage_charges", ["career_id", "round_index"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wage_charge_career_round", table_name="career_wage_charges")
    op.drop_table("career_wage_charges")
