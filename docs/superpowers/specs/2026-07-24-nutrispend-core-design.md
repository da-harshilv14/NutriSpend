# NutriSpend — Core (Cycle 1) Design Spec

**Date:** 2026-07-24
**Status:** Approved for planning
**Scope:** Cycle 1 only — the "brain": agent + tools + data + DB + auth + REST APIs, testable via text. Voice, Android, FastMCP, and multi-provider LLMs are deferred to later cycles.

---

## 1. What NutriSpend is

A conversational assistant that takes plain-language input (text now; voice later) and acts as:

1. A **general chatbot** (conversation + web search), and
2. Primarily, a **day-wise expense tracker** that doubles as a **calorie/nutrition tracker** when the expense is food or the user made/ate food.

The user talks or types; a single agent decides what to do and logs it, scoped per user, stored day-wise in a remote Postgres (Supabase) database.

## 2. Full project map (context, not all built now)

| # | Cycle | What it is | Status |
|---|-------|-----------|--------|
| **1** | **Core brain + data + DB + APIs** | Agent, tools, DB, auth, nutrition dataset — testable via text | **This spec** |
| 2 | FastMCP server | Wrap Cycle-1 tools as remote MCP tools | later |
| 3 | Voice layer | STT / TTS + wake + HITL | later |
| 4 | Android app | Chat + voice UI | later |
| 5 | General chat / web search polish | Richer conversation | partly in #1 |
| 6 | Multi-provider LLM | OpenAI/Gemini beyond Claude | later |

Each later cycle is its own design → plan → build.

## 3. Design principles

- **SOLID + explicit design patterns** so new sites/tasks/sources/tools are *additions, never modifications* to core classes.
- **Dependency Injection everywhere** — collaborators passed into `__init__`, never instantiated inside the class that uses them. This is what makes the agent testable without a real DB or LLM.
- **Narrow interfaces** (ISP) — each abstraction exposes only what its consumers need.
- **Speed is architectural** — minimize LLM round-trips (one call per message) and DB round-trips (no N+1); measure both from day one.
- **Improves over time** — the nutrition table is a growing cache: foods resolved via API/web-search are written back, so repeat lookups become instant and dataset-backed.

## 4. Architecture: patterns → SOLID payoff

| Concern | Pattern | Payoff |
|---|---|---|
| Nutrition lookup ladder (exact → fuzzy → api → websearch) | **Chain of Responsibility** — each step is a link; add/reorder without touching others | OCP: new source = new link |
| DB access | **Repository** — `UserRepo`, `FoodLogRepo`, `ExpenseRepo`, `NutritionRepo` behind interfaces | DIP: services depend on repo interface, not Supabase |
| LLM provider | **Adapter** — `ClaudeAdapter` now behind one `LLMClient` interface | OCP/LSP: swap provider later, no core change |
| Nutrition sources | **Adapter** behind `NutritionSource` interface (`lookup(name) -> Nutrition | None`) | new API = new adapter, registered |
| Agent tools | **Registry + Command** — tools self-register; agent invokes uniformly | OCP: new tool without editing the agent |
| Wiring | **Dependency Injection** (constructor injection) | testable without real DB/LLM |

## 5. Agent: single-call tool routing

One Claude call per user message. Claude is given the tool schemas and decides itself whether to reply conversationally or call a tool. Fewest round-trips = fastest, most robust, and maps directly onto the MCP-tool model for Cycle 2.

**Tools Claude can call:**
- `log_expense(amount, category, description, date?)`
- `log_food(food_name, portion_text, date?)`
- `lookup_nutrition(food_name)`
- `query_summary(kind, period)` — `kind` = spend | calories; `period` = today | week
- `web_search(query)`

Tools and REST endpoints share the **same service layer** (`ExpenseService`, `FoodService`, `NutritionService`) — no duplicated logic. `/chat` is the conversational path; REST endpoints are the direct/programmatic path; both call the same services.

## 6. Data model (Supabase Postgres)

**`users`**
```
id · username · email · password_hash · api_key (nullable) · created_at
```

**`nutrition_reference`** — seeded from the Kaggle Indian-food dataset; values are **per 100g**
```
id
name              -- original, e.g. "Dal Tadka"
name_normalized   -- lowercased/trimmed          ← INDEXED (+ pg_trgm GIN for fuzzy)
calories_per_100g · protein_per_100g · carbs_per_100g · fats_per_100g · sugar_per_100g
serving_size · serving_unit         -- if dataset provides
source            -- 'dataset' | 'api' | 'websearch' | 'user'
created_at
```

