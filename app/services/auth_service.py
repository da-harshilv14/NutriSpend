from app.core.security import hash_password, verify_password
from app.db.models import User
from app.repos.interfaces import UserRepository


class UsernameTakenError(Exception):
    pass


class EmailTakenError(Exception):
    pass


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def signup(self, *, username: str, email: str, password: str) -> User:
        if self._user_repo.get_by_username(username) is not None:
            raise UsernameTakenError(username)
        if self._user_repo.get_by_email(email) is not None:
            raise EmailTakenError(email)
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        return self._user_repo.add(user)

    def authenticate(self, *, identifier: str, password: str) -> User | None:
        """Verify credentials by username OR email. Returns the user or None."""
        user = self._user_repo.get_by_username(identifier)
        if user is None:
            user = self._user_repo.get_by_email(identifier)
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    def set_api_key(self, *, user_id: int, api_key: str) -> User | None:
        return self._user_repo.set_api_key(user_id, api_key)
