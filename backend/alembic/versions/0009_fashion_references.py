"""Customer-confirmed cultural-to-fashion reference connections."""
from alembic import op
import sqlalchemy as sa

revision = '0009_fashion_references'
down_revision = '0008_discovery_sessions'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('muselly_cultural_feedback', sa.Column('reference_image_ids', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    op.drop_column('muselly_cultural_feedback', 'reference_image_ids')
