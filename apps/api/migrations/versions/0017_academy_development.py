"""the youth academy (spec §40): curricula, one plan per child, assessments, feedback, cited clips, consent

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-25 19:10:00.000000

`0016` gave a club a tenant, staff and team sheets. §40 asks for the thing a tenant is *for* at academy level:
a child with a plan, a coach who rates them, a clip that shows why, and a parent who allowed all of it. So this
migration is six tables — `academy_curricula`, `development_plans`, `plan_assessments`, `coach_feedback`,
`plan_video_evidence`, `guardian_consents` — and every one of them is an answer to a question §40 lists as a
capability or as a minor-priority.

**`guardian_consents` is a gate, an access-control list and an erasure anchor, in one row.** The obvious shape
was a boolean on a player, and it is wrong three times over: consent is per purpose (a guardian who allows a
development plan does not thereby allow their child's face to appear in a video), per tenant (consent given to
one academy is not consent given to the next), and revocable while the record of what was done under it stays.
So the row is `(organization_id, guardian_user_id, player_id)` unique, carrying a `state` and a `scopes` list,
and the service reads *that row* to decide both whether a write is allowed and whether this reader may see the
child's plan. A `parent` in the permission matrix holds almost nothing on its own: what it holds is whatever a
granted row ties it to. `withdrawn` keeps the row for the same reason `0016` keeps a revoked membership — a
consent that was in force for a season was in force, and the tenant must still be able to say what it saw under it.

**A plan points at the world's player row and stores no rating of its own.** `development_plans.player_id` is a
foreign key into `real_players` with CASCADE, exactly like `club_team_members`: an academy's plan is a selection
over the rows the scout already searches, not a second copy that could disagree. What a plan *does* store is
`age_at_open` and `minor_at_open`, because `real_players.age` is an integer for a season and a plan written in
spring has to be able to say which rule applied to it when it was written. The live age is read too, and when
the two disagree the answer prints both rather than picking a side.

**`plan_assessments` keeps its own numbers and `progress` is not a column.** An assessment is the record of what
was seen on a day, so it stores `overall_observed` and the five `ratings` copied from the world's row at that
moment. Progress is the difference between a plan's first and last assessment — arithmetic over those rows,
recomputed on every read, with its formula printed beside each figure. A stored `progress` column would be a
number that goes out of date the moment the next assessment is written, which is the one kind of figure a
development page must not show.

**A clip citation is a window, and the clip stays the uploader's.** `plan_video_evidence` holds `t_start`/`t_end`
over a `video_assets` row that M5 already owns, and the link is SET NULL with `assessed_on`-style honesty: when
a person deletes their upload, the tenant's record of what was watched for a reason survives and reports
`clip_present=False`. Cascading would have let one account's deletion rewrite another tenant's history. No
playback URL is stored or issued here — §40's own list of what must never be default-public includes video, and
a plan is not a way to watch somebody else's clip.

**`phases` and `focus` are shape-limited, because §40's data-minimisation promise is a column list.** A phase
dict holds a label, a focus string and minutes; a goal holds a title, a measure and a date; the route bodies
refuse any other key. That is why those columns are JSON and `guardian_consents` has no free-text column at
all: the tier's answer to *what do you hold on my child?* has to be a list somebody can check, and a JSON blob
that accepts arbitrary keys would make the published list a claim rather than a fact.

What this tier still does not do: no training *sessions* and no attendance record (a curriculum describes a
week, it does not log a Tuesday), no medical or safeguarding field of any kind, no push notification to a
guardian, no way to email a report, and no verification that the account claiming a child is that child's
guardian — `limitations()` states that last one out loud rather than letting a consent row imply a check that
does not exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "academy_curricula",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("age_group", sa.String(length=24), nullable=False),
        sa.Column("weekly_minutes", sa.Integer(), nullable=False),
        sa.Column("phases", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_academy_curricula_organization_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academy_curricula")),
        sa.UniqueConstraint("organization_id", "name", name=op.f("uq_academy_curriculum_name")),
    )
    op.create_index("ix_academy_curriculum_org", "academy_curricula", ["organization_id"], unique=False)

    op.create_table(
        "development_plans",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("curriculum_id", sa.String(length=40), nullable=True),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("author_user_id", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("focus", sa.JSON(), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("review_weeks", sa.Integer(), nullable=False),
        sa.Column("age_at_open", sa.Integer(), nullable=False),
        sa.Column("minor_at_open", sa.Boolean(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_development_plans_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curriculum_id"], ["academy_curricula.id"], name=op.f("fk_development_plans_curriculum_id_academy_curricula"), ondelete="SET NULL"),
        # A curriculum is a tenant's own document, so the reference is aimed and not chained: deleting one
        # must not delete the plans written under it, and a plan left pointing at another tenant's curriculum
        # would be the isolation breach this whole tier exists to prevent. `academy_problems()` reports one.
        sa.ForeignKeyConstraint(["team_id"], ["club_teams.id"], name=op.f("fk_development_plans_team_id_club_teams"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_development_plans_player_id_real_players"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], name=op.f("fk_development_plans_author_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_development_plans")),
    )
    op.create_index("ix_development_plan_org", "development_plans", ["organization_id"], unique=False)
    # The two questions this table is asked constantly: *what does this tenant have open*, and
    # *does this child already have a live plan* — the latter is the one-plan rule, checked on every write.
    op.create_index("ix_development_plan_player", "development_plans", ["player_id", "status"], unique=False)

    op.create_table(
        "plan_assessments",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False),
        sa.Column("assessor_user_id", sa.String(length=40), nullable=True),
        sa.Column("assessed_on", sa.String(length=10), nullable=False),
        sa.Column("ratings", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("areas", sa.Text(), nullable=False),
        sa.Column("overall_observed", sa.Integer(), nullable=False),
        sa.Column("next_focus", sa.String(length=120), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["development_plans.id"], name=op.f("fk_plan_assessments_plan_id_development_plans"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessor_user_id"], ["users.id"], name=op.f("fk_plan_assessments_assessor_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_assessments")),
    )
    op.create_index("ix_plan_assessment_plan", "plan_assessments", ["plan_id", "assessed_on"], unique=False)

    op.create_table(
        "coach_feedback",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False),
        sa.Column("coach_user_id", sa.String(length=40), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("shared_with_guardian", sa.Boolean(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["development_plans.id"], name=op.f("fk_coach_feedback_plan_id_development_plans"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["coach_user_id"], ["users.id"], name=op.f("fk_coach_feedback_coach_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coach_feedback")),
    )
    op.create_index("ix_coach_feedback_plan", "coach_feedback", ["plan_id", "created_at"], unique=False)

    op.create_table(
        "plan_video_evidence",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False),
        sa.Column("assessment_id", sa.String(length=40), nullable=True),
        sa.Column("asset_id", sa.String(length=40), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("t_start", sa.Float(), nullable=False),
        sa.Column("t_end", sa.Float(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["development_plans.id"], name=op.f("fk_plan_video_evidence_plan_id_development_plans"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["plan_assessments.id"], name=op.f("fk_plan_video_evidence_assessment_id_plan_assessments"), ondelete="SET NULL"),
        # Deliberately SET NULL rather than CASCADE: the clip belongs to the account that uploaded it, and
        # deleting a person's own upload must not rewrite a tenant's record of what was cited for a reason.
        # The citation then reports `clip_present=False`, which is the truth about what remains.
        sa.ForeignKeyConstraint(["asset_id"], ["video_assets.id"], name=op.f("fk_plan_video_evidence_asset_id_video_assets"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_video_evidence")),
    )
    op.create_index("ix_plan_evidence_plan", "plan_video_evidence", ["plan_id"], unique=False)

    op.create_table(
        "guardian_consents",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("guardian_user_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_guardian_consents_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guardian_user_id"], ["users.id"], name=op.f("fk_guardian_consents_guardian_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_guardian_consents_player_id_real_players"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardian_consents")),
        # One account's standing toward one child inside one tenant: the scope set is what changes when a
        # guardian ticks more boxes, so a second row for the same triple would be two answers to one question.
        sa.UniqueConstraint("organization_id", "guardian_user_id", "player_id", name=op.f("uq_guardian_consent")),
    )
    # `player_id, state` is the gate's own lookup: every write asks *is there a granted row for this child*.
    op.create_index("ix_guardian_consent_player", "guardian_consents", ["player_id", "state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_guardian_consent_player", table_name="guardian_consents")
    op.drop_table("guardian_consents")
    op.drop_index("ix_plan_evidence_plan", table_name="plan_video_evidence")
    op.drop_table("plan_video_evidence")
    op.drop_index("ix_coach_feedback_plan", table_name="coach_feedback")
    op.drop_table("coach_feedback")
    op.drop_index("ix_plan_assessment_plan", table_name="plan_assessments")
    op.drop_table("plan_assessments")
    op.drop_index("ix_development_plan_player", table_name="development_plans")
    op.drop_index("ix_development_plan_org", table_name="development_plans")
    op.drop_table("development_plans")
    op.drop_index("ix_academy_curriculum_org", table_name="academy_curricula")
    op.drop_table("academy_curricula")
