import pytest

from app.services.user_food_service import DuplicateFoodError, UserFoodService
from tests.fakes import FakeUserFoodRepository


@pytest.fixture
def service():
    return UserFoodService(FakeUserFoodRepository())


def test_create_normalizes_and_stores(service):
    food = service.create(user_id=1, name="Poha ", calories_per_100g=110)

    assert food.id is not None
    assert food.user_id == 1
    assert food.name_normalized == "poha"
    assert food.calories_per_100g == 110
    assert food.source == "user"


def test_create_duplicate_raises(service):
    service.create(user_id=1, name="Poha", calories_per_100g=110)

    with pytest.raises(DuplicateFoodError):
        service.create(user_id=1, name="  poha ", calories_per_100g=120)


def test_create_same_name_for_different_users_is_allowed(service):
    service.create(user_id=1, name="Poha", calories_per_100g=110)

    other = service.create(user_id=2, name="Poha", calories_per_100g=120)

    assert other.user_id == 2


def test_create_blank_name_raises(service):
    with pytest.raises(ValueError):
        service.create(user_id=1, name="   ", calories_per_100g=110)


def test_update_changes_fields(service):
    food = service.create(user_id=1, name="Poha", calories_per_100g=110)

    updated = service.update(1, food.id, {"calories_per_100g": 150})

    assert updated is not None
    assert updated.calories_per_100g == 150


def test_update_unknown_returns_none(service):
    assert service.update(1, 999, {"calories_per_100g": 150}) is None


def test_update_other_users_food_returns_none(service):
    food = service.create(user_id=1, name="Poha", calories_per_100g=110)

    assert service.update(2, food.id, {"calories_per_100g": 150}) is None


def test_delete_removes(service):
    food = service.create(user_id=1, name="Poha", calories_per_100g=110)

    assert service.delete(1, food.id) is True
    assert service.list(1) == []


def test_delete_unknown_false(service):
    assert service.delete(1, 999) is False


def test_list_only_users_own(service):
    service.create(user_id=1, name="Poha", calories_per_100g=110)
    service.create(user_id=2, name="Idli", calories_per_100g=130)

    foods = service.list(1)

    assert [f.name_normalized for f in foods] == ["poha"]
