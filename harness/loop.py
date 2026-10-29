"""One episode: the model's requests and replies until it submits a query or a limit ends it
(guide, section 6 and Appendix A).

- Driver interface: the query is the first ```cypher block in the reply. A reply cut off with an unclosed
  block fails ("cut off"); a partial query is never run.
- MCP interface: tool calls are handled in order. `execute_cypher_query` runs the query and ends the
  episode; nothing after it in the same reply is run. `load_skill` returns the skill body, or "No skill
  with that name."; a repeat load returns the body again. Cypher written as plain text is never run.
- Schema on request (C3r, C3rn): `get_schema` returns the configuration's schema text (a counted request).
- C7 also: `read_skill_file` returns a skill file, `run_skill_script` runs a skill script (validate.py) on
  the given input and returns its output (harness/skills.py); unknown names get a short message.
- Requests: at most `max_requests` (8) are served; after that each request gets "Request limit reached.
  Submit your query now." The C5 harness load is part of the prompt and doesn't count.
- Model calls: at most `max_calls` (11). Parallel calls are switched off; if several still arrive in one
  reply they are handled in order and logged.
- Failures (score 0): "no query", "cut off" (a reply cut off before its query or request was complete),
  "call limit".

Time: from the first request until the query's result comes back, or to the end for a failed episode.
`seconds` is the wall-clock time; `retry_wait_s` (API retry waits) is recorded so it can be left out.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from harness.backends import QueryResult
from harness.config import Config
from harness.context import Prompt, read_text
from harness.models.base import ModelReply
from harness.backends import DATABASE
from harness.skills import NO_FILE, NO_SCRIPT, Skill, _clean, read_file, run_script
from harness.tools import GET_SCHEMA_TOOL, LOAD_SKILL_TOOL, QUERY_TOOL, READ_FILE_TOOL, RUN_SCRIPT_TOOL

CYPHER_BLOCK = re.compile(r"```cypher[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
CYPHER_OPEN = re.compile(r"```cypher", re.IGNORECASE)
LIMIT_REACHED = "Request limit reached. Submit your query now."
NO_SKILL = "No skill with that name."
UNKNOWN_TOOL = "Unknown tool."


@dataclass
class Episode:
    query: str | None = None
    result: QueryResult | None = None             # through the configuration's interface
    failure: str = "none"                         # none | no query | cut off | call limit
    calls: list[ModelReply] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)     # {tool, arguments, counted, answer}
    messages: list[dict] = field(default_factory=list)     # full conversation after the prompt's messages
    skill_loaded: bool = False                    # loaded by the model (or by the harness in C5)
    request_limit_hit: bool = False
    files_read: list[str] = field(default_factory=list)      # C7: files the model read
    validator_run: bool = False                   # C7: the model ran validate.py at least once
    schema_requested: bool = False                # C3r, C3rn: the model called get_schema at least once
    parallel_calls: int = 0                       # replies with more than one tool call
    ignored_calls: list[dict] = field(default_factory=list)   # tool calls after the query in the same reply
    cypher_blocks: int = 0                        # driver: complete ```cypher blocks in the reply
    seconds: float = 0.0
    retry_wait_s: float = 0.0


def extract_cypher(text: str) -> tuple[str | None, int, bool]:
    """(first complete ```cypher block, number of complete blocks, an unclosed block follows the last one)."""
    blocks = CYPHER_BLOCK.findall(text)
    tail = CYPHER_BLOCK.sub("", text)
    unclosed = bool(CYPHER_OPEN.search(tail))
    return (blocks[0].strip() if blocks else None), len(blocks), unclosed


def run_episode(config: Config, prompt: Prompt, tools: list[dict], adapter, backend, skill: Skill | None) -> Episode:
    ep = Episode(skill_loaded=config.skill_loading == "harness")
    messages = list(prompt.messages)
    counted = 0
    offered = {t["name"] for t in tools}
    start = time.perf_counter()

    def finish() -> Episode:
        ep.messages = messages[len(prompt.messages):]
        ep.seconds = time.perf_counter() - start
        ep.retry_wait_s = sum(c.retry_wait_s for c in ep.calls)
        return ep

    for _ in range(config.max_calls):
        reply = adapter.call(prompt.system, messages, tools)
        ep.calls.append(reply)
        messages.append(reply.as_message())

        if config.interface == "driver":
            query, ep.cypher_blocks, _ = extract_cypher(reply.text)
            if query is None:                     # a complete block is run even if the reply was cut off later
                ep.failure = "cut off" if reply.cut_off else "no query"
                return finish()
            ep.query = query
            ep.result = backend.run(query)
            return finish()

        if not reply.tool_calls:
            ep.failure = "cut off" if reply.cut_off else "no query"
            return finish()
        if reply.cut_off:                         # the last tool call is incomplete: never run it
            ep.failure = "cut off"
            return finish()
        if len(reply.tool_calls) > 1:
            ep.parallel_calls += 1

        results = []
        for i, call in enumerate(reply.tool_calls):
            name, args = call["name"], call["arguments"]
            if name == QUERY_TOOL["name"]:
                ep.query = args.get("query", "")
                ep.result = backend.run(ep.query)
                ep.ignored_calls = reply.tool_calls[i + 1:]
                return finish()
            if counted >= config.max_requests:
                answer, is_counted = LIMIT_REACHED, False
                ep.request_limit_hit = True
            else:
                counted += 1
                is_counted = True
                if name == GET_SCHEMA_TOOL["name"] and name in offered:
                    answer = read_text(config.schema)
                    ep.schema_requested = True
                elif name not in offered or skill is None:
                    answer = UNKNOWN_TOOL
                elif name == LOAD_SKILL_TOOL["name"]:
                    if args.get("name") == skill.name:
                        answer = skill.body
                        ep.skill_loaded = True
                    else:
                        answer = NO_SKILL
                elif name == READ_FILE_TOOL["name"]:
                    answer, found = read_file(skill, str(args.get("path", "")))
                    if found:
                        ep.files_read.append(_clean(str(args.get("path", ""))))
                else:                                 # run_skill_script
                    script = str(args.get("script", ""))
                    answer, found = run_script(skill, script, str(args.get("input", "")), DATABASE)
                    if found and _clean(script) == "validate.py":
                        ep.validator_run = True
            short = {LIMIT_REACHED, NO_SKILL, UNKNOWN_TOOL, NO_FILE, NO_SCRIPT}
            if answer in short or name == RUN_SCRIPT_TOOL["name"]:
                kept = answer                         # script output is short and worth keeping
            else:
                kept = {LOAD_SKILL_TOOL["name"]: "skill body", GET_SCHEMA_TOOL["name"]: "schema text"}.get(name, "file text")
            ep.requests.append({"tool": name, "arguments": args, "counted": is_counted, "answer": kept})
            results.append({"role": "tool", "tool_call_id": call["id"], "name": name, "content": answer})
        messages.extend(results)

    ep.failure = "call limit"
    return finish()
