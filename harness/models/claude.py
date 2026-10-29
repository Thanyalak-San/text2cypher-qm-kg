"""Claude adapter: the neutral format to the Anthropic Messages API and back.

Settings come from configurations/models.yaml (`claude`): model, max_tokens, temperature 0, no caching,
parallel tool use off when the request has tools.

API version: 2023-06-01 (author's decision, 2026-10-22, docs/audit.md). Version 2026-10-21 rejects any
request that sends `temperature`, and the study fixes temperature at 0 as in the published runs. The
version is sent explicitly and recorded in every reply; the SDK must stay below 2.0 (its 2.x releases
default to 2026-10-21 and drop `temperature`).

Neutral messages are translated as follows: a user text becomes a user message; an assistant message
becomes text and tool_use blocks; tool results become tool_result blocks in the next user message
(consecutive tool results and texts after them are merged into that one user message).
"""

from __future__ import annotations

import time

import anthropic

from harness.models.base import BACKOFF_S, MAX_ATTEMPTS, ApiFailure, ModelReply

API_VERSION = "2023-06-01"
RETRYABLE = (anthropic.RateLimitError, anthropic.InternalServerError,
             anthropic.APIConnectionError, anthropic.APITimeoutError)


def check_sdk() -> None:
    major = int(anthropic.__version__.split(".")[0])
    if major >= 2:
        raise RuntimeError(f"anthropic {anthropic.__version__} defaults to API version 2026-10-21, which rejects "
                           f"temperature; install anthropic<2 (the harness was built on 0.116.0).")


def to_claude_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m["role"] == "assistant":
            content = ([{"type": "text", "text": m["text"]}] if m.get("text") else [])
            content += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                        for c in m.get("tool_calls", [])]
            out.append({"role": "assistant", "content": content})
            continue
        if m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
        elif m["role"] == "user":
            block = {"type": "text", "text": m["text"]}
        else:
            raise ValueError(f"unknown role {m['role']!r}")
        if out and out[-1]["role"] == "user":
            out[-1]["content"].append(block)
        else:
            out.append({"role": "user", "content": [block]})
    return out


def to_claude_tools(tools: list[dict]) -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]


class ClaudeAdapter:
    name = "claude"
    content_keys = ("system", "messages", "tools")    # prompt content, stored in prompts.jsonl, not per episode

    def __init__(self, settings: dict, client: anthropic.Anthropic | None = None, sleep=time.sleep):
        check_sdk()
        if settings.get("caching"):
            raise ValueError("caching must stay off for Claude (Appendix A)")
        self.settings = settings
        self.model = settings["id"]
        # retries are done here (not by the SDK) so each attempt and wait is recorded
        self.client = client or anthropic.Anthropic(max_retries=0, default_headers={"anthropic-version": API_VERSION})
        self._sleep = sleep

    def request(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        """The exact keyword arguments sent to messages.create (also stored in the record)."""
        kwargs = {"model": self.model, "max_tokens": self.settings["max_tokens"],
                  "temperature": self.settings["temperature"], "system": system,
                  "messages": to_claude_messages(messages)}
        if tools:
            kwargs["tools"] = to_claude_tools(tools)
            if self.settings.get("disable_parallel_tool_use"):
                kwargs["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
        return kwargs

    def call(self, system: str, messages: list[dict], tools: list[dict]) -> ModelReply:
        kwargs = self.request(system, messages, tools)
        errors: list[str] = []
        waited = 0.0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.perf_counter()
            try:
                response = self.client.messages.create(**kwargs)
            except RETRYABLE as e:
                errors.append(f"{type(e).__name__}: {e}")
                if attempt == MAX_ATTEMPTS:
                    raise ApiFailure(f"{MAX_ATTEMPTS} attempts failed; last: {errors[-1]}") from e
                wait = BACKOFF_S[attempt - 1]
                self._sleep(wait)
                waited += wait
                continue
            seconds = time.perf_counter() - start
            return self._reply(response, seconds, attempt, waited, errors)
        raise AssertionError("unreachable")

    @staticmethod
    def _reply(response, seconds: float, attempt: int, waited: float, errors: list[str]) -> ModelReply:
        text = "\n".join(b.text for b in response.content if b.type == "text")
        calls = [{"id": b.id, "name": b.name, "arguments": dict(b.input)} for b in response.content if b.type == "tool_use"]
        u = response.usage
        cached = (getattr(u, "cache_read_input_tokens", 0) or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        return ModelReply(text=text, tool_calls=calls, stop_reason=response.stop_reason,
                          cut_off=response.stop_reason == "max_tokens",
                          input_tokens=u.input_tokens, output_tokens=u.output_tokens, cached_tokens=cached,
                          model_returned=response.model, api_version=API_VERSION,
                          request_id=getattr(response, "_request_id", None), seconds=seconds,
                          attempts=attempt, retry_wait_s=waited, errors=errors)
