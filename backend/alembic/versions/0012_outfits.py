"""Private generated outfit images and durable quotas."""
from alembic import op
import sqlalchemy as sa
revision = '0012_outfits'
down_revision = '0011_shopping_agent'
branch_labels = depends_on = None

def upgrade():
    op.create_table('muselly_outfit_limits', sa.Column('user_id', sa.String(36), primary_key=True),
                    sa.Column('day', sa.String(10), nullable=False), sa.Column('daily', sa.Integer(), nullable=False),
                    sa.Column('total', sa.Integer(), nullable=False))
    op.create_table('muselly_outfits', sa.Column('id', sa.String(36), primary_key=True),
                    sa.Column('user_id', sa.String(36), nullable=False, index=True),
                    sa.Column('payload', sa.Text(), nullable=False), sa.Column('created_at', sa.String(40), nullable=False))
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('muselly_outfits', 'muselly_outfit_limits'):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')

def downgrade():
    op.drop_table('muselly_outfits')
    op.drop_table('muselly_outfit_limits')
