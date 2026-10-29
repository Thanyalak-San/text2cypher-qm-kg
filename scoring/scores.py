"""Automatic scores for one episode (guide, Appendix D; decisions in docs/audit.md).

All three take the query's result as re-run through the driver (ground rule 6): `ok`, `columns`, `rows`
as in harness.backends.QueryResult.

EA_S (main measure)
  1. Tidy the values: trim spaces, ignore letter case, round numbers to 6 significant figures; dates are
     already ISO strings from the driver. Nulls are kept as values. A list inside a cell is compared as an
     unordered set, unless the question's `order_matters` is true (P19).
  2. Keep only the question's `required_columns` from the expected rows. Each required column must be
     matched to a different returned column; extra returned columns are ignored.
  3. Remove duplicate rows on both sides after this projection, then compare: as sets, or as sequences
     if order matters. Extra or missing rows score 0.
  4. Where order matters and one column is required, a sequence may come either as one list in one row
     or as one row per item in the right order (P19: the stages as a list, or as ordered rows).
  5. Where order doesn't matter and the expected values hold no lists, a grouped answer also counts: if
     one returned column holds a list in every row, it is expanded to one row per item (duplicates then
     removed) and compared again (P10: each machine with a list of its operators).

EAA (old count-based rule, unchanged)
  The published MCP/skill scripts' rule, used for every configuration: the row count must equal the
  expected count, or, for a single row, any list in it may have that length or any number in it may
  equal it. P1 and P8 accept at least the count; P19 accepts 6–7. P18 expects 7 (the number of
  dependency edges), so its own answer query scores 0 (audit, "Published scripts"). `cap` keeps only the
  first rows, for the Graph RAG reproduction column (LangChain's top_k = 10).

LA (old rule, unchanged)
  The published per-question checks (identical in all three scripts): the query ran without error and
  its text contains the key labels, relationship types or properties (case-sensitive substrings).

LA for the new questions (`la_items`; author's rules, 2026-10-25)
  The question file's `la_items` for each new question: a list of items, all required; an item is met if
  any of its alternatives appears in the query. Schema names (labels, relationship types, properties) are
  matched exactly, as in the published rules; other items (keywords, functions, filter values) ignore
  letter case and all spaces. An item counts as a schema name if it is one in any letter case, but it is
  then matched as written. The query must also run without error.
"""

from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path

# ---------------------------------------------------------------- EA_S

MAX_COLUMN_TRIES = 100_000


def tidy(v, order_matters: bool = False):
    """A value in a comparable, hashable form."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(f"{v:.6g}")
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, list):
        items = [tidy(x, order_matters) for x in v]
        if order_matters:
            return ("list", tuple(items))
        return ("set", tuple(sorted(set(items), key=_key)))
    if isinstance(v, dict):
        return ("map", tuple(sorted((str(k).strip().lower(), tidy(x, order_matters)) for k, x in v.items())))
    return str(v).strip().lower()


def _key(x) -> str:
    return json.dumps(x, sort_keys=True, default=str)


def _project(rows: list[list], idx: tuple[int, ...], order_matters: bool) -> list[tuple]:
    """Rows reduced to the given column positions, tidied, duplicates removed (first one kept)."""
    seen, out = set(), []
    for r in rows:
        t = tuple(tidy(r[i], order_matters) for i in idx)
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def ea_s(ok: bool, columns: list[str], rows: list[list], question: dict) -> int:
    if not ok:
        return 0
    order = question["order_matters"]
    exp_cols = question["expected_columns"]
    req = question["required_columns"]
    expected = _project(question["expected_rows"], tuple(exp_cols.index(c) for c in req), order)
    if len(columns) < len(req):
        return 0
    if _matches(rows, len(columns), expected, len(req), order):
        return 1
    if not order and not any(isinstance(v, tuple) for row in expected for v in row):
        for i in range(len(columns)):
            flat = _expand(rows, i)
            if flat and _matches(flat, len(columns), expected, len(req), order):
                return 1
    if order and len(req) == 1:
        want = _sequence(expected)
        for i in range(len(columns)):
            if _sequence(_project(rows, (i,), True)) == want:
                return 1
    return 0


def _matches(rows: list[list], n_cols: int, expected: list[tuple], n_req: int, order: bool) -> bool:
    """Some assignment of required columns to distinct returned columns gives exactly the expected rows."""
    target = expected if order else set(expected)
    for n, idx in enumerate(permutations(range(n_cols), n_req)):
        if n >= MAX_COLUMN_TRIES:
            break
        got = _project(rows, idx, order)
        if (got if order else set(got)) == target and len(got) == len(expected):
            return True
    return False


def _expand(rows: list[list], i: int) -> list[list] | None:
    """Rows with list column i expanded to one row per item; None if column i isn't a list in every row."""
    out = []
    for r in rows:
        if not isinstance(r[i], list):
            return None
        out += [r[:i] + [x] + r[i + 1:] for x in r[i]]
    return out


