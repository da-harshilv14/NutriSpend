import json

from openai import OpenAI

from app.core.observability import record_llm_call
from app.llm.client import LLMClient, LLMResponse, ToolCall


class OpenAICompatibleAdapter(LLMClient):
    """Talks to any OpenAI-compatible chat-completions endpoint (here, the
    aicredits.in gateway serving a Claude model)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = 1024,
        timeout: float = 30.0,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=1, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, *, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        kwargs: dict = {"model": self._model, "messages": messages, "max_tokens": self._max_tokens}
        if tools:
            kwargs["tools"] = tools
        record_llm_call()
        completion = self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message

        tool_calls: list[ToolCall] = []
        for raw in message.tool_calls or []:
            try:
                arguments = json.loads(raw.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(ToolCall(id=raw.id, name=raw.function.name, arguments=arguments))

        assistant_message: dict = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": raw.id,
                    "type": "function",
                    "function": {"name": raw.function.name, "arguments": raw.function.arguments},
                }
                for raw in message.tool_calls
            ]

        return LLMResponse(text=message.content, tool_calls=tool_calls, assistant_message=assistant_message)
