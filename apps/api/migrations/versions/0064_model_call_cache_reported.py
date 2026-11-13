"""The ledger learns the difference between a zero and a silence (M17, cache arc)

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-13 23:40:00

0063 added `cached_input_tokens`, and the rate it feeds was computed as
`sum(cached) / sum(input)` over every row. That arithmetic is only correct when the gateway always
prints a cache figure, and on the gateway this project runs against it does not: measured across six
cells on 2026-11-13, four calls printed `prompt_tokens_details.cached_tokens` and two printed no
details object at all. A silent call contributes its full input to the denominator and nothing to
the numerator, so a deployment whose warm calls hit **97.3 %** reported roughly **50 %** — the
cache was working and the meter said it was half broken.

`cache_reported` is the missing bit: true when the provider's usage object carried a cache field,
false when it said nothing. Rows written before this column existed read false, which is exactly
what they are — no earlier call can prove the gateway reported a figure.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_calls",
        sa.Column("cache_reported", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("model_calls", "cache_reported")
