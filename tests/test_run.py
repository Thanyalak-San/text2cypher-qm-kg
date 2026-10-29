"""Tests for harness/run.py: plan, shuffle, resume, re-queue, folder checks and the dirty-tree refusal.
Uses a fake model and fake backends: no API call, no database.

Usage:
    python tests/test_run.py
"""

import dataclasses
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X, run as R          # noqa: E402
from harness.backends import QueryResult                          # noqa: E402
from harness.models.base import ApiFailure, ModelReply            # noqa: E402
from harness.record import RunWriter                              # noqa: E402

failures = 0
MAIN = C.load_all(R.config_paths(["configurations"]))
if (ROOT / "configurations" / "pilot").is_dir():
    PILOT = C.load_all(R.config_paths(["configurations/pilot"]))
    PILOT_ARGS = ["configurations/pilot"]
else:   # public copy: 7 main configurations, Claude only, stand in for the pilot's 7
    PILOT = [dataclasses.replace(c, models=("claude",)) for c in MAIN if c.id in ("C1", "C3", "C3n", "C4", "C5", "C7t", "C7f")]
    PILOT_ARGS = ["configurations/C1.yaml", "configurations/C3.yaml", "configurations/C3n.yaml", "configurations/C4.yaml",
                  "configurations/C5.yaml", "configurations/C7t.yaml", "configurations/C7f.yaml", "--model", "claude"]
QS = X.load_questions()
QSHA = "q" * 64


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


class FakeModel:
    """Answers every question with a query tool call (MCP) or a cypher block (driver); can fail on chosen questions."""
    def __init__(self, fail_on=(), fail_times=1):
        self.fail = Counter({q: fail_times for q in fail_on})
        self.calls = 0

    def call(self, system, messages, tools):
        self.calls += 1
        q = messages[0]["text"]
        if self.fail[q] > 0:
            self.fail[q] -= 1
            raise ApiFailure("overloaded")
        if tools:
            calls = [{"id": "t", "name": "execute_cypher_query", "arguments": {"query": "MATCH (n) RETURN n"}}]
            return ModelReply("", calls, "tool_use", False, 100, 10, 0, "fake", "test", None, 0.01)
        return ModelReply("```cypher\nMATCH (n) RETURN n\n```", [], "end_turn", False, 100, 10, 0, "fake", "test", None, 0.01)

    def request(self, system, messages, tools):
        return {"model": "fake", "system": system, "messages": messages, "tools": tools}


class FakeBackend:
    def run(self, q):
        return QueryResult(ok=True, columns=["n"], rows=[[1]])


GIT = {"commit": "0" * 40, "dirty": False}


def run_jobs(folder, jobs, model=None, configs=PILOT):
    writer = RunWriter(folder)
    counts = R.execute(jobs, {c.id: c for c in configs}, {q["id"]: q for q in QS}, "original", QSHA, writer, "s",
                       GIT, {"claude": model or FakeModel()}, {"driver": FakeBackend(), "mcp": FakeBackend()}, None,
                       log=lambda *a: None)
    return writer, counts


# ---------------------------------------------------------------- plan
jobs = R.plan(PILOT, QS, 3)
check("pilot plan: 7 configurations x 20 questions x 3 runs = 420", len(jobs) == 420)
check("each configuration 60 episodes", set(Counter(j.config for j in jobs).values()) == {60})
check("no episode planned twice", len({(j.config, j.model, j.qid, j.run_idx) for j in jobs}) == 420)
check("run 1 before run 2 before run 3", [j.run_idx for j in jobs] == sorted(j.run_idx for j in jobs))
check("same seed, same order", R.plan(PILOT, QS, 3) == jobs)
r1 = [(j.config, j.qid) for j in jobs if j.run_idx == 1]
r2 = [(j.config, j.qid) for j in jobs if j.run_idx == 2]
check("runs shuffled differently", r1 != r2 and sorted(r1) == sorted(r2))
check("shuffle mixes configurations (not blocked by configuration)", len({c for c, _ in r1[:20]}) > 3)
check("seed is 1000 + run", R.SEED_BASE == 1000)
main_jobs = R.plan(MAIN, QS, 1)
check("main configurations: models listed per configuration (C1 has claude and gpt)",
      Counter(j.model for j in main_jobs if j.config == "C1") == {"claude": 20, "gpt": 20})
check("--model claude keeps only Claude", {j.model for j in R.plan(MAIN, QS, 1, {"claude"})} == {"claude"})

