from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExpenseLog
from app.repos.interfaces import ExpenseLogRepository


class SqlAlchemyExpenseLogRepository(ExpenseLogRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: ExpenseLog) -> ExpenseLog:
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_for_period(self, user_id: int, start: date, end: date) -> list[ExpenseLog]:
        statement = (
            select(ExpenseLog)
            .where(
                ExpenseLog.user_id == user_id,
                ExpenseLog.log_date >= start,
                ExpenseLog.log_date <= end,
            )
            .order_by(ExpenseLog.log_date)
        )
        return list(self._session.scalars(statement))
