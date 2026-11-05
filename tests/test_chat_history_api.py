import json

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import AgentReply
from app.api.deps import Services, get_agent, get_current_user, get_services
from app.db.models import User
from app.main import app
from app.services.chat_message_service import ChatMessageService
from tests.fakes import FakeChatMessageRepository

RECEIPT = {"title": "Idli", "amount": None, "calories": 137}


class StubAgent:
    def run(self, *, user_message, context, history):
        return AgentReply(reply="Logged idli", history=[], pending=None, receipts=[dict(RECEIPT)])


@pytest.fixture
def ctx():
    """Offline TestClient: stub auth user, stub agent, in-memory chat history."""
    chat_service = ChatMessageService(FakeChatMessageRepository())
    current = {"user": User(id=1)}
    services = Services(
        auth=None, food=None, expense=None, nutrition=None, user_food=None,
        chat_message=chat_service,
    )
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_agent] = lambda: StubAgent()
    client = TestClient(app)
    yield client, current
    app.dependency_overrides.clear()


def test_chat_turn_is_persisted_in_order(ctx):
    client, _ = ctx
    resp = client.post("/chat", json={"message": "had 2 idli"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Logged idli"

    messages = client.get("/chat/history").json()["messages"]
    assert [(m["kind"], m["content"]) for m in messages[:2]] == [
        ("user", "had 2 idli"),
        ("assistant", "Logged idli"),
    ]
    assert messages[2]["kind"] == "receipt"
    assert len(messages) == 3
    for m in messages:
        assert isinstance(m["id"], int)
        assert isinstance(m["created_at"], str) and m["created_at"]


def test_receipt_content_parses_back_to_dict(ctx):
    client, _ = ctx
    client.post("/chat", json={"message": "had 2 idli"})
    receipt = client.get("/chat/history").json()["messages"][2]
    assert json.loads(receipt["content"]) == RECEIPT


def test_history_is_per_user(ctx):
    client, current = ctx
    client.post("/chat", json={"message": "had 2 idli"})
    current["user"] = User(id=2)
    assert client.get("/chat/history").json() == {"messages": []}
    current["user"] = User(id=1)
    assert len(client.get("/chat/history").json()["messages"]) == 3


def test_history_empty_before_any_chat(ctx):
    client, _ = ctx
    assert client.get("/chat/history").json() == {"messages": []}


def test_days_above_seven_is_rejected(ctx):
    client, _ = ctx
    assert client.get("/chat/history?days=8").status_code == 422
    assert client.get("/chat/history?days=0").status_code == 422
    assert client.get("/chat/history?days=7").status_code == 200
