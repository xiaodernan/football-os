"""the stored timeline (ROADMAP item 4): every event the engine reported becomes a row of its own

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-25 01:40:00.000000

The premise this table corrects is in the roadmap line itself, which read as if a match timeline were
regenerated on every view. It is not: `simulate_match` produces the event list once and `run_simulation`
stores the whole report — events included — in `sim_matches.report`, and the report route reads that JSON
back without asking the engine anything. The only path that re-derives a timeline is `/replay`, and that
one does so deliberately, to prove the engine still agrees with itself.

So the reason to store these rows is not duplication, it is *addressability*. A report is one blob per
match: "who scored most in this career", "how many sendings-off across this competition", "who took the
most attempts and at what quality" all currently mean loading every report in the world and picking JSON out
of it in Python. One row per event answers all three in a query, and gives the next module — a scoring
chart, a disciplinary balance, an AI scout (§23) that has to reason over a season rather than a match —
something to read. Not every question, though: `shot_saved` names the shooter, because that is what the
engine draws, so a goalkeeper's record is not among the things these rows can be asked.

Two decisions the row shape carries. `ordinal` is the event's index in the report's own list, and
`(match_id, ordinal)` is unique, because that pair is an event's whole identity: the report is sorted by
minute with ties broken by insertion order, so two events in one minute are distinguishable only by which
the engine appended first. And `player_id` is nullable with a SET NULL cascade rather than a required
foreign key, because the engine names a scorer out of the side's eleven and the printed `lineup` is
inside every stored match's digest — it cannot be changed to carry ids without making every stored
report disagree with its own hash. Identity is therefore recovered by looking the name back up in the
same eleven: unique name, an id; two players of one name, none, and the row says `ambiguous` out loud
rather than guessing which man's record it is writing.

What this does not claim: these rows are a copy, not a second opinion. They are written in the same
transaction as the report they came from, they never feed the engine, and a match simulated before this
migration has none — which the timeline check reports as *predates the events table* and reads off the
report instead, rather than presenting an empty timeline as a goalless match.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("match_id", sa.String(length=40), nullable=False),
        sa.Column("match_slug", sa.String(length=80), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        sa.Column("team", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=True),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=16), nullable=False),
        sa.Column("chance", sa.String(length=24), nullable=False),
        sa.Column("expected_goals", sa.Float(), nullable=True),
        sa.Column("score", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("attribution", sa.String(length=12), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["sim_matches.id"], name=op.f("fk_sim_events_match_id_sim_matches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_sim_events_team_id_teams"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_sim_events_player_id_real_players"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sim_events")),
        sa.UniqueConstraint("match_id", "ordinal", name="uq_sim_event_position"),
    )
    op.create_index("ix_sim_event_match", "sim_events", ["match_id"], unique=False)
    op.create_index("ix_sim_event_player_type", "sim_events", ["player_id", "event_type"], unique=False)
    op.create_index("ix_sim_event_type_minute", "sim_events", ["event_type", "minute"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sim_event_type_minute", table_name="sim_events")
    op.drop_index("ix_sim_event_player_type", table_name="sim_events")
    op.drop_index("ix_sim_event_match", table_name="sim_events")
    op.drop_table("sim_events")
