from app.agent.agent import Agent
from app.agent.tools import Tool, ToolRegistry
from app.llm.client import LLMResponse, ToolCall
from tests.fakes import ScriptedLLM


class EchoTool(Tool):
    name = "echo"
    description = "echo the text back"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    def run(self, context, *, text):
        return {"echoed": text}


def _assistant(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": "{}"}}
            for tc in tool_calls
        ]
    return message


def test_plain_reply_no_tool():
    llm = ScriptedLLM([LLMResponse(text="hi there", assistant_message=_assistant("hi there"))])
    agent = Agent(llm, ToolRegistry([EchoTool()]), system_prompt="sys")
    reply = agent.run(user_message="hello", context=None, history=[])
    assert reply.reply == "hi there"
    assert len(llm.calls) == 1


def test_tool_call_then_final_reply():
    call = ToolCall(id="t1", name="echo", arguments={"text": "yo"})
    llm = ScriptedLLM([
        LLMResponse(text=None, tool_calls=[call], assistant_message=_assistant(None, [call])),
        LLMResponse(text="done: yo", assistant_message=_assistant("done: yo")),
    ])
    agent = Agent(llm, ToolRegistry([EchoTool()]))
    reply = agent.run(user_message="echo yo", context=None, history=[])

    assert reply.reply == "done: yo"
    assert len(llm.calls) == 2  # one to call the tool, one to answer after it
    # the tool result was fed back as a tool-role message
    assert any(m.get("role") == "tool" for m in reply.history)


def test_history_is_threaded():
    llm = ScriptedLLM([LLMResponse(text="ok", assistant_message=_assistant("ok"))])
    agent = Agent(llm, ToolRegistry([EchoTool()]))
    reply = agent.run(user_message="remember this", context=None, history=[])
    assert reply.history[0] == {"role": "user", "content": "remember this"}
