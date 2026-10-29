"""Development tests for skills/concrete-qm-graph/validate.py (Phase 3).

Uses only non-benchmark queries, as Phase 3 requires: the patterns in patterns.md and the
examples in prompts/few_shot.txt must pass, and planted errors in those queries must be caught.
Test T10 (validator against the benchmark answer queries) runs only after the skill is frozen.

Needs the Neo4j database running (for the EXPLAIN checks).

Usage:
    python tests/test_validate.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "concrete-qm-graph"))
import validate as V                      # noqa: E402

failures = 0


def parse_examples(path: Path) -> list[tuple[str, str]]:
    """Split the few-shot file into (question, cypher) pairs. Questions are '// ...' lines
    that start a block; a '//' comment inside a query stays part of the query."""
    pairs, question, lines = [], None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("// "):
            if question is not None:
                pairs.append((question, "\n".join(lines).strip()))
            question, lines = line[3:].strip(), []
        elif question is not None:
            lines.append(line)
    if question is not None:
        pairs.append((question, "\n".join(lines).strip()))
    return pairs


def check(name: str, query: str, expect: str | None) -> None:
    """expect=None: query must pass. Otherwise a problem containing `expect` must be reported."""
    global failures
    problems = V.validate(query)
    if expect is None:
        ok = not problems
    else:
        ok = any(expect.lower() in p.lower() for p in problems)
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok or expect is not None:
        for p in problems or ["(no problems reported)"]:
            print(f"        {p}")


# 1. correct non-benchmark queries must pass
patterns = re.findall(r"```cypher\n(.*?)```", (ROOT / "skills/concrete-qm-graph/patterns.md").read_text(encoding="utf-8"), re.S)
for i, q in enumerate(patterns, 1):
    check(f"patterns.md pattern {i}", q, None)
for i, (_, q) in enumerate(parse_examples(ROOT / "prompts/few_shot.txt"), 1):
    check(f"few_shot.txt E{i}", q, None)

# 2. planted errors (each in a non-benchmark query)
P1 = "MATCH (ip:IntermediatedProduct)-[:USED_IN]->(t:PlannedTask) RETURN ip.name, t.name"
check("wrong direction", P1.replace("(ip:IntermediatedProduct)-[:USED_IN]->(t:PlannedTask)",
                                    "(t:PlannedTask)-[:USED_IN]->(ip:IntermediatedProduct)"), "wrong direction")
check("wrong direction, written with <-", "MATCH (ip:IntermediatedProduct)<-[:USED_IN]-(t:PlannedTask) RETURN ip", "wrong direction")
check("unknown label (misspelt)", P1.replace("IntermediatedProduct", "IntermediateProduct"), "unknown label")
check("unknown label (wrong case)", P1.replace("PlannedTask", "plannedTask"), "case-sensitive")
check("unknown relationship type", P1.replace("USED_IN", "USES"), "unknown relationship type")
check("type between labels it never connects",
      "MATCH (ip:IntermediatedProduct)-[:STORED_IN]->(t:PlannedTask) RETURN ip", "connects only")
check("direction via variable label",
      "MATCH (t:PlannedTask) MATCH (t)-[:USED_IN]->(ip:IntermediatedProduct) RETURN t", "wrong direction")
check("unknown label in WHERE predicate",
      "MATCH (n) WHERE n:StandardConcreteConstituents RETURN n.name", "unknown label")
check("syntax error", "MATCH (ip:IntermediatedProduct)-[:USED_IN]->(t:PlannedTask RETURN ip", "syntax error")
check("write clause", "MATCH (ip:IntermediatedProduct) SET ip.name = 'x' RETURN ip", "write clause")
check("unknown property (EXPLAIN warning)", "MATCH (ip:IntermediatedProduct) RETURN ip.colour", "does not exist")

# 3. things that are fine and must not be flagged
check("undirected relationship", "MATCH (ip:IntermediatedProduct)-[:USED_IN]-(t:PlannedTask) RETURN ip", None)
check("variable-length path", "MATCH (a:StandardAggregateProperty)-[:MEASURED_FROM*1..2]->(b) RETURN a, b", None)
check("label-like text inside a string", "MATCH (t:PlannedTask) WHERE t.name = 'x:Nothing' RETURN t", None)
check("comment containing a pattern", "// (a:Nope)-[:NOPE]->(b)\nMATCH (t:PlannedTask) RETURN t", None)

print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
sys.exit(1 if failures else 0)
