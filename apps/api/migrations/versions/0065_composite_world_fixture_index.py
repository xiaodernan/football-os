"""0065 — the two world-fixture composite indexes the five recent read-doors ask for.

The Tier-1 world doors all walk the same fixture shape: the league's completed fixtures by
kickoff order (`compute_timeline`, `compute_story`, `compute_gazette`, `compute_noise`,
`compute_finals`), and `compute_finals` is the only door that reads `real_player_match_stats`
as a team-scoped time series for the player-of-the-final walk. SQLite at the seeded world holds
280 completed fixtures, so the measured gain is seconds per call at best — the point is the
PostgreSQL prod path, where the columns are filtered + sorted on every read.

  - `ix_match_competition_status_kickoff` (`competition_id, status, kickoff_at`)
      The exact prefix the five tier-1 doors always use — competition + status + sorted by kickoff.
  - `ix_stat_team_match` (`team_id, match_id`)
      The team-scoped iteration pattern the matchday hero & the player-of-the-final walks take.

No other table is touched. Downgrade drops both indexes.
"""

from __future__ import annotations

from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_match_competition_status_kickoff",
        "real_matches",
        ["competition_id", "status", "kickoff_at"],
    )
    op.create_index(
        "ix_stat_team_match",
        "real_player_match_stats",
        ["team_id", "match_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stat_team_match", table_name="real_player_match_stats")
    op.drop_index("ix_match_competition_status_kickoff", table_name="real_matches")
