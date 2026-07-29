import time

from sqlalchemy import text

from app.db.session import engine


def ping_database() -> dict:
    started = time.perf_counter()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return {"status": "ok", "db_time_ms": elapsed_ms}
