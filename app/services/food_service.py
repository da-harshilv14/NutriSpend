from dataclasses import dataclass
from datetime import date

from app.core.dates import today
from app.db.models import FoodLog, NutritionReference, UserFood
from app.nutrition.lookup import (
    UNVERIFIED_SOURCES,
    LookupResult,
    NutritionLookup,
    needs_confirmation,
)
from app.nutrition.portions import PortionEstimate, resolve_portion
from app.nutrition.scaling import TRACKED, scale_nutrition
from app.nutrition.text import normalize_name
from app.repos.interfaces import FoodLogRepository, NutritionRepository, UserFoodRepository


@dataclass(frozen=True)
class FoodPreview:
    lookup: LookupResult
    portion: PortionEstimate
    snapshot: dict[str, float | None] | None  # nutrients for the best candidate
    needs_confirmation: bool


class FoodService:
    def __init__(
        self,
        food_repo: FoodLogRepository,
        nutrition_repo: NutritionRepository,
        user_food_repo: UserFoodRepository,
        lookup: NutritionLookup,
    ) -> None:
        self._food_repo = food_repo
        self._nutrition_repo = nutrition_repo
        self._user_food_repo = user_food_repo
        self._lookup = lookup

    def preview_food(self, *, user_id: int, food_name: str, portion_text: str) -> FoodPreview:
        """Resolve name + portion without writing — the agent shows this and,
        if needed, asks the user to confirm before calling log_food."""
        result = self._lookup.find(food_name, user_id)
        portion = resolve_portion(portion_text)
        best = result.best
        snapshot = scale_nutrition(best.reference, portion.grams) if best else None
        return FoodPreview(
            lookup=result,
            portion=portion,
            snapshot=snapshot,
            needs_confirmation=needs_confirmation(result),
        )

    def log_food(
        self,
        *,
        user_id: int,
        origin: str,
        food_id: int,
        portion_text: str,
        log_date: date | None = None,
    ) -> FoodLog:
        """Log a food. origin='user' links straight to the caller's own
        user_food; origin='reference' copies the shared row into their
        personal list first (copy-forward, deduped by name)."""
        if origin == "user":
            user_food = self._user_food_repo.get(user_id, food_id)
            if user_food is None:
                raise ValueError(f"unknown user food: {food_id}")
            is_estimate = False
        else:
            reference = self._nutrition_repo.get_by_id(food_id)
            if reference is None:
                raise ValueError(f"unknown nutrition_id: {food_id}")
            is_estimate = reference.source in UNVERIFIED_SOURCES
            if is_estimate:
                reference.source = "user"  # a user chose to log it -> now verified
            user_food = self._ensure_user_food(user_id, reference)
        portion = resolve_portion(portion_text)
        snapshot = scale_nutrition(user_food, portion.grams)
        entry = FoodLog(
            user_id=user_id,
            log_date=log_date or today(),
            user_food_id=user_food.id,
            nutrition_id=None,
            quantity_grams=portion.grams,
            portion_text=portion_text,
            is_estimate=is_estimate,
            **snapshot,
        )
        return self._food_repo.add(entry)

    def _ensure_user_food(self, user_id: int, reference: NutritionReference) -> UserFood:
        """The user's personal copy of a shared food (reused if already there)."""
        name_normalized = normalize_name(reference.name)
        existing = self._user_food_repo.get_by_normalized_name(user_id, name_normalized)
        if existing is not None:
            return existing
        return self._user_food_repo.add(
            UserFood(
                user_id=user_id,
                name=reference.name,
                name_normalized=name_normalized,
                calories_per_100g=reference.calories_per_100g,
                protein_per_100g=reference.protein_per_100g,
                carbs_per_100g=reference.carbs_per_100g,
                fats_per_100g=reference.fats_per_100g,
                sugar_per_100g=reference.sugar_per_100g,
                serving_size=reference.serving_size,
                serving_unit=reference.serving_unit,
                source="user",
            )
        )

    def entry_name(self, entry: FoodLog) -> str | None:
        """Dish name for a log entry: personal food first, else the shared
        reference (pre-personal-foods entries)."""
        if entry.user_food_id is not None:
            food = self._user_food_repo.get(entry.user_id, entry.user_food_id)
            if food is not None:
                return food.name
        return self.reference_name(entry.nutrition_id)

    def reference_name(self, nutrition_id: int | None) -> str | None:
        if nutrition_id is None:
            return None
        reference = self._nutrition_repo.get_by_id(nutrition_id)
        return reference.name if reference else None

    def list_for_period(self, *, user_id: int, start: date, end: date) -> list[FoodLog]:
        return self._food_repo.list_for_period(user_id, start, end)

    def list_with_names(self, *, user_id: int, start: date, end: date) -> list[tuple[FoodLog, str | None]]:
        """Food entries paired with their dish name (personal food, else shared reference)."""
        entries = self._food_repo.list_for_period(user_id, start, end)
        result: list[tuple[FoodLog, str | None]] = []
        for entry in entries:
            result.append((entry, self.entry_name(entry)))
        return result

    def summary(self, *, user_id: int, start: date, end: date) -> dict:
        entries = self._food_repo.list_for_period(user_id, start, end)
        totals = {nutrient: 0.0 for nutrient in TRACKED}
        for entry in entries:
            for nutrient in TRACKED:
                value = getattr(entry, nutrient)
                if value is not None:
                    totals[nutrient] += value
        result = {nutrient: round(value, 2) for nutrient, value in totals.items()}
        result["entries"] = len(entries)
        return result
