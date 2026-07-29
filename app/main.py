from fastapi import FastAPI

from app.db.health import ping_database

app = FastAPI(title="NutriSpend API")


@app.get("/health")
def health() -> dict:
    return ping_database()
