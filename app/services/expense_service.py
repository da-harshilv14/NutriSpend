from datetime import date
from decimal import Decimal

from app.core.dates import today
from app.db.models import ExpenseLog
from app.repos.interfaces import ExpenseLogRepository


class ExpenseService:
    def __init__(self, expense_repo: ExpenseLogRepository) -> None:
        self._expense_repo = expense_repo

    def log_expense(
        self,
        *,
        user_id: int,
        amount: float | str | Decimal,
        category: str | None = None,
        description: str | None = None,
        log_date: date | None = None,
        food_log_id: int | None = None,
    ) -> ExpenseLog:
        entry = ExpenseLog(
            user_id=user_id,
            log_date=log_date or today(),
            amount=Decimal(str(amount)),  # str() first so floats don't carry binary error
            category=category,
            description=description,
            food_log_id=food_log_id,
        )
        return self._expense_repo.add(entry)

    def summary(self, *, user_id: int, start: date, end: date) -> dict:
        entries = self._expense_repo.list_for_period(user_id, start, end)
        total = sum((entry.amount for entry in entries), Decimal("0"))
        by_category: dict[str, Decimal] = {}
        for entry in entries:
            key = entry.category or "uncategorized"
            by_category[key] = by_category.get(key, Decimal("0")) + entry.amount
        return {
            "total": float(total),
            "count": len(entries),
            "by_category": {key: float(value) for key, value in by_category.items()},
        }
