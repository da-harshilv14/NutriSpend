import time

from fastapi import FastAPI, Request

from app.api import auth, chat, tracking, users
from app.core.observability import log_request, register_db_listeners, start_metrics
from app.db.health import ping_database
from app.db.session import engine

app = FastAPI(title="NutriSpend API")

register_db_listeners(engine)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    metrics = start_metrics()
    started = time.perf_counter()
    response = await call_next(request)
    total_ms = (time.perf_counter() - started) * 1000
    log_request(
        method=request.method, path=request.url.path,
        status=response.status_code, total_ms=total_ms, metrics=metrics,
    )
    response.headers["X-DB-Time-Ms"] = str(round(metrics.db_time_ms, 1))
    response.headers["X-LLM-Calls"] = str(metrics.llm_calls)
    return response


@app.get("/health")
def health() -> dict:
    return ping_database()


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)
app.include_router(tracking.router)
