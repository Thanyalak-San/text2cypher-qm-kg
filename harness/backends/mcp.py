"""Run Cypher through the ChatQMS MCP server (the MCP interface).

The server (Node.js, `mcp-server/dist/index.js`, copied byte for byte from `ChatQMS/mcp-neo4j-concrete`; its
`dist/` fingerprint equals the one recorded in the main run) is started once over stdio and spoken to
with JSON-RPC, as the original scripts did: `initialize`, then `tools/call` for `execute_cypher_query`
with `{"query": ..., "limit": 50}`.

The server reads `.env` from its working folder and lets it override the settings it is given, so it is
started from an empty temporary folder, with the connection settings from this project's `.env` and
`NEO4J_DATABASE` set to the database here. The server's own checks are kept as they are (docs/audit.md,
"Harness settings"): it rejects any query containing a write keyword as a substring, cuts rows at the
limit, and runs the rest in a read session.

`fingerprint()` gives the SHA-256 of every file under the server's `dist/` folder, for the episode record.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from dotenv import dotenv_values

from harness.backends import DATABASE, QueryResult, check_database
from harness.config import ROOT

SERVER = ROOT / "mcp-server" / "dist" / "index.js"
QUERY_TOOL = "execute_cypher_query"
LIMIT = 50                      # as the original scripts passed it
RESPONSE_TIMEOUT_S = 60         # the server's own query timeout is 30 s


class McpError(RuntimeError):
    pass


class McpBackend:
    name = "mcp"

    def __init__(self, database: str = DATABASE, server: Path = SERVER):
        self.database = check_database(database)
        self.server = server
        settings = {k: v for k, v in dotenv_values(ROOT / ".env").items() if k.startswith("NEO4J_") and v}
        if "NEO4J_USER" not in settings and "NEO4J_USERNAME" in settings:
            settings["NEO4J_USER"] = settings["NEO4J_USERNAME"]
        env = {**os.environ, **settings, "NEO4J_DATABASE": self.database}
        self._cwd = tempfile.TemporaryDirectory(prefix="mcp_server_")
        self._proc = subprocess.Popen(["node", str(server)], cwd=self._cwd.name, env=env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding="utf-8")
        self._messages: queue.Queue = queue.Queue()
        self.stderr: deque[str] = deque(maxlen=200)     # last lines of the server's log
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._id = 0
        try:
            self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                         "clientInfo": {"name": "text2cypher-harness", "version": "1.0"}})
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self.tools = self._request("tools/list", {}).get("tools", [])
        except Exception:
            self.close()
            raise

    # JSON-RPC over stdio
    def _read_stdout(self) -> None:
        for line in self._proc.stdout:
            line = line.strip()
            if line:
                try:
                    self._messages.put(json.loads(line))
                except json.JSONDecodeError:
                    self.stderr.append(f"[non-JSON stdout] {line}")

    def _read_stderr(self) -> None:
        for line in self._proc.stderr:
            self.stderr.append(line.rstrip())

    def _send(self, msg: dict) -> None:
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        deadline = time.monotonic() + RESPONSE_TIMEOUT_S
        while (left := deadline - time.monotonic()) > 0:
            try:
                msg = self._messages.get(timeout=left)
            except queue.Empty:
                break
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise McpError(f"{method}: {msg['error']}")
                return msg.get("result", {})
        if self._proc.poll() is not None:
            raise McpError(f"{method}: server exited ({self._proc.returncode}); log: {list(self.stderr)[-5:]}")
        raise McpError(f"{method}: no response within {RESPONSE_TIMEOUT_S} s")

    # queries
    def run(self, cypher: str) -> QueryResult:
        start = time.perf_counter()
        try:
            result = self._request("tools/call", {"name": QUERY_TOOL, "arguments": {"query": cypher, "limit": LIMIT}})
        except McpError as e:
            return QueryResult(ok=False, error=str(e), seconds=time.perf_counter() - start)
        seconds = time.perf_counter() - start
        text = next((c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"), "")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return QueryResult(ok=False, error=f"unreadable tool result: {text[:200]}", seconds=seconds)
        if result.get("isError") or "error" in payload or payload.get("success") is False:
            return QueryResult(ok=False, error=str(payload.get("error", payload)), seconds=seconds)
        records = payload.get("records", [])
        columns = list(records[0]) if records else []
        return QueryResult(ok=True, columns=columns, rows=[[r.get(c) for c in columns] for r in records],
                           truncated=bool(payload.get("truncated")), seconds=seconds)

    def fingerprint(self) -> dict[str, str]:
        dist = self.server.parent
        return {f.relative_to(dist).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(dist.rglob("*")) if f.is_file()}

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._cwd.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
