"""GPT adapter: the neutral format to the OpenAI Responses API and back.

Settings come from configurations/models.yaml (`gpt`): model snapshot, max_tokens (sent as
max_output_tokens), temperature 0, reasoning effort, parallel tool calls off, nothing stored at OpenAI.

Temperature (Appendix A): 0 is sent if the model accepts it. If the API rejects the parameter, the call is
repeated without it (the model's default) and later calls leave it out; the request settings stored with
each episode show which was used.

Neutral messages are translated as follows: the system prompt is sent as `instructions`; a user text
becomes a user message; an assistant message becomes an assistant text message (if it has text) and one
`function_call` item per tool call; a tool result becomes a `function_call_output` item.

A reply counts as cut off when the response is incomplete because it reached max_output_tokens.
Reasoning tokens are recorded, so any hidden reasoning despite effort `none` shows up in the records.
"""

from __future__ import annotations

import json
import time

import openai

from harness.models.base import BACKOFF_S, MAX_ATTEMPTS, ApiFailure, ModelReply

API = "openai-responses"
RETRYABLE = (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError, openai.APITimeoutError)


def to_gpt_input(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        elif m["role"] == "assistant":
            if m.get("text"):
                out.append({"role": "assistant", "content": m["text"]})
            out += [{"type": "function_call", "call_id": c["id"], "name": c["name"],
                     "arguments": json.dumps(c["arguments"], ensure_ascii=False)} for c in m.get("tool_calls", [])]
        elif m["role"] == "tool":
            out.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": m["content"]})
        else:
            raise ValueError(f"unknown role {m['role']!r}")
    return out


def to_gpt_tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["parameters"], "strict": False} for t in tools]


def _arguments(raw: str) -> dict:
    """Tool-call arguments arrive as a JSON string; unreadable JSON is kept under '_unparsed'."""
    try:
        args = json.loads(raw)
        return args if isinstance(args, dict) else {"_unparsed": raw}
    except json.JSONDecodeError:
        return {"_unparsed": raw}


def _rejects_temperature(e: openai.BadRequestError) -> bool:
    return "temperature" in str(e).lower()


class GptAdapter:
    name = "gpt"
    content_keys = ("instructions", "input", "tools")  # prompt content, stored in prompts.jsonl, not per episode

    def __init__(self, settings: dict, client: openai.OpenAI | None = None, sleep=time.sleep):
        if not settings.get("id"):
            raise ValueError("models.yaml: gpt id is not set")
        self.settings = settings
        self.model = settings["id"]
        self.send_temperature = settings.get("temperature") is not None
        # retries are done here (not by the SDK) so each attempt and wait is recorded
        self.client = client or openai.OpenAI(max_retries=0)
        self._sleep = sleep

    def request(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        """The exact keyword arguments sent to responses.create (also stored in the record)."""
        kwargs = {"model": self.model, "instructions": system, "input": to_gpt_input(messages),
                  "max_output_tokens": self.settings["max_tokens"], "store": False}
        if self.settings.get("reasoning_effort"):
            kwargs["reasoning"] = {"effort": self.settings["reasoning_effort"]}
        if self.send_temperature:
            kwargs["temperature"] = self.settings["temperature"]
        if tools:
            kwargs["tools"] = to_gpt_tools(tools)
            kwargs["parallel_tool_calls"] = bool(self.settings.get("parallel_tool_calls", False))
        return kwargs

    def call(self, system: str, messages: list[dict], tools: list[dict]) -> ModelReply:
        errors: list[str] = []
        waited = 0.0
        attempt = 0
        while attempt < MAX_ATTEMPTS:
            attempt += 1
            kwargs = self.request(system, messages, tools)
            start = time.perf_counter()
            try:
                response = self.client.responses.create(**kwargs)
            except openai.BadRequestError as e:
                if self.send_temperature and _rejects_temperature(e):
                    self.send_temperature = False          # use the model's default from now on (Appendix A)
                    errors.append(f"temperature rejected, using the default: {e}")
                    attempt -= 1                           # not an API failure
                    continue
                raise
            except RETRYABLE as e:
                errors.append(f"{type(e).__name__}: {e}")
                if attempt == MAX_ATTEMPTS:
                    raise ApiFailure(f"{MAX_ATTEMPTS} attempts failed; last: {errors[-1]}") from e
                wait = BACKOFF_S[attempt - 1]
                self._sleep(wait)
                waited += wait
                continue
            return self._reply(response, time.perf_counter() - start, attempt, waited, errors)
        raise AssertionError("unreachable")

    @staticmethod
    def _reply(response, seconds: float, attempt: int, waited: float, errors: list[str]) -> ModelReply:
        texts, calls = [], []
        for item in response.output:
            if item.type == "message":
                texts += [c.text for c in item.content if getattr(c, "type", "") == "output_text"]
            elif item.type == "function_call":
                calls.append({"id": item.call_id, "name": item.name, "arguments": _arguments(item.arguments)})
        reason = getattr(response.incomplete_details, "reason", None) if response.incomplete_details else None
        cut = response.status == "incomplete" and reason == "max_output_tokens"
        stop = reason if response.status == "incomplete" else ("tool_calls" if calls else response.status)
        u = response.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
        return ModelReply(text="\n".join(texts), tool_calls=calls, stop_reason=stop, cut_off=cut,
                          input_tokens=u.input_tokens, output_tokens=u.output_tokens, cached_tokens=cached,
                          model_returned=response.model, api_version=API,
                          request_id=getattr(response, "_request_id", None), seconds=seconds,
                          attempts=attempt, retry_wait_s=waited, errors=errors, reasoning_tokens=reasoning)
