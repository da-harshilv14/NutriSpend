import json
from dataclasses import dataclass, field

from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import ToolContext, ToolRegistry
from app.llm.client import LLMClient

# Safety cap so a misbehaving model can't loop on tool calls forever.
MAX_TOOL_ROUNDS = 6


@dataclass
class AgentReply:
    reply: str
    history: list[dict] = field(default_factory=list)  # conversation minus the system turn
    pending: dict | None = None  # structured HITL awaiting the user (candidates / estimate)
    receipts: list[dict] = field(default_factory=list)  # what got logged this turn (for the receipt card)


def _finalize_receipts(raw: list[dict]) -> list[dict]:
    """Turn the raw 'logged' tool results into receipt rows, folding an expense
    that was linked to a food (food_log_id) into one combined row."""
    foods = {r["food_log_id"]: r for r in raw if r["tool"] == "log_food"}
    linked: set[int] = {
        r.get("food_log_id") for r in raw
        if r["tool"] == "log_expense" and r.get("food_log_id") in foods
    }
    rows: list[dict] = []
    for r in raw:
        if r["tool"] == "log_food":
            if r.get("food_log_id") in linked:
                continue  # folded into its expense row below
            rows.append({"title": r.get("food") or "Food", "amount": None, "calories": r.get("calories")})
        else:  # log_expense
            fid = r.get("food_log_id")
            if fid in foods:
                food = foods[fid]
                rows.append({"title": food.get("food") or "Food", "amount": r.get("amount"), "calories": food.get("calories")})
            else:
                rows.append({"title": r.get("description") or r.get("category") or "Expense", "amount": r.get("amount"), "calories": None})
    return rows


class Agent:
    def __init__(self, llm: LLMClient, registry: ToolRegistry, system_prompt: str = SYSTEM_PROMPT) -> None:
        self._llm = llm
        self._registry = registry
        self._system_prompt = system_prompt

    def run(self, *, user_message: str, context: ToolContext, history: list[dict] | None = None) -> AgentReply:
        conversation: list[dict] = list(history or [])
        conversation.append({"role": "user", "content": user_message})
        pending: dict | None = None
        logged: list[dict] = []

        for _ in range(MAX_TOOL_ROUNDS):
            messages = [{"role": "system", "content": self._system_prompt}, *conversation]
            response = self._llm.complete(messages=messages, tools=self._registry.schemas())
            conversation.append(response.assistant_message)

            if not response.tool_calls:  # plain reply — done
                return AgentReply(reply=response.text or "", history=conversation,
                                  pending=pending, receipts=_finalize_receipts(logged))

            for call in response.tool_calls:
                result = self._registry.execute(call.name, context, call.arguments)
                if isinstance(result, dict):
                    if result.get("status") == "needs_confirmation":
                        pending = result  # awaiting the user's choice
                    elif result.get("status") == "logged":
                        logged.append({"tool": call.name, **result})
                        if call.name == "log_food":
                            pending = None  # a food was logged this turn — nothing left pending
                conversation.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                })

        return AgentReply(reply="(stopped after too many tool steps)", history=conversation,
                          pending=pending, receipts=_finalize_receipts(logged))
