"""Run Cypher through the Neo4j Python driver (the driver interface, and scoring for every configuration).

Queries run in a read transaction (`execute_read`), so the server rejects any write. Values are returned
as plain JSON: temporal types as ISO strings, lists and maps kept. The 30-second timeout matches the MCP
server's default.
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase, unit_of_work

from harness.backends import DATABASE, QueryResult, check_database
from harness.config import ROOT

TIMEOUT_S = 30


def to_json(v):
    """Neo4j values to plain JSON values (temporal types as ISO strings)."""
    if isinstance(v, list):
        return [to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    if hasattr(v, "iso_format"):
        return v.iso_format()
    return v


class DriverBackend:
    name = "driver"

    def __init__(self, database: str = DATABASE):
        self.database = check_database(database)
        load_dotenv(ROOT / ".env")
        user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
        self._driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(user, os.getenv("NEO4J_PASSWORD")))

    def run(self, cypher: str) -> QueryResult:
        @unit_of_work(timeout=TIMEOUT_S)
        def work(tx):
            res = tx.run(cypher)
            cols = list(res.keys())
            return cols, [[to_json(r[c]) for c in cols] for r in res]

        start = time.perf_counter()
        try:
            with self._driver.session(database=self.database) as s:
                cols, rows = s.execute_read(work)
            return QueryResult(ok=True, columns=cols, rows=rows, seconds=time.perf_counter() - start)
        except Exception as e:
            return QueryResult(ok=False, error=f"{type(e).__name__}: {e}", seconds=time.perf_counter() - start)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
