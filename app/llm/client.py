from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The assistant turn in wire format, to append back to the message history
    # so the model sees its own tool calls on the next round.
    assistant_message: dict = field(default_factory=dict)


class LLMClient(ABC):
    """One narrow seam for all model calls. Swapping providers = new adapter."""

    @abstractmethod
    def complete(self, *, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse: ...
