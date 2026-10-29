from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import UserFood
from app.repos.interfaces import UserFoodRepository


class SqlAlchemyUserFoodRepository(UserFoodRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: int) -> list[UserFood]:
        return list(
            self._session.scalars(
                select(UserFood)
                .where(UserFood.user_id == user_id)
                .order_by(UserFood.name_normalized)
            )
        )

    def get(self, user_id: int, food_id: int) -> UserFood | None:
        return self._session.scalar(
            select(UserFood).where(UserFood.user_id == user_id, UserFood.id == food_id)
        )

    def get_by_normalized_name(self, user_id: int, name_normalized: str) -> UserFood | None:
        return self._session.scalar(
            select(UserFood).where(
                UserFood.user_id == user_id, UserFood.name_normalized == name_normalized
            )
        )

    def search_fuzzy(
        self, user_id: int, name_normalized: str, *, limit: int = 6, threshold: float = 0.3
    ) -> list[tuple[UserFood, float]]:
        # Same trigram approach as the shared nutrition repo, restricted to the
        # caller's own foods so one user's list never leaks into another's.
        self._session.execute(
            text("SELECT set_config('pg_trgm.similarity_threshold', :t, true)"),
            {"t": str(threshold)},
        )
        similarity = func.similarity(UserFood.name_normalized, name_normalized)
        statement = (
            select(UserFood, similarity.label("score"))
            .where(
                UserFood.user_id == user_id,
                UserFood.name_normalized.op("%")(name_normalized),
            )
            .order_by(similarity.desc())
            .limit(limit)
        )
        return [(row[0], float(row[1])) for row in self._session.execute(statement).all()]

    def add(self, food: UserFood) -> UserFood:
        self._session.add(food)
        self._session.flush()
        return food

    def update(self, user_id: int, food_id: int, fields: dict) -> UserFood | None:
        food = self.get(user_id, food_id)
        if food is None:
            return None
        for name, value in fields.items():
            setattr(food, name, value)
        self._session.flush()
        return food

    def delete(self, user_id: int, food_id: int) -> bool:
        food = self.get(user_id, food_id)
        if food is None:
            return False
        self._session.delete(food)
        self._session.flush()
        return True
