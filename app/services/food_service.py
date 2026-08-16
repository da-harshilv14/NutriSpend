from dataclasses import dataclass
from datetime import date

from app.core.dates import today
from app.db.models import FoodLog
from app.nutrition.lookup import (
    UNVERIFIED_SOURCES,
    LookupResult,
    NutritionLookup,
    needs_confirmation,
)
from app.nutrition.portions import PortionEstimate, resolve_portion
from app.nutrition.scaling import TRACKED, scale_nutrition
from app.repos.interfaces import FoodLogRepository, NutritionRepository


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
        lookup: NutritionLookup,
    ) -> None:
        self._food_repo = food_repo
        self._nutrition_repo = nutrition_repo
        self._lookup = lookup

    def preview_food(self, *, food_name: str, portion_text: str) -> FoodPreview:
        """Resolve name + portion without writing — the agent shows this and,
        if needed, asks the user to confirm before calling log_food."""
        result = self._lookup.find(food_name)
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
        nutrition_id: int,
        portion_text: str,
        log_date: date | None = None,
    ) -> FoodLog:
        reference = self._nutrition_repo.get_by_id(nutrition_id)
        if reference is None:
            raise ValueError(f"unknown nutrition_id: {nutrition_id}")
        is_estimate = reference.source in UNVERIFIED_SOURCES
        if is_estimate:
            reference.source = "user"  # a user chose to log it -> now verified
        portion = resolve_portion(portion_text)
        snapshot = scale_nutrition(reference, portion.grams)
        entry = FoodLog(
            user_id=user_id,
            log_date=log_date or today(),
            nutrition_id=nutrition_id,
            quantity_grams=portion.grams,
            portion_text=portion_text,
            is_estimate=is_estimate,
            **snapshot,
        )
        return self._food_repo.add(entry)

    def reference_name(self, nutrition_id: int | None) -> str | None:
        if nutrition_id is None:
            return None
        reference = self._nutrition_repo.get_by_id(nutrition_id)
        return reference.name if reference else None

    def list_for_period(self, *, user_id: int, start: date, end: date) -> list[FoodLog]:
        return self._food_repo.list_for_period(user_id, start, end)

    def list_with_names(self, *, user_id: int, start: date, end: date) -> list[tuple[FoodLog, str | None]]:
        """Food entries paired with their dish name (from nutrition_reference)."""
        entries = self._food_repo.list_for_period(user_id, start, end)
        result: list[tuple[FoodLog, str | None]] = []
        for entry in entries:
            reference = self._nutrition_repo.get_by_id(entry.nutrition_id) if entry.nutrition_id else None
            result.append((entry, reference.name if reference else None))
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
