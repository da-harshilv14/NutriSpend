from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.deps import Services, get_current_user, get_services
from app.core.dates import today
from app.db.models import ExpenseLog, User
from app.main import app
from app.services.expense_service import ExpenseService
from tests.fakes import FakeExpenseLogRepository


@pytest.fixture
def env():
    repo = FakeExpenseLogRepository()
    return ExpenseService(repo), repo


@pytest.fixture
def api(env):
    service, _ = env
    current = {"user": User(id=1)}
    services = Services(auth=None, food=None, expense=service, nutrition=None, user_food=None)
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_services] = lambda: services
    yield TestClient(app), current
    app.dependency_overrides.clear()


def _logged(repo, user_id=1):
    return repo.add(
        ExpenseLog(user_id=user_id, log_date=today(), amount=Decimal("50"), category="food",
                   description="lunch")
    )


def test_edit_amount(env, api):
    _, repo = env
    client, _ = api
    entry = _logged(repo)

    res = client.patch(f"/expenses/{entry.id}", json={"amount": 75.5})

    assert res.status_code == 200
    assert res.json() == {"id": entry.id, "amount": 75.5, "category": "food",
                          "description": "lunch", "log_date": str(entry.log_date)}
    assert entry.amount == Decimal("75.5")


def test_edit_category_description(env, api):
    _, repo = env
    client, _ = api
    entry = _logged(repo)

    res = client.patch(f"/expenses/{entry.id}",
                       json={"category": "travel", "description": "cab"})

    assert res.status_code == 200
    body = res.json()
    assert body["category"] == "travel" and body["description"] == "cab"
    assert body["amount"] == 50.0  # untouched
    assert entry.category == "travel" and entry.description == "cab"


def test_edit_amount_zero_422(env, api):
    _, repo = env
    client, _ = api
    entry = _logged(repo)

    assert client.patch(f"/expenses/{entry.id}", json={"amount": 0}).status_code == 422
    assert entry.amount == Decimal("50")


def test_patch_other_users_expense_404(env, api):
    _, repo = env
    client, current = api
    entry = _logged(repo, user_id=1)
    current["user"] = User(id=2)

    assert client.patch(f"/expenses/{entry.id}", json={"amount": 10}).status_code == 404
    assert entry.amount == Decimal("50")


def test_patch_empty_body_422(env, api):
    _, repo = env
    client, _ = api
    entry = _logged(repo)

    assert client.patch(f"/expenses/{entry.id}", json={}).status_code == 422
    assert client.patch(f"/expenses/{entry.id}", json={"amount": None}).status_code == 422
