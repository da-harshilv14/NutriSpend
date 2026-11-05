from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.adapters.nutrition_source import StubApiSource, StubWebSearchSource
from app.api.deps import Services, get_current_user, get_services
from app.core.dates import today
from app.db.models import ExpenseLog, FoodLog, User, UserFood
from app.main import app
from app.nutrition.lookup import build_nutrition_lookup
from app.services.expense_service import ExpenseService
from app.services.food_service import FoodService
from tests.fakes import (
    FakeExpenseLogRepository,
    FakeFoodLogRepository,
    FakeNutritionRepository,
    FakeUserFoodRepository,
)


@pytest.fixture
def env():
    nutrition_repo = FakeNutritionRepository()
    user_food_repo = FakeUserFoodRepository()
    food_repo = FakeFoodLogRepository()
    expense_repo = FakeExpenseLogRepository()
    lookup = build_nutrition_lookup(
        nutrition_repo, user_food_repo, StubApiSource(), StubWebSearchSource()
    )
    food = FoodService(food_repo, nutrition_repo, user_food_repo, lookup)
    expense = ExpenseService(expense_repo)
    app.dependency_overrides[get_current_user] = lambda: User(id=1)
    app.dependency_overrides[get_services] = lambda: Services(
        auth=None, food=food, expense=expense, nutrition=None, user_food=None
    )
    yield food_repo, expense_repo, user_food_repo
    app.dependency_overrides.clear()


def _ts(minute):
    return datetime.now(timezone.utc).replace(minute=minute, second=0, microsecond=0)


def _food(food_repo, user_food_repo, name, minute):
    pf = user_food_repo.add(
        UserFood(user_id=1, name=name, name_normalized=name.lower(), calories_per_100g=100)
    )
    return food_repo.add(
        FoodLog(user_id=1, log_date=today(), user_food_id=pf.id, quantity_grams=100,
                portion_text="100g", calories=100, is_estimate=False, created_at=_ts(minute))
    )


def _expense(expense_repo, minute, food_log_id=None, description="spend"):
    return expense_repo.add(
        ExpenseLog(user_id=1, log_date=today(), amount=Decimal("40"), category="food",
                   description=description, food_log_id=food_log_id, created_at=_ts(minute))
    )


def test_history_entries_expose_ids(env):
    food_repo, expense_repo, user_food_repo = env
    lone_food = _food(food_repo, user_food_repo, "Apple", 1)
    lone_expense = _expense(expense_repo, 2, description="cab")
    linked_food = _food(food_repo, user_food_repo, "Poha", 3)
    linked_expense = _expense(expense_repo, 4, food_log_id=linked_food.id, description="poha")

    res = TestClient(app).get("/history")

    assert res.status_code == 200
    entries = res.json()["days"][0]["entries"]
    by_type = {e["type"]: e for e in entries}
    assert sorted(by_type) == ["combined", "expense", "food"]

    assert by_type["food"]["food_id"] == lone_food.id
    assert by_type["food"]["expense_id"] is None
    assert by_type["expense"]["expense_id"] == lone_expense.id
    assert by_type["expense"]["food_id"] is None
    assert by_type["combined"]["food_id"] == linked_food.id
    assert by_type["combined"]["expense_id"] == linked_expense.id

    for e in entries:
        assert not [k for k in e if k.startswith("_")]
