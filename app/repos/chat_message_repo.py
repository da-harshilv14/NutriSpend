from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage
from app.repos.interfaces import ChatMessageRepository


class SqlAlchemyChatMessageRepository(ChatMessageRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, message: ChatMessage) -> ChatMessage:
        self._session.add(message)
        self._session.flush()
        return message

    def list_since(self, user_id: int, since: datetime) -> list[ChatMessage]:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id, ChatMessage.created_at >= since)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return list(self._session.scalars(statement))

    def delete_before(self, user_id: int, cutoff: datetime) -> int:
        result = self._session.execute(
            delete(ChatMessage).where(
                ChatMessage.user_id == user_id, ChatMessage.created_at < cutoff
            )
        )
        self._session.flush()
        return result.rowcount or 0
