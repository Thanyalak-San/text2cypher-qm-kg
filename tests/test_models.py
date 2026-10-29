"""Tests for harness/models (Claude adapter), with a fake client: no API call, no cost.

Checks the request sent (settings, tools, parallel calls off, no caching, API version), the translation of
neutral messages (including the C5 harness load), the reply read back (text, tool calls, tokens, stop
reason), and the retry rule: retryable errors are retried up to 5 times with backoff, others are not.

Usage:
    python tests/test_models.py
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import anthropic
import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X                      # noqa: E402
from harness.models.base import ApiFailure                          # noqa: E402
from harness.models.claude import API_VERSION, ClaudeAdapter, to_claude_messages   # noqa: E402

failures = 0
SETTINGS = C.load_models()["claude"]
TOOL = {"name": "execute_cypher_query", "description": "Execute a Cypher query.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def response(content, stop="tool_use", usage=None):
    u = usage or NS(input_tokens=1200, output_tokens=85, cache_read_input_tokens=0, cache_creation_input_tokens=None)
    r = NS(content=content, stop_reason=stop, usage=u, model="claude-sonnet-4-6")
    r._request_id = "req_test"
    return r


class FakeClient:
    """Returns or raises the given items in turn; records every request."""
    def __init__(self, *items):
        self.items, self.sent = list(items), []
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.sent.append(kwargs)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def adapter(*items):
    waits = []
    a = ClaudeAdapter(SETTINGS, client=FakeClient(*items), sleep=waits.append)
    return a, a.client, waits


def overloaded():
    return anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=REQ), body=None)


# ---------------------------------------------------------------- request
tool_reply = response([NS(type="text", text="Looking up machines."),
                       NS(type="tool_use", id="toolu_1", name="execute_cypher_query", input={"query": "MATCH (m) RETURN m"})])
a, client, _ = adapter(tool_reply)
r = a.call("SYSTEM", [{"role": "user", "text": "Which machines?"}], [TOOL])
sent = client.sent[0]
check("model, max_tokens and temperature from models.yaml",
      (sent["model"], sent["max_tokens"], sent["temperature"]) == ("claude-sonnet-4-6", 1024, 0))
check("system prompt sent as given", sent["system"] == "SYSTEM")
check("tools translated (parameters -> input_schema)",
      sent["tools"] == [{"name": TOOL["name"], "description": TOOL["description"], "input_schema": TOOL["parameters"]}])
check("parallel tool use off when there are tools", sent["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True})
check("no cache_control anywhere in the request", "cache_control" not in repr(sent))
check("question sent as the user message", sent["messages"] == [{"role": "user", "content": [{"type": "text", "text": "Which machines?"}]}])

a, client, _ = adapter(response([NS(type="text", text="```cypher\nMATCH (m) RETURN m\n```")], stop="end_turn"))
a.call("SYSTEM", [{"role": "user", "text": "Q"}], [])
check("driver configuration: no tools and no tool_choice sent", "tools" not in client.sent[0] and "tool_choice" not in client.sent[0])

# ---------------------------------------------------------------- reply
check("text read back", r.text == "Looking up machines.")
check("tool call read back", r.tool_calls == [{"id": "toolu_1", "name": "execute_cypher_query", "arguments": {"query": "MATCH (m) RETURN m"}}])
check("stop reason, tokens, model, request id read back",
      (r.stop_reason, r.input_tokens, r.output_tokens, r.cached_tokens, r.model_returned, r.request_id)
      == ("tool_use", 1200, 85, 0, "claude-sonnet-4-6", "req_test"))
check("API version recorded", r.api_version == API_VERSION == "2023-06-01")
check("one attempt, no wait", (r.attempts, r.retry_wait_s, r.errors) == (1, 0.0, []))
check("reply as a neutral assistant message",
      r.as_message() == {"role": "assistant", "text": "Looking up machines.", "tool_calls": r.tool_calls})
cut = adapter(response([NS(type="text", text="```cypher\nMATCH (m:Prod")], stop="max_tokens",
                       usage=NS(input_tokens=900, output_tokens=1024, cache_read_input_tokens=None, cache_creation_input_tokens=None)))[0]
cr = cut.call("S", [{"role": "user", "text": "Q"}], [])
check("max_tokens stop reason kept and marked cut off", cr.stop_reason == "max_tokens" and cr.cut_off)
check("a normal reply is not cut off", not r.cut_off)

# ---------------------------------------------------------------- messages
c5 = X.build(C.load(C.CONFIG_DIR / "C5.yaml"), "Which machines?")
m = to_claude_messages(c5.messages)
check("C5: question, then assistant tool_use, then user tool_result", [x["role"] for x in m] == ["user", "assistant", "user"])
check("C5: harness load sent as tool_use with the fixed id",
      m[1]["content"] == [{"type": "tool_use", "id": "harness_load", "name": "load_skill", "input": {"name": "neo4j-query"}}])
check("C5: skill body sent as the tool result", m[2]["content"][0] == {"type": "tool_result", "tool_use_id": "harness_load", "content": c5.messages[2]["content"]})
merged = to_claude_messages([{"role": "user", "text": "Q"},
                             {"role": "assistant", "text": None, "tool_calls": [{"id": "t1", "name": "load_skill", "arguments": {"name": "x"}}]},
                             {"role": "tool", "tool_call_id": "t1", "name": "load_skill", "content": "No skill with that name."},
                             {"role": "user", "text": "Request limit reached. Submit your query now."}])
check("tool result and a following text merged into one user message",
      len(merged) == 3 and [b["type"] for b in merged[2]["content"]] == ["tool_result", "text"])
check("assistant message without text has no empty text block", merged[1]["content"][0]["type"] == "tool_use")

# ---------------------------------------------------------------- retries
a, client, waits = adapter(overloaded(), anthropic.APIConnectionError(request=REQ), tool_reply)
r = a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
check("retryable errors retried, then success", r.attempts == 3 and len(client.sent) == 3)
check("backoff waits recorded (2 s, 4 s)", waits == [2, 4] and r.retry_wait_s == 6)
check("failed attempts' messages kept", len(r.errors) == 2 and r.errors[0].startswith("InternalServerError"))

a, client, waits = adapter(*[overloaded() for _ in range(5)])
try:
    a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
    check("5 failed attempts raise ApiFailure", False)
except ApiFailure:
    check("5 failed attempts raise ApiFailure", len(client.sent) == 5 and waits == [2, 4, 8, 16])

bad = anthropic.BadRequestError("bad", response=httpx.Response(400, request=REQ), body=None)
a, client, waits = adapter(bad)
try:
    a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
    check("a 400 error is not retried", False)
except anthropic.BadRequestError:
    check("a 400 error is not retried", len(client.sent) == 1 and waits == [])

# ---------------------------------------------------------------- client setup
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-not-used")
real = ClaudeAdapter(SETTINGS)
check("real client sends anthropic-version 2023-06-01", real.client.default_headers.get("anthropic-version") == "2023-06-01")
check("SDK retries off (the adapter retries)", real.client.max_retries == 0)
try:
    ClaudeAdapter({**SETTINGS, "caching": True}, client=FakeClient())
    check("caching on is refused", False)
except ValueError:
    check("caching on is refused", True)

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
