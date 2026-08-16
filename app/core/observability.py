import contextvars
import json
import logging
import time
from dataclasses import dataclass

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("nutrispend.request")


@dataclass
class RequestMetrics:
    db_time_ms: float = 0.0
    db_queries: int = 0
    llm_calls: int = 0


_metrics: contextvars.ContextVar[RequestMetrics | None] = contextvars.ContextVar(
    "request_metrics", default=None
)


def start_metrics() -> RequestMetrics:
    metrics = RequestMetrics()
    _metrics.set(metrics)
    return metrics


def record_llm_call() -> None:
    metrics = _metrics.get()
    if metrics is not None:
        metrics.llm_calls += 1


def register_db_listeners(engine: Engine) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        context._query_started = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        metrics = _metrics.get()
        if metrics is not None:
            started = getattr(context, "_query_started", None)
            if started is not None:
                metrics.db_time_ms += (time.perf_counter() - started) * 1000
                metrics.db_queries += 1


def log_request(*, method: str, path: str, status: int, total_ms: float, metrics: RequestMetrics) -> None:
    logger.info(json.dumps({
        "method": method,
        "path": path,
        "status": status,
        "total_ms": round(total_ms, 1),
        "db_ms": round(metrics.db_time_ms, 1),
        "db_queries": metrics.db_queries,
        "llm_calls": metrics.llm_calls,
    }))
