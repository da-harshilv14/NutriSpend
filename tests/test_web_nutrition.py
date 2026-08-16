from app.adapters.web_nutrition_source import WebSearchNutritionSource
from app.adapters.web_search import SearchResult
from app.llm.client import LLMResponse
from tests.fakes import FakeWebSearch, ScriptedLLM


def test_extracts_per_100g_from_fenced_json():
    web = FakeWebSearch([SearchResult("t", "u", "sushi ~166 kcal per 100g")])
    llm = ScriptedLLM([LLMResponse(text='```json\n{"calories":166,"protein":7,"carbs":30,"fat":5,"sugar":null}\n```')])
    data = WebSearchNutritionSource(web, llm).lookup("sushi")
    assert data is not None
    assert data.calories_per_100g == 166 and data.fats_per_100g == 5 and data.sugar_per_100g is None


def test_no_search_results_is_a_miss():
    source = WebSearchNutritionSource(FakeWebSearch([]), ScriptedLLM([]))
    assert source.lookup("anything") is None


def test_no_calories_is_a_miss():
    web = FakeWebSearch([SearchResult("t", "u", "no numbers here")])
    llm = ScriptedLLM([LLMResponse(text='{"calories":null,"protein":null}')])
    assert WebSearchNutritionSource(web, llm).lookup("mystery") is None
