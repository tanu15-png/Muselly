"""Private Qloo enrichment runs and persistent affinity dismissals."""
from alembic import op
import sqlalchemy as sa

revision = '0004_qloo_enrichment'
down_revision = '0003_taste_analysis'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_taste_enrichment_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('resolver_version', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result', sa.JSON()),
        sa.Column('error', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_muselly_taste_enrichment_runs_user_id', 'muselly_taste_enrichment_runs', ['user_id'])
    op.create_table('muselly_taste_affinity_dismissals',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('muselly_taste_enrichment_runs', 'muselly_taste_affinity_dismissals'):
            op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON TABLE public.{table} FROM anon, authenticated')


def downgrade():
    op.drop_table('muselly_taste_affinity_dismissals')
    op.drop_index('ix_muselly_taste_enrichment_runs_user_id', table_name='muselly_taste_enrichment_runs')
    op.drop_table('muselly_taste_enrichment_runs')
