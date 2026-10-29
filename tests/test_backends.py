"""Tests for harness/backends: T1 and T5 (guide, Appendix C).

T1: every answer query in data/questions_original.jsonl gives identical rows through the driver and
through MCP (ignoring row order), and the driver rows equal the stored expected rows.
T5: `CREATE (n:Test)` is rejected by both interfaces and the database is unchanged.
Also checks the known MCP behaviours recorded in docs/audit.md, so a change in the server is noticed.

Needs Neo4j running with `qmsoriginal`, and Node.js for the MCP server. No API is needed.

Usage:
    python tests/test_backends.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.backends import check_database                 # noqa: E402
from harness.backends.driver import DriverBackend           # noqa: E402
from harness.backends.mcp import QUERY_TOOL, McpBackend     # noqa: E402
from harness.context import load_questions                  # noqa: E402

failures = 0
WRITE = "CREATE (n:Test) RETURN n"


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def bag(rows: list) -> list:
    return sorted(json.dumps(r, sort_keys=True) for r in rows)


class Rollback(Exception):
    pass


def driver_write_rejected(driver: DriverBackend) -> tuple[bool, str]:
    """Run the write in a read transaction; if the server ever accepted it, roll it back."""
    def work(tx):
        tx.run(WRITE).consume()
        raise Rollback
    try:
        with driver._driver.session(database=driver.database) as s:
            s.execute_read(work)
    except Rollback:
        return False, "write accepted in a read transaction (rolled back)"
    except Exception as e:
        return True, f"{type(e).__name__}: {e}"
    return False, "no error"


for db in ("neo4j", "system", "NEO4J"):
    try:
        check_database(db)
        check(f"refuses the '{db}' database", False)
    except ValueError:
        check(f"refuses the '{db}' database", True)

questions = load_questions()
with DriverBackend() as driver, McpBackend() as mcp:
    names = [t["name"] for t in mcp.tools]
    check(f"MCP server lists {QUERY_TOOL}", QUERY_TOOL in names, str(names))

    # T1
    for q in questions:
        d, m = driver.run(q["answer_query"]), mcp.run(q["answer_query"])
        check(f"T1 {q['id']}: runs through both", d.ok and m.ok, d.error or m.error or "")
        if d.ok and m.ok:
            check(f"T1 {q['id']}: same columns", d.columns == m.columns, f"{d.columns} vs {m.columns}")
            check(f"T1 {q['id']}: identical rows (ignoring order)", bag(d.rows) == bag(m.rows))
            check(f"T1 {q['id']}: MCP not truncated", not m.truncated)
            check(f"T1 {q['id']}: driver rows equal the stored expected rows",
                  d.columns == q["expected_columns"] and bag(d.rows) == bag(q["expected_rows"]))

    # T5
    count = "MATCH (n) RETURN count(n) AS nodes"
    before = driver.run(count).rows
    ok, detail = driver_write_rejected(driver)
    check("T5 driver: CREATE rejected", ok, detail)
    r = mcp.run(WRITE)
    check("T5 MCP: CREATE rejected", not r.ok and "not allowed" in (r.error or ""), r.error or "accepted")
    check("T5 database unchanged (node count)", driver.run(count).rows == before)
    check("T5 no Test nodes", driver.run("MATCH (n:Test) RETURN count(n) AS c").rows == [[0]])

    # known MCP behaviour (docs/audit.md): substring write check
    q = "MATCH (p:StandardFreshConcreteProperty {name: 'Setting time'}) RETURN p.name AS name"
    d, m = driver.run(q), mcp.run(q)
    check("known: 'Setting time' query runs through the driver", d.ok and d.rows == [["Setting time"]], d.error or str(d.rows))
    check("known: 'Setting time' query rejected by MCP's substring check", not m.ok and "SET" in (m.error or ""), m.error or "accepted")
    check("MCP server fingerprint covers dist/index.js", "index.js" in mcp.fingerprint())

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
