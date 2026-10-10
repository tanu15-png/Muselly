"""Create application user and taste profiles; Supabase manages authentication."""
from alembic import op
import sqlalchemy as sa

revision = "0001_profiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "muselly_user_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "muselly_taste_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("muselly_user_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("selected_styles", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    if op.get_bind().dialect.name == "postgresql":
        # Browser clients only use Auth. Application tables are accessed through
        # the Python API using a private database connection, never the Data API.
        for table in ("muselly_user_profiles", "muselly_taste_profiles"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"REVOKE ALL ON TABLE public.{table} FROM anon, authenticated")


def downgrade():
    op.drop_table("muselly_taste_profiles")
    op.drop_table("muselly_user_profiles")
