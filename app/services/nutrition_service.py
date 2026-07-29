from app.nutrition.lookup import LookupResult, NutritionLookup


class NutritionService:
    def __init__(self, lookup: NutritionLookup) -> None:
        self._lookup = lookup

    def find(self, food_name: str) -> LookupResult:
        return self._lookup.find(food_name)
