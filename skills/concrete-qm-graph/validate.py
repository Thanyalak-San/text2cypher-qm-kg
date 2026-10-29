"""Check a Cypher query against the concrete production quality management graph.

Usage:
    python validate.py "MATCH (a:Label)-[:TYPE]->(b:Label) RETURN a"
    echo "MATCH ..." | python validate.py

Prints "OK" if no problems are found, otherwise a numbered list of problems.

Checks:
  1. every node label and relationship type exists in the graph
  2. every relationship is used in a direction, and between labels, that exist in the graph
  3. the query contains no write clauses
  4. Neo4j accepts the query: it is run with EXPLAIN, which plans the query without executing it,
     and any syntax error or warning (e.g. a property that does not exist) is reported

The schema is read from schema_reference.md and relationship_directions.md in this folder.
EXPLAIN needs NEO4J_URI, NEO4J_USER (or NEO4J_USERNAME), NEO4J_PASSWORD and optionally
NEO4J_DATABASE, from the environment or a .env file in the current folder or one of its parents.
"""

from __future__ import annotations

import difflib
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATTERN_LINE = re.compile(r"^\(:(\w+)\)-\[:(\w+)\]->\(:(\w+)\)$", re.M)
LABEL_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|", re.M)
WRITE_CLAUSES = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH)\b", re.I)
NODE = r"\(\s*(\w*)\s*((?::\s*`?\w+`?\s*)*)(?:\{[^{}]*\})?\s*\)"
REL = r"(<?)-(?:\[\s*\w*\s*(?::\s*([\w|:`\s]+?))?\s*(?:\*[\d.\s]*)?\s*(?:\{[^{}]*\})?\s*\])?-(>?)"
SEGMENT = re.compile(NODE + r"\s*" + REL + r"\s*(?=" + NODE + ")")
NODE_RE = re.compile(NODE)


def load_schema() -> tuple[set[str], set[str], set[tuple[str, str, str]]]:
    """Read known labels, relationship types, and directed label pairs from the skill docs."""
    rel_text = (HERE / "relationship_directions.md").read_text(encoding="utf-8")
    triples = {tuple(m) for m in PATTERN_LINE.findall(rel_text)}
    labels = set(LABEL_ROW.findall((HERE / "schema_reference.md").read_text(encoding="utf-8")))
    labels |= {a for a, _, _ in triples} | {b for _, _, b in triples}
    types = {t for _, t, _ in triples}
    return labels, types, triples


def clean(query: str) -> str:
    """Remove comments and string contents so they are not mistaken for patterns."""
    q = re.sub(r"//[^\n]*", "", query)
    q = re.sub(r"/\*.*?\*/", "", q, flags=re.S)
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", q)


def node_labels(spec: str) -> list[str]:
    """Extract label names from a node-pattern label specification."""
    return [l.strip("` ") for l in spec.split(":") if l.strip("` ")]


def suggest(name: str, options: set[str]) -> str:
    """Suggest a case correction or close schema name for an unknown name."""
    lower = {o.lower(): o for o in options}
    if name.lower() in lower:
        return f" Did you mean `{lower[name.lower()]}`? Names are case-sensitive."
    close = difflib.get_close_matches(name, options, n=2, cutoff=0.6)
    return f" Did you mean {' or '.join(f'`{c}`' for c in close)}?" if close else ""


