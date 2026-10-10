from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.models import Base

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata
url = get_settings().database_url
if not url:
    raise RuntimeError("Set DATABASE_URL in backend/.env before running migrations.")


def include_object(obj, name, type_, reflected, compare_to):
    # Never generate changes to Supabase-managed or unrelated public tables.
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, include_object=include_object, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"prepare_threshold": None} if url.startswith("postgresql+psycopg:") else {})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
