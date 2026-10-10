"""Persistent questionnaire drafts and private inspiration metadata."""
from alembic import op
import sqlalchemy as sa

revision = '0002_taste_test'
down_revision = '0001_profiles'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('muselly_taste_tests',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_user_profiles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('muselly_inspiration_images',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('storage_path', sa.String(300), unique=True, nullable=False),
        sa.Column('filename', sa.String(200), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_muselly_inspiration_images_user_id', 'muselly_inspiration_images', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('muselly_taste_tests', 'muselly_inspiration_images'):
            op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON TABLE public.{table} FROM anon, authenticated')
        # No browser policies: only the backend service-role key accesses files.
        op.execute("""DO $$ BEGIN
            IF to_regclass('storage.buckets') IS NOT NULL THEN
                INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
                VALUES ('muselly-inspirations', 'muselly-inspirations', false, 10485760,
                    ARRAY['image/jpeg','image/png','image/webp'])
                ON CONFLICT (id) DO UPDATE SET public = false, file_size_limit = 10485760,
                    allowed_mime_types = EXCLUDED.allowed_mime_types;
            END IF;
        END $$;""")


def downgrade():
    # Storage objects are intentionally preserved; delete via Storage API, not SQL.
    op.drop_index('ix_muselly_inspiration_images_user_id', table_name='muselly_inspiration_images')
    op.drop_table('muselly_inspiration_images')
    op.drop_table('muselly_taste_tests')
