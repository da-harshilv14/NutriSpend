from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# This is a long-running server, so we keep a warm connection pool: reusing
# connections avoids paying the ~600ms TLS+auth handshake to Supabase on every
# request (measured — a fresh connect dominates; a warm query is ~20ms).
# pool_pre_ping guards against connections the pooler dropped while idle.
# prepared statements stay off — Supabase's transaction pooler (pgBouncer,
# port 6543) rejects them.
engine = create_engine(
    _settings.database_url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
