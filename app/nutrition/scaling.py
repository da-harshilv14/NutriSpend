from app.db.models import NutritionReference

TRACKED = ("calories", "protein", "carbs", "fats", "sugar")


def scale_nutrition(reference: NutritionReference, grams: float) -> dict[str, float | None]:
    """Scale a per-100g reference to `grams`, returning the tracked nutrients.

    A missing (None) value stays None rather than becoming 0 — unknown is not zero.
    """
    factor = grams / 100.0

    def scaled(value_per_100g: float | None) -> float | None:
        return round(value_per_100g * factor, 2) if value_per_100g is not None else None

    return {
        "calories": scaled(reference.calories_per_100g),
        "protein": scaled(reference.protein_per_100g),
        "carbs": scaled(reference.carbs_per_100g),
        "fats": scaled(reference.fats_per_100g),
        "sugar": scaled(reference.sugar_per_100g),
    }
