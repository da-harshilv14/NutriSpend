from app.adapters.nutrition_source import NutritionData, NutritionSource, StubApiSource
from app.db.models import NutritionReference
from app.nutrition.lookup import build_nutrition_lookup
from tests.fakes import FakeNutritionRepository


class _CannedSource(NutritionSource):
    source_name = "websearch"

    def __init__(self, data: NutritionData | None) -> None:
        self._data = data

    def lookup(self, food_name):
        return self._data


def _row(name, normalized, source="dataset", cal=150):
    return NutritionReference(name=name, name_normalized=normalized, source=source, calories_per_100g=cal)


def test_exact_match_wins_first():
    repo = FakeNutritionRepository([_row("Masala Dosa", "masala dosa")])
    lookup = build_nutrition_lookup(repo, StubApiSource(), _CannedSource(None))
    result = lookup.find("Masala Dosa")
    assert result.best.match_type == "exact" and result.best.reference.name == "Masala Dosa"


def test_fuzzy_when_no_exact():
    repo = FakeNutritionRepository([_row("Masala Dosa", "masala dosa")])
    lookup = build_nutrition_lookup(repo, StubApiSource(), _CannedSource(None))
    result = lookup.find("masala dosaa")  # typo — no exact row
    assert result.best.match_type == "fuzzy"


def test_websearch_fallback_caches_back():
    repo = FakeNutritionRepository([])  # nothing local
    canned = NutritionData(name="sushi", calories_per_100g=166.0, protein_per_100g=7.0)
    lookup = build_nutrition_lookup(repo, StubApiSource(), _CannedSource(canned))

    result = lookup.find("sushi")
    assert result.best.match_type == "websearch"
    assert result.best.reference.calories_per_100g == 166.0
    # self-improving: the found value is now a local row for next time
    cached = repo.get_by_normalized_name("sushi")
    assert cached is not None and cached.source == "websearch"


def test_total_miss_returns_no_candidates():
    repo = FakeNutritionRepository([])
    lookup = build_nutrition_lookup(repo, StubApiSource(), _CannedSource(None))
    assert lookup.find("nonexistent food").best is None
