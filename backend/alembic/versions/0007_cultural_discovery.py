"""Private cultural discovery and explicit preferences."""
from alembic import op
import sqlalchemy as sa

revision = '0007_cultural_discovery'
down_revision = '0006_product_feedback'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_cultural_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result', sa.JSON()), sa.Column('error', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_muselly_cultural_runs_user_id', 'muselly_cultural_runs', ['user_id'])
    op.create_table('muselly_cultural_feedback',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_id', sa.Uuid(), primary_key=True),
        sa.Column('entity', sa.JSON(), nullable=False),
        sa.Column('preference', sa.String(20)),
        sa.Column('fashion_inspiration', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    if op.get_bind().dialect.name == 'postgresql':
        for name in ('muselly_cultural_runs', 'muselly_cultural_feedback'):
            op.execute(f'ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON TABLE public.{name} FROM anon, authenticated')


def downgrade():
    op.drop_table('muselly_cultural_feedback')
    op.drop_table('muselly_cultural_runs')
