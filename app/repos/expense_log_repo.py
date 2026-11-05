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

    def get(self, user_id: int, expense_id: int) -> ExpenseLog | None:
        return self._session.scalar(
            select(ExpenseLog).where(ExpenseLog.user_id == user_id, ExpenseLog.id == expense_id)
        )

    def update(self, user_id: int, expense_id: int, fields: dict) -> ExpenseLog | None:
        entry = self.get(user_id, expense_id)
        if entry is None:
            return None
        for name, value in fields.items():
            setattr(entry, name, value)
        self._session.flush()
        return entry
