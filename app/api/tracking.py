from collections import defaultdict
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import Services, get_current_user, get_services
from app.api.schemas import ExpenseCreate, FoodCreate
from app.core.dates import resolve_period, today
from app.db.models import User
from app.nutrition.lookup import needs_confirmation

router = APIRouter(tags=["tracking"])

IST = ZoneInfo("Asia/Kolkata")


def _period(period: str) -> tuple:
    try:
        return resolve_period(period)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "period must be 'today' or 'week'")


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(
    body: ExpenseCreate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    entry = services.expense.log_expense(
        user_id=user.id, amount=body.amount, category=body.category, description=body.description
    )
    return {"id": entry.id, "amount": float(entry.amount), "category": entry.category,
            "description": entry.description, "log_date": str(entry.log_date)}


@router.get("/expenses")
def list_expenses(
    period: str = Query("today"),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    start, end = _period(period)
    entries = services.expense.list_for_period(user_id=user.id, start=start, end=end)
    return {"period": period, "expenses": [
        {"id": e.id, "amount": float(e.amount), "category": e.category,
         "description": e.description, "log_date": str(e.log_date)} for e in entries
    ]}


@router.post("/food")
def create_food(
    body: FoodCreate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    if body.nutrition_id is not None:
        entry = services.food.log_food(
            user_id=user.id, nutrition_id=body.nutrition_id, portion_text=body.portion_text
        )
        return _food_entry(entry)

    if not body.food_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "food_name or nutrition_id is required")

    preview = services.food.preview_food(food_name=body.food_name, portion_text=body.portion_text)
    if needs_confirmation(preview.lookup):
        return {
            "status": "needs_confirmation",
            "portion_grams": preview.portion.grams,
            "estimated_for_portion": preview.snapshot,
            "candidates": [
                {"nutrition_id": c.reference.id, "name": c.reference.name,
                 "source": c.reference.source, "score": round(c.score, 2)}
                for c in preview.lookup.candidates[:5]
            ],
        }
    best = preview.lookup.best
    entry = services.food.log_food(
        user_id=user.id, nutrition_id=best.reference.id, portion_text=body.portion_text
    )
    return _food_entry(entry, name=best.reference.name)


@router.get("/food")
def list_food(
    period: str = Query("today"),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    start, end = _period(period)
    entries = services.food.list_for_period(user_id=user.id, start=start, end=end)
    return {"period": period, "food": [_food_entry(e) for e in entries]}


@router.get("/summary")
def summary(
    kind: str = Query(..., pattern="^(spend|calories)$"),
    period: str = Query("today"),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    start, end = _period(period)
    if kind == "calories":
        return services.food.summary(user_id=user.id, start=start, end=end)
    return services.expense.summary(user_id=user.id, start=start, end=end)


@router.get("/summary/hourly")
def hourly_spend(
    period: str = Query("today"),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Spend bucketed by hour-of-day (0–23), so the Today screen can show when
    money goes out. created_at is UTC; buckets are in IST since this is an
    India-facing app."""
    start, end = _period(period)
    buckets = [0.0] * 24
    for expense in services.expense.list_for_period(user_id=user.id, start=start, end=end):
        created = expense.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        buckets[created.astimezone(IST).hour] += float(expense.amount)
    return {"period": period, "hours": [
        {"hour": hour, "total": round(buckets[hour], 2)} for hour in range(24)
    ]}


@router.get("/history")
def history(
    days: int = Query(7, ge=1, le=31),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    end = today()
    start = end - timedelta(days=days - 1)
    per_day: dict[str, dict] = defaultdict(
        lambda: {"total_spend": 0.0, "total_calories": 0.0, "entries": []}
    )

    for expense in services.expense.list_for_period(user_id=user.id, start=start, end=end):
        day = str(expense.log_date)
        per_day[day]["total_spend"] += float(expense.amount)
        per_day[day]["entries"].append({
            "type": "expense",
            "time": expense.created_at.isoformat(),
            "title": expense.description or (expense.category or "Expense"),
            "category": expense.category,
            "amount": float(expense.amount),
            "calories": None,
            "is_estimate": False,
            "_food_log_id": expense.food_log_id,
            "_id": None,
        })

    for entry, name in services.food.list_with_names(user_id=user.id, start=start, end=end):
        day = str(entry.log_date)
        if entry.calories:
            per_day[day]["total_calories"] += entry.calories
        per_day[day]["entries"].append({
            "type": "food",
            "time": entry.created_at.isoformat(),
            "title": name or "Food",
            "category": entry.portion_text,
            "amount": None,
            "calories": entry.calories,
            "is_estimate": entry.is_estimate,
            "_food_log_id": None,
            "_id": entry.id,
        })

    days_out = []
    for day in sorted(per_day.keys(), reverse=True):
        info = per_day[day]
        entries = info["entries"]
        food_by_id = {e["_id"]: e for e in entries if e["type"] == "food"}

        # Merge an expense linked to a food (food_log_id) into a single combined row.
        combined_for: dict[int, dict] = {}
        linked_food_ids: set[int] = set()
        for e in entries:
            fid = e["_food_log_id"]
            if e["type"] == "expense" and fid is not None and fid in food_by_id:
                food = food_by_id[fid]
                linked_food_ids.add(fid)
                combined_for[id(e)] = {
                    "type": "combined",
                    "time": e["time"],
                    "title": food["title"],
                    "category": e["category"],
                    "amount": e["amount"],
                    "calories": food["calories"],
                    "is_estimate": food["is_estimate"],
                }

        merged = []
        for e in entries:
            if e["type"] == "food" and e["_id"] in linked_food_ids:
                continue  # folded into its combined expense row
            merged.append(combined_for.get(id(e)) or {k: v for k, v in e.items() if not k.startswith("_")})

        days_out.append({
            "date": day,
            "total_spend": round(info["total_spend"], 2),
            "total_calories": round(info["total_calories"], 2),
            "count": len(merged),
            "entries": sorted(merged, key=lambda item: item["time"]),
        })
    return {"days": days_out}


@router.get("/nutrition/lookup")
def nutrition_lookup(
    name: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> dict:
    result = services.nutrition.find(name)
    return {"query": name, "candidates": [
        {"nutrition_id": c.reference.id, "name": c.reference.name, "match": c.match_type,
         "score": round(c.score, 2), "calories_per_100g": c.reference.calories_per_100g,
         "protein_per_100g": c.reference.protein_per_100g}
        for c in result.candidates[:5]
    ]}


def _food_entry(entry, name=None) -> dict:
    return {"id": entry.id, "food": name, "nutrition_id": entry.nutrition_id,
            "grams": entry.quantity_grams, "portion_text": entry.portion_text,
            "calories": entry.calories, "protein": entry.protein, "carbs": entry.carbs,
            "fats": entry.fats, "sugar": entry.sugar, "log_date": str(entry.log_date)}
