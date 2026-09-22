"""video assets and detections: uploaded clips and what the vision provider measured (spec §14, §47, §62)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22 12:00:00.000000

Two new tables. `video_assets` holds the container facts ffprobe reported (not the file itself —
bytes live on the storage provider's disk, keyed by `storage_key`), and `video_detections` holds one
row per measured event, each carrying the provider, model and `demo_mode` that produced it, so a
report cannot present pixel statistics as football analysis. Deleting an asset cascades its
detections; deleting a job leaves the detections and nulls their `job_id`, because the measurement
was made and should not disappear with the bookkeeping row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_assets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("filename", sa.String(length=240), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("content_type", sa.String(length=60), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("codec", sa.String(length=30), nullable=False),
        sa.Column("bitrate_kbps", sa.Float(), nullable=False),
        sa.Column("frame_count", sa.Integer(), nullable=False),
        sa.Column("frame_interval_s", sa.Float(), nullable=False),
        sa.Column("media", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_video_assets_owner_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video_assets")),
    )
    op.create_index("ix_video_assets_sha256", "video_assets", ["sha256"], unique=False)
    op.create_index("ix_video_owner_created", "video_assets", ["owner_id", "created_at"], unique=False)
    op.create_index("ix_video_status", "video_assets", ["status"], unique=False)

    op.create_table(
        "video_detections",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("asset_id", sa.String(length=40), nullable=False),
        sa.Column("job_id", sa.String(length=40), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("t_s", sa.Float(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("demo_mode", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["video_assets.id"], name=op.f("fk_video_detections_asset_id_video_assets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_video_detections_job_id_jobs"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video_detections")),
    )
    op.create_index("ix_detection_asset_time", "video_detections", ["asset_id", "t_s"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_detection_asset_time", table_name="video_detections")
    op.drop_table("video_detections")
    op.drop_index("ix_video_status", table_name="video_assets")
    op.drop_index("ix_video_owner_created", table_name="video_assets")
    op.drop_index("ix_video_assets_sha256", table_name="video_assets")
    op.drop_table("video_assets")
