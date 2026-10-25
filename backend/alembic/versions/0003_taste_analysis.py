"""Private, versioned Gemini analysis results and input provenance."""
from alembic import op
import sqlalchemy as sa

revision = '0003_taste_analysis'
down_revision = '0002_taste_test'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_taste_analysis_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result', sa.JSON()),
        sa.Column('error', sa.String(500)),
        sa.Column('usage', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_muselly_taste_analysis_runs_user_id', 'muselly_taste_analysis_runs', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.muselly_taste_analysis_runs ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public.muselly_taste_analysis_runs FROM anon, authenticated')


def downgrade():
    op.drop_index('ix_muselly_taste_analysis_runs_user_id', table_name='muselly_taste_analysis_runs')
    op.drop_table('muselly_taste_analysis_runs')
