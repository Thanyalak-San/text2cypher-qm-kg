"""Tests for harness/tools.py and harness/loop.py: the tool-list part of T2, T7 and the episode rules
(guide, Appendix A). Uses a fake model and a fake backend: no API call, no database.

Usage:
    python tests/test_loop.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X, loop as L          # noqa: E402
from harness.config import ROOT                                   # noqa: E402
from harness.backends import QueryResult                            # noqa: E402
from harness.models.base import ModelReply                          # noqa: E402
from harness.skills import read_skill                               # noqa: E402
from harness.tools import LOAD_SKILL_TOOL, QUERY_TOOL, tools_for     # noqa: E402

failures = 0
KNOWN = set(C.load_models())
CFG = {p.relative_to(C.CONFIG_DIR).with_suffix("").as_posix(): C.load(p, KNOWN)
       for p in sorted(C.CONFIG_DIR.glob("C*.yaml")) + sorted((C.CONFIG_DIR / "pilot").glob("C*.yaml"))
       + sorted((C.CONFIG_DIR / "extra_schema").glob("C*.yaml"))}


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def reply(text="", calls=(), cut=False, wait=0.0):
    return ModelReply(text=text, tool_calls=list(calls), stop_reason="max_tokens" if cut else ("tool_use" if calls else "end_turn"),
                      cut_off=cut, input_tokens=100, output_tokens=20, cached_tokens=0, model_returned="fake",
                      api_version="test", request_id=None, seconds=0.01, retry_wait_s=wait)


def call(tool, n=1, **args):
    return {"id": f"call_{tool}_{n}", "name": tool, "arguments": args}


class FakeModel:
    """Replies in turn from a list; `forever` repeats the last reply for ever."""
    def __init__(self, *replies, forever=False):
        self.replies, self.forever, self.seen = list(replies), forever, []

    def call(self, system, messages, tools):
        self.seen.append((system, list(messages), tools))
        if self.forever and len(self.replies) == 1:
            return self.replies[0]
        return self.replies.pop(0)


class FakeBackend:
    def __init__(self):
        self.ran = []

    def run(self, q):
        self.ran.append(q)
        return QueryResult(ok=True, columns=["x"], rows=[[1]])


def episode(key, *replies, forever=False):
    cfg = CFG[key]
    prompt = X.build(cfg, "Which machines?")
    model, backend = FakeModel(*replies, forever=forever), FakeBackend()
    skill = read_skill(cfg.skill) if cfg.skill else None
    ep = L.run_episode(cfg, prompt, tools_for(cfg), model, backend, skill)
    return ep, model, backend


# ---------------------------------------------------------------- T2: tool lists
TOOLS = {k: [t["name"] for t in tools_for(c)] for k, c in CFG.items()}
present = lambda ks: [k for k in ks if k in TOOLS or not k.startswith("pilot/")]   # pilot/ absent in the public copy
for k in present(("C0", "C1", "C2", "pilot/C1")):
    check(f"T2 tools {k}: none (driver)", TOOLS[k] == [])
for k in present(("C3", "C3n", "C4", "C4w", "C4p", "C7t", "pilot/C3", "pilot/C3n", "pilot/C4", "pilot/C4n")):
    check(f"T2 tools {k}: query tool only", TOOLS[k] == ["execute_cypher_query"])
for k in present(("C5", "C6", "C6n", "pilot/C5", "pilot/C5n")):
    check(f"T2 tools {k}: query tool and load_skill", TOOLS[k] == ["execute_cypher_query", "load_skill"])
check("T2 tools: query tool is the published one-line definition",
      QUERY_TOOL["description"] == "Execute a Cypher query against the Neo4j concrete factory knowledge graph."
      and list(QUERY_TOOL["parameters"]["properties"]) == ["query"])
check("T2 tools C7: query tool, load_skill, read_skill_file, run_skill_script",
      TOOLS["C7"] == ["execute_cypher_query", "load_skill", "read_skill_file", "run_skill_script"])
check("T2 tools C7f, C7n: same as C7", TOOLS["C7f"] == TOOLS["C7n"] == TOOLS["C7"])
check("T2 tools C6 vs C7: C7 adds only the file and script tools",
      TOOLS["C7"][:2] == TOOLS["C6"] and TOOLS["C7t"] == ["execute_cypher_query"])

# ---------------------------------------------------------------- driver
ep, model, backend = episode("C1", reply("Here it is:\n```cypher\nMATCH (m:ProductionMachine) RETURN m.name\n```"))
check("driver: query from the cypher block is run", backend.ran == ["MATCH (m:ProductionMachine) RETURN m.name"] and ep.failure == "none")
check("driver: no tools sent", model.seen[0][2] == [])
ep, _, backend = episode("C1", reply("```cypher\nMATCH (a) RETURN a\n```\nor\n```cypher\nMATCH (b) RETURN b\n```"))
check("driver: first of two blocks run, count logged", backend.ran == ["MATCH (a) RETURN a"] and ep.cypher_blocks == 2)
ep, _, backend = episode("C1", reply("```cypher\nMATCH (m:ProductionMachine)\nWHERE m.na", cut=True))
check("driver: unclosed block when cut off -> 'cut off', nothing run", ep.failure == "cut off" and backend.ran == [])
ep, _, backend = episode("C1", reply("```cypher\nMATCH (m) RETURN m\n```\nThis query returns", cut=True))
check("driver: complete block before the cut is run", backend.ran == ["MATCH (m) RETURN m"] and ep.failure == "none")
ep, _, backend = episode("C1", reply("MATCH (m) RETURN m"))
check("driver: plain text without a cypher block -> 'no query'", ep.failure == "no query" and backend.ran == [])
ep, _, _ = episode("C1", reply("```\nMATCH (m) RETURN m\n```"))
check("driver: unlabelled code block is not a query", ep.failure == "no query")

# ---------------------------------------------------------------- MCP
ep, model, backend = episode("C3", reply("I'll query.", [call("execute_cypher_query", query="MATCH (m) RETURN m")]))
check("MCP: tool query run, episode ends", backend.ran == ["MATCH (m) RETURN m"] and ep.failure == "none" and len(ep.calls) == 1)
check("MCP: query tool sent", [t["name"] for t in model.seen[0][2]] == ["execute_cypher_query"])
ep, _, backend = episode("C3", reply("```cypher\nMATCH (m) RETURN m\n```"))
check("MCP: Cypher written as text is never run -> 'no query'", ep.failure == "no query" and backend.ran == [])
ep, _, backend = episode("C3", reply("", [call("execute_cypher_query", query="MATCH (m:Prod")], cut=True))
check("MCP: cut-off tool call is never run -> 'cut off'", ep.failure == "cut off" and backend.ran == [])
ep, _, backend = episode("C3", reply("", [call("execute_cypher_query", 1, query="Q1"), call("execute_cypher_query", 2, query="Q2")]))
check("MCP: parallel calls handled in order, nothing run after the query",
      backend.ran == ["Q1"] and ep.parallel_calls == 1 and [c["arguments"]["query"] for c in ep.ignored_calls] == ["Q2"])

# ---------------------------------------------------------------- skills
ep, model, backend = episode("C6", reply("", [call("load_skill", name="neo4j-query")]),
                             reply("", [call("execute_cypher_query", query="Q")]))
check("C6: model loads the skill, body returned, then query", ep.skill_loaded and backend.ran == ["Q"] and len(ep.calls) == 2)
body = read_skill(CFG["C6"].skill).body
check("C6: tool result is the skill body", model.seen[1][1][-1] == {"role": "tool", "tool_call_id": "call_load_skill_1", "name": "load_skill", "content": body})
check("C6: one counted request", [r["counted"] for r in ep.requests] == [True])
ep, model, _ = episode("C6", reply("", [call("load_skill", name="neo4j")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C6: unknown skill name -> 'No skill with that name.'", model.seen[1][1][-1]["content"] == L.NO_SKILL and not ep.skill_loaded)
ep, _, _ = episode("C6", reply("", [call("execute_cypher_query", query="Q")]))
check("C6: skill not loaded if the model never asks", not ep.skill_loaded and ep.requests == [])
ep, model, _ = episode("C5", reply("", [call("execute_cypher_query", query="Q")]))
check("C5: harness load counts as loaded, not as a request", ep.skill_loaded and ep.requests == [])
check("C5: model sees question, harness load and body", [m["role"] for m in model.seen[0][1]] == ["user", "assistant", "tool"])
ep, model, _ = episode("C5", reply("", [call("load_skill", name="neo4j-query")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C5: a repeat load returns the body again and counts", model.seen[1][1][-1]["content"] == body and len(ep.requests) == 1)

# ---------------------------------------------------------------- T7: limits
ep, model, backend = episode("C6", reply("", [call("load_skill", name="neo4j-query")]), forever=True)
check("T7: a model that keeps calling tools stops at 11 calls", len(ep.calls) == 11 and ep.failure == "call limit" and backend.ran == [])
check("T7: 8 requests served, then 'Request limit reached'",
      [r["counted"] for r in ep.requests] == [True] * 8 + [False] * 3
      and all(r["answer"] == L.LIMIT_REACHED for r in ep.requests[8:]) and ep.request_limit_hit)
check("T7: the limit message is what the model sees", model.seen[-1][1][-1]["content"] == L.LIMIT_REACHED)
ep, _, _ = episode("C3", reply("", [call("get_schema")]), forever=True)
check("T7: unknown tool answered, counted, and the call limit still ends the episode",
      ep.requests[0]["answer"] == L.UNKNOWN_TOOL and ep.failure == "call limit" and len(ep.calls) == 11)
ep, _, backend = episode("C6", *([reply("", [call("load_skill", i, name="neo4j-query")]) for i in range(10)]
                                 + [reply("", [call("execute_cypher_query", query="Q")])]))
check("T7: a query on the 11th call is still run", backend.ran == ["Q"] and ep.failure == "none" and len(ep.calls) == 11)

# ---------------------------------------------------------------- C7 file and script tools (no database needed)
ep, model, backend = episode("C7f", reply("", [call("read_skill_file", path="relationship_directions.md")]),
                            reply("", [call("execute_cypher_query", query="Q")]))
check("C7f: skill loaded by the harness, file read without a load request, then query",
      ep.skill_loaded and ep.files_read == ["relationship_directions.md"] and backend.ran == ["Q"] and len(ep.requests) == 1)
schema_ref = (ROOT / "skills/concrete-qm-graph/schema_reference.md").read_text(encoding="utf-8")
ep, model, backend = episode("C7", reply("", [call("load_skill", name="concrete-qm-graph")]),
                             reply("", [call("read_skill_file", path="schema_reference.md")]),
                             reply("", [call("execute_cypher_query", query="Q")]))
check("C7: load, then file read, then query", ep.skill_loaded and ep.files_read == ["schema_reference.md"] and backend.ran == ["Q"])
check("C7: file read returns the file text", model.seen[2][1][-1]["content"] == schema_ref)
check("C7: both requests counted", [r["counted"] for r in ep.requests] == [True, True])
check("T6: body appears only after a load (not in the prompt)",
      read_skill(CFG["C7"].skill).body not in model.seen[0][0] and all(m.get("content") != read_skill(CFG["C7"].skill).body
                                                                        for m in model.seen[0][1]))
check("T6: file text appears only after a file request", schema_ref not in model.seen[0][0] and schema_ref not in model.seen[1][0]
      and all(m.get("content") != schema_ref for m in model.seen[1][1]))
ep, model, _ = episode("C7", reply("", [call("read_skill_file", path="./patterns.md")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C7: './' prefix accepted, file read without loading first", ep.files_read == ["patterns.md"] and not ep.skill_loaded)
ep, model, _ = episode("C7", reply("", [call("read_skill_file", path="SKILL.md")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C7: SKILL.md is not readable as a file (use load_skill)", model.seen[1][1][-1]["content"] == L.NO_FILE and ep.files_read == [])
ep, model, _ = episode("C7", reply("", [call("run_skill_script", script="check.py", input="Q")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C7: unknown script -> 'No script with that name in the skill.'", model.seen[1][1][-1]["content"] == L.NO_SCRIPT and not ep.validator_run)
ep, model, _ = episode("C7", reply("", [call("run_skill_script", script="patterns.md", input="Q")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C7: only .py files run as scripts", model.seen[1][1][-1]["content"] == L.NO_SCRIPT)
ep, model, _ = episode("C6", reply("", [call("read_skill_file", path="schema_reference.md")]), reply("", [call("execute_cypher_query", query="Q")]))
check("C6: file tool not offered -> 'Unknown tool.'", model.seen[1][1][-1]["content"] == L.UNKNOWN_TOOL)

# ---------------------------------------------------------------- schema on request (C3r, C3rn; exploratory)
if "extra_schema/C3r" in CFG:
    schema = X.read_text(CFG["extra_schema/C3r"].schema)
    for k in ("extra_schema/C3r", "extra_schema/C3rn"):
        check(f"schema on request {k}: query tool and get_schema", TOOLS[k] == ["execute_cypher_query", "get_schema"])
        check(f"schema on request {k}: no schema block in the prompt",
              "schema" not in X.build(CFG[k], "Q").blocks and schema not in X.build(CFG[k], "Q").system)
    check("schema on request: C3r prompt = C3 prompt without the schema block",
          {b: t for b, t in X.build(CFG["C3"], "Q").blocks.items() if b != "schema"} == X.build(CFG["extra_schema/C3r"], "Q").blocks
          and {b: t for b, t in X.build(CFG["C3n"], "Q").blocks.items() if b != "schema"} == X.build(CFG["extra_schema/C3rn"], "Q").blocks)
    check("schema on request: C3's fixed schema block holds the same text get_schema returns",
          X.build(CFG["C3"], "Q").blocks["schema"] == X.HEADERS["schema"] + "\n" + schema)
    ep, model, backend = episode("extra_schema/C3r", reply("", [call("get_schema")]), reply("", [call("execute_cypher_query", query="Q")]))
    check("schema on request: get_schema returns the schema text, counted, then the query runs",
          model.seen[1][1][-1]["content"] == schema and ep.requests[0]["counted"] and ep.requests[0]["answer"] == "schema text"
          and ep.schema_requested and backend.ran == ["Q"])
    check("schema on request: the schema is not seen before the request", schema not in model.seen[0][0]
          and all(m.get("content") != schema for m in model.seen[0][1]))
    ep, _, _ = episode("extra_schema/C3rn", reply("", [call("execute_cypher_query", query="Q")]))
    check("schema on request: a query without a request leaves schema_requested False", not ep.schema_requested)
    ep, _, _ = episode("C3", reply("", [call("get_schema")]), reply("", [call("execute_cypher_query", query="Q")]))
    check("schema on request: C3 still answers get_schema with 'Unknown tool.'", ep.requests[0]["answer"] == L.UNKNOWN_TOOL and not ep.schema_requested)

# ---------------------------------------------------------------- record fields
ep, _, _ = episode("C6", reply("", [call("load_skill", name="neo4j-query")], wait=6.0), reply("", [call("execute_cypher_query", query="Q")]))
check("retry waits summed for the episode", ep.retry_wait_s == 6.0)
check("conversation after the prompt kept", [m["role"] for m in ep.messages] == ["assistant", "tool", "assistant"])

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
