"""§39's Matches row as one table: a fixture the tenant arranged, and no figure about the match.

The rows this migration creates are complemented by the models — `ClubFixture` and `club_match_appearances` in
`app/models/__init__.py` — and by the club fixtures door that reads them.

Two design decisions the table's shape makes:

* **A lineup is a selection, an appearance is a record — so they live apart.** Who the tenant *named* is a
  selection over its sheet, and §41 already stores one of those: `club_sessions.attendees` is a JSON list of
  player ids resolved to the person at write time. Who actually *played* is different in kind: the engine's own
  eleven for a match that has already happened. Re-deriving it at read time would be a claim about the past
  computed from rows that can still move (a player taken off the sheet, an attribute that shifted the band
  order), and `simulation.squad.replay_squads` cannot help — it rebuilds a *career's* overlays from move rows,
  and a tenant's fixture has none. So `club_match_appearances` is written in the same transaction as the result,
  checked against the stored report the way `career._trace_round` checks it, and the row is the record of the act
  — exactly the standing `career_appearances` and `transfer_listings` have.
* **No minutes, no score, no opponent rating on the fixture.** The goals live in `sim_matches` (one row, one
  truth), the timeline and every counted figure live in `sim_events`, and the appearance rows carry the
  fixture's `minutes` with the rule printed beside it, because the engine makes no substitutions.

Column choices mirror `club_sessions` exactly where the meaning is the same: ISO date as `String(10)` text,
`data_origin='user'` with `is_demo_data=False`, `created_at`/`updated_at` from the timestamp mixin, and
constraint names through `op.f(...)` because both engines have to accept the DDL as written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_fixtures",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=False),
        sa.Column("opponent_team_id", sa.String(length=40), nullable=True),
        # The name the arrangement was made against. `career_fixtures` stores its opponent's name for the same
        # reason: a fixture is the record of a promise between two sides, and a world regeneration that renames
        # a club must not rewrite what the tenant agreed to. Every *figure* is still read from the rows behind it.
        sa.Column("opponent_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("side", sa.String(length=5), nullable=False, server_default="home"),
        sa.Column("competition", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("scheduled_on", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="scheduled"),
        sa.Column("match_id", sa.String(length=40), nullable=True),
        sa.Column("match_slug", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("digest", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(length=60), nullable=False, server_default=""),
        # Player ids the tenant named for this fixture, resolved the way §42 resolved attendance: the row stores
        # the person, not the spelling. An empty list is allowed *here* (a fixture can be arranged before a squad
        # is picked) where a session may not, which is why it is not refused at the write door.
        sa.Column("named", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=280), nullable=False, server_default=""),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_fixtures_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["club_teams.id"], name=op.f("fk_club_fixtures_club_teams"), ondelete="CASCADE"),
        # A borrowed world club that vanishes leaves the arrangement standing as a row with no opponent row
        # behind it, and the read says so; it does not delete the tenant's history.
        sa.ForeignKeyConstraint(["opponent_team_id"], ["teams.id"], name=op.f("fk_club_fixtures_teams"), ondelete="SET NULL"),
        # The engine's match outlives the fixture that points at it, and a deleted simulation must not take the
        # tenant's record of the fixture with it — the read then prints that the played rows are gone.
        sa.ForeignKeyConstraint(["match_id"], ["sim_matches.id"], name=op.f("fk_club_fixtures_sim_matches"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_fixtures")),
        # One side cannot be at home twice on one date: the third coordinate a collision has to name. A tenant
        # may well play two fixtures on a date (home and away, or two teams), and both stay legal.
        sa.UniqueConstraint("organization_id", "team_id", "scheduled_on", "side", name=op.f("uq_club_fixture_day_side")),
    )
    op.create_index("ix_club_fixture_org_date", "club_fixtures", ["organization_id", "scheduled_on"])
    op.create_index("ix_club_fixture_team_date", "club_fixtures", ["team_id", "scheduled_on"])
    op.create_index("ix_club_fixture_match", "club_fixtures", ["match_id"])

    op.create_table(
        "club_match_appearances",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("fixture_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        # Denormalised the way `career_appearances` does it, and for the same reason: the row is a record of an act,
        # and a person who is renamed afterwards must not have their appearance re-titled. The id stays the join,
        # so a read that wants today's record can follow it.
        sa.Column("player_slug", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("player_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("position", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("band", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("side", sa.String(length=5), nullable=False, server_default="home"),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=280), nullable=False, server_default=""),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_match_appearances_organizations"), ondelete="CASCADE"),
        # Erasing the fixture erases the record of who played it: the appearance is a fact *about* that fixture,
        # and §40's deletion rule asks for the child's rows to follow their own tenant's erasure, not to outlive it.
        sa.ForeignKeyConstraint(["fixture_id"], ["club_fixtures.id"], name=op.f("fk_club_match_appearances_club_fixtures"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_club_match_appearances_real_players"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_match_appearances")),
        # One player cannot have played the same fixture twice, whichever side the row was written from.
        sa.UniqueConstraint("fixture_id", "player_id", name=op.f("uq_club_match_appearance_player")),
    )
    op.create_index("ix_club_match_appearance_fixture", "club_match_appearances", ["fixture_id"])
    op.create_index("ix_club_match_appearance_player", "club_match_appearances", ["player_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_club_match_appearance_player", table_name="club_match_appearances")
    op.drop_index("ix_club_match_appearance_fixture", table_name="club_match_appearances")
    op.drop_table("club_match_appearances")
    op.drop_index("ix_club_fixture_match", table_name="club_fixtures")
    op.drop_index("ix_club_fixture_team_date", table_name="club_fixtures")
    op.drop_index("ix_club_fixture_org_date", table_name="club_fixtures")
    op.drop_table("club_fixtures")
