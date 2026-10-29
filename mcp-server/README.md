# MCP server (mcp-neo4j-concrete)

The Model Context Protocol server used by the Neo4j-MCP configurations (C2–C7t). It offers three tools over stdio:
`get_schema`, `execute_cypher_query` (read-only, with a row limit and a timeout) and `validate_cypher`. The harness
uses only `execute_cypher_query`; it starts the server itself (`harness/backends/mcp.py`), so there is nothing to
run by hand.

`dist/` is the build the study ran: copied byte for byte from the author's ChatQMS project, and its SHA-256 per file
equals the `mcp_fingerprint` recorded in every main-run episode. Use it as it is to reproduce the study; rebuilding
from `src/` with another TypeScript version may give different files.

## Setup

Node.js (tested with v26.12.0). Install the packages from the lock file:

```bash
cd mcp-server
npm ci
```

The server reads `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` from its environment; the harness passes them from
the project's `.env` and sets `NEO4J_DATABASE=qmsoriginal`. Other settings (`RESULT_LIMIT`, `QUERY_TIMEOUT_MS`,
`SCHEMA_CACHE_TTL_MS`, `LOG_LEVEL`, `MCP_SERVER_NAME`) keep their defaults in the study.

To rebuild from source (not needed for reproduction): `npm run build`.
