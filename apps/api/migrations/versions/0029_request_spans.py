"""The span store's table (M12 observability)

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-21 10:00:00

OpenTelemetry was wired with an OTLP exporter, so a span went wherever a collector was
listening and nowhere at all on a host that runs none. The verification document recorded that
as the one observability claim it could not make: "no span has reached a real backend".

This table is that backend. The exporter writes each finished span here - the trace's own
identifiers, the parent link, the span's own timings and its attributes - and a door reads a
request's spans back by trace id.

The table is not a copy of anything the API stores about a request: it holds the *shape* of
the work (which spans ran, how long each took), not the request's answer. The indexes are the
two questions the door asks: "every span of this trace" and "what is still inside the
retention window".
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_spans",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("span_id", sa.String(length=16), nullable=False),
        sa.Column("parent_span_id", sa.String(length=16), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="unset"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_request_spans_trace", "request_spans", ["trace_id"])
    op.create_index("ix_request_spans_start", "request_spans", ["start_time"])


def downgrade() -> None:
    op.drop_index("ix_request_spans_start", table_name="request_spans")
    op.drop_index("ix_request_spans_trace", table_name="request_spans")
    op.drop_table("request_spans")
