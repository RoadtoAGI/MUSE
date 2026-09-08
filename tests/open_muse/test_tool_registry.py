"""Tests for tool registry."""
import pytest
from open_muse.tools.registry import ToolRegistry


def test_register_and_dispatch():
    registry = ToolRegistry()
    registry.register(
        name="echo",
        description="Echo input back",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=lambda params: params["text"],
    )
    result = registry.dispatch("echo", {"text": "hello"})
    assert result == "hello"


def test_dispatch_unknown_tool():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.dispatch("nonexistent", {})


def test_get_schemas():
    registry = ToolRegistry()
    registry.register(name="tool_a", description="Tool A",
        parameters={"type": "object", "properties": {}}, handler=lambda params: "a")
    registry.register(name="tool_b", description="Tool B",
        parameters={"type": "object", "properties": {}}, handler=lambda params: "b")

    schemas = registry.get_schemas()
    assert len(schemas) == 2
    assert schemas[0]["function"]["name"] == "tool_a"
    assert schemas[1]["function"]["name"] == "tool_b"


def test_get_schemas_filtered():
    registry = ToolRegistry()
    for name in ["tool_a", "tool_b", "tool_c"]:
        registry.register(name=name, description=name, parameters={}, handler=lambda p: name)

    schemas = registry.get_schemas(allowed=["tool_a", "tool_c"])
    assert len(schemas) == 2
    names = [s["function"]["name"] for s in schemas]
    assert "tool_b" not in names


def test_handler_error_returns_error_string():
    registry = ToolRegistry()
    def bad_handler(params):
        raise ValueError("boom")
    registry.register(name="failing", description="Always fails", parameters={}, handler=bad_handler)
    result = registry.dispatch("failing", {})
    assert "Error" in result
