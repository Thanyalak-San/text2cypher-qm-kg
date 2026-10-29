"""Restore docs/backup.json (the graph as it was during the original runs) into its own database.

The current 'neo4j' database was restructured after the original runs (extra labels such as
Versioned/Immutable/Mutable, role/shift/access_level moved from properties to labels).
R2 uses the original state, restored into a separate database in the same DBMS
(Neo4j Enterprise allows several). The 'neo4j' database is never touched.

Steps:
  1. create the target database (default: qmsoriginal)
  2. import backup.json with apoc.import.json
     (APOC needs a temporary uniqueness constraint on the import id for every label first)
  3. tidy up: drop the temporary constraints/indexes, remove the import-id property,
     and turn the date fields that are DATE in the live database back into dates
     (a JSON export stores dates as plain strings)
  4. check the result against backup.json: node and relationship counts, labels,
     relationship types, and property keys per label

Before running:
  - add  apoc.import.file.enabled=true  to the DBMS's conf/apoc.conf and restart the DBMS
  - copy docs/backup.json into the DBMS's import folder
  - NEO4J_URI, NEO4J_USER (or NEO4J_USERNAME) and NEO4J_PASSWORD in the project's .env

Usage:
    python scripts/restore_original_db.py --check      # read-only: checks everything is ready
    python scripts/restore_original_db.py              # creates and fills the database
    python scripts/restore_original_db.py --replace    # drop and rebuild it if it already exists
Then:
    python scripts/dump_full_schema.py --database qmsoriginal
"""

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / "docs" / "backup.json"
IMPORT_ID = "neo4jImportId"            # property apoc.import.json uses to link relationships
# Properties that are DATE in the live database (STRING in the JSON export).
# ProductionProject.expectedDue_date / placedOrder_date are STRING in the live database too.
NODE_DATES = [("CustomerOrder", "requestedDue_date")]
REL_DATES = [("PLACES_ORDER", "placedOrder_date")]
PROTECTED = {"neo4j", "system"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_from_backup() -> dict:
    nodes = rels = 0
    labels, types, props = set(), set(), defaultdict(set)
    for line in BACKUP.open(encoding="utf-8"):
        o = json.loads(line)
        if o["type"] == "node":
            nodes += 1
            for label in o["labels"]:
                labels.add(label)
                props[label] |= set(o.get("properties") or {})
        else:
            rels += 1
            types.add(o["label"])
    return dict(nodes=nodes, rels=rels, labels=labels, types=types, props=dict(props))


def actual_from_db(session) -> dict:
    nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    props = {r["l"]: set(r["ks"]) for r in session.run(
        "MATCH (n) UNWIND labels(n) AS l UNWIND keys(n) AS k RETURN l, collect(DISTINCT k) AS ks")}
    labels = {r["l"] for r in session.run("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")}
    types = {r["t"] for r in session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t")}
    return dict(nodes=nodes, rels=rels, labels=labels, types=types, props=props)


def compare(expected: dict, actual: dict) -> list[str]:
    problems = []
    for k in ("nodes", "rels"):
        if expected[k] != actual[k]:
            problems.append(f"{k}: expected {expected[k]}, got {actual[k]}")
    for k in ("labels", "types"):
        if expected[k] != actual[k]:
            problems.append(f"{k}: missing {sorted(expected[k] - actual[k])}, "
                            f"extra {sorted(actual[k] - expected[k])}")
    for label, keys in expected["props"].items():
        got = actual["props"].get(label, set())
        if keys != got:
            problems.append(f"{label} properties: missing {sorted(keys - got)}, extra {sorted(got - keys)}")
    return problems


def check_ready(driver, db: str) -> bool:
    ok = True
    with driver.session(database="system") as s:
        exists = s.run("SHOW DATABASES YIELD name WHERE name = $db RETURN count(*) AS c", db=db).single()["c"]
    with driver.session(default_access_mode="READ") as s:
        import_dir = Path(s.run("CALL dbms.listConfig() YIELD name, value "
                                "WHERE name = 'server.directories.import' RETURN value").single()["value"])
        copy = import_dir / BACKUP.name
        if not copy.exists():
            print(f"[!] {BACKUP.name} is not in the import folder: copy it to {import_dir}")
            ok = False
        elif sha256(copy) != sha256(BACKUP):
            print(f"[!] {copy} differs from {BACKUP}: copy it again")
            ok = False
        else:
            print(f"[ok] {BACKUP.name} is in the import folder and identical to docs/backup.json")
            try:
                n = s.run("CALL apoc.load.json($f) YIELD value RETURN count(*) AS c", f=BACKUP.name).single()["c"]
                print(f"[ok] APOC can read it ({n} records)")
            except Exception as e:
                print(f"[!] APOC cannot read files yet: add apoc.import.file.enabled=true to "
                      f"conf/apoc.conf and restart the DBMS\n    ({str(e).splitlines()[0][:160]})")
                ok = False
    print(f"[{'!' if exists else 'ok'}] database '{db}' "
          + ("already exists (use --replace to rebuild it)" if exists else "does not exist yet"))
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--database", default="qmsoriginal")
    ap.add_argument("--check", action="store_true", help="read-only: check everything is ready")
    ap.add_argument("--replace", action="store_true", help="drop and rebuild the database if it exists")
    args = ap.parse_args()
    db = args.database
    if db.lower() in PROTECTED:
        raise SystemExit(f"Refusing to restore into '{db}'. Choose another database name.")

    load_dotenv(ROOT / ".env")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(user, os.getenv("NEO4J_PASSWORD")))
    try:
        driver.verify_connectivity()
    except ServiceUnavailable:
        raise SystemExit(f"Cannot connect to {os.getenv('NEO4J_URI')}: start the DBMS in Neo4j Desktop.")
    print(f"backup.json SHA-256: {sha256(BACKUP)}")
    expected = expected_from_backup()
    print(f"backup.json: {expected['nodes']} nodes, {expected['rels']} relationships, "
          f"{len(expected['labels'])} labels, {len(expected['types'])} relationship types\n")

    ready = check_ready(driver, db)
    if args.check or not ready:
        driver.close()
        raise SystemExit(0 if ready else 1)

    # 1. create the database
    with driver.session(database="system") as s:
        verb = "CREATE OR REPLACE DATABASE" if args.replace else "CREATE DATABASE"
        s.run(f"{verb} `{db}` IF NOT EXISTS WAIT" if not args.replace else f"{verb} `{db}` WAIT").consume()
    with driver.session(database=db) as s:
        if s.run("MATCH (n) RETURN count(n) AS c").single()["c"]:
            raise SystemExit(f"Database '{db}' is not empty. Use --replace to rebuild it.")

        # 2. import (APOC requires a uniqueness constraint on the import id for every label)
        for label in sorted(expected["labels"]):
            s.run(f"CREATE CONSTRAINT `import_{label}` IF NOT EXISTS "
                  f"FOR (n:`{label}`) REQUIRE n.{IMPORT_ID} IS UNIQUE").consume()
        s.run("CALL apoc.import.json($f, {importIdName: $id})", f=BACKUP.name, id=IMPORT_ID).consume()

        # 3. tidy up
        dropped = []
        for kind in ("CONSTRAINT", "INDEX"):
            for r in s.run(f"SHOW {kind}S YIELD name, properties RETURN name, properties"):
                if r["properties"] and IMPORT_ID in r["properties"]:
                    dropped.append(f"{kind.lower()} {r['name']}")
                    s.run(f"DROP {kind} `{r['name']}` IF EXISTS").consume()
        s.run(f"MATCH (n) WHERE n.{IMPORT_ID} IS NOT NULL REMOVE n.{IMPORT_ID}").consume()
        s.run(f"MATCH ()-[r]->() WHERE r.{IMPORT_ID} IS NOT NULL REMOVE r.{IMPORT_ID}").consume()
        for label, prop in NODE_DATES:
            s.run(f"MATCH (n:`{label}`) WHERE n.`{prop}` IS NOT NULL SET n.`{prop}` = date(n.`{prop}`)").consume()
        for rtype, prop in REL_DATES:
            s.run(f"MATCH ()-[r:`{rtype}`]->() WHERE r.`{prop}` IS NOT NULL "
                  f"SET r.`{prop}` = date(r.`{prop}`)").consume()

        # 4. check
        problems = compare(expected, actual_from_db(s))
        leftover = [r["name"] for r in s.run("SHOW CONSTRAINTS YIELD name RETURN name")]

    driver.close()
    print(f"\nRestored into '{db}'.")
    print(f"Removed after import: {', '.join(dropped) or 'nothing'}; import-id property removed.")
    print(f"Dates converted: {', '.join(f'{a}.{b}' for a, b in NODE_DATES + REL_DATES)}")
    print(f"Constraints now in '{db}': {', '.join(leftover) or 'none'}")
    if problems:
        print("\n[!] The restored database does not match backup.json:")
        for p in problems:
            print("    -", p)
        raise SystemExit(1)
    print("[ok] Matches backup.json: counts, labels, relationship types and property keys.")
    print(f"\nNext: python scripts/dump_full_schema.py --database {db}")


if __name__ == "__main__":
    main()
