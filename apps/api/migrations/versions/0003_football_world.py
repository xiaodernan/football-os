"""football world: competitions, teams, real players, matches, stat lines, news (spec §4, §7, §25, §65)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22 06:00:00.000000

Migration 0001 created `competitions`, `teams`, `real_players` and `news_articles` as the bare
identity columns M3 was expected to grow into. M3 grows them a lot — provenance, content hashes,
season/stat fields, indexes for every browse path — and both PostgreSQL and SQLite refuse a
NOT NULL column without a default on an existing table, so this revision **drops and recreates**
those four rather than stacking `alter_column` defaults that the models do not declare (which is
how `alembic check` drift starts). Dropping is safe by construction: the tables are empty on every
database that has not run M3, `sync_world` is the only writer, and the throwaway test databases are
rebuilt by `Base.metadata.drop_all` anyway. A deployment that has data in them is a deployment
running an unreleased milestone.

The three new tables (`real_matches`, `real_player_match_stats`, `news_article_links`) are created
normally. `news_article_links` exists because JSON containment queries differ per dialect; a typed
edge table filters "news about this club" portably and satisfies the spec §4 rule that entities must
be *related*, not merely mentioned.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_RESERVED = (
    "real_player_match_stats",
    "news_article_links",
    "real_matches",
    "news_articles",
    "real_players",
    "teams",
    "competitions",
)


def upgrade() -> None:
    # Child-first, and `cascade` only where the dialect understands it (SQLite does not).
    suffix = " cascade" if op.get_bind().dialect.name == "postgresql" else ""
    for table in _RESERVED:
        op.execute(f"drop table if exists {table}{suffix}")

    op.create_table(
        "competitions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_competition_kind", "competitions", ["kind"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("competition_id", sa.String(length=40), nullable=True),
        sa.Column("logo_ref", sa.String(length=200), nullable=True),
        sa.Column("short_name", sa.String(length=24), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("stadium", sa.String(length=120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("manager_name", sa.String(length=120), nullable=False),
        sa.Column("formation", sa.String(length=8), nullable=False),
        sa.Column("brand_color", sa.String(length=9), nullable=False),
        sa.Column("nation", sa.String(length=60), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("squad_size", sa.Integer(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_team_competition", "teams", ["competition_id"], unique=False)

    op.create_table(
        "real_players",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("secondary_positions", sa.JSON(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("preferred_foot", sa.String(length=8), nullable=False),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("nation", sa.String(length=60), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("derivation_reasons", sa.JSON(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("potential", sa.Integer(), nullable=False),
        sa.Column("archetype", sa.String(length=60), nullable=False),
        sa.Column("archetype_match", sa.Float(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("appearances", sa.Integer(), nullable=False),
        sa.Column("starts", sa.Integer(), nullable=False),
        sa.Column("goals", sa.Integer(), nullable=False),
        sa.Column("assists", sa.Integer(), nullable=False),
        sa.Column("clean_sheets", sa.Integer(), nullable=False),
        sa.Column("yellow_cards", sa.Integer(), nullable=False),
        sa.Column("red_cards", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("form", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_real_player_team", "real_players", ["team_id"], unique=False)
    op.create_index("ix_real_player_position_overall", "real_players", ["position", "overall"], unique=False)

    op.create_table(
        "real_matches",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("competition_id", sa.String(length=40), nullable=True),
        sa.Column("home_team_id", sa.String(length=40), nullable=False),
        sa.Column("away_team_id", sa.String(length=40), nullable=False),
        sa.Column("round_label", sa.String(length=40), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue_name", sa.String(length=120), nullable=False),
        sa.Column("venue_city", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("haystack", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_match_competition_season", "real_matches", ["competition_id", "season"], unique=False)
    op.create_index("ix_match_kickoff", "real_matches", ["kickoff_at"], unique=False)
    op.create_index("ix_match_home_team", "real_matches", ["home_team_id"], unique=False)
    op.create_index("ix_match_away_team", "real_matches", ["away_team_id"], unique=False)

    op.create_table(
        "real_player_match_stats",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("natural_key", sa.String(length=200), nullable=False),
        sa.Column("match_id", sa.String(length=40), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("minute_rank", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("goals", sa.Integer(), nullable=False),
        sa.Column("assists", sa.Integer(), nullable=False),
        sa.Column("shots", sa.Integer(), nullable=False),
        sa.Column("shots_on_target", sa.Integer(), nullable=False),
        sa.Column("passes", sa.Integer(), nullable=False),
        sa.Column("passes_accurate", sa.Integer(), nullable=False),
        sa.Column("key_passes", sa.Integer(), nullable=False),
        sa.Column("tackles", sa.Integer(), nullable=False),
        sa.Column("interceptions", sa.Integer(), nullable=False),
        sa.Column("duels_won", sa.Integer(), nullable=False),
        sa.Column("saves", sa.Integer(), nullable=False),
        sa.Column("fouls", sa.Integer(), nullable=False),
        sa.Column("yellow_cards", sa.Integer(), nullable=False),
        sa.Column("red_cards", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["real_matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "player_id", name="uq_match_stat_line"),
        sa.UniqueConstraint("natural_key", name="uq_match_stat_natural_key"),
    )
    op.create_index("ix_stat_line_player", "real_player_match_stats", ["player_id"], unique=False)
    op.create_index("ix_stat_line_match", "real_player_match_stats", ["match_id"], unique=False)

    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("claim_class", sa.String(length=16), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("haystack", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_news_category_published", "news_articles", ["category", "published_at"], unique=False)

    op.create_table(
        "news_article_links",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("article_id", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_slug", sa.String(length=200), nullable=False),
        sa.Column("entity_id", sa.String(length=40), nullable=True),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "entity_type", "entity_slug", name="uq_news_article_link"),
    )
    op.create_index("ix_news_link_entity", "news_article_links", ["entity_type", "entity_slug"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_link_entity", table_name="news_article_links")
    op.drop_table("news_article_links")
    op.drop_index("ix_news_category_published", table_name="news_articles")
    op.drop_table("news_articles")
    op.drop_index("ix_stat_line_match", table_name="real_player_match_stats")
    op.drop_index("ix_stat_line_player", table_name="real_player_match_stats")
    op.drop_table("real_player_match_stats")
    for index in ("ix_match_away_team", "ix_match_home_team", "ix_match_kickoff", "ix_match_competition_season"):
        op.drop_index(index, table_name="real_matches")
    op.drop_table("real_matches")
    op.drop_index("ix_real_player_position_overall", table_name="real_players")
    op.drop_index("ix_real_player_team", table_name="real_players")
    op.drop_table("real_players")
    op.drop_index("ix_team_competition", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_competition_kind", table_name="competitions")
    op.drop_table("competitions")

    # Back to exactly what migration 0001 created: the M3-reserved identity shells.
    op.create_table(
        "competitions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("competition_id", sa.String(length=40), nullable=True),
        sa.Column("logo_ref", sa.String(length=200), nullable=True),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "real_players",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("derivation_reasons", sa.JSON(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("archetype", sa.String(length=60), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
