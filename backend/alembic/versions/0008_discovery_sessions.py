"""Persistent discovery queues, actual exposures and feedback history."""
from alembic import op
import sqlalchemy as sa

revision = '0008_discovery_sessions'
down_revision = '0007_cultural_discovery'
branch_labels = None
depends_on = None


def upgrade():
    owner = lambda: sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE')
    session = lambda: sa.ForeignKey('muselly_cultural_sessions.id', ondelete='CASCADE')
    created = lambda: sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    op.create_table('muselly_cultural_sessions',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), owner(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False), created(),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('muselly_cultural_exposures',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), owner(), nullable=False),
        sa.Column('session_id', sa.Uuid(), session(), nullable=False), sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('entity', sa.JSON(), nullable=False), created(),
        sa.UniqueConstraint('session_id', 'entity_id', name='uq_cultural_exposure_session_entity'))
    op.create_table('muselly_cultural_events',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), owner(), nullable=False),
        sa.Column('session_id', sa.Uuid(), session()), sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False), sa.Column('data', sa.JSON(), nullable=False), created())
    for table in ('muselly_cultural_sessions', 'muselly_cultural_exposures', 'muselly_cultural_events'):
        op.create_index('ix_' + table + '_user_id', table, ['user_id'])
        if op.get_bind().dialect.name == 'postgresql':
            op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON TABLE public.{table} FROM anon, authenticated')


def downgrade():
    for table in ('muselly_cultural_events', 'muselly_cultural_exposures', 'muselly_cultural_sessions'):
        op.drop_table(table)