def schema_problems(query: str, labels: set[str], types: set[str], triples: set) -> list[str]:
    """Find unknown labels, invalid relationship patterns, and write clauses."""
    q = clean(query)
    problems: list[str] = []

    # Track labels by variable so a relationship can use labels declared elsewhere in the query.
    var_labels: dict[str, set[str]] = {}
    used_labels: set[str] = set()
    for m in NODE_RE.finditer(q):
        ls = node_labels(m.group(2))
        used_labels |= set(ls)
        if m.group(1) and ls:
            var_labels.setdefault(m.group(1), set()).update(ls)
    variables = set(re.findall(r"\(\s*(\w+)", q))
    no_maps = re.sub(r"\{[^{}]*\}", "{}", q)                        # map keys ({key: value}) are not labels
    for var, label in re.findall(r"\b(\w+):`?(\w+)`?", no_maps):    # label predicates: WHERE n:Label
        if var in variables:
            used_labels.add(label)
            var_labels.setdefault(var, set()).add(label)
    # Check labels from both node patterns and label predicates against the known schema.
    for l in sorted(used_labels - labels):
        problems.append(f"Unknown label `{l}`.{suggest(l, labels)}")

    # Check each relationship type and its direction against the known label-pair triples.
    pos, seen = 0, set()
    while (m := SEGMENT.search(q, pos)):
        v1, spec1, left, tspec, right = m.group(1, 2, 3, 4, 5)
        m2 = NODE_RE.match(q, m.end())
        v2, spec2 = m2.group(1, 2)
        pos = m.end()
        a = node_labels(spec1) or sorted(var_labels.get(v1, []))
        b = node_labels(spec2) or sorted(var_labels.get(v2, []))
        if not tspec:
            continue                                   # untyped relationship: nothing to check
        rtypes = [t.strip("` ") for t in re.split(r"[|:]", tspec) if t.strip("` ")]
        if left and not right:                         # (a)<-[r]-(b) is (b)-[r]->(a)
            a, b = b, a
        directed = bool(left) != bool(right)
        for t in rtypes:
            if t not in types:
                msg = f"Unknown relationship type `{t}`.{suggest(t, types)}"
                if msg not in seen:
                    seen.add(msg); problems.append(msg)
                continue
            a_known = [x for x in a if x in labels] or [None]
            b_known = [x for x in b if x in labels] or [None]
            ok = any(_exists(x, t, y, triples, directed) for x in a_known for y in b_known)
            if ok:
                continue
            reverse = directed and any(_exists(y, t, x, triples, True) for x in a_known for y in b_known)
            shown = f"({_fmt(a_known)})-[:{t}]{'->' if directed else '-'}({_fmt(b_known)})"
            if reverse:
                msg = (f"Wrong direction: {shown} does not exist. "
                       f"It runs the other way: ({_fmt(b_known)})-[:{t}]->({_fmt(a_known)}).")
            else:
                pairs = sorted(f"(:{x})-[:{t}]->(:{y})" for x, tt, y in triples if tt == t)
                msg = (f"{shown} does not exist. `{t}` connects only: " + ", ".join(pairs[:8])
                       + (" ..." if len(pairs) > 8 else "") + ".")
            if msg not in seen:
                seen.add(msg); problems.append(msg)

    if WRITE_CLAUSES.search(q):
        problems.append("The query contains a write clause (" + WRITE_CLAUSES.search(q).group(1).upper()
                        + "). Only read queries are allowed.")
    return problems


def _exists(a, t, b, triples, directed: bool) -> bool:
    """Return whether a relationship triple matches these labels and direction."""
    def match(x, y):
        return any((x is None or s == x) and (y is None or e == y) for s, tt, e in triples if tt == t)
    return match(a, b) or (not directed and match(b, a))


def _fmt(ls: list) -> str:
    """Format candidate labels for inclusion in a diagnostic message."""
    return ":" + ":".join(ls) if ls and ls[0] is not None else ""


def load_env() -> None:
    """Load the first nearby .env file without overriding existing environment values."""
    for d in [Path.cwd(), *Path.cwd().parents, HERE, *HERE.parents]:
        env = d / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and m.group(1) not in os.environ:
                    os.environ[m.group(1)] = m.group(2).strip("'\"")
            return


def explain_problems(query: str) -> list[str]:
    """Run EXPLAIN in a read-only Neo4j session and translate errors or warnings."""
    load_env()
    uri, pw = os.getenv("NEO4J_URI"), os.getenv("NEO4J_PASSWORD")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    if not (uri and user and pw):
        return ["Could not run EXPLAIN: Neo4j connection settings are missing."]
    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import CypherSyntaxError, Neo4jError, ServiceUnavailable
    except ImportError:
        return ["Could not run EXPLAIN: the neo4j Python driver is not installed."]
    import logging
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    problems = []
    try:
        # EXPLAIN plans the query without running it; inspect returned statuses for missing schema items.
        with GraphDatabase.driver(uri, auth=(user, pw)) as driver:
            with driver.session(database=os.getenv("NEO4J_DATABASE") or None, default_access_mode="READ") as s:
                summary = s.run("EXPLAIN " + query).consume()
                for n in summary.gql_status_objects or []:
                    desc = n.status_description or ""
                    if "does not exist" in desc.lower():      # unknown label, type or property key
                        problems.append("Neo4j warning: " + re.sub(r"^[\w ]+:\s*", "", desc, count=1))
    except CypherSyntaxError as e:
        problems.append("Syntax error: " + str(e.message).split("\n")[0])
    except ServiceUnavailable:
        problems.append("Could not run EXPLAIN: the database is not reachable.")
    except Neo4jError as e:
        problems.append("Neo4j rejected the query: " + str(e.message).split("\n")[0])
    return problems


def validate(query: str) -> list[str]:
    """Combine local schema checks with Neo4j's EXPLAIN diagnostics."""
    labels, types, triples = load_schema()
    return schema_problems(query, labels, types, triples) + explain_problems(query)


def main() -> None:
    """Read a query from arguments or stdin, print diagnostics, and set the exit status."""
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if not query.strip():
        print("No query given.")
        sys.exit(2)
    problems = validate(query)
    if not problems:
        print("OK")
        sys.exit(0)
    for i, p in enumerate(problems, 1):
        print(f"{i}. {p}")
    sys.exit(1)


if __name__ == "__main__":
    main()
