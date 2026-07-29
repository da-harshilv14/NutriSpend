from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FoodLog
from app.repos.interfaces import FoodLogRepository


class SqlAlchemyFoodLogRepository(FoodLogRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: FoodLog) -> FoodLog:
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_for_period(self, user_id: int, start: date, end: date) -> list[FoodLog]:
        statement = (
            select(FoodLog)
            .where(
                FoodLog.user_id == user_id,
                FoodLog.log_date >= start,
                FoodLog.log_date <= end,
            )
            .order_by(FoodLog.log_date)
        )
        return list(self._session.scalars(statement))