# ---------------------------------------------------------------- execute, resume, re-queue
with tempfile.TemporaryDirectory() as d:
    folder = Path(d) / "pilot"
    first = jobs[:30]
    writer, counts = run_jobs(folder, first)
    check("30 episodes recorded", counts["done"] == 30 and len(writer.done()) == 30)
    recs = [json.loads(l) for l in writer.episodes_path.read_text(encoding="utf-8").splitlines()]
    check("records carry the question file's checksum", {r["questions_sha256"] for r in recs} == {QSHA})
    check("records carry the run number", {r["run_idx"] for r in recs} == {1})
    todo = [j for j in jobs if j.key("original") not in RunWriter(folder).done()]
    check("resume: the 30 finished episodes are skipped", len(todo) == 390 and todo[0] == jobs[30])

    target = jobs[0]
    qtext = next(q["question"] for q in QS if q["id"] == target.qid)
    writer, counts = run_jobs(Path(d) / "requeue", [target, jobs[1]], FakeModel(fail_on=[qtext], fail_times=1))
    order = [json.loads(l)["qid"] for l in writer.episodes_path.read_text(encoding="utf-8").splitlines()]
    check("API failure: episode moved to the end, then recorded", counts["requeued"] == 1 and order == [jobs[1].qid, target.qid])
    writer, counts = run_jobs(Path(d) / "twice", [target], FakeModel(fail_on=[qtext], fail_times=2))
    check("API failure twice: logged in failures.jsonl, no record",
          counts["api_failed"] == 1 and not writer.episodes_path.exists() and (writer.folder / "failures.jsonl").exists())

    # each episode records its own question's set (one combined question file)
    mixed = [{**q, "qset": "new"} if i % 2 else q for i, q in enumerate(QS)]      # half new, half with no qset
    mjobs = R.plan(PILOT, mixed, 1)[:40]
    writer = RunWriter(Path(d) / "mixed")
    R.execute(mjobs, {c.id: c for c in PILOT}, {q["id"]: q for q in mixed}, "original", QSHA, writer, "s",
              GIT, {"claude": FakeModel()}, {"driver": FakeBackend(), "mcp": FakeBackend()}, None, log=lambda *a: None)
    want = {q["id"]: q.get("qset", "original") for q in mixed}
    recs = [json.loads(l) for l in writer.episodes_path.read_text(encoding="utf-8").splitlines()]
    check("qset: each record carries its question's set (or --qset where the question has none)",
          all(r["qset"] == want[r["qid"]] for r in recs) and {r["qset"] for r in recs} == {"original", "new"})
    left = [j for j in R.plan(PILOT, mixed, 1) if j.key(want[j.qid]) not in RunWriter(Path(d) / "mixed").done()]
    check("qset: resume with per-question sets skips the finished episodes", len(left) == 140 - 40)
    check("qset_of: question's own set first, --qset otherwise",
          R.qset_of({"qset": "new"}, "original") == "new" and R.qset_of({}, "original") == "original")

    # folder checks
    changed = [c if c.id != "C3" else C.Config(**{**c.__dict__, "config_hash": "different"}) for c in PILOT]
    try:
        R.check_folder(RunWriter(folder), changed, QSHA)
        check("refuses a folder with another configuration version", False)
    except SystemExit:
        check("refuses a folder with another configuration version", any(j.config == "C3" for j in first))
    try:
        R.check_folder(RunWriter(folder), PILOT, "x" * 64)
        check("refuses a folder with another question file", False)
    except SystemExit:
        check("refuses a folder with another question file", True)
    R.check_folder(RunWriter(folder), PILOT, QSHA)
    check("accepts the same versions", True)

    # main(): dry run writes nothing; dirty tree refused
    out = Path(d) / "dry"
    check("dry run returns 0 and creates no folder",
          R.main(PILOT_ARGS + ["--runs", "3", "--out", str(out), "--dry-run"]) == 0 and not out.exists())
    real_git = R.git_state
    R.git_state = lambda: {"commit": "0" * 40, "dirty": True}
    try:
        R.main(PILOT_ARGS + ["--runs", "1", "--out", str(Path(d) / "dirty"), "--limit", "1"])
        check("dirty tree refused", False)
    except SystemExit as e:
        check("dirty tree refused", "uncommitted" in str(e) and not (Path(d) / "dirty").exists())
    finally:
        R.git_state = real_git

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
