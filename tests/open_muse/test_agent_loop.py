"""Tests for agent loop mechanics using a test double."""
import pytest
from open_muse.core.agent_loop import AgentLoop
from open_muse.core.types import Message, ToolCall
from open_muse.tools.registry import ToolRegistry


class FakeLLMClient:
    """Test double that returns pre-scripted responses."""
    def __init__(self, responses: list[Message]):
        self._responses = list(responses)
        self._call_count = 0

    def chat(self, model, messages, tools=None, **kwargs) -> Message:
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


def test_loop_no_tools():
    """LLM responds with text only — loop ends after one turn."""
    client = FakeLLMClient([Message(role="assistant", content="Hello!")])
    registry = ToolRegistry()
    loop = AgentLoop(client=client, registry=registry, model="test")

    result = loop.run(
        system_prompt="You are a helper.",
        messages=[Message(role="user", content="Hi")],
    )
    assert result.content == "Hello!"
    assert client._call_count == 1


def test_loop_with_tool_call():
    """LLM calls a tool, gets result, then responds with text."""
    client = FakeLLMClient([
        Message(role="assistant", content="", tool_calls=[
            ToolCall(id="tc_1", name="echo", arguments={"text": "world"}),
        ]),
        Message(role="assistant", content="Done: world"),
    ])

    registry = ToolRegistry()
    registry.register(
        name="echo", description="Echo",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=lambda params: params["text"],
    )

    loop = AgentLoop(client=client, registry=registry, model="test")
    result = loop.run(
        system_prompt="System",
        messages=[Message(role="user", content="echo world")],
    )

    assert result.content == "Done: world"
    assert client._call_count == 2


def test_loop_max_turns():
    """Loop should stop after max_turns even if LLM keeps calling tools."""
    responses = [
        Message(role="assistant", content="", tool_calls=[
            ToolCall(id=f"tc_{i}", name="echo", arguments={"text": "loop"}),
        ])
        for i in range(20)
    ]
    client = FakeLLMClient(responses)

    registry = ToolRegistry()
    registry.register(name="echo", description="Echo", parameters={},
                      handler=lambda params: "ok")

    loop = AgentLoop(client=client, registry=registry, model="test")
    result = loop.run(
        system_prompt="System",
        messages=[Message(role="user", content="go")],
        max_turns=3,
    )
    assert client._call_count == 3
