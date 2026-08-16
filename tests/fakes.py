from datetime import date

from app.adapters.web_search import SearchResult, WebSearch
from app.db.models import ExpenseLog, FoodLog, NutritionReference, User
from app.llm.client import LLMClient, LLMResponse
from app.repos.interfaces import (
    ExpenseLogRepository,
    FoodLogRepository,
    NutritionRepository,
    UserRepository,
)


def _char_similarity(a: str, b: str) -> float:
    """Rough character-set Jaccard — enough for fuzzy-link tests, no pg_trgm."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self._next_id = 0

    def add(self, user: User) -> User:
        self._next_id += 1
        user.id = self._next_id
        self.users[user.id] = user
        return user

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_username(self, username):
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email), None)

    def set_api_key(self, user_id, api_key):
        user = self.users.get(user_id)
        if user is not None:
            user.api_key = api_key
        return user

    def set_goals(self, user_id, goals):
        user = self.users.get(user_id)
        if user is not None:
            for name, value in goals.items():
                setattr(user, name, value)
        return user


class FakeNutritionRepository(NutritionRepository):
    def __init__(self, rows: list[NutritionReference] | None = None) -> None:
        self.rows: dict[int, NutritionReference] = {}
        self._next_id = 0
        for row in rows or []:
            self.add(row)

    def add(self, reference: NutritionReference) -> NutritionReference:
        self._next_id += 1
        reference.id = self._next_id
        self.rows[reference.id] = reference
        return reference

    def get_by_id(self, reference_id):
        return self.rows.get(reference_id)

    def get_by_normalized_name(self, name_normalized):
        return next((r for r in self.rows.values() if r.name_normalized == name_normalized), None)

    def search_fuzzy(self, name_normalized, *, limit=5, threshold=0.3):
        scored = [
            (r, _char_similarity(name_normalized, r.name_normalized)) for r in self.rows.values()
        ]
        scored = [(r, s) for r, s in scored if s >= threshold]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


class FakeFoodLogRepository(FoodLogRepository):
    def __init__(self) -> None:
        self.entries: list[FoodLog] = []
        self._next_id = 0

    def add(self, entry: FoodLog) -> FoodLog:
        self._next_id += 1
        entry.id = self._next_id
        self.entries.append(entry)
        return entry

    def list_for_period(self, user_id, start: date, end: date):
        return [e for e in self.entries if e.user_id == user_id and start <= e.log_date <= end]


class FakeExpenseLogRepository(ExpenseLogRepository):
    def __init__(self) -> None:
        self.entries: list[ExpenseLog] = []
        self._next_id = 0

    def add(self, entry: ExpenseLog) -> ExpenseLog:
        self._next_id += 1
        entry.id = self._next_id
        self.entries.append(entry)
        return entry

    def list_for_period(self, user_id, start: date, end: date):
        return [e for e in self.entries if e.user_id == user_id and start <= e.log_date <= end]


class ScriptedLLM(LLMClient):
    """Returns pre-baked responses in order — no network."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def complete(self, *, messages, tools=None) -> LLMResponse:
        self.calls.append(messages)
        return self._responses.pop(0)


class FakeWebSearch(WebSearch):
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results

    def search(self, query, *, max_results=5):
        return self._results
