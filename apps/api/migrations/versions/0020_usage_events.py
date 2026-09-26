"""§42's Usage: one row per act, so a ceiling is compared against something that cannot drift

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-26 09:20:00.000000

`entitlements` has existed since `0001` — a feature/plan/limit matrix stored as data, with a docstring claiming no
payment vendor is needed. It has also had **no consumer at all** since then: nothing reads it, nothing seeds it,
and no ceiling anywhere in the product is compared against it. §42 asks for the entitlement architecture before any
payment, and its list names five parts: Feature, Plan, Limit, **Usage**, Entitlement. Four of them had a table;
Usage did not.

This migration adds it, and the shape is deliberate:

* **A row per act, not a counter.** `units` is per-row (so an act that consumes more than one unit stays honest),
  and the ceiling is compared against a count taken at read time. A stored total would be a number that goes out
  of date the moment a row is deleted underneath it — the same class of mistake §40 refused for a stored
  `progress` and §41 for a stored report body.
* **The period is part of the row**, not a filter the caller has to remember: `period_key` is `YYYY-MM` for a
  monthly ceiling and `YYYY-MM-DD` for a daily one, which is what makes "yesterday's acts spent today's
  allowance" impossible rather than merely discouraged.
* **`source_id` plus a unique constraint** means the same act cannot spend a ceiling twice. A retried request is
  the common way a meter lies, and it is a constraint problem, not a code-review problem.
* **`subject_kind` separates an account from a tenant.** `organizations` is metered against a user; `sessions`
  against an organization. Counting across the two id namespaces would produce a number that means nothing, and a
  ceiling that appears to work.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.String(length=40), nullable=False),
        sa.Column("subject_kind", sa.String(length=12), nullable=False),
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("recorded_on", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
        sa.UniqueConstraint("subject_id", "feature", "period_key", "source_id", name=op.f("uq_usage_act_once")),
    )
    op.create_index("ix_usage_subject_feature", "usage_events", ["subject_id", "feature", "period_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_subject_feature", table_name="usage_events")
    op.drop_table("usage_events")
