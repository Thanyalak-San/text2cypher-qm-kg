"""Re-run every recorded query through the driver and score it (guide, ground rule 6 and section 7).

Reads a run folder's episodes.jsonl, runs each episode's query on `qmsoriginal` through the Neo4j driver
(read-only), scores LA, EAA and EA_S (scoring/scores.py), and writes runs_scored.csv in the same folder:
one row per episode with the columns the analysis script needs

    benchmark, qset, model, config, qid, run_idx, la, ea_a, ea_s, ea_m, ct_s

followed by extra columns: ea_a_cap10 (EAA on the first 10 rows, the Graph RAG reproduction column),
failure, tokens_in, tokens_out, n_calls, row_count (driver), driver_error, mcp_error, skill_loaded,
request_limit_hit. `ea_m` stays empty until the manual rating (Phase 9). Episodes that failed, or whose
query raised an error, score 0.

EAA and LA are the published rules for the original questions P1–P20 (scoring/scores.py). The new
questions have no EAA, so their `ea_a` and `ea_a_cap10` are left empty; their LA uses the author's rules,
the question file's `la_items` (scoring/scores.py, `la_items`). EA_S is scored for every question.

`need` and `main_wording` come from the question file (fields `need` and `main_wording`). An original
question P1–P20 without them is its own need N01–N20 and its need's main wording. The analysis averages a
need's wordings (primary) or uses its main wording (sensitivity).

Questions are read from the frozen question file data/questions_v2.jsonl (the 60 main questions) if it
exists, otherwise from data/questions_original.jsonl (or from the files given with --questions-file); a
question ID found in two files is an error.

Each episode's recorded `qset` must match its question's `qset` in the question file (where the file has
one); otherwise rescoring stops and lists the mismatches (a run made with another question file, or an older
harness that labelled every episode with --qset).

Time-dependent questions (`time_dependent: true` in the question file, e.g. one that uses date() for
today) have an answer that changes from day to day, so their stored expected rows are not used: the
answer query is re-run together with the model's query, and EA_S compares the two results.

Usage:
    python -m scoring.rescore runs/pilot
    python -m scoring.rescore runs/main --questions-file data/questions_v2.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from harness.backends.driver import DriverBackend
from harness.context import QUESTIONS, load_questions
from scoring.scores import EAA_EXPECTED, ea_s, eaa, la, la_items

QUESTIONS_V2 = QUESTIONS.parent / "questions_v2.jsonl"

COLUMNS = ["benchmark", "qset", "model", "config", "qid", "need", "main_wording", "run_idx", "la", "ea_a", "ea_s", "ea_m", "ct_s",
           "ea_a_cap10", "failure", "tokens_in", "tokens_out", "n_calls", "row_count", "driver_error",
           "mcp_error", "skill_loaded", "request_limit_hit"]


def expected_for(question: dict, driver) -> dict:
    """The question with its expected rows; for a time-dependent question, from re-running the answer query now."""
    if not question.get("time_dependent"):
        return question
    res = driver.run(question["answer_query"])
    if not res.ok:
        raise RuntimeError(f"{question['id']}: answer query failed on re-run: {res.error}")
    return {**question, "expected_columns": res.columns, "expected_rows": res.rows}


def question_files() -> list[Path]:
    """The default question file: the frozen questions-v2 once it exists, otherwise the originals."""
    return [QUESTIONS_V2] if QUESTIONS_V2.exists() else [QUESTIONS]


def load_all(paths: list[Path]) -> dict[str, dict]:
    """Questions from several files by ID; an ID found twice is an error."""
    questions: dict[str, dict] = {}
    for path in paths:
        for q in load_questions(path):
            if q["id"] in questions:
                raise SystemExit(f"{path}: question {q['id']} is also in another question file")
            questions[q["id"]] = q
    return questions


def check_qsets(episodes: list[dict], questions: dict[str, dict]) -> None:
    """Stop if an episode's recorded qset differs from its question's qset in the question file."""
    bad = sorted({(r["qid"], r["qset"], questions[r["qid"]]["qset"]) for r in episodes
                  if "qset" in questions[r["qid"]] and r["qset"] != questions[r["qid"]]["qset"]})
    if bad:
        raise SystemExit("qset differs from the question file: "
                         + ", ".join(f"{qid} recorded {got}, file {want}" for qid, got, want in bad))


def has_published_rules(qid: str) -> bool:
    """EAA and LA exist only for the original questions (the published count and keyword rules)."""
    return qid in EAA_EXPECTED


def la_score(ok: bool, query: str, q: dict) -> int:
    """LA: the published rule for P1–P20, the question file's `la_items` for a new question."""
    if has_published_rules(q["id"]):
        return la(ok, query, q["id"])
    if "la_items" not in q:
        raise SystemExit(f"{q['id']}: no la_items in the question file")
    return la_items(ok, query, q["la_items"])


def need_of(q: dict) -> tuple[str, int]:
    """The question's need ID and whether it is its need's main wording (1/0)."""
    if "need" in q:
        return q["need"], int(q.get("main_wording", 1))
    if has_published_rules(q["id"]):
        return f"N{int(q['id'][1:]):02d}", 1
    raise SystemExit(f"{q['id']}: no need ID in the question file")


def score_row(r: dict, q: dict, res) -> dict:
    """One runs_scored.csv row for episode record r, its question q and the driver re-run result res (or None)."""
    ok = bool(res and res.ok and r["failure"] == "none")
    cols, data = (res.columns, res.rows) if res else ([], [])
    published = has_published_rules(r["qid"])
    need, main = need_of(q)
    return {
        "benchmark": r["benchmark"], "qset": r["qset"], "model": r["model"], "config": r["config"],
        "qid": r["qid"], "need": need, "main_wording": main, "run_idx": r["run_idx"],
        "la": la_score(ok, r["query"] or "", q),
        "ea_a": eaa(ok, cols, data, r["qid"]) if published else "",
        "ea_s": ea_s(ok, cols, data, q), "ea_m": "", "ct_s": round(r["ct_s"], 4),
        "ea_a_cap10": eaa(ok, cols, data, r["qid"], cap=10) if published else "",
        "failure": r["failure"], "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"], "n_calls": r["n_calls"],
        "row_count": len(data) if res and res.ok else "", "driver_error": (res.error or "") if res else "",
        "mcp_error": (r["query_error"] or "") if r.get("mcp_fingerprint") else "",   # MCP configurations only
        "skill_loaded": int(r["skill_loaded"]), "request_limit_hit": int(r["request_limit_hit"])}


def main(folder: Path, paths: list[Path] | None = None) -> None:
    episodes = [json.loads(l) for l in (folder / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    questions = load_all(paths or question_files())
    missing = sorted({r["qid"] for r in episodes} - set(questions))
    if missing:
        raise SystemExit(f"no question file has {', '.join(missing)}")
    check_qsets(episodes, questions)
    rows = []
    with DriverBackend() as driver:
        for r in episodes:
            q = expected_for(questions[r["qid"]], driver)
            res = driver.run(r["query"]) if r["query"] else None
            rows.append(score_row(r, q, res))
    out = folder / "runs_scored.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Scored {len(rows)} episodes. Saved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-run and score every episode in a run folder.")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--questions-file", type=Path, action="append", dest="files")
    args = ap.parse_args()
    main(args.folder, args.files)
