from abc import ABC, abstractmethod
from datetime import date

from app.db.models import ExpenseLog, FoodLog, NutritionReference, User, UserFood


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def set_api_key(self, user_id: int, api_key: str) -> User | None: ...

    @abstractmethod
    def set_goals(self, user_id: int, goals: dict[str, float]) -> User | None: ...


class NutritionRepository(ABC):
    @abstractmethod
    def get_by_id(self, reference_id: int) -> NutritionReference | None: ...

    @abstractmethod
    def get_by_normalized_name(self, name_normalized: str) -> NutritionReference | None: ...

    @abstractmethod
    def search_fuzzy(
        self, name_normalized: str, *, limit: int = 5, threshold: float = 0.3
    ) -> list[tuple[NutritionReference, float]]: ...

    @abstractmethod
    def add(self, reference: NutritionReference) -> NutritionReference: ...


class UserFoodRepository(ABC):
    """Per-user personal foods. Every method is scoped by user_id."""

    @abstractmethod
    def list_for_user(self, user_id: int) -> list[UserFood]: ...

    @abstractmethod
    def get(self, user_id: int, food_id: int) -> UserFood | None: ...

    @abstractmethod
    def get_by_normalized_name(self, user_id: int, name_normalized: str) -> UserFood | None: ...

    @abstractmethod
    def search_fuzzy(
        self, user_id: int, name_normalized: str, *, limit: int = 6, threshold: float = 0.3
    ) -> list[tuple[UserFood, float]]: ...

    @abstractmethod
    def add(self, food: UserFood) -> UserFood: ...

    @abstractmethod
    def update(self, user_id: int, food_id: int, fields: dict) -> UserFood | None: ...

    @abstractmethod
    def delete(self, user_id: int, food_id: int) -> bool: ...


class FoodLogRepository(ABC):
    @abstractmethod
    def add(self, entry: FoodLog) -> FoodLog: ...

    @abstractmethod
    def list_for_period(self, user_id: int, start: date, end: date) -> list[FoodLog]: ...


class ExpenseLogRepository(ABC):
    @abstractmethod
    def add(self, entry: ExpenseLog) -> ExpenseLog: ...

    @abstractmethod
    def list_for_period(self, user_id: int, start: date, end: date) -> list[ExpenseLog]: ...