def _sequence(rows: list[tuple]) -> tuple:
    """One-column rows as a sequence: the list itself if there is one row holding a list, else the values."""
    if len(rows) == 1 and isinstance(rows[0][0], tuple) and rows[0][0][:1] == ("list",):
        return rows[0][0][1]
    return tuple(r[0] for r in rows)


# ---------------------------------------------------------------- EAA

# question: (expected, mode) with mode "eq", "min" or a maximum
EAA_EXPECTED = {
    "P1": (40, "min"), "P2": (7, "eq"), "P3": (17, "eq"), "P4": (1, "eq"), "P5": (1, "eq"),
    "P6": (4, "eq"), "P7": (1, "eq"), "P8": (3, "min"), "P9": (5, "eq"), "P10": (5, "eq"),
    "P11": (1, "eq"), "P12": (2, "eq"), "P13": (1, "eq"), "P14": (1, "eq"), "P15": (1, "eq"),
    "P16": (1, "eq"), "P17": (1, "eq"), "P18": (7, "eq"), "P19": (6, 7), "P20": (3, "eq"),
}


def _in_bounds(n, expected: int, mode) -> bool:
    if mode == "min":
        return n >= expected
    if mode == "eq":
        return n == expected
    return expected <= n <= mode


def eaa(ok: bool, columns: list[str], rows: list[list], qid: str, cap: int | None = None) -> int:
    if not ok:
        return 0
    expected, mode = EAA_EXPECTED[qid]
    rows = rows[:cap] if cap is not None else rows
    if _in_bounds(len(rows), expected, mode):
        return 1
    if len(rows) == 1:
        for v in rows[0]:              # isinstance(True, int) holds, as in the original scripts
            if isinstance(v, list) and _in_bounds(len(v), expected, mode):
                return 1
            if isinstance(v, (int, float)) and _in_bounds(v, expected, mode):
                return 1
    return 0


# ---------------------------------------------------------------- LA

# question: substrings that must all appear (P8: any one of them)
LA_ALL = {
    "P1": ["MATCH", "ComplianceStandard"],
    "P2": ["COMPLIES_WITH", "ComplianceStandard"],
    "P3": ["StandardAggregateProperty", "COMPLIES_WITH", "ComplianceStandard"],
    "P4": ["COMPLIES_WITH", "ComplianceStandard"],
    "P5": ["ProductionProject", "PLANNED_FROM", "requestedQuantity"],
    "P6": ["MATCH", "ProductionMachine"],
    "P7": ["ProductionMachine", "batchSize"],
    "P9": ["DesignedMixProportion", "INFLUENCED_BY"],
    "P10": ["InternalPersonnel", "ASSIGNED_TO"],
    "P11": ["StandardMixingWaterType", "isAllowed"],
    "P12": ["StandardCuringEnvironment", "INFLUENCED_BY"],
    "P13": ["InternalPersonnel", "shift"],
    "P14": ["ExternalClient", "PLACES_ORDER", "product_type"],
    "P15": ["ProductionProject", "APPROVED_BY", "InternalPersonnel"],
    "P16": ["QualityInspectionTask", "PERFORMED_AT"],
    "P17": ["QualityInspectionTask", "ASSIGNED_TO"],
    "P18": ["DesignedMixProportion", "INFLUENCED_BY"],
    "P19": ["PRECEDES", "PlannedTask"],
    "P20": ["INFLUENCED_BY", "StandardHardenedConcreteProperty", "StandardFreshConcreteProperty"],
}
LA_ANY = {"P8": ["MonitoredConcreteConstituent", "USED_IN"]}


def la(ok: bool, query: str, qid: str) -> int:
    if not ok or not query:
        return 0
    if qid in LA_ANY:
        return int(any(s in query for s in LA_ANY[qid]))
    return int(all(s in query for s in LA_ALL[qid]))


# ---------------------------------------------------------------- LA, new questions

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "prompts" / "original" / "full_schema_qmsoriginal_structured.json"


def _schema_names(path: Path = SCHEMA_FILE) -> set[str]:
    """Labels, relationship types and property names of the graph, lower-cased."""
    s = json.loads(path.read_text(encoding="utf-8"))
    names = set(s["node_props"]) | {r["type"] for r in s["relationships"]}
    names |= {p["property"] for props in list(s["node_props"].values()) + list(s.get("rel_props", {}).values())
              for p in props}
    return {n.lower() for n in names}


SCHEMA_NAMES = _schema_names()


def _squash(s: str) -> str:
    return "".join(s.split()).lower()


def la_items(ok: bool, query: str, items: list[list[str]]) -> int:
    """LA for a new question: every item met; an item is met if any alternative appears."""
    if not ok or not query:
        return 0
    met = lambda a: a in query if a.lower() in SCHEMA_NAMES else _squash(a) in _squash(query)
    return int(all(any(met(a) for a in alts) for alts in items))
