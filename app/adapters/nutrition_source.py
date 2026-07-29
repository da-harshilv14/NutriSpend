from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class NutritionData:
    """Per-100g nutrition returned by an external source (API or web search)."""

    name: str
    calories_per_100g: float | None = None
    protein_per_100g: float | None = None
    carbs_per_100g: float | None = None
    fats_per_100g: float | None = None
    sugar_per_100g: float | None = None


class NutritionSource(ABC):
    # 'api' | 'websearch' — also used as the source tag on cached rows.
    source_name: str

    @abstractmethod
    def lookup(self, food_name: str) -> NutritionData | None: ...


class StubApiSource(NutritionSource):
    source_name = "api"

    def lookup(self, food_name: str) -> NutritionData | None:
        return None


class StubWebSearchSource(NutritionSource):
    source_name = "websearch"

    def lookup(self, food_name: str) -> NutritionData | None:
        return None
