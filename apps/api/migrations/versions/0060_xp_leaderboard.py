"""0060: XP leaderboard opt-in flag (spec §37, gamification).

Adds the opt-in the account's own leaderboard visibility column. Default false:
a new account is not shown on the board until it says so itself.
"""

from alembic import op
import sqlalchemy as sa

revision = "0060_xp_leaderboard"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("leaderboard_visible", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "leaderboard_visible")
