from app.adapters.nutrition_source import StubApiSource, StubWebSearchSource
from app.core.dates import today
from app.db.models import NutritionReference
from app.nutrition.lookup import build_nutrition_lookup
from app.services.auth_service import AuthService, EmailTakenError, UsernameTakenError
from app.services.expense_service import ExpenseService
from app.services.food_service import FoodService
from tests.fakes import (
    FakeExpenseLogRepository,
    FakeFoodLogRepository,
    FakeNutritionRepository,
    FakeUserRepository,
)


def _food_service(nutrition_repo):
    lookup = build_nutrition_lookup(nutrition_repo, StubApiSource(), StubWebSearchSource())
    return FoodService(FakeFoodLogRepository(), nutrition_repo, lookup)


def test_log_food_snapshots_and_promotes_source():
    ref = NutritionReference(
        name="Sushi", name_normalized="sushi", source="websearch",
        calories_per_100g=200, protein_per_100g=10,
    )
    nutrition_repo = FakeNutritionRepository([ref])
    service = _food_service(nutrition_repo)

    entry = service.log_food(user_id=1, nutrition_id=ref.id, portion_text="150g")

    assert entry.quantity_grams == 150
    assert entry.calories == 300 and entry.protein == 15  # 200/100 * 150
    assert ref.source == "user"  # web guess, once logged, becomes verified


def test_food_summary_totals():
    ref = NutritionReference(name="Rice", name_normalized="rice", source="dataset", calories_per_100g=100)
    nutrition_repo = FakeNutritionRepository([ref])
    service = _food_service(nutrition_repo)
    service.log_food(user_id=1, nutrition_id=ref.id, portion_text="200g")  # 200 kcal
    service.log_food(user_id=1, nutrition_id=ref.id, portion_text="100g")  # 100 kcal
    day = today()
    summary = service.summary(user_id=1, start=day, end=day)
    assert summary["calories"] == 300 and summary["entries"] == 2


def test_expense_summary_by_category():
    service = ExpenseService(FakeExpenseLogRepository())
    service.log_expense(user_id=1, amount=100, category="food")
    service.log_expense(user_id=1, amount=50, category="transport")
    day = today()
    summary = service.summary(user_id=1, start=day, end=day)
    assert summary["total"] == 150.0
    assert summary["by_category"] == {"food": 100.0, "transport": 50.0}


def test_auth_signup_login_and_uniqueness():
    service = AuthService(FakeUserRepository())
    service.signup(username="alice", email="alice@example.com", password="s3cret-pw")

    assert service.authenticate(identifier="alice", password="s3cret-pw") is not None
    assert service.authenticate(identifier="alice", password="wrong") is None
    assert service.authenticate(identifier="alice@example.com", password="s3cret-pw") is not None

    import pytest

    with pytest.raises(UsernameTakenError):
        service.signup(username="alice", email="other@example.com", password="x123456")
    with pytest.raises(EmailTakenError):
        service.signup(username="bob", email="alice@example.com", password="x123456")
