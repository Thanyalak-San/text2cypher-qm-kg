"""Tests for the C7 script tool with the real validate.py (harness/skills.py: run_script).

Needs Neo4j with `qmsoriginal` (validate.py runs EXPLAIN, read-only). Checks that the script gets the
study database, that a correct query prints OK, and that a wrong direction, an unknown label and a
syntax error are reported. The skill itself is frozen and is not changed.

Usage:
    python tests/test_skill_tools.py
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.backends import DATABASE                         # noqa: E402
from harness.skills import NO_SCRIPT, Skill, read_skill, run_script   # noqa: E402

failures = 0
SKILL = read_skill(ROOT / "skills" / "concrete-qm-graph")


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def validate(q: str) -> str:
    out, found = run_script(SKILL, "validate.py", q, DATABASE)
    assert found
    return out


with tempfile.TemporaryDirectory() as d:
    (Path(d) / "SKILL.md").write_text("---\nname: t\ndescription: t\n---\nbody\n", encoding="utf-8")
    (Path(d) / "env.py").write_text("import os, sys\nprint(os.environ.get('NEO4J_DATABASE'), sys.stdin.read())\n",
                                     encoding="utf-8")
    fake = Skill("t", "t", "body", Path(d))
    out, _ = run_script(fake, "env.py", "hello", DATABASE)
    check("script gets NEO4J_DATABASE=qmsoriginal and the input on stdin", out == "qmsoriginal hello", out)
    check("script outside the folder is not run", run_script(fake, "../env.py", "x", DATABASE) == (NO_SCRIPT, False))

good = "MATCH (hp:StandardHardenedConcreteProperty {name: 'Compressive strength'})-[:INFLUENCED_BY]->(fp:StandardFreshConcreteProperty) RETURN fp.name"
check("correct query (P20's answer query) -> OK", validate(good) == "OK", validate(good))
rev = "MATCH (fp:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(hp:StandardHardenedConcreteProperty) RETURN fp.name"
out = validate(rev)
check("wrong direction reported", out != "OK" and "INFLUENCED_BY" in out, out)
out = validate("MATCH (m:Machine) RETURN m.name")
check("unknown label reported", out != "OK" and "Machine" in out, out)
out = validate("MATCH (m:ProductionMachine RETURN m.name")
check("syntax error reported", out != "OK" and "yntax" in out, out)
out = validate("MATCH (m:ProductionMachine) SET m.name = 'x' RETURN m")
check("write clause reported (nothing is run)", out != "OK", out)

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
