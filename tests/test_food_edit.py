import pytest
from fastapi.testclient import TestClient

from app.adapters.nutrition_source import StubApiSource, StubWebSearchSource
from app.api.deps import Services, get_current_user, get_services
from app.core.dates import today
from app.db.models import FoodLog, User, UserFood
from app.main import app
from app.nutrition.lookup import build_nutrition_lookup
from app.services.food_service import FoodService
from tests.fakes import FakeFoodLogRepository, FakeNutritionRepository, FakeUserFoodRepository


@pytest.fixture
def env():
    nutrition_repo = FakeNutritionRepository()
    user_food_repo = FakeUserFoodRepository()
    food_repo = FakeFoodLogRepository()
    lookup = build_nutrition_lookup(
        nutrition_repo, user_food_repo, StubApiSource(), StubWebSearchSource()
    )
    service = FoodService(food_repo, nutrition_repo, user_food_repo, lookup)
    return service, food_repo, user_food_repo


def _logged(env, grams=150, calories=150, user_id=1):
    """A personal food (100 cal/100g) with one entry logged against it."""
    service, food_repo, user_food_repo = env
    food = user_food_repo.add(
        UserFood(user_id=user_id, name="Poha", name_normalized="poha", calories_per_100g=100,
                 protein_per_100g=4)
    )
    entry = food_repo.add(
        FoodLog(user_id=user_id, log_date=today(), user_food_id=food.id, quantity_grams=grams,
                portion_text=f"{grams}g", calories=calories, protein=6)
    )
    return entry, food


def test_edit_calories_updates_entry_and_personal_food(env):
    service, _, _ = env
    entry, food = _logged(env, grams=150, calories=150)

    updated = service.update_food_log(user_id=1, food_log_id=entry.id, calories=300)

    assert updated.calories == 300
    assert food.calories_per_100g == 200  # 300 / 150 * 100
    assert food.protein_per_100g == 4  # untouched nutrient left alone


def test_edit_portion_reresolves_grams_without_rescaling_calories(env):
    service, _, _ = env
    entry, food = _logged(env, grams=150, calories=150)

    updated = service.update_food_log(user_id=1, food_log_id=entry.id, portion_text="2 bowls")

    assert updated.quantity_grams == 300
    assert updated.portion_text == "2 bowls"
    assert updated.calories == 150  # typed value kept, not rescaled
    assert food.calories_per_100g == 100  # no nutrient edited -> personal food unchanged


def test_edit_portion_and_calories_together_use_new_grams(env):
    service, _, _ = env
    entry, food = _logged(env, grams=150, calories=150)

    service.update_food_log(user_id=1, food_log_id=entry.id, calories=600, portion_text="2 bowls")

    assert food.calories_per_100g == 200  # 600 / 300 * 100


def test_edit_pre1b_entry_only_updates_row(env):
    service, food_repo, _ = env
    entry = food_repo.add(
        FoodLog(user_id=1, log_date=today(), user_food_id=None, quantity_grams=100, calories=80)
    )

    updated = service.update_food_log(user_id=1, food_log_id=entry.id, calories=120)

    assert updated.calories == 120


def test_edit_grams_zero_no_divide_error(env):
    service, _, _ = env
    entry, food = _logged(env, grams=0, calories=0)

    updated = service.update_food_log(user_id=1, food_log_id=entry.id, calories=50)

    assert updated.calories == 50
    assert food.calories_per_100g == 100  # per-100g update skipped


def test_edit_unparseable_portion_uses_default(env):
    service, _, _ = env
    entry, _ = _logged(env)

    updated = service.update_food_log(user_id=1, food_log_id=entry.id, portion_text="???")

    assert updated.quantity_grams == 100.0  # resolve_portion's default


def test_update_missing_or_other_users_entry_returns_none(env):
    service, _, _ = env
    entry, food = _logged(env, user_id=1)

    assert service.update_food_log(user_id=2, food_log_id=entry.id, calories=999) is None
    assert service.update_food_log(user_id=1, food_log_id=12345, calories=999) is None
    assert entry.calories == 150 and food.calories_per_100g == 100


# --- API ---
@pytest.fixture
def api(env):
    service, _, _ = env
    current = {"user": User(id=1)}
    services = Services(auth=None, food=service, expense=None, nutrition=None, user_food=None)
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_services] = lambda: services
    yield TestClient(app), current
    app.dependency_overrides.clear()


def test_patch_updates_entry_and_returns_it(env, api):
    client, _ = api
    entry, food = _logged(env, grams=150, calories=150)

    res = client.patch(f"/food/{entry.id}", json={"calories": 300})

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == entry.id and body["calories"] == 300 and body["food"] == "Poha"
    assert food.calories_per_100g == 200


def test_patch_other_users_food_404(env, api):
    client, current = api
    entry, _ = _logged(env, user_id=1)
    current["user"] = User(id=2)

    assert client.patch(f"/food/{entry.id}", json={"calories": 300}).status_code == 404
    assert entry.calories == 150


def test_patch_empty_body_422(env, api):
    client, _ = api
    entry, _ = _logged(env)

    assert client.patch(f"/food/{entry.id}", json={}).status_code == 422


def test_patch_negative_nutrient_422(env, api):
    client, _ = api
    entry, _ = _logged(env)

    assert client.patch(f"/food/{entry.id}", json={"calories": -1}).status_code == 422
