from app.adapters.nutrition_source import StubApiSource, StubWebSearchSource
from app.core.dates import today
from app.db.models import NutritionReference, UserFood
from app.nutrition.lookup import build_nutrition_lookup
from app.services.food_service import FoodService
from tests.fakes import FakeFoodLogRepository, FakeNutritionRepository, FakeUserFoodRepository


def _setup(refs=None):
    nutrition_repo = FakeNutritionRepository(refs or [])
    user_food_repo = FakeUserFoodRepository()
    food_repo = FakeFoodLogRepository()
    lookup = build_nutrition_lookup(
        nutrition_repo, user_food_repo, StubApiSource(), StubWebSearchSource()
    )
    service = FoodService(food_repo, nutrition_repo, user_food_repo, lookup)
    return service, nutrition_repo, user_food_repo, food_repo


def _ref(name="Dosa", source="dataset", cal=200.0):
    return NutritionReference(
        name=name, name_normalized=name.lower(), source=source,
        calories_per_100g=cal, protein_per_100g=5.0,
    )


def test_log_shared_food_creates_user_food():
    ref = _ref()
    service, nutrition_repo, user_food_repo, _ = _setup([ref])

    entry = service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")

    foods = user_food_repo.list_for_user(1)
    assert len(foods) == 1
    assert foods[0].name == "Dosa" and foods[0].source == "user"
    assert foods[0].calories_per_100g == 200.0
    assert entry.user_food_id == foods[0].id
    assert entry.nutrition_id is None
    assert entry.calories == 200.0
    assert entry.is_estimate is False


def test_relog_reuses_user_food():
    ref = _ref()
    service, _, user_food_repo, food_repo = _setup([ref])

    service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")
    service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="200g")

    foods = user_food_repo.list_for_user(1)
    assert len(foods) == 1
    assert len(food_repo.entries) == 2
    assert {e.user_food_id for e in food_repo.entries} == {foods[0].id}


def test_copy_forward_is_per_user():
    ref = _ref()
    service, _, user_food_repo, _ = _setup([ref])

    service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")
    service.log_food(user_id=2, origin="reference", food_id=ref.id, portion_text="100g")

    assert len(user_food_repo.list_for_user(1)) == 1
    assert len(user_food_repo.list_for_user(2)) == 1


def test_log_personal_food_links_directly():
    service, _, user_food_repo, _ = _setup()
    uf = user_food_repo.add(
        UserFood(user_id=1, name="My Oats", name_normalized="my oats", calories_per_100g=400.0)
    )

    entry = service.log_food(user_id=1, origin="user", food_id=uf.id, portion_text="50g")

    assert entry.user_food_id == uf.id
    assert entry.nutrition_id is None
    assert entry.calories == 200.0
    assert entry.is_estimate is False
    assert len(user_food_repo.list_for_user(1)) == 1


def test_log_personal_food_of_other_user_is_rejected():
    import pytest

    service, _, user_food_repo, _ = _setup()
    uf = user_food_repo.add(UserFood(user_id=2, name="Theirs", name_normalized="theirs"))

    with pytest.raises(ValueError):
        service.log_food(user_id=1, origin="user", food_id=uf.id, portion_text="50g")


def test_copy_forward_from_web_sets_is_estimate():
    ref = _ref(name="Sushi", source="websearch", cal=150.0)
    service, _, user_food_repo, _ = _setup([ref])

    entry = service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")

    assert entry.is_estimate is True
    # once the user logs it, the personal copy is verified
    assert user_food_repo.list_for_user(1)[0].source == "user"


def test_list_with_names_prefers_user_food():
    ref = _ref()
    service, _, _, _ = _setup([ref])
    service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")

    day = today()
    rows = service.list_with_names(user_id=1, start=day, end=day)

    assert [name for _, name in rows] == ["Dosa"]


def test_list_with_names_falls_back_to_reference():
    from app.db.models import FoodLog

    ref = _ref(name="Idli")
    service, _, _, food_repo = _setup([ref])
    food_repo.add(FoodLog(user_id=1, log_date=today(), nutrition_id=ref.id, quantity_grams=100))

    day = today()
    rows = service.list_with_names(user_id=1, start=day, end=day)

    assert [name for _, name in rows] == ["Idli"]


def test_preview_food_threads_user_id_for_personal_match():
    service, _, user_food_repo, _ = _setup()
    user_food_repo.add(
        UserFood(user_id=1, name="My Oats", name_normalized="my oats", calories_per_100g=400.0)
    )

    mine = service.preview_food(user_id=1, food_name="my oats", portion_text="50g")
    other = service.preview_food(user_id=2, food_name="my oats", portion_text="50g")

    assert mine.lookup.best.origin == "user" and not mine.needs_confirmation
    assert not (other.lookup.best and other.lookup.best.origin == "user")


def _tool_context(service):
    from app.agent.tools import ToolContext

    return ToolContext(user_id=1, food_service=service, expense_service=None, nutrition_service=None)


def test_log_food_tool_auto_logs_personal_match_without_confirmation():
    from app.agent.tools import LogFoodTool

    service, _, user_food_repo, food_repo = _setup()
    uf = user_food_repo.add(
        UserFood(user_id=1, name="My Oats", name_normalized="my oats", calories_per_100g=400.0)
    )

    result = LogFoodTool().run(_tool_context(service), food_name="my oats", portion_text="50g")

    assert result["status"] == "logged" and result["food"] == "My Oats"
    assert food_repo.entries[0].user_food_id == uf.id
    assert len(user_food_repo.list_for_user(1)) == 1


def test_log_food_tool_confirmation_path_copies_forward_shared_food():
    from app.agent.tools import LogFoodTool

    ref = _ref(name="Sushi", source="websearch")
    service, _, user_food_repo, food_repo = _setup([ref])

    result = LogFoodTool().run(
        _tool_context(service), portion_text="100g", nutrition_id=ref.id
    )

    assert result["status"] == "logged" and result["food"] == "Sushi"
    assert food_repo.entries[0].user_food_id == user_food_repo.list_for_user(1)[0].id


def test_log_does_not_mutate_shared_reference_source():
    ref = _ref(name="Sushi", source="websearch")
    service, *_ = _setup([ref])

    service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")

    assert ref.source == "websearch"


def test_log_web_food_reuses_existing_personal_food_without_estimate():
    ref = _ref(name="Sushi", source="websearch", cal=150.0)
    service, _, user_food_repo, _ = _setup([ref])
    mine = user_food_repo.add(
        UserFood(user_id=1, name="Sushi", name_normalized="sushi", calories_per_100g=300.0)
    )

    entry = service.log_food(user_id=1, origin="reference", food_id=ref.id, portion_text="100g")

    assert entry.is_estimate is False
    assert entry.user_food_id == mine.id
    assert entry.calories == 300.0  # the user's own values, not the web guess
    assert len(user_food_repo.list_for_user(1)) == 1
