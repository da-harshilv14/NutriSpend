from app.db.models import UserFood
from app.nutrition.text import normalize_name
from app.repos.interfaces import UserFoodRepository


# Columns a caller may change. user_id / id / source / created_at / name_normalized
# are owned by the service and can never be set through update().
_UPDATABLE_FIELDS = frozenset(
    {
        "name",
        "calories_per_100g",
        "protein_per_100g",
        "carbs_per_100g",
        "fats_per_100g",
        "sugar_per_100g",
        "serving_size",
        "serving_unit",
    }
)


class DuplicateFoodError(Exception):
    """The user already has a personal food with this (normalized) name."""


class UserFoodService:
    """Per-user personal food CRUD. Never commits — the request owns the transaction."""

    def __init__(self, repo: UserFoodRepository) -> None:
        self._repo = repo

    def list(self, user_id: int) -> list[UserFood]:
        return self._repo.list_for_user(user_id)

    def create(
        self,
        *,
        user_id: int,
        name: str,
        calories_per_100g: float | None,
        protein_per_100g: float | None = None,
        carbs_per_100g: float | None = None,
        fats_per_100g: float | None = None,
        sugar_per_100g: float | None = None,
        serving_size: float | None = None,
        serving_unit: str | None = None,
    ) -> UserFood:
        name_normalized = normalize_name(name)
        if not name_normalized:
            raise ValueError("Food name must not be blank.")
        if self._repo.get_by_normalized_name(user_id, name_normalized) is not None:
            raise DuplicateFoodError(f"You already have a food named '{name.strip()}'.")
        return self._repo.add(
            UserFood(
                user_id=user_id,
                name=name.strip(),
                name_normalized=name_normalized,
                calories_per_100g=calories_per_100g,
                protein_per_100g=protein_per_100g,
                carbs_per_100g=carbs_per_100g,
                fats_per_100g=fats_per_100g,
                sugar_per_100g=sugar_per_100g,
                serving_size=serving_size,
                serving_unit=serving_unit,
                source="user",
            )
        )

    def get(self, user_id: int, food_id: int) -> UserFood | None:
        return self._repo.get(user_id, food_id)

    def update(self, user_id: int, food_id: int, fields: dict) -> UserFood | None:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"Cannot update field(s): {', '.join(sorted(unknown))}.")
        fields = dict(fields)
        if "name" in fields:
            name = (fields["name"] or "").strip()
            name_normalized = normalize_name(name)
            if not name_normalized:
                raise ValueError("Food name must not be blank.")
            existing = self._repo.get_by_normalized_name(user_id, name_normalized)
            if existing is not None and existing.id != food_id:
                raise DuplicateFoodError(f"You already have a food named '{name}'.")
            fields["name"] = name
            fields["name_normalized"] = name_normalized
        return self._repo.update(user_id, food_id, fields)

    def delete(self, user_id: int, food_id: int) -> bool:
        return self._repo.delete(user_id, food_id)
