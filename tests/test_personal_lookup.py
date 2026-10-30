from app.adapters.nutrition_source import StubApiSource, StubWebSearchSource
from app.db.models import NutritionReference, UserFood
from app.nutrition.lookup import build_nutrition_lookup, needs_confirmation
from tests.fakes import FakeNutritionRepository, FakeUserFoodRepository


def _user_food(user_id, name, normalized):
    return UserFood(user_id=user_id, name=name, name_normalized=normalized, calories_per_100g=150)


def _lookup(user_foods=(), shared=()):
    user_repo = FakeUserFoodRepository()
    for food in user_foods:
        user_repo.add(food)
    nutrition_repo = FakeNutritionRepository(list(shared))
    return build_nutrition_lookup(nutrition_repo, user_repo, StubApiSource(), StubWebSearchSource())


def _shared(name, normalized):
    return NutritionReference(
        name=name, name_normalized=normalized, source="dataset", calories_per_100g=200
    )


def test_exact_personal_match_wins_and_is_confident():
    lookup = _lookup([_user_food(1, "Poha", "poha")], [_shared("Poha", "poha")])
    result = lookup.find("poha", user_id=1)
    assert len(result.candidates) == 1
    assert result.best.origin == "user"
    assert result.best.match_type == "personal"
    assert needs_confirmation(result) is False


def test_strong_fuzzy_personal_match_returned():
    lookup = _lookup([_user_food(1, "Kanda Poha", "kanda poha")])
    result = lookup.find("kanda pohaa", user_id=1)
    assert len(result.candidates) == 1
    assert result.best.match_type == "personal" and result.best.origin == "user"
    assert result.best.score >= 0.6
    assert needs_confirmation(result) is False


def test_weak_personal_match_falls_through_to_shared():
    lookup = _lookup(
        [_user_food(1, "Poha", "poha")],
        [_shared("Chicken Biryani", "chicken biryani")],
    )
    result = lookup.find("chicken biryani", user_id=1)
    assert result.best.reference.name == "Chicken Biryani"
    assert all(c.origin == "reference" for c in result.candidates)
    assert all(c.match_type != "personal" for c in result.candidates)


def test_no_user_id_skips_personal():
    lookup = _lookup([_user_food(1, "Poha", "poha")], [_shared("Poha Shared", "poha")])
    result = lookup.find("poha")
    assert result.best.match_type == "exact"
    assert result.best.origin == "reference"
    assert result.best.reference.name == "Poha Shared"


def test_personal_scoped_per_user():
    lookup = _lookup([_user_food(1, "Poha", "poha")])
    result = lookup.find("poha", user_id=2)
    assert all(c.match_type != "personal" for c in result.candidates)
    assert all(c.origin == "reference" for c in result.candidates)
