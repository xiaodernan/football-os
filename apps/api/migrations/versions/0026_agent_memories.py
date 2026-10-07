"""0026 agent memories

Agent memory storage for M11 multi-agent system. Each row persists a named fact or
context fragment for a specific user and agent type, with optional TTL-based expiration.

**Corrected 2026-10-07, and it needed three separate repairs.**

1. `down_revision` was `'0025'`, which is also `2e197f085070`'s parent. Two children of one parent is two heads,
   and `alembic upgrade head` refuses to run at all: *"Multiple head revisions are present for given argument
   'head'"*. That is not a warning — it is every fresh database, every `scripts/check.sh` run and every deploy
   failing at the first step, and it stayed invisible to anything that built its schema from the models instead
   of from the migrations, which is what `python -m seed` does. This revision now follows `2e197f085070`.
2. It could not run on SQLite. `sa.Index(...)` passed inside `create_table` is not a table constraint; it renders
   as `near "(": syntax error`, and `server_default=sa.text('now()')` is not a function SQLite has. Indexes go
   through `op.create_index` and timestamps through the mixin's Python-side default, as every other migration in
   this directory does.
3. **It did not describe the model.** The table here was `id INTEGER` / `user_id INTEGER` with no `updated_at`,
   while `AgentMemory` declares `id String(40)`, `user_id String` foreign-keyed to `users.id`, and inherits
   `created_at` *and* `updated_at` from `TimestampMixin`. A migration that disagrees with the model is worse than
   a missing one: it builds a database the application cannot use, and only `alembic check` can see the
   disagreement — which never ran, because `upgrade head` never finished.
"""

from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '2e197f085070'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_memories',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('user_id', sa.String(length=40), nullable=False),
        sa.Column('agent_type', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=128), nullable=True),
        sa.Column('key', sa.String(length=256), nullable=False),
        sa.Column('value_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_memories_user_agent', 'agent_memories', ['user_id', 'agent_type'])
    op.create_index('ix_agent_memories_expires', 'agent_memories', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_agent_memories_expires', table_name='agent_memories')
    op.drop_index('ix_agent_memories_user_agent', table_name='agent_memories')
    op.drop_table('agent_memories')
