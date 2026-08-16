import json

from app.adapters.nutrition_source import NutritionData, NutritionSource
from app.adapters.web_search import WebSearch
from app.llm.client import LLMClient

_PROMPT = (
    'From these web search snippets, give the best-estimate nutrition PER 100g for "{food}". '
    "Reply with ONLY compact JSON and nothing else: "
    '{{"calories":kcal,"protein":g,"carbs":g,"fat":g,"sugar":g}}. '
    "Use numbers only; use null for any value the snippets don't support.\n\nSnippets:\n{snippets}"
)


class WebSearchNutritionSource(NutritionSource):
    """Last-resort nutrition lookup: search the web, let the LLM reconcile the
    messy snippets into per-100g numbers. Best-effort — results always route to
    HITL confirmation (see needs_confirmation)."""

    source_name = "websearch"

    def __init__(self, web_search: WebSearch, llm: LLMClient) -> None:
        self._web_search = web_search
        self._llm = llm

    def lookup(self, food_name: str) -> NutritionData | None:
        results = self._web_search.search(
            f"{food_name} nutrition per 100g calories protein carbs fat sugar", max_results=6
        )
        if not results:
            return None
        snippets = "\n".join(f"{r.title}: {r.snippet}" for r in results)
        response = self._llm.complete(
            messages=[{"role": "user", "content": _PROMPT.format(food=food_name, snippets=snippets)}]
        )
        values = _parse_json(response.text or "")
        if values is None or values.get("calories") is None:
            return None  # no usable calorie figure -> treat as a miss
        return NutritionData(
            name=food_name,
            calories_per_100g=_as_number(values.get("calories")),
            protein_per_100g=_as_number(values.get("protein")),
            carbs_per_100g=_as_number(values.get("carbs")),
            fats_per_100g=_as_number(values.get("fat")),
            sugar_per_100g=_as_number(values.get("sugar")),
        )


def _parse_json(text: str) -> dict | None:
    # The model may wrap JSON in prose or ```fences``` — grab the outermost braces.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _as_number(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
