"""Tests for scoring/scores.py: T8, T9 and unit tests (guide, Appendix C).

T8: LA scores 1 on every answer query. T9: EA_S scores 1 on every answer query, plus the unit tests below.
Both run on the expected rows stored in data/questions_original.jsonl; with --db the answer queries are
also re-run through the driver and scored on the live result.

Usage:
    python tests/test_scores.py [--db]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.context import load_questions               # noqa: E402
from scoring.scores import EAA_EXPECTED, LA_ALL, LA_ANY, SCHEMA_NAMES, ea_s, eaa, la, la_items   # noqa: E402

failures = 0
Q = {q["id"]: q for q in load_questions()}


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def S(qid, columns, rows, ok=True):
    return ea_s(ok, columns, rows, Q[qid])


# ---------------------------------------------------------------- T8, T9 (stored rows)
check("rules cover P1-P20", set(Q) == set(EAA_EXPECTED) == set(LA_ALL) | set(LA_ANY))
for qid, q in Q.items():
    check(f"T8 {qid}: LA = 1 on the answer query", la(True, q["answer_query"], qid) == 1)
    check(f"T9 {qid}: EA_S = 1 on the expected rows", S(qid, q["expected_columns"], q["expected_rows"]) == 1)

# ---------------------------------------------------------------- EA_S unit tests
p6 = Q["P6"]["expected_rows"]
check("columns may be renamed", S("P6", ["m"], p6) == 1)
check("row order ignored when order doesn't matter", S("P6", ["machine"], p6[::-1]) == 1)
check("extra returned column ignored", S("P6", ["id", "machine"], [[i, r[0]] for i, r in enumerate(p6)]) == 1)
check("required column may be in any position", S("P10", ["operator", "machine"], [r[::-1] for r in Q["P10"]["expected_rows"]]) == 1)
check("missing row scores 0", S("P6", ["machine"], p6[:-1]) == 0)
check("extra row scores 0", S("P6", ["machine"], p6 + [["Forklift"]]) == 0)
check("wrong value scores 0", S("P6", ["machine"], p6[:-1] + [["Mixer"]]) == 0)
check("too few columns scores 0", S("P10", ["machine"], [[r[0]] for r in Q["P10"]["expected_rows"]]) == 0)
check("failed query scores 0", S("P6", [], [], ok=False) == 0)
check("empty result scores 0", S("P6", ["machine"], []) == 0)
check("case and spaces ignored", S("P6", ["machine"], [[f"  {r[0].upper()} "] for r in p6]) == 1)
check("duplicate rows removed", S("P6", ["machine"], p6 + p6) == 1)
check("41 equals 41.0", S("P1", ["n", "names"], [[41.0, Q["P1"]["expected_rows"][0][1]]]) == 1)
check("numbers rounded to 6 significant figures", S("P7", ["b"], [[5.0000001]]) == 1)
check("number stored as text doesn't match", S("P7", ["b"], [["5"]]) == 0)

names = Q["P1"]["expected_rows"][0][1]
check("P1: list cell compared as a set (shuffled)", S("P1", ["c", "l"], [[41, names[::-1]]]) == 1)
check("P1: list cell with a duplicate name still a set", S("P1", ["c", "l"], [[41, names + names[:1]]]) == 1)
check("P1: list missing a name scores 0", S("P1", ["c", "l"], [[40, names[:-1]]]) == 0)
check("P1: wrong count scores 0", S("P1", ["c", "l"], [[42, names]]) == 0)
check("P1: names as 41 rows (no count) scores 0", S("P1", ["name"], [[n] for n in names]) == 0)

seq = Q["P19"]["expected_rows"][0][0]
check("P19: sequence in order scores 1", S("P19", ["s"], [[seq]]) == 1)
check("P19: reversed sequence scores 0", S("P19", ["s"], [[seq[::-1]]]) == 0)
check("P19: stages as ordered rows score 1", S("P19", ["stage"], [[s] for s in seq]) == 1)
check("P19: stages as rows in the wrong order score 0", S("P19", ["stage"], [[s] for s in seq[::-1]]) == 0)
check("P19: ordered rows with an extra column score 1", S("P19", ["n", "stage"], [[i, s] for i, s in enumerate(seq)]) == 1)
check("P19: ordered rows missing a stage score 0", S("P19", ["stage"], [[s] for s in seq[:-1]]) == 0)
check("P19: list missing a stage scores 0", S("P19", ["s"], [[seq[:-1]]]) == 0)

check("P8: null kept as a value", S("P8", ["c", "t"], Q["P8"]["expected_rows"]) == 1)
check("P8: null replaced by text scores 0",
      S("P8", ["c", "t"], [[c, t or "none"] for c, t in Q["P8"]["expected_rows"]]) == 0)
check("P8: type column required", S("P8", ["c"], [[c] for c, _ in Q["P8"]["expected_rows"]]) == 0)

check("P5: requested quantity alone scores 1", S("P5", ["q"], [[10850]]) == 1)
check("P13: operator alone scores 1", S("P13", ["op"], [["OperatorB"]]) == 1)
check("P16: stage alone scores 1", S("P16", ["stage"], [["Mixing"]]) == 1)
check("P17: person alone scores 1", S("P17", ["who"], [["InspectorA"]]) == 1)
p18 = Q["P18"]["expected_rows"]
check("P18: parameter alone scores 1", S("P18", ["p"], [[r[0]] for r in p18]) == 1)
check("P18: one row per edge also scores 1 (duplicates removed after projection)",
      S("P18", ["p", "d"], [[r[0], d] for r in p18 for d in r[1]]) == 1)
check("P15: approver without project scores 0", S("P15", ["a"], [["ManagerA"]]) == 0)
p10 = Q["P10"]["expected_rows"]
grouped = {}
for m, o in p10:
    grouped.setdefault(m, []).append(o)
check("P10: grouped answer (machine, list of operators) scores 1", S("P10", ["m", "ops"], [[m, os] for m, os in grouped.items()]) == 1)
check("P10: grouped with list column first scores 1", S("P10", ["ops", "m"], [[os, m] for m, os in grouped.items()]) == 1)
check("P10: grouped with an operator missing scores 0",
      S("P10", ["m", "ops"], [[m, os[:1]] for m, os in grouped.items()]) == 0)
check("P10: grouped with a wrong operator scores 0",
      S("P10", ["m", "ops"], [[m, os + ["OperatorZ"]] for m, os in grouped.items()]) == 0)
check("P10: one row with all operators, no machine column, scores 0",
      S("P10", ["ops"], [[[o for _, o in p10]]]) == 0)
check("P6: machines as one list scores 1 (grouped form, one column)", S("P6", ["l"], [[[r[0] for r in p6]]]) == 1)
check("P1: grouped rule doesn't apply where expected holds a list", S("P1", ["c", "name"], [[41, n] for n in names]) == 0)

# ---------------------------------------------------------------- EAA unit tests
def A(qid, rows, cap=None, ok=True):
    return eaa(ok, [], rows, qid, cap)

check("EAA P18: its answer query scores 0 (expects 7)", A("P18", p18) == 0)
check("EAA P18: one row per edge scores 1", A("P18", [[r[0], d] for r in p18 for d in r[1]]) == 1)
check("EAA P3: 17 rows score 1", A("P3", Q["P3"]["expected_rows"]) == 1)
check("EAA P3: 17 rows capped at 10 score 0", A("P3", Q["P3"]["expected_rows"], cap=10) == 0)
check("EAA P3: one collected row capped at 10 scores 1", A("P3", [[[r[0] for r in Q["P3"]["expected_rows"]]]], cap=10) == 1)
check("EAA P19: 6 or 7 items accepted", A("P19", [[seq[:6]]]) == 1 and A("P19", [[seq]]) == 1)
check("EAA P19: 5 items rejected", A("P19", [[seq[:5]]]) == 0)
check("EAA P1: any matching value in a single row (count then list)", A("P1", [[3, names]]) == 1)
check("EAA P1: at least 40", A("P1", [[39]]) == 0 and A("P1", [[41]]) == 1)
check("EAA: counts only, wrong values still score 1 (old rule)", A("P6", [["a"], ["b"], ["c"], ["d"]]) == 1)
check("EAA: failed query scores 0", A("P4", [], ok=False) == 0)

# ---------------------------------------------------------------- LA unit tests
check("LA P8: either substring is enough", la(True, "MATCH (c)-[:USED_IN]->(t) RETURN c", "P8") == 1)
check("LA P3: missing StandardAggregateProperty scores 0",
      la(True, "MATCH (a)-[:COMPLIES_WITH]->(s:ComplianceStandard) RETURN s", "P3") == 0)
check("LA: case-sensitive (complies_with is not COMPLIES_WITH)",
      la(True, "MATCH (p)-[:complies_with]->(s:ComplianceStandard) RETURN s", "P2") == 0)
check("LA: failed query scores 0", la(False, Q["P1"]["answer_query"], "P1") == 0)
check("LA: no query scores 0", la(True, "", "P1") == 0)

# ---------------------------------------------------------------- LA unit tests, new questions (la_items)
LI = [["PlannedTask"], ["PROCESSED_ON"], ["'curing", "\"curing"], ["max(", "LIMIT 1"]]
QOK = "MATCH (t:PlannedTask {name: 'Curing'})-[:PROCESSED_ON]->(m) RETURN MAX (m.batchSize)"
check("la_items: schema names read from the schema file", {"plannedtask", "processed_on", "batchsize"} <= SCHEMA_NAMES)
check("la_items: all items met (other items ignore case and spaces: 'Curing', MAX ()", la_items(True, QOK, LI) == 1)
check("la_items: an alternative is enough (LIMIT 1 for max()",
      la_items(True, QOK.replace("RETURN MAX (m.batchSize)", "RETURN m ORDER BY m.batchSize DESC LIMIT 1"), LI) == 1)
check("la_items: schema names are case-sensitive (plannedtask is not PlannedTask)",
      la_items(True, QOK.replace("PlannedTask", "plannedtask"), LI) == 0)
check("la_items: a missing item scores 0", la_items(True, QOK.replace("'Curing'", "'Mixing'"), LI) == 0)
check("la_items: a name typed in another case is still a name, matched as written",
      la_items(True, QOK, [["plannedtask"]]) == 0 and la_items(True, QOK, [["PlannedTask"]]) == 1)
check("la_items: failed query or no query scores 0", la_items(False, QOK, LI) == 0 and la_items(True, "", LI) == 0)

# T8 for the new questions, before the freeze: the author's rules against the ground-truth draft (files not in git)
RULES, DRAFT = ROOT / "docs" / "la_rules_author.json", ROOT / "docs" / "ground_truth_new_DRAFT.json"
if RULES.exists() and DRAFT.exists():
    import json as _j
    _rules = _j.loads(RULES.read_text(encoding="utf-8"))["rules"]
    _draft = {q["id"]: q for q in _j.loads(DRAFT.read_text(encoding="utf-8"))["questions"]}
    check("T8 draft: a rule for every new question", set(_rules) == set(_draft))
    for qid in sorted(set(_rules) & set(_draft), key=lambda x: int(x[1:])):
        check(f"T8 draft {qid}: LA = 1 on the answer query", la_items(True, _draft[qid]["answer_query"], _rules[qid]["items"]) == 1)
else:
    print("SKIP  T8 draft: docs/la_rules_author.json or the ground-truth draft not found")

# ---------------------------------------------------------------- live re-run (optional)
if "--db" in sys.argv:
    from harness.backends.driver import DriverBackend
    with DriverBackend() as d:
        for qid, q in Q.items():
            r = d.run(q["answer_query"])
            check(f"T8/T9 {qid} (live): LA = 1 and EA_S = 1",
                  la(r.ok, q["answer_query"], qid) == 1 and ea_s(r.ok, r.columns, r.rows, q) == 1, r.error or "")

# ---------------------------------------------------------------- time-dependent questions (rescore)
from types import SimpleNamespace as NS                               # noqa: E402
from scoring.rescore import expected_for                              # noqa: E402


class FakeDriver:
    def __init__(self, result):
        self.result, self.ran = result, []

    def run(self, query):
        self.ran.append(query)
        return self.result


fixed = dict(Q["P6"])
drv = FakeDriver(NS(ok=True, columns=["x"], rows=[[1]], error=None))
check("fixed question: stored expected rows used, nothing re-run", expected_for(fixed, drv) is fixed and not drv.ran)
timed = {**Q["P6"], "id": "T1", "time_dependent": True, "answer_query": "RETURN duration.inDays(date(), date('2027-01-01')).days AS d"}
drv = FakeDriver(NS(ok=True, columns=["d"], rows=[[70]], error=None))
now = expected_for(timed, drv)
check("time-dependent question: answer query re-run, its result is the expected rows",
      drv.ran == [timed["answer_query"]] and now["expected_columns"] == ["d"] and now["expected_rows"] == [[70]])
check("time-dependent question: scored against the re-run result", ea_s(True, ["days"], [[70]], {**now, "required_columns": ["d"]}) == 1)
try:
    expected_for(timed, FakeDriver(NS(ok=False, columns=[], rows=[], error="boom")))
    check("time-dependent question: failed re-run raises", False)
except RuntimeError:
    check("time-dependent question: failed re-run raises", True)

# ---------------------------------------------------------------- rescore: original and new questions
import tempfile, json as _json                                        # noqa: E401, E402
from scoring.rescore import check_qsets, has_published_rules, load_all, score_row  # noqa: E402
from harness.context import QUESTIONS                                 # noqa: E402


def rec(qid, query="Q", failure="none"):
    return {"benchmark": "qp", "qset": "x", "model": "claude", "config": "C3", "qid": qid, "run_idx": 1, "query": query,
            "failure": failure, "ct_s": 1.0, "tokens_in": 1, "tokens_out": 1, "n_calls": 1, "query_error": None,
            "skill_loaded": False, "request_limit_hit": False}


p6 = Q["P6"]
good = NS(ok=True, columns=p6["expected_columns"], rows=p6["expected_rows"], error=None)
row = score_row(rec("P6", p6["answer_query"]), p6, good)
check("original question: EA_S, EAA and LA all scored", (row["ea_s"], row["ea_a"], row["la"]) == (1, 1, 1))
check("original question: its own need (N06) and main wording", (row["need"], row["main_wording"]) == ("N06", 1))
NEWQ = {"id": "P99", "question": "Which machine is used at each stage?", "answer_query": "…",
        "expected_columns": ["stage", "machine"], "expected_rows": [["Mixing", "Mixer machine"], ["Moulding", "Press machine"]],
        "required_columns": ["stage", "machine"], "order_matters": False, "need": "N29", "main_wording": 0,
        "la_items": [["PlannedTask"], ["ProductionMachine"]]}
row = score_row(rec("P99"), NEWQ, NS(ok=True, columns=["s", "m"], rows=[["Moulding", "Press machine"], ["Mixing", "Mixer machine"]], error=None))
check("new question: EA_S scored, EAA left empty; need and main wording from the question file",
      (row["need"], row["main_wording"]) == ("N29", 0) and row["ea_s"] == 1 and row["ea_a"] == row["ea_a_cap10"] == "" and not has_published_rules("P99"))
row = score_row(rec("P99", "MATCH (t:PlannedTask)-[:PROCESSED_ON]->(m:ProductionMachine) RETURN t, m"), NEWQ, good)
check("new question: LA from the question file's la_items", row["la"] == 1)
row = score_row(rec("P99", "MATCH (t:PlannedTask) RETURN t"), NEWQ, good)
check("new question: LA 0 when an item is missing", row["la"] == 0)
try:
    score_row(rec("P99"), {k: v for k, v in NEWQ.items() if k != "la_items"}, good)
    check("new question without la_items stops rescoring", False)
except SystemExit:
    check("new question without la_items stops rescoring", True)
row = score_row(rec("P99"), NEWQ, NS(ok=True, columns=["s", "m"], rows=[["Mixing", "Mixer machine"]], error=None))
check("new question: an incomplete answer scores 0", row["ea_s"] == 0)
row = score_row(rec("P99", failure="no query"), NEWQ, None)
check("new question: a failed episode scores 0 with empty row count", row["ea_s"] == 0 and row["row_count"] == "")
with tempfile.TemporaryDirectory() as tmp:
    new = Path(tmp) / "questions_new.jsonl"
    new.write_text(_json.dumps({"_header": True}) + "\n" + _json.dumps(NEWQ) + "\n", encoding="utf-8")
    both = load_all([QUESTIONS, new])
    check("question files combined by ID", set(both) == set(Q) | {"P99"})
    dup = Path(tmp) / "dup.jsonl"
    dup.write_text(_json.dumps(Q["P6"]) + "\n", encoding="utf-8")
    try:
        load_all([QUESTIONS, dup])
        check("an ID found in two question files is an error", False)
    except SystemExit:
        check("an ID found in two question files is an error", True)
qfile = {"P6": {**Q["P6"], "qset": "original"}, "P99": {**NEWQ, "qset": "new"}, "P7": Q["P7"]}
check_qsets([{**rec("P6"), "qset": "original"}, {**rec("P99"), "qset": "new"}, {**rec("P7"), "qset": "x"}], qfile)
check("check_qsets: matching sets pass (a question without qset is not checked)", True)
try:
    check_qsets([{**rec("P99"), "qset": "original"}], qfile)
    check("check_qsets: a recorded qset that differs from the question file stops rescoring", False)
except SystemExit as e:
    check("check_qsets: a recorded qset that differs from the question file stops rescoring", "P99 recorded original, file new" in str(e))
NEWFILE = QUESTIONS.parent / "questions_v2.jsonl"
if NEWFILE.exists():
    V2 = load_questions(NEWFILE)
    KEEP = ["question", "answer_query", "expected_columns", "expected_rows", "required_columns", "order_matters"]
    check("questions-v2: 60 questions, 20 original (unchanged) and 40 new, IDs P1-P60",
          len(V2) == 60 and [q["id"] for q in V2] == [f"P{i}" for i in range(1, 61)]
          and all(q["qset"] == ("original" if q["id"] in Q else "new") for q in V2)
          and all(all(q[k] == Q[q["id"]][k] for k in KEEP) for q in V2 if q["id"] in Q))
    check("questions-v2: one main wording per need", sorted(q["need"] for q in V2 if q["main_wording"] == 1)
          == sorted({q["need"] for q in V2}))
    for q in V2:
        check(f"T9 {q['id']}: EA_S = 1 on the expected rows", S(q["id"], q["expected_columns"], q["expected_rows"]) == 1
              if q["id"] in Q else ea_s(True, q["expected_columns"], q["expected_rows"], q) == 1)
        if q["id"] not in Q:
            check(f"T8 {q['id']}: LA = 1 on the answer query (la_items)", la_items(True, q["answer_query"], q.get("la_items", [[""]])) == 1
                  and "la_items" in q)
else:
    print("SKIP  T9 for the new questions: data/questions_v2.jsonl not built yet (after the question freeze)")

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
