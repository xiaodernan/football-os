"""the B2B spine (spec §39 CLUB OS, §41 B2B): organisations, memberships, teams, and one player per sheet

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-25 12:40:00.000000

Everything built so far belongs to a person: a career, a board, a clip, a shortlist. §39 and §41 ask for the
other thing — a club, or an academy, or a school, with staff in it — and the difference is not cosmetic. A
tenant's rows are read by several people with different standing, they outlive any one of them, and a report
written inside one must not be legible from inside another. So this migration is the spine those rules sit on:
`organizations`, `organization_members`, `club_teams`, `club_team_members`.

Two decisions the shape carries, both of them the opposite of the first pass.

**Membership is a row, not a column.** `users.organization_id` has been there since `0001` and says, by its
type, that a person belongs to at most one organisation. §41 lists Coach and Scout among the tenants it
expects to serve, and the ordinary reality of either is standing in two places at once — the coach who runs a
club's Under-16s and scouts for an academy, the analyst employed by a school and volunteering at a grassroots
club. A single id would force one of those relationships out of the database entirely, which is worse than the
denormalisation it saves, so `organization_members` is the source of truth. `users.organization_id` is left in
place rather than dropped — this migration does not remove a column another module may still be reading — and
the club tier's own integrity gate reports every user whose `organization_id` names an organisation they are
not an active member of. The stale column can therefore go out of date; it cannot go unnoticed.

**A role is stored and a permission is not.** Each membership carries `role`; the rights that role grants live
in code and are printed by the API. A per-row permission blob would let one member's access drift from their
title with no record of when or by whom, and the honest question — *why can this person see that?* — would stop
having an answer. Storing the role and publishing the matrix means the answer is always a line of the
`GET /club/capabilities` output.

`status` is `invited` / `active` / `revoked` rather than a boolean for the same kind of reason: a membership can
be offered before it exists, and a departure should leave a row behind. Deleting a member's row would erase the
record of who was able to see what while they were standing in the room, and `revoked` keeps that history while
granting nothing.

A team is an organisation's own, and `world_team_id` is nullable on purpose: the fictional world's 20 clubs are
the fixtures an academy's Tuesday side plays against, and a team that has not been placed in that ladder is
still a team. The squad table points at `real_players` because that is where a player's attributes, age and club
are stored — an academy's roster is a *selection over* the same rows the scout searches, not a second copy of a
person that could disagree with the first. `uq_club_team_player` is the rule that one sheet lists a player once.

What this tier still does not do, and the following migrations must not be assumed to have done it: no reports,
no development plans, no sessions, no invitations by email, no billing. Nothing here grants a right yet either —
the matrix is in `app/services/club/access.py`, and until a route reads it, this is storage with a promise.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("visibility_default", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=40), nullable=True),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_organizations_created_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_index("ix_organization_kind", "organizations", ["kind"], unique=False)
    # No separate index on `slug`: the UNIQUE constraint is backed by an index in both engines, and
    # declaring one here would be a second object the models do not know about.

    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("invited_by", sa.String(length=40), nullable=True),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_organization_members_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_organization_members_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], name=op.f("fk_organization_members_invited_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_members")),
        sa.UniqueConstraint("organization_id", "user_id", name=op.f("uq_organization_member")),
    )
    op.create_index("ix_organization_member_user", "organization_members", ["user_id", "status"], unique=False)

    op.create_table(
        "club_teams",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("age_group", sa.String(length=24), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("world_team_id", sa.String(length=40), nullable=True),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_teams_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_team_id"], ["teams.id"], name=op.f("fk_club_teams_world_team_id_teams"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_teams")),
        sa.UniqueConstraint("organization_id", "name", name=op.f("uq_club_team_name")),
    )
    op.create_index("ix_club_team_organization", "club_teams", ["organization_id"], unique=False)

    op.create_table(
        "club_team_members",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["club_teams.id"], name=op.f("fk_club_team_members_team_id_club_teams"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_club_team_members_player_id_real_players"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_team_members")),
        sa.UniqueConstraint("team_id", "player_id", name=op.f("uq_club_team_player")),
    )
    op.create_index("ix_club_team_member_player", "club_team_members", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_club_team_member_player", table_name="club_team_members")
    op.drop_table("club_team_members")
    op.drop_index("ix_club_team_organization", table_name="club_teams")
    op.drop_table("club_teams")
    op.drop_index("ix_organization_member_user", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_index("ix_organization_kind", table_name="organizations")
    op.drop_table("organizations")
