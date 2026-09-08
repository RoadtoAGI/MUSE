"""Tool registry: register, lookup, dispatch, and schema export."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDef:
    """A registered tool."""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]


class ToolRegistry:
    """Central registry for tool definitions."""

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, name: str, description: str, parameters: dict[str, Any],
                 handler: Callable[[dict[str, Any]], str]) -> None:
        self._tools[name] = ToolDef(name=name, description=description,
                                     parameters=parameters, handler=handler)

    def dispatch(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool by name. Returns result string."""
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        try:
            return self._tools[name].handler(params)
        except Exception as e:
            return f"Error executing {name}: {e}"

    def get_schemas(self, allowed: list[str] | None = None) -> list[dict]:
        """Return OpenAI-format tool schemas, optionally filtered."""
        result = []
        for tool in self._tools.values():
            if allowed is not None and tool.name not in allowed:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return result
