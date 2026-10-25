"""Private recommendation corrections."""
from alembic import op
import sqlalchemy as sa

revision = '0006_product_feedback'
down_revision = '0005_extension_saved'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_product_feedback',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_user_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('product', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'url', name='uq_product_feedback_owner_url'))
    op.create_index('ix_muselly_product_feedback_user_id', 'muselly_product_feedback', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.muselly_product_feedback ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public.muselly_product_feedback FROM anon, authenticated')


def downgrade():
    op.drop_table('muselly_product_feedback')
