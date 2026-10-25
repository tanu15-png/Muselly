"""Private product bookmarks saved by the browser extension."""
from alembic import op
import sqlalchemy as sa

revision = '0005_extension_saved'
down_revision = '0004_qloo_enrichment'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_saved_products',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_user_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('image', sa.String(2048), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'url', name='uq_saved_product_owner_url'))
    op.create_index('ix_muselly_saved_products_user_id', 'muselly_saved_products', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.muselly_saved_products ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public.muselly_saved_products FROM anon, authenticated')


def downgrade():
    op.drop_index('ix_muselly_saved_products_user_id', table_name='muselly_saved_products')
    op.drop_table('muselly_saved_products')
