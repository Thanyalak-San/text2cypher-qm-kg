"""Tests for harness/record.py with a fake episode: no API call, no database.

Usage:
    python tests/test_record.py
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X                    # noqa: E402
from harness.backends import QueryResult                          # noqa: E402
from harness.loop import Episode                                  # noqa: E402
from harness.models.base import ModelReply                        # noqa: E402
from harness.record import RunWriter, git_state, make_record, prompt_id   # noqa: E402
from harness.tools import tools_for                               # noqa: E402

failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def reply(out, wait=0.0, cut=False):
    return ModelReply(text="", tool_calls=[], stop_reason="end_turn", cut_off=cut, input_tokens=3000, output_tokens=out,
                      cached_tokens=0, model_returned="claude-sonnet-4-6", api_version="2023-06-01", request_id="r",
                      seconds=1.0, retry_wait_s=wait)


cfg = C.load(C.CONFIG_DIR / "C6.yaml")
q = X.load_questions()[5]
prompt = X.build(cfg, q["question"])
tools = tools_for(cfg)
ep = Episode(query="MATCH (m:ProductionMachine) RETURN m.name",
             result=QueryResult(ok=True, columns=["m.name"], rows=[[f"M{i}"] for i in range(8)], seconds=0.02),
             calls=[reply(40, wait=2.0), reply(90)], requests=[{"tool": "load_skill", "arguments": {"name": "neo4j-query"},
                                                                 "counted": True, "answer": "skill body"}],
             skill_loaded=True, seconds=5.0, retry_wait_s=2.0)
git = git_state()
rec = make_record(ep=ep, config=cfg, model_key="claude", request_settings={"model": "claude-sonnet-4-6", "max_tokens": 1024},
                  question=q, qset="original", run_idx=2, session="s1", prompt=prompt, tools=tools, git=git,
                  mcp_fingerprint={"index.js": "abc"})

check("git commit recorded", len(rec["git_commit"]) == 40 and isinstance(rec["git_dirty"], bool))
check("identification fields", (rec["config"], rec["model"], rec["qid"], rec["qset"], rec["run_idx"], rec["benchmark"])
      == ("C6", "claude", q["id"], "original", 2, "qp"))
check("configuration hash and checksums", rec["config_hash"] == cfg.config_hash and rec["checksums"] == cfg.checksums)
check("token totals and largest reply", (rec["tokens_in"], rec["tokens_out"], rec["max_output_tokens_call"]) == (6000, 130, 90))
check("CT leaves out retry waits", rec["seconds"] == 5.0 and rec["ct_s"] == 3.0)
check("rows: count and a 5-row sample", rec["row_count"] == 8 and len(rec["rows_sample"]) == 5)
check("skill flags and request counts", rec["skill_loaded"] and not rec["harness_loaded"] and rec["n_requests"] == 1 and rec["n_calls"] == 2)
check("API version and model returned", rec["api_versions"] == ["2023-06-01"] and rec["model_ids_returned"] == ["claude-sonnet-4-6"])
check("prompt id covers the tools", prompt_id(prompt, tools) != prompt_id(prompt, []))
check("record is JSON-serialisable", bool(json.dumps(rec, default=str)))

with tempfile.TemporaryDirectory() as d:
    w = RunWriter(Path(d))
    w.write(rec, prompt, tools)
    w.write({**rec, "qid": "P7"}, prompt, tools)
    check("prompt stored once for two episodes", len(w.prompts_path.read_text(encoding="utf-8").splitlines()) == 1)
    check("one line per episode", len(w.episodes_path.read_text(encoding="utf-8").splitlines()) == 2)
    again = RunWriter(Path(d))
    check("resume: finished episodes found", again.done() == {("C6", "claude", "original", q["id"], 2), ("C6", "claude", "original", "P7", 2)})
    check("resume: known prompts found", again.prompt_ids == {rec["prompt_id"]})

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
