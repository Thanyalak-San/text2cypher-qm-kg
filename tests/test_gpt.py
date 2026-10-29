"""Tests for harness/models/gpt.py with a fake client: no API call, no cost.

Checks the request sent (model snapshot, instructions, max_output_tokens, temperature 0, reasoning effort,
parallel tool calls off, nothing stored), the translation of neutral messages (including the C5 harness
load), the reply read back (text, tool calls with JSON arguments, tokens incl. cached and reasoning, cut
off), the temperature fallback (Appendix A), and the retry rule.

Usage:
    python tests/test_gpt.py
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X                       # noqa: E402
from harness.models.base import ApiFailure                           # noqa: E402
from harness.models.gpt import API, GptAdapter, to_gpt_input         # noqa: E402

failures = 0
SETTINGS = C.load_models()["gpt"]
TOOL = {"name": "execute_cypher_query", "description": "Execute a Cypher query.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
REQ = httpx.Request("POST", "https://api.openai.com/v1/responses")


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def response(output, status="completed", reason=None, out_tokens=40, reasoning=0, cached=0):
    r = NS(output=output, status=status, incomplete_details=NS(reason=reason) if reason else None,
           model="gpt-5.4-2026-03-05",
           usage=NS(input_tokens=1500, output_tokens=out_tokens, input_tokens_details=NS(cached_tokens=cached),
                    output_tokens_details=NS(reasoning_tokens=reasoning)))
    r._request_id = "req_gpt"
    return r


def fcall(query, call_id="call_1"):
    return NS(type="function_call", call_id=call_id, name="execute_cypher_query", arguments=f'{{"query": "{query}"}}')


def message(text):
    return NS(type="message", content=[NS(type="output_text", text=text)])


class FakeClient:
    def __init__(self, *items):
        self.items, self.sent = list(items), []
        self.responses = NS(create=self._create)

    def _create(self, **kwargs):
        self.sent.append(kwargs)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def adapter(*items):
    waits = []
    a = GptAdapter(SETTINGS, client=FakeClient(*items), sleep=waits.append)
    return a, a.client, waits


def bad(msg):
    return openai.BadRequestError(msg, response=httpx.Response(400, request=REQ), body=None)


def overloaded():
    return openai.InternalServerError("overloaded", response=httpx.Response(503, request=REQ), body=None)


# ---------------------------------------------------------------- request
a, client, _ = adapter(response([fcall("MATCH (m) RETURN m")]))
r = a.call("SYSTEM", [{"role": "user", "text": "Which machines?"}], [TOOL])
sent = client.sent[0]
check("model snapshot from models.yaml", sent["model"] == "gpt-5.4-2026-03-05")
check("system prompt sent as instructions", sent["instructions"] == "SYSTEM")
check("max_tokens sent as max_output_tokens", sent["max_output_tokens"] == 1024)
check("temperature 0 sent", sent["temperature"] == 0)
check("reasoning effort none", sent["reasoning"] == {"effort": "none"})
check("nothing stored at OpenAI", sent["store"] is False)
check("parallel tool calls off when there are tools", sent["parallel_tool_calls"] is False)
check("tools translated to function tools",
      sent["tools"] == [{"type": "function", "name": TOOL["name"], "description": TOOL["description"],
                         "parameters": TOOL["parameters"], "strict": False}])
check("question sent as the user message", sent["input"] == [{"role": "user", "content": "Which machines?"}])
a, client, _ = adapter(response([message("```cypher\nMATCH (m) RETURN m\n```")]))
a.call("S", [{"role": "user", "text": "Q"}], [])
check("driver configuration: no tools and no parallel_tool_calls sent",
      "tools" not in client.sent[0] and "parallel_tool_calls" not in client.sent[0])

# ---------------------------------------------------------------- reply
check("tool call read back, JSON arguments parsed", r.tool_calls == [{"id": "call_1", "name": "execute_cypher_query",
                                                                       "arguments": {"query": "MATCH (m) RETURN m"}}])
check("stop reason, tokens, model, API, request id",
      (r.stop_reason, r.input_tokens, r.output_tokens, r.model_returned, r.api_version, r.request_id)
      == ("tool_calls", 1500, 40, "gpt-5.4-2026-03-05", API, "req_gpt"))
check("not cut off", not r.cut_off)
a, _, _ = adapter(response([message("Here it is."), fcall("Q")], cached=1024, reasoning=12))
r2 = a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
check("text and tool call in one reply", r2.text == "Here it is." and len(r2.tool_calls) == 1)
check("cached and reasoning tokens recorded", r2.cached_tokens == 1024 and r2.reasoning_tokens == 12)
a, _, _ = adapter(response([message("```cypher\nMATCH (m:Prod")], status="incomplete", reason="max_output_tokens", out_tokens=1024))
r3 = a.call("S", [{"role": "user", "text": "Q"}], [])
check("incomplete at max_output_tokens -> cut off", r3.cut_off and r3.stop_reason == "max_output_tokens")
a, _, _ = adapter(response([NS(type="function_call", call_id="c", name="execute_cypher_query", arguments='{"query": "MATCH')]))
check("unreadable arguments kept under _unparsed", a.call("S", [{"role": "user", "text": "Q"}], [TOOL]).tool_calls[0]["arguments"]
      == {"_unparsed": '{"query": "MATCH'})

# ---------------------------------------------------------------- messages
c5 = X.build(C.load(C.CONFIG_DIR / "C5.yaml"), "Which machines?")
items = to_gpt_input(c5.messages)
check("C5: user message, function_call (harness load), function_call_output",
      [i.get("type", "message") for i in items] == ["message", "function_call", "function_call_output"])
check("C5: harness load as a function call with the fixed id and JSON arguments",
      items[1] == {"type": "function_call", "call_id": "harness_load", "name": "load_skill", "arguments": '{"name": "neo4j-query"}'})
check("C5: skill body as the call's output", items[2] == {"type": "function_call_output", "call_id": "harness_load",
                                                          "output": c5.messages[2]["content"]})
mixed = to_gpt_input([{"role": "user", "text": "Q"},
                      {"role": "assistant", "text": "Loading.", "tool_calls": [{"id": "c1", "name": "load_skill", "arguments": {"name": "x"}}]}])
check("assistant text kept before its function call",
      mixed[1] == {"role": "assistant", "content": "Loading."} and mixed[2]["type"] == "function_call")

# ---------------------------------------------------------------- temperature fallback
a, client, _ = adapter(bad("Unsupported parameter: 'temperature' is not supported with this model."), response([fcall("Q")]),
                       response([fcall("Q")]))
r4 = a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
check("temperature rejected: same call repeated without it", "temperature" in client.sent[0] and "temperature" not in client.sent[1])
check("the fallback is not counted as an API failure", r4.attempts == 1 and "temperature rejected" in r4.errors[0])
a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
check("later calls leave temperature out", "temperature" not in client.sent[2])
check("request settings show temperature left out", "temperature" not in a.request("S", [], [TOOL]))
a, client, _ = adapter(bad("Invalid value for 'input'."))
try:
    a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
    check("other 400 errors are not retried", False)
except openai.BadRequestError:
    check("other 400 errors are not retried", len(client.sent) == 1)

# ---------------------------------------------------------------- retries
a, client, waits = adapter(overloaded(), openai.APIConnectionError(request=REQ), response([fcall("Q")]))
r5 = a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
check("retryable errors retried, then success", r5.attempts == 3 and waits == [2, 4] and r5.retry_wait_s == 6)
a, client, waits = adapter(*[overloaded() for _ in range(5)])
try:
    a.call("S", [{"role": "user", "text": "Q"}], [TOOL])
    check("5 failed attempts raise ApiFailure", False)
except ApiFailure:
    check("5 failed attempts raise ApiFailure", len(client.sent) == 5 and waits == [2, 4, 8, 16])

from harness.models.base import request_settings                      # noqa: E402
rs = request_settings(adapter(response([fcall("Q")]))[0], GptAdapter(SETTINGS, client=FakeClient()).request("SYS", [{"role": "user", "text": "Q"}], [TOOL]))
check("record settings leave out the prompt (instructions, input, tools)",
      not ({"instructions", "input", "tools"} & set(rs)) and rs["model"] == "gpt-5.4-2026-03-05" and rs["temperature"] == 0)

# ---------------------------------------------------------------- client setup
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")
real = GptAdapter(SETTINGS)
check("SDK retries off (the adapter retries)", real.client.max_retries == 0)
try:
    GptAdapter({**SETTINGS, "id": None}, client=FakeClient())
    check("missing model id refused", False)
except ValueError:
    check("missing model id refused", True)

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
