"""0026 agent memories

Agent memory storage for M11 multi-agent system. Each row persists a named fact or
context fragment for a specific user and agent type, with optional TTL-based expiration.
"""

from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_memories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agent_type', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=128), nullable=True),
        sa.Column('key', sa.String(length=256), nullable=False),
        sa.Column('value_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_agent_memories_user_agent', 'user_id', 'agent_type'),
        sa.Index('ix_agent_memories_expires', 'expires_at'),
    )


def downgrade() -> None:
    op.drop_table('agent_memories')
