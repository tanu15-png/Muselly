"""Customer explanations of cultural fashion inspiration."""
from alembic import op
import sqlalchemy as sa

revision = '0010_fashion_notes'
down_revision = '0009_fashion_references'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('muselly_cultural_feedback', sa.Column('fashion_note', sa.String(500), nullable=False, server_default=''))


def downgrade():
    op.drop_column('muselly_cultural_feedback', 'fashion_note')
