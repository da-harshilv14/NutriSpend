from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401 — imported so tables register on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # Build the engine from our settings (not alembic.ini) so the URL and the
    # pgBouncer-safe connect args stay in one place. NullPool: migrations are a
    # one-shot process, no need to keep connections.
    engine = create_engine(
        get_settings().database_url,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; run with a live DATABASE_URL.")
else:
    run_migrations_online()
