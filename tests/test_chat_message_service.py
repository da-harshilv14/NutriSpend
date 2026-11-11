import json
from datetime import datetime, timedelta, timezone

from app.db.models import ChatMessage
from app.services.chat_message_service import ChatMessageService
from tests.fakes import FakeChatMessageRepository


def _service():
    repo = FakeChatMessageRepository()
    return ChatMessageService(repo), repo


def _old(user_id, days_ago, content="old"):
    return ChatMessage(
        user_id=user_id,
        kind="user",
        content=content,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_record_turn_persists_user_assistant_receipts_in_order():
    service, _ = _service()
    receipt = {"type": "food", "name": "dal", "calories": 200}
    service.record_turn(
        user_id=1, user_message="ate dal", assistant_reply="Logged dal.", receipts=[receipt]
    )

    rows = service.recent(user_id=1)

    assert [r.kind for r in rows] == ["user", "assistant", "receipt"]
    assert rows[0].content == "ate dal"
    assert rows[1].content == "Logged dal."
    assert json.loads(rows[2].content) == receipt


def test_record_turn_blank_reply_skips_assistant():
    service, _ = _service()
    service.record_turn(user_id=1, user_message="hi", assistant_reply="", receipts=[])
    service.record_turn(user_id=1, user_message="yo", assistant_reply="   ", receipts=[])
    service.record_turn(user_id=1, user_message="hey", assistant_reply=None, receipts=[])

    rows = service.recent(user_id=1)

    assert [r.kind for r in rows] == ["user", "user", "user"]


def test_record_turn_prunes_older_than_7_days():
    service, repo = _service()
    repo.add(_old(1, 8, "eight"))
    repo.add(_old(1, 6, "six"))

    service.record_turn(user_id=1, user_message="new", assistant_reply=None, receipts=[])

    contents = [m.content for m in repo.messages]
    assert "eight" not in contents
    assert "six" in contents
    assert "new" in contents


def test_recent_only_returns_users_own():
    service, _ = _service()
    service.record_turn(user_id=1, user_message="mine", assistant_reply="ok", receipts=[])
    service.record_turn(user_id=2, user_message="theirs", assistant_reply="ok", receipts=[])

    rows = service.recent(user_id=1)

    assert {r.user_id for r in rows} == {1}
    assert "theirs" not in [r.content for r in rows]


def test_prune_does_not_touch_other_users():
    service, repo = _service()
    repo.add(_old(2, 10, "other-old"))

    service.record_turn(user_id=1, user_message="new", assistant_reply=None, receipts=[])

    assert "other-old" in [m.content for m in repo.messages]


def test_recent_respects_days_window():
    service, repo = _service()
    repo.add(_old(1, 3, "three"))
    repo.add(_old(1, 1, "one"))

    rows = service.recent(user_id=1, days=2)

    assert [r.content for r in rows] == ["one"]


def test_recent_orders_by_created_at():
    service, repo = _service()
    repo.add(_old(1, 1, "later"))
    repo.add(_old(1, 3, "earlier"))

    rows = service.recent(user_id=1)

    assert [r.content for r in rows] == ["earlier", "later"]


def test_recent_tiebreaks_equal_created_at_by_id():
    service, repo = _service()
    ts = datetime.now(timezone.utc) - timedelta(minutes=5)
    # Stored in reverse id order so only the (created_at, id) sort can fix it
    # (a stable sort on created_at alone would keep insertion order).
    for mid, content in ((3, "third"), (1, "first"), (2, "second")):
        repo.messages.append(
            ChatMessage(id=mid, user_id=1, kind="user", content=content, created_at=ts)
        )

    rows = service.recent(user_id=1)

    assert [r.id for r in rows] == [1, 2, 3]
    assert [r.content for r in rows] == ["first", "second", "third"]


def test_receipt_content_is_json_roundtrip():
    service, _ = _service()
    receipt = {"type": "expense", "amount": 120.5, "category": "food", "note": "chai ☕"}
    service.record_turn(user_id=1, user_message="x", assistant_reply=None, receipts=[receipt])

    rows = [r for r in service.recent(user_id=1) if r.kind == "receipt"]

    assert len(rows) == 1
    assert json.loads(rows[0].content) == receipt
