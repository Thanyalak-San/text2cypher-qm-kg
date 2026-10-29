"""Run Cypher on the `qmsoriginal` database, read-only: through the Neo4j driver or the MCP server.

Both backends return a QueryResult with the same row format (a list of columns and a list of rows, values
as plain JSON), so their results can be compared directly (T1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

DATABASE = "qmsoriginal"
PROTECTED = {"neo4j", "system"}


@dataclass
class QueryResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    error: str | None = None
    truncated: bool = False          # MCP only: the server cut the rows at its limit
    seconds: float = 0.0


def check_database(database: str) -> str:
    if database.lower() in PROTECTED:
        raise ValueError(f"Refusing to run on the '{database}' database.")
    return database
