import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.deps import Services, get_current_user, get_services
from app.db.models import User
from app.main import app
from app.services.user_food_service import UserFoodService
from tests.fakes import FakeUserFoodRepository


@pytest.fixture
def ctx():
    """Offline TestClient: stub auth user + in-memory personal-food service."""
    repo = FakeUserFoodRepository()
    service = UserFoodService(repo)
    current = {"user": User(id=1)}
    services = Services(auth=None, food=None, expense=None, nutrition=None, user_food=service)
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)
    yield client, service, current
    app.dependency_overrides.clear()


def _create(client, name="Poha", calories=110, **extra):
    return client.post("/foods", json={"name": name, "calories_per_100g": calories, **extra})


def test_create_then_list_roundtrip(ctx):
    client, _, _ = ctx

    res = _create(client, protein_per_100g=2.5, serving_size=150, serving_unit="g")

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Poha"
    assert body["calories_per_100g"] == 110
    assert body["protein_per_100g"] == 2.5
    assert body["serving_size"] == 150
    assert body["serving_unit"] == "g"
    assert body["carbs_per_100g"] is None
    listed = client.get("/foods").json()["foods"]
    assert [f["id"] for f in listed] == [body["id"]]
    assert "user_id" not in body and "source" not in body


def test_duplicate_name_409(ctx):
    client, _, _ = ctx
    assert _create(client, "Poha").status_code == 201

    assert _create(client, "  poha ").status_code == 409


def test_calories_zero_422(ctx):
    client, _, _ = ctx
    assert _create(client, calories=0).status_code == 422


def test_negative_calories_422(ctx):
    client, _, _ = ctx
    assert _create(client, calories=-5).status_code == 422


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(ctx, name):
    client, _, _ = ctx
    assert _create(client, name=name).status_code in (400, 422)


def test_get_own_food(ctx):
    client, _, _ = ctx
    food_id = _create(client).json()["id"]

    res = client.get(f"/foods/{food_id}")

    assert res.status_code == 200
    assert res.json()["name"] == "Poha"


def test_other_users_food_is_404_for_get_patch_delete(ctx):
    client, service, _ = ctx
    other = service.create(user_id=2, name="Secret", calories_per_100g=300)

    assert client.get(f"/foods/{other.id}").status_code == 404
    assert client.patch(f"/foods/{other.id}", json={"calories_per_100g": 1}).status_code == 404
    assert client.delete(f"/foods/{other.id}").status_code == 404
    # untouched, and invisible in the list
    assert service.list(2)[0].calories_per_100g == 300
    assert client.get("/foods").json()["foods"] == []


def test_unknown_id_404(ctx):
    client, _, _ = ctx
    assert client.get("/foods/999").status_code == 404
    assert client.patch("/foods/999", json={"calories_per_100g": 1}).status_code == 404
    assert client.delete("/foods/999").status_code == 404


def test_delete_204_then_gone(ctx):
    client, _, _ = ctx
    food_id = _create(client).json()["id"]

    res = client.delete(f"/foods/{food_id}")

    assert res.status_code == 204
    assert res.content == b""
    assert client.get("/foods").json()["foods"] == []
    assert client.get(f"/foods/{food_id}").status_code == 404
    assert client.delete(f"/foods/{food_id}").status_code == 404


def test_patch_updates_only_given_fields(ctx):
    client, _, _ = ctx
    food_id = _create(client, protein_per_100g=2.5).json()["id"]

    res = client.patch(f"/foods/{food_id}", json={"calories_per_100g": 150})

    assert res.status_code == 200
    body = res.json()
    assert body["calories_per_100g"] == 150
    assert body["protein_per_100g"] == 2.5
    assert body["name"] == "Poha"


def test_patch_empty_body_400(ctx):
    client, _, _ = ctx
    food_id = _create(client).json()["id"]
    assert client.patch(f"/foods/{food_id}", json={}).status_code == 400


def test_patch_calories_zero_422(ctx):
    client, _, _ = ctx
    food_id = _create(client).json()["id"]
    assert client.patch(f"/foods/{food_id}", json={"calories_per_100g": 0}).status_code == 422


def test_patch_cannot_touch_protected_fields(ctx):
    client, service, _ = ctx
    food_id = _create(client).json()["id"]

    res = client.patch(
        f"/foods/{food_id}",
        json={"user_id": 2, "id": 99, "source": "hacked", "calories_per_100g": 120},
    )

    assert res.status_code == 200
    stored = service.list(1)[0]
    assert (stored.id, stored.user_id, stored.source) == (food_id, 1, "user")
    assert stored.calories_per_100g == 120
    assert service.list(2) == []


def test_rename_to_existing_name_409(ctx):
    client, _, _ = ctx
    _create(client, "Poha")
    other_id = _create(client, "Upma").json()["id"]

    res = client.patch(f"/foods/{other_id}", json={"name": "  POHA "})

    assert res.status_code == 409


def test_rename_keeps_normalized_name_fresh(ctx):
    client, service, _ = ctx
    food_id = _create(client, "Poha").json()["id"]

    res = client.patch(f"/foods/{food_id}", json={"name": "  Kanda   Poha "})

    assert res.status_code == 200
    assert res.json()["name"] == "Kanda   Poha"
    assert service.list(1)[0].name_normalized == "kanda poha"
    # old name is free again; new name is taken
    assert _create(client, "Poha").status_code == 201
    assert _create(client, "kanda poha").status_code == 409


def test_rename_to_own_name_is_ok(ctx):
    client, _, _ = ctx
    food_id = _create(client, "Poha").json()["id"]
    assert client.patch(f"/foods/{food_id}", json={"name": "POHA"}).status_code == 200


def test_patch_blank_name_rejected(ctx):
    client, _, _ = ctx
    food_id = _create(client).json()["id"]
    assert client.patch(f"/foods/{food_id}", json={"name": "   "}).status_code in (400, 422)


def test_other_user_can_use_same_name(ctx):
    client, service, _ = ctx
    service.create(user_id=2, name="Poha", calories_per_100g=100)
    assert _create(client, "Poha").status_code == 201


def test_integrity_error_maps_to_409(ctx):
    client, service, _ = ctx

    def boom(**_):
        raise IntegrityError("insert", {}, Exception("uq_user_food_user_name"))

    service.create = boom
    assert _create(client).status_code == 409


def test_requires_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/foods").status_code == 401
