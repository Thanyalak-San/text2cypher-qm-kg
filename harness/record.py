"""Write what happened in each episode (guide, section 7).

A run folder holds two JSON-lines files:

- `episodes.jsonl`: one line per episode (fields below). Each line is flushed to disk as it is written,
  so a stopped run loses nothing and can resume.
- `prompts.jsonl`: each distinct prompt once: system prompt, the messages before the model's first reply,
  and the tool list, keyed by `prompt_id` (a hash of all three). Episodes refer to it by `prompt_id`.

Episode fields: identification (configuration, model, model ID returned, question, question set, run,
session), reproducibility (git commit, configuration hash and file checksums, API version, MCP server
fingerprint), the conversation after the prompt, every model call (tokens, stop reason, cut off,
attempts, retry waits, request ID), every request, the query with its row count, a sample of rows and
any error, totals (tokens in/out/cached, time), the skill-use flags and the failure reason.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from harness.config import ROOT, Config
from harness.context import Prompt
from harness.loop import Episode

SAMPLE_ROWS = 5


def git_state() -> dict:
    """Commit of the harness and whether tracked files have uncommitted changes."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def prompt_id(prompt: Prompt, tools: list[dict]) -> str:
    blob = json.dumps([prompt.system, prompt.messages, tools], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class RunWriter:
    def __init__(self, folder: Path):
        self.folder = Path(folder)                 # created on the first write, not here
        self.episodes_path = self.folder / "episodes.jsonl"
        self.prompts_path = self.folder / "prompts.jsonl"
        self.prompt_ids = {json.loads(l)["prompt_id"] for l in self._lines(self.prompts_path)}

    @staticmethod
    def _lines(path: Path) -> list[str]:
        return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []

    def done(self) -> set[tuple]:
        """(config, model, qset, qid, run) of the episodes already recorded, for resuming."""
        out = set()
        for l in self._lines(self.episodes_path):
            r = json.loads(l)
            out.add((r["config"], r["model"], r["qset"], r["qid"], r["run_idx"]))
        return out

    def _append(self, path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def write(self, record: dict, prompt: Prompt, tools: list[dict]) -> None:
        pid = record["prompt_id"]
        if pid not in self.prompt_ids:
            self._append(self.prompts_path, {"prompt_id": pid, "system": prompt.system,
                                             "messages": prompt.messages, "tools": tools})
            self.prompt_ids.add(pid)
        self._append(self.episodes_path, record)


def make_record(*, ep: Episode, config: Config, model_key: str, request_settings: dict, question: dict,
                qset: str, run_idx: int, session: str, prompt: Prompt, tools: list[dict], git: dict,
                mcp_fingerprint: dict | None) -> dict:
    calls = [asdict(c) for c in ep.calls]
    res = ep.result
    return {
        # identification
        "benchmark": "qp", "qset": qset, "config": config.id, "model": model_key, "qid": question["id"],
        "run_idx": run_idx, "session": session, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_id": request_settings.get("model"),
        "model_ids_returned": sorted({c["model_returned"] for c in calls}),
        # reproducibility
        "git_commit": git["commit"], "git_dirty": git["dirty"],
        "config_hash": config.config_hash, "config_file": config.source.relative_to(ROOT).as_posix(),
        "checksums": config.checksums, "request_settings": request_settings,
        "api_versions": sorted({c["api_version"] for c in calls}), "mcp_fingerprint": mcp_fingerprint,
        "prompt_id": prompt_id(prompt, tools),
        # what happened
        "question": question["question"],
        "query": ep.query,
        "query_ok": res.ok if res else None,
        "query_error": res.error if res else None,        # as the interface reported it (MCP errors kept here)
        "row_count": len(res.rows) if res else None,
        "columns": res.columns if res else None,
        "rows_sample": res.rows[:SAMPLE_ROWS] if res else None,
        "truncated": res.truncated if res else None,
        "query_seconds": res.seconds if res else None,
        "failure": ep.failure,
        "messages": ep.messages,
        "calls": calls,
        "requests": ep.requests,
        "ignored_calls": ep.ignored_calls, "parallel_calls": ep.parallel_calls, "cypher_blocks": ep.cypher_blocks,
        # skill use
        "skill_loaded": ep.skill_loaded, "harness_loaded": config.skill_loading == "harness",
        "validator_run": ep.validator_run, "files_read": ep.files_read,
        "schema_requested": ep.schema_requested,                    # only C3r, C3rn offer get_schema
        "request_limit_hit": ep.request_limit_hit,
        "n_requests": sum(r["counted"] for r in ep.requests), "n_calls": len(calls),
        # efficiency
        "tokens_in": sum(c["input_tokens"] for c in calls),
        "tokens_out": sum(c["output_tokens"] for c in calls),
        "tokens_cached": sum(c["cached_tokens"] for c in calls),
        "tokens_reasoning": sum(c.get("reasoning_tokens", 0) for c in calls),
        "max_output_tokens_call": max((c["output_tokens"] for c in calls), default=0),
        "any_cut_off": any(c["cut_off"] for c in calls),
        "seconds": ep.seconds, "retry_wait_s": ep.retry_wait_s, "ct_s": ep.seconds - ep.retry_wait_s,
    }
