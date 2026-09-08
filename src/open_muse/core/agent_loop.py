"""Agent loop: message -> LLM -> tool_call -> dispatch -> repeat."""
from __future__ import annotations

from open_muse.core.types import Message
from open_muse.tools.registry import ToolRegistry


class AgentLoop:
    """Core agent conversation loop with tool dispatch."""

    def __init__(self, client, registry: ToolRegistry, model: str, logger=None):
        self._client = client
        self._registry = registry
        self._model = model
        self._logger = logger

    def run(
        self,
        system_prompt: str,
        messages: list[Message],
        allowed_tools: list[str] | None = None,
        max_turns: int = 10,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tool_choice: str = "auto",
    ) -> Message:
        """Run the agent loop until no tool_calls or max_turns reached.

        Returns the final assistant Message.
        """
        full_messages = [Message(role="system", content=system_prompt)] + messages

        tool_schemas = self._registry.get_schemas(allowed=allowed_tools)

        last_response = None

        for turn in range(max_turns):
            if self._logger:
                self._logger.llm_call(turn=turn + 1)

            # Use tool_choice="required" only on first turn; auto on subsequent
            effective_tool_choice = tool_choice if turn == 0 else "auto"

            response = self._client.chat(
                model=self._model,
                messages=full_messages,
                tools=tool_schemas if tool_schemas else None,
                temperature=temperature,
                max_tokens=max_tokens,
                tool_choice=effective_tool_choice if tool_schemas else None,
            )

            full_messages.append(response)
            last_response = response

            # Log finish_reason for diagnostics
            if self._logger and hasattr(self._client, "last_call_info") and self._client.last_call_info:
                info = self._client.last_call_info
                self._logger.emit("llm_result", turn=turn + 1,
                                  finish_reason=info.get("finish_reason"),
                                  completion_tokens=info.get("tokens", {}).get("completion"))

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                if self._logger:
                    self._logger.tool_call(tc.name, tc.arguments)
                result = self._registry.dispatch(tc.name, tc.arguments)
                if self._logger:
                    self._logger.tool_result(tc.name, result)
                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
                full_messages.append(tool_msg)

        return last_response