**`food_log`** — day-wise intake per user
```
id · user_id · log_date · nutrition_id (FK)
quantity_grams          -- resolved to grams
portion_text            -- what the user said, e.g. "2 bowls" (HITL / transparency)
calories · protein · carbs · fats · sugar   -- computed SNAPSHOT for this entry
created_at
```

**`expense_log`** — day-wise spend per user
```
id · user_id · log_date · amount · category · description
food_log_id (nullable FK)   -- links a food purchase to its calorie entry
created_at
```

**Tracked nutrients (only these 5):** calories, protein, carbs, fats, sugar.

**Snapshotting rationale:** `food_log` stores computed nutrition, not just an FK, so later corrections to `nutrition_reference` never silently change historical logs.

## 7. Nutrition lookup ladder (the speed core)

Chain of Responsibility, cheapest first; stops at first hit:

1. **Exact match** on `name_normalized` (indexed) → microseconds. Most common.
2. **Fuzzy match** — `pg_trgm` trigram index handles variants ("dal"/"daal"/"yellow dal"). Local, fast.
3. **API → web-search fallback** — only if 1 and 2 miss. Slow, rare.
4. **Cache-back** — result from step 3 is inserted into `nutrition_reference` tagged `source='api'/'websearch'`. Next lookup is step-1 instant.

The last two links are pluggable `NutritionSource` adapters. When a real nutrition API is chosen, it slots in as one new adapter — zero core changes (OCP).

**Reliability note:** the API/web-search path is the only fragile external dependency. It is **best-effort enrichment with HITL**, never blocking — on failure, ask the user or store "pending", never crash the log. (This is why NutriSpend will not break the way a live-website scraper does: its core loop depends only on our DB + the Claude API + our owned dataset.)

## 8. Portion handling

Dataset is per-100g; users speak in servings. Bridge = a small **portion map** (constant for now, YAGNI):

```
bowl / katori ≈ 150g · plate ≈ 300g · glass ≈ 250g
piece ≈ 50g · roti ≈ 40g · serving ≈ 100g · tbsp ≈ 15g
```

Flow: "2 bowls of dal" → 2 × 150 = 300g → `calories = calories_per_100g × 300/100`. Direct grams ("200g rice") skip the map. `portion_text` is retained so HITL can show and let the user correct the estimate. Estimates are surfaced as estimates, never fake-precise.

## 9. HITL — confirm only when uncertain

- Write immediately when confident (food in dataset, clear amount).
- Confirm first **only** when: value came from web-search, portion vague, or amount ambiguous.
- Confirmation shows the estimate transparently: *"2 bowls dal ≈ 300g, 450 kcal — correct?"*

## 10. REST API surface

```
POST /auth/signup        POST /auth/login
GET  /me                 PATCH /me            # set api_key, profile
POST /chat               # agent entrypoint (routing lives here)
POST /expenses           GET /expenses?date=&period=
POST /food               GET /food?date=&period=
GET  /nutrition/lookup?name=
GET  /summary?kind=spend|calories&period=today|week
```

## 11. Auth

Custom JWT auth; Supabase is **pure Postgres** (no Supabase Auth). We own `users`, password hashing (bcrypt/argon2), and JWT issuance/verification. `api_key` is a nullable column set later via `PATCH /me`. Claude-only for now; provider-agnostic later via the `LLMClient` adapter.

## 12. Tech stack

- **Backend:** FastAPI + SQLAlchemy + Alembic (migrations)
- **DB:** Supabase Postgres from day one; `pg_trgm` enabled; connect via the **connection pooler** (pgBouncer) to avoid cold-connection latency
- **LLM:** Anthropic Claude via official SDK, behind one `LLMClient` wrapper
- **Observability:** structured JSON run log per request, including **per-request DB time** and LLM round-trip count — this is how we answer "will it be slow when deployed?"
- **Testing:** services and repos are DI'd, so the agent is tested against mock `LLMClient` and in-memory/fake repos; integration tests hit a Supabase test schema

## 13. Explicitly out of scope for Cycle 1

Voice, Android UI, FastMCP wrapping, multi-provider LLMs, checkout/purchase, budgets/goals/alerts, charts/reports, multi-currency.

## 14. Open items to resolve during planning

- Exact Kaggle dataset columns & units (verified during EDA) → confirms `serving_size`/`serving_unit` availability and whether values are truly per-100g.
- Specific nutrition API (user to research) → determines the `ApiNutritionSource` adapter contract.
- Timezone for "day-wise" boundaries (default IST, user is in India).
