from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.repos.interfaces import UserRepository


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def set_api_key(self, user_id: int, api_key: str) -> User | None:
        user = self._session.get(User, user_id)
        if user is None:
            return None
        user.api_key = api_key
        self._session.flush()
        return user

    def set_goals(self, user_id: int, goals: dict[str, float]) -> User | None:
        user = self._session.get(User, user_id)
        if user is None:
            return None
        for name, value in goals.items():
            setattr(user, name, value)
        self._session.flush()
        return user
