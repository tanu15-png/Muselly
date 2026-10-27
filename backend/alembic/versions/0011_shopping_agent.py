"""Owner-scoped, bounded shopping conversations."""
from alembic import op
import sqlalchemy as sa

revision = '0011_shopping_agent'
down_revision = '0010_fashion_notes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_shopping_agent_sessions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_muselly_shopping_agent_sessions_user_id', 'muselly_shopping_agent_sessions', ['user_id'])


def downgrade():
    op.drop_table('muselly_shopping_agent_sessions')
