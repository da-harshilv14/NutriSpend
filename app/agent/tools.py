from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.adapters.web_search import WebSearch
from app.core.dates import resolve_period
from app.services.expense_service import ExpenseService
from app.services.food_service import FoodService
from app.services.nutrition_service import NutritionService


@dataclass
class ToolContext:
    """Per-request state a tool needs. user_id is injected here, not by the
    model, so the model can never act on another user's data."""

    user_id: int
    food_service: FoodService
    expense_service: ExpenseService
    nutrition_service: NutritionService


class Tool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments

    @abstractmethod
    def run(self, context: ToolContext, **arguments) -> dict: ...

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LogExpenseTool(Tool):
    name = "log_expense"
    description = "Record a spending expense for today (amount is in Indian Rupees)."
    parameters = {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "amount spent in rupees"},
            "category": {"type": "string", "description": "e.g. food, transport, groceries"},
            "description": {"type": "string", "description": "short note on what it was for"},
            "food_log_id": {"type": "integer", "description": "if this spend was for a food you just logged, pass its food_log_id to link them into one entry"},
        },
        "required": ["amount"],
    }

    def run(self, context: ToolContext, *, amount, category=None, description=None, food_log_id=None) -> dict:
        entry = context.expense_service.log_expense(
            user_id=context.user_id, amount=amount, category=category,
            description=description, food_log_id=food_log_id,
        )
        return {"status": "logged", "expense_id": entry.id, "amount": float(entry.amount),
                "category": entry.category, "description": entry.description,
                "food_log_id": entry.food_log_id}


class LogFoodTool(Tool):
    name = "log_food"
    description = (
        "Record a food the user ate. Give food_name and portion_text (e.g. '2 bowls'). "
        "If the result is 'needs_confirmation', ask the user which candidate they meant, "
        "then call this again with the chosen nutrition_id and the same portion_text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "food_name": {"type": "string", "description": "what the user ate"},
            "portion_text": {"type": "string", "description": "portion, e.g. '2 bowls', '200g'"},
            "nutrition_id": {"type": "integer", "description": "chosen candidate id (only after confirmation)"},
        },
        "required": [],
    }

    def run(self, context: ToolContext, *, food_name=None, portion_text="1 serving", nutrition_id=None) -> dict:
        if nutrition_id is not None:
            entry = context.food_service.log_food(
                user_id=context.user_id, nutrition_id=nutrition_id, portion_text=portion_text
            )
            return self._logged(entry, name=context.food_service.reference_name(entry.nutrition_id))

        preview = context.food_service.preview_food(food_name=food_name, portion_text=portion_text)
        if preview.needs_confirmation:
            best_source = preview.lookup.best.reference.source if preview.lookup.best else None
            candidate_count = len(preview.lookup.candidates)
            # Estimate card only for a lone web-sourced guess; if there are several
            # options, show them all as pickable chips even when the top is web-sourced.
            kind = "estimate" if (best_source in ("websearch", "api") and candidate_count == 1) else "candidates"
            return {
                "status": "needs_confirmation",
                "kind": kind,  # 'candidates' (pick one) | 'estimate' (web guess, confirm)
                "food_name": food_name,
                "portion_text": portion_text,
                "portion_grams": preview.portion.grams,
                "estimated_for_portion": preview.snapshot,  # nutrients for the top candidate at this portion
                "candidates": [
                    {
                        "nutrition_id": c.reference.id,
                        "name": c.reference.name,
                        "source": c.reference.source,  # 'websearch' = rough web estimate
                        "calories_per_100g": c.reference.calories_per_100g,
                        "score": round(c.score, 2),
                    }
                    for c in preview.lookup.candidates[:5]
                ],
            }
        best = preview.lookup.best
        entry = context.food_service.log_food(
            user_id=context.user_id, nutrition_id=best.reference.id, portion_text=portion_text
        )
        return self._logged(entry, name=best.reference.name)

    @staticmethod
    def _logged(entry, name=None) -> dict:
        return {"status": "logged", "food_log_id": entry.id, "food": name,
                "grams": entry.quantity_grams, "calories": entry.calories, "protein": entry.protein}


class LookupNutritionTool(Tool):
    name = "lookup_nutrition"
    description = "Look up nutrition (per 100g) for a food without logging it."
    parameters = {
        "type": "object",
        "properties": {"food_name": {"type": "string"}},
        "required": ["food_name"],
    }

    def run(self, context: ToolContext, *, food_name) -> dict:
        result = context.nutrition_service.find(food_name)
        return {
            "candidates": [
                {
                    "name": c.reference.name,
                    "calories_per_100g": c.reference.calories_per_100g,
                    "protein_per_100g": c.reference.protein_per_100g,
                    "match": c.match_type,
                    "score": round(c.score, 2),
                }
                for c in result.candidates[:5]
            ]
        }


class QuerySummaryTool(Tool):
    name = "query_summary"
    description = "Summarize the user's spending or calories for today or this week."
    parameters = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["spend", "calories"]},
            "period": {"type": "string", "enum": ["today", "week"]},
        },
        "required": ["kind", "period"],
    }

    def run(self, context: ToolContext, *, kind, period) -> dict:
        start, end = resolve_period(period)
        if kind == "calories":
            return context.food_service.summary(user_id=context.user_id, start=start, end=end)
        return context.expense_service.summary(user_id=context.user_id, start=start, end=end)


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for current or general information (news, facts, prices, etc.). Returns titles and snippets to answer from."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "what to search for"}},
        "required": ["query"],
    }

    def __init__(self, web_search: WebSearch) -> None:
        self._web_search = web_search

    def run(self, context: ToolContext, *, query) -> dict:
        results = self._web_search.search(query, max_results=5)
        return {"results": [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]}


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, context: ToolContext, arguments: dict) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return tool.run(context, **arguments)
        except Exception as exc:  # surfaced to the model as a tool error, not a crash
            return {"error": f"{type(exc).__name__}: {exc}"}


def build_default_registry(web_search: WebSearch) -> ToolRegistry:
    return ToolRegistry([
        LogExpenseTool(),
        LogFoodTool(),
        LookupNutritionTool(),
        QuerySummaryTool(),
        WebSearchTool(web_search),
    ])
