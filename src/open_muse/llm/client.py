"""LLM client with tool_use support. All providers use OpenAI-compatible API.

Uses streaming by default because some OpenAI-compatible services return
null content or tool calls in non-streaming responses.
"""
from __future__ import annotations

import json
import time
import sys
from typing import Any
import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError

from open_muse.core.types import Message, ToolCall

# Errors that indicate a broken stream (connection drop mid-response)
_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, httpx.RemoteProtocolError, httpx.ReadError)


class LLMClient:
    """LLM client for OpenAI-compatible endpoints with tool_use."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 1800):
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.last_call_info: dict | None = None

    def chat(
        self,
        model: str,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tool_choice: str | None = None,
    ) -> Message:
        """Send messages to LLM, return assistant response with optional tool_calls.

        Always uses streaming to handle providers whose non-streaming responses
        omit content or tool calls.
        """
        oai_messages = [self._to_openai_message(m) for m in messages]

        kwargs: dict[str, Any] = dict(
            model=model, messages=oai_messages,
            max_tokens=max_tokens, temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        max_retries = 3
        last_error = None

        for retry in range(max_retries):
            t0 = time.perf_counter()
            try:
                stream = self._client.chat.completions.create(**kwargs)

                # Accumulate streamed chunks
                content_parts: list[str] = []
                # tool_calls indexed by position: {index: {id, name, arguments_parts}}
                tc_accum: dict[int, dict] = {}
                finish_reason = None
                response_model = model
                prompt_tokens = 0
                completion_tokens = 0

                for chunk in stream:
                    # Usage comes in the final chunk (with choices=[])
                    if chunk.usage:
                        prompt_tokens = chunk.usage.prompt_tokens or 0
                        completion_tokens = chunk.usage.completion_tokens or 0

                    if not chunk.choices:
                        if chunk.model:
                            response_model = chunk.model
                        continue

                    delta = chunk.choices[0].delta
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                    if chunk.model:
                        response_model = chunk.model

                    # Accumulate content
                    if delta and delta.content:
                        content_parts.append(delta.content)

                    # Accumulate tool calls
                    if delta and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tc_accum:
                                tc_accum[idx] = {"id": "", "name": "", "arguments_parts": []}
                            if tc_delta.id:
                                tc_accum[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tc_accum[idx]["name"] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tc_accum[idx]["arguments_parts"].append(tc_delta.function.arguments)

                # Stream completed successfully — break out of retry loop
                break

            except _RETRYABLE_ERRORS as e:
                last_error = e
                wait = 2 ** retry * 5  # 5s, 10s, 20s
                print(f"[LLMClient] Stream error (attempt {retry+1}/{max_retries}): {e}. Retrying in {wait}s...",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            except APIStatusError as e:
                if e.status_code in (500, 502, 503, 529):
                    last_error = e
                    wait = 2 ** retry * 5
                    print(f"[LLMClient] API {e.status_code} (attempt {retry+1}/{max_retries}). Retrying in {wait}s...",
                          file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
        else:
            # All retries exhausted
            raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_error}") from last_error

        duration_s = time.perf_counter() - t0

        # Build tool calls
        tool_calls = []
        for idx in sorted(tc_accum):
            tc_data = tc_accum[idx]
            args_str = "".join(tc_data["arguments_parts"])
            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                # Truncated stream — try to salvage by closing the JSON string
                print(f"[LLMClient] WARNING: truncated tool_call arguments for {tc_data['name']}, "
                      f"attempting repair ({len(args_str)} chars)", file=sys.stderr)
                # Most common case: unclosed string value in {"content": "...
                repaired = args_str.rstrip()
                if not repaired.endswith('}'):
                    repaired += '"}'
                try:
                    args = json.loads(repaired)
                except json.JSONDecodeError:
                    args = {"_raw_truncated": args_str[:500] + "...", "_error": "truncated_arguments"}
            tool_calls.append(ToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                arguments=args,
            ))

        self.last_call_info = {
            "model": response_model,
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
            },
            "duration_s": round(duration_s, 3),
            "finish_reason": finish_reason,
        }

        return Message(
            role="assistant",
            content="".join(content_parts),
            tool_calls=tool_calls,
        )

    @staticmethod
    def _to_openai_message(msg: Message) -> dict:
        """Convert neutral Message to OpenAI API format."""
        if msg.role == "tool":
            return {"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content}
        if msg.role == "assistant" and msg.tool_calls:
            return {
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                    for tc in msg.tool_calls
                ],
            }
        return {"role": msg.role, "content": msg.content}
