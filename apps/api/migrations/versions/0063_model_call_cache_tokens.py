"""The provider ledger learns what the gateway cached (M12, spec §46/§59)

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-13 12:30:00

`model_calls` recorded what a call cost and what it produced, but nothing about
**prefix caching** — the one lever the operator can actually move on a real provider bill, and
the figure the dashboard prints as the cache-hit rate. `cached_input_tokens` is the number the
provider reported (zero when it reports none, never invented), so
`sum(cached_input_tokens) / sum(input_tokens)` is the measurable hit rate from here on.

Nullable-safe: existing rows read zero, which is indistinguishable from "the gateway did not
report it" — and true of every call recorded before this column existed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_calls",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("model_calls", "cached_input_tokens")
