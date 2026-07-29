from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.adapters.nutrition_source import NutritionSource
from app.db.models import NutritionReference
from app.nutrition.text import normalize_name
from app.repos.interfaces import NutritionRepository

# A fuzzy hit is trusted outright only above this score; below it (or when the
# top two are near-tied) HITL confirmation kicks in — the EDA lesson encoded.
CONFIDENT_SCORE = 0.8
AMBIGUOUS_GAP = 0.1


@dataclass(frozen=True)
class NutritionCandidate:
    reference: NutritionReference
    score: float
    match_type: str  # 'exact' | 'fuzzy' | 'api' | 'websearch'


@dataclass(frozen=True)
class LookupResult:
    query: str
    candidates: list[NutritionCandidate]

    @property
    def best(self) -> NutritionCandidate | None:
        return self.candidates[0] if self.candidates else None


def needs_confirmation(result: LookupResult) -> bool:
    best = result.best
    if best is None:
        return True  # nothing found — must ask the user
    if best.match_type == "exact":
        return False
    if best.score < CONFIDENT_SCORE:
        return True
    if len(result.candidates) > 1:
        runner_up = result.candidates[1]
        if best.score - runner_up.score < AMBIGUOUS_GAP:
            return True  # too close to call between the top two
    return False


class NutritionLookupLink(ABC):
    def __init__(self, next_link: "NutritionLookupLink | None" = None) -> None:
        self._next = next_link

    @abstractmethod
    def handle(self, query: str) -> list[NutritionCandidate]: ...

    def _delegate(self, query: str) -> list[NutritionCandidate]:
        return self._next.handle(query) if self._next else []


class ExactMatchLink(NutritionLookupLink):
    def __init__(self, repo: NutritionRepository, next_link: NutritionLookupLink | None = None) -> None:
        super().__init__(next_link)
        self._repo = repo

    def handle(self, query: str) -> list[NutritionCandidate]:
        match = self._repo.get_by_normalized_name(query)
        if match is None:
            return self._delegate(query)
        return [NutritionCandidate(reference=match, score=1.0, match_type="exact")]


class FuzzyMatchLink(NutritionLookupLink):
    def __init__(
        self,
        repo: NutritionRepository,
        next_link: NutritionLookupLink | None = None,
        *,
        limit: int = 5,
        threshold: float = 0.3,
    ) -> None:
        super().__init__(next_link)
        self._repo = repo
        self._limit = limit
        self._threshold = threshold

    def handle(self, query: str) -> list[NutritionCandidate]:
        scored = self._repo.search_fuzzy(query, limit=self._limit, threshold=self._threshold)
        if not scored:
            return self._delegate(query)
        return [
            NutritionCandidate(reference=reference, score=score, match_type="fuzzy")
            for reference, score in scored
        ]


class ExternalSourceLink(NutritionLookupLink):
    """Look a food up via an external source; on success cache it back so the
    next lookup is served locally (the self-improving path)."""

    def __init__(
        self,
        source: NutritionSource,
        repo: NutritionRepository,
        next_link: NutritionLookupLink | None = None,
    ) -> None:
        super().__init__(next_link)
        self._source = source
        self._repo = repo

    def handle(self, query: str) -> list[NutritionCandidate]:
        data = self._source.lookup(query)
        if data is None:
            return self._delegate(query)
        reference = self._repo.add(
            NutritionReference(
                name=data.name,
                name_normalized=normalize_name(data.name),
                calories_per_100g=data.calories_per_100g,
                protein_per_100g=data.protein_per_100g,
                carbs_per_100g=data.carbs_per_100g,
                fats_per_100g=data.fats_per_100g,
                sugar_per_100g=data.sugar_per_100g,
                source=self._source.source_name,
            )
        )
        return [NutritionCandidate(reference=reference, score=1.0, match_type=self._source.source_name)]


class NutritionLookup:
    def __init__(self, head: NutritionLookupLink) -> None:
        self._head = head

    def find(self, food_name: str) -> LookupResult:
        query = normalize_name(food_name)
        return LookupResult(query=food_name, candidates=self._head.handle(query))


def build_nutrition_lookup(
    repo: NutritionRepository,
    api_source: NutritionSource,
    websearch_source: NutritionSource,
) -> NutritionLookup:
    # Cheapest / most reliable first: exact -> fuzzy -> api -> websearch.
    websearch = ExternalSourceLink(websearch_source, repo)
    api = ExternalSourceLink(api_source, repo, websearch)
    fuzzy = FuzzyMatchLink(repo, api)
    exact = ExactMatchLink(repo, fuzzy)
    return NutritionLookup(exact)
