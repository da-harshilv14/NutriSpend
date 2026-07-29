# NutriSpend

Conversational day-wise **expense tracker** that doubles as a **calorie/nutrition
tracker** for Indian food. Talk or type; one agent logs it. See the design spec in
[docs/superpowers/specs](docs/superpowers/specs/).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in DATABASE_URL
```

Get `DATABASE_URL` from Supabase: Dashboard → Project Settings → Database →
Connection string → **Transaction pooler** (port 6543). Change the prefix to
`postgresql+psycopg://`.

## Run (Phase 0 health check)

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/health — it should return
`{"status": "ok", "db_time_ms": <n>}`, confirming the Supabase connection works
and reporting the round-trip latency.
