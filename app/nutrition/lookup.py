from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.adapters.nutrition_source import NutritionSource
from app.db.models import NutritionReference, UserFood
from app.nutrition.text import normalize_name
from app.repos.interfaces import NutritionRepository, UserFoodRepository

# A fuzzy hit is trusted outright only above this score; below it (or when the
# top two are near-tied) HITL confirmation kicks in — the EDA lesson encoded.
CONFIDENT_SCORE = 0.8
AMBIGUOUS_GAP = 0.1
# Web/api-sourced values are best-effort guesses — always confirm them, even on
# a later exact match, until a user has verified one by logging it.
UNVERIFIED_SOURCES = ("websearch", "api")


@dataclass(frozen=True)
class NutritionCandidate:
    reference: NutritionReference | UserFood
    score: float
    match_type: str  # 'personal' | 'exact' | 'fuzzy' | 'api' | 'websearch'
    origin: str = "reference"  # 'user' (personal food) | 'reference' (shared)


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
    if best.match_type == "personal":
        return False  # the user's own saved food — trust it outright
    if best.reference.source in UNVERIFIED_SOURCES:
        return True  # web/api guess — confirm regardless of how it matched
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
    def handle(self, query: str, user_id: int | None) -> list[NutritionCandidate]: ...

    def _delegate(self, query: str, user_id: int | None) -> list[NutritionCandidate]:
        return self._next.handle(query, user_id) if self._next else []


class PersonalFoodLink(NutritionLookupLink):
    """Head of the chain: the user's own foods win over the shared dataset.
    Returns at most one candidate (exact, else a strong fuzzy hit)."""

    def __init__(
        self,
        user_food_repo: UserFoodRepository,
        next_link: NutritionLookupLink | None = None,
        *,
        accept_score: float = 0.6,
    ) -> None:
        super().__init__(next_link)
        self._repo = user_food_repo
        self._accept_score = accept_score

    def handle(self, query: str, user_id: int | None) -> list[NutritionCandidate]:
        if user_id is None:
            return self._delegate(query, user_id)
        match = self._repo.get_by_normalized_name(user_id, query)
        if match is not None:
            return [NutritionCandidate(reference=match, score=1.0, match_type="personal", origin="user")]
        scored = self._repo.search_fuzzy(user_id, query, limit=1)
        if scored and scored[0][1] >= self._accept_score:
            food, score = scored[0]
            return [NutritionCandidate(reference=food, score=score, match_type="personal", origin="user")]
        return self._delegate(query, user_id)


class ExactMatchLink(NutritionLookupLink):
    def __init__(self, repo: NutritionRepository, next_link: NutritionLookupLink | None = None) -> None:
        super().__init__(next_link)
        self._repo = repo

    def handle(self, query: str, user_id: int | None) -> list[NutritionCandidate]:
        match = self._repo.get_by_normalized_name(query)
        if match is None:
            return self._delegate(query, user_id)
        return [NutritionCandidate(reference=match, score=1.0, match_type="exact", origin="reference")]


class FuzzyMatchLink(NutritionLookupLink):
    def __init__(
        self,
        repo: NutritionRepository,
        next_link: NutritionLookupLink | None = None,
        *,
        limit: int = 6,
        threshold: float = 0.3,
        accept_score: float = 0.48,
    ) -> None:
        super().__init__(next_link)
        self._repo = repo
        self._limit = limit
        self._threshold = threshold
        # If the best fuzzy match is weaker than this, the dataset has nothing
        # close (e.g. "paneer dum biryani" only weakly hits "Paneer kheer") — fall
        # through to a web estimate instead of offering a wrong chip.
        self._accept_score = accept_score

    def handle(self, query: str, user_id: int | None) -> list[NutritionCandidate]:
        scored = self._repo.search_fuzzy(query, limit=self._limit, threshold=self._threshold)
        if not scored or scored[0][1] < self._accept_score:
            return self._delegate(query, user_id)
        return [
            NutritionCandidate(reference=reference, score=score, match_type="fuzzy", origin="reference")
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

    def handle(self, query: str, user_id: int | None) -> list[NutritionCandidate]:
        data = self._source.lookup(query)
        if data is None:
            return self._delegate(query, user_id)
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
        return [
            NutritionCandidate(
                reference=reference,
                score=1.0,
                match_type=self._source.source_name,
                origin="reference",
            )
        ]


class NutritionLookup:
    def __init__(self, head: NutritionLookupLink) -> None:
        self._head = head

    def find(self, food_name: str, user_id: int | None = None) -> LookupResult:
        query = normalize_name(food_name)
        return LookupResult(query=food_name, candidates=self._head.handle(query, user_id))


def build_nutrition_lookup(
    repo: NutritionRepository,
    user_food_repo: UserFoodRepository,
    api_source: NutritionSource,
    websearch_source: NutritionSource,
) -> NutritionLookup:
    # Personal first, then cheapest / most reliable: exact -> fuzzy -> api -> websearch.
    websearch = ExternalSourceLink(websearch_source, repo)
    api = ExternalSourceLink(api_source, repo, websearch)
    fuzzy = FuzzyMatchLink(repo, api)
    exact = ExactMatchLink(repo, fuzzy)
    personal = PersonalFoodLink(user_food_repo, exact)
    return NutritionLookup(personal)
