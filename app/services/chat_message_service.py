import json
from datetime import datetime, timedelta, timezone

from app.db.models import ChatMessage
from app.repos.interfaces import ChatMessageRepository

RETENTION_DAYS = 7


class ChatMessageService:
    RETENTION_DAYS = RETENTION_DAYS

    def __init__(self, chat_repo: ChatMessageRepository) -> None:
        self._chat_repo = chat_repo

    def record_turn(
        self,
        *,
        user_id: int,
        user_message: str,
        assistant_reply: str | None,
        receipts: list[dict],
    ) -> None:
        self._chat_repo.add(ChatMessage(user_id=user_id, kind="user", content=user_message))
        if assistant_reply and assistant_reply.strip():
            self._chat_repo.add(
                ChatMessage(user_id=user_id, kind="assistant", content=assistant_reply)
            )
        for receipt in receipts:
            self._chat_repo.add(
                ChatMessage(user_id=user_id, kind="receipt", content=json.dumps(receipt))
            )
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.RETENTION_DAYS)
        self._chat_repo.delete_before(user_id, cutoff)

    def recent(self, *, user_id: int, days: int = RETENTION_DAYS) -> list[ChatMessage]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return self._chat_repo.list_since(user_id, since)
