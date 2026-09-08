"""Shared types for Open-MUSE agent system."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """Provider-independent message format."""
    role: str                          # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""             # only for role="tool"
    name: str = ""                     # tool name, only for role="tool"


@dataclass
class ToolCall:
    """A single tool invocation from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_call_id: str
    name: str
    content: str
    success: bool = True
