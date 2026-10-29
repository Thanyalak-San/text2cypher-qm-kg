"""Plan and run episodes: configurations × questions × runs (guide, Phase 5 and 7).

- Plan: every configuration in the given folder (or files), every question in the question file, runs
  1..N, for each model the configuration lists (filtered by --model). Each episode records its question's own
  set (`qset` in the question file, original or new); --qset is used only for questions without one. Each run's episodes are shuffled
  with seed 1000 + run number, and run 1 is done before run 2, and so on.
- Resume: episodes already in the output folder's episodes.jsonl are skipped. The folder refuses to mix
  versions: if an earlier session recorded a configuration with a different configuration hash, or a
  different question file, the run stops.
- Sequential: one episode at a time.
- API failures: an episode whose model call fails 5 times (ApiFailure) is moved to the end of the queue
  once; if it fails again it is logged in failures.jsonl and left for the next session.
- Git: refuses to start if tracked files have uncommitted changes (records name a commit that must be
  the code that ran). --dry-run only prints the plan and needs a clean tree for nothing.

Writes to the output folder: episodes.jsonl and prompts.jsonl (harness/record.py), sessions.jsonl (one
line per session: arguments, git commit, versions, plan size, counts) and failures.jsonl.

Usage:
    python -m harness.run configurations/pilot --runs 3 --out runs/pilot --dry-run
    python -m harness.run configurations/pilot --runs 3 --out runs/pilot
    python -m harness.run configurations/pilot --runs 3 --out runs/pilot --limit 10     # first 10 only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from harness import config as C, context as X
from harness.config import ROOT, Config
from harness.loop import run_episode
from harness.models.base import ApiFailure, request_settings
from harness.record import RunWriter, git_state, make_record
from harness.skills import read_skill
from harness.tools import tools_for

SEED_BASE = 1000


@dataclass(frozen=True)
class Job:
    config: str
    model: str
    qid: str
    run_idx: int

    def key(self, qset: str) -> tuple:
        return (self.config, self.model, qset, self.qid, self.run_idx)


def qset_of(question: dict, default: str) -> str:
    """The question's own set from the question file; `default` (--qset) only if it has none."""
    return question.get("qset", default)


def plan(configs: list[Config], questions: list[dict], runs: int, models: set[str] | None = None) -> list[Job]:
    jobs = []
    for run_idx in range(1, runs + 1):
        batch = [Job(c.id, m, q["id"], run_idx) for c in configs for m in c.models
                 if models is None or m in models for q in questions]
        random.Random(SEED_BASE + run_idx).shuffle(batch)
        jobs += batch
    return jobs


def config_paths(targets: list[str]) -> list[Path]:
    paths = []
    for t in targets:
        p = Path(t)
        paths += sorted(p.glob("C*.yaml")) if p.is_dir() else [p]
    return paths


def check_folder(writer: RunWriter, configs: list[Config], questions_sha: str) -> None:
    """Stop if the folder already holds episodes from other configuration versions or another question file."""
    current = {c.id: c.config_hash for c in configs}
    seen: dict[str, set] = {}
    files = set()
    for l in writer._lines(writer.episodes_path):
        r = json.loads(l)
        seen.setdefault(r["config"], set()).add(r["config_hash"])
        files.add(r.get("questions_sha256"))
    bad = [f"{cid}: recorded {sorted(h)}, now {current[cid]}" for cid, h in seen.items()
           if cid in current and h != {current[cid]}]
    if bad:
        raise SystemExit("This folder holds episodes from other configuration versions:\n  " + "\n  ".join(bad)
                         + "\nUse a new --out folder, or restore the configuration files.")
    if files - {questions_sha}:
        raise SystemExit("This folder holds episodes from another question file. Use a new --out folder.")


def default_adapter(model_key: str, settings: dict):
    if model_key == "claude":
        from harness.models.claude import ClaudeAdapter
        return ClaudeAdapter(settings)
    if model_key == "gpt":
        from harness.models.gpt import GptAdapter
        return GptAdapter(settings)
    raise NotImplementedError(f"no adapter for model '{model_key}'")


def execute(jobs: list[Job], configs: dict[str, Config], questions: dict[str, dict], qset: str, questions_sha: str,
            writer: RunWriter, session: str, git: dict, adapters: dict, backends: dict, mcp_fingerprint,
            log=print) -> Counter:
    counts = Counter()
    queue = deque((j, 0) for j in jobs)
    total = len(jobs)
    n = 0
    while queue:
        job, tries = queue.popleft()
        cfg, q = configs[job.config], questions[job.qid]
        prompt = X.build(cfg, q["question"])
        tools = tools_for(cfg)
        adapter = adapters[job.model]
        try:
            ep = run_episode(cfg, prompt, tools, adapter, backends[cfg.interface],
                             read_skill(cfg.skill) if cfg.skill else None)
        except ApiFailure as e:
            if tries == 0:
                queue.append((job, 1))
                counts["requeued"] += 1
                log(f"  API failure, moved to the end of the queue: {job} ({e})")
            else:
                writer._append(writer.folder / "failures.jsonl",
                               {"session": session, "job": job.__dict__, "error": str(e),
                                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                counts["api_failed"] += 1
                log(f"  API failure again, left for the next session: {job}")
            continue
        settings = request_settings(adapter, adapter.request(prompt.system, prompt.messages, tools))
        rec = make_record(ep=ep, config=cfg, model_key=job.model, request_settings=settings, question=q,
                          qset=qset_of(q, qset), run_idx=job.run_idx, session=session, prompt=prompt, tools=tools, git=git,
                          mcp_fingerprint=mcp_fingerprint if cfg.interface == "mcp" else None)
        rec["questions_sha256"] = questions_sha
        writer.write(rec, prompt, tools)
        n += 1
        counts["done"] += 1
        counts[f"failure: {ep.failure}"] += 1
        counts["tokens_in"] += rec["tokens_in"]
        counts["tokens_out"] += rec["tokens_out"]
        log(f"[{n}/{total}] {job.config} {job.model} {job.qid} run {job.run_idx}: {ep.failure}, "
            f"calls {rec['n_calls']}, tokens {rec['tokens_in']}/{rec['tokens_out']}, ct {rec['ct_s']:.1f}s")
    return counts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("configs", nargs="+", help="configuration folder(s) or YAML file(s)")
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--questions-file", type=Path, default=X.QUESTIONS)
    ap.add_argument("--qset", default="original", help="set for questions without a qset field (default: original)")
    ap.add_argument("--model", action="append", help="only these models (default: all a configuration lists)")
    ap.add_argument("--limit", type=int, help="run at most this many episodes in this session")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    args = ap.parse_args(argv)

    models = C.load_models()
    configs = C.load_all(config_paths(args.configs))
    questions = X.load_questions(args.questions_file)
    questions_sha = hashlib.sha256(args.questions_file.read_bytes()).hexdigest()
    jobs = plan(configs, questions, args.runs, set(args.model) if args.model else None)
    writer = RunWriter(args.out)
    check_folder(writer, configs, questions_sha)
    done = writer.done()
    qsets = {q["id"]: qset_of(q, args.qset) for q in questions}
    todo = [j for j in jobs if j.key(qsets[j.qid]) not in done]
    if args.limit is not None:
        todo = todo[:args.limit]

    per_config = Counter(j.config for j in jobs)
    print(f"Plan: {len(jobs)} episodes ({len(configs)} configurations x {len(questions)} questions x {args.runs} runs"
          f"{' x models' if any(len(c.models) > 1 for c in configs) and not args.model else ''}); "
          f"{len(jobs) - len([j for j in jobs if j.key(qsets[j.qid]) not in done])} already done; {len(todo)} to run now.")
    print("  per configuration: " + ", ".join(f"{k} {v}" for k, v in sorted(per_config.items())))
    if args.dry_run:
        for j in todo[:10]:
            print(f"  {j}")
        if len(todo) > 10:
            print(f"  ... {len(todo) - 10} more")
        return 0
    if not todo:
        print("Nothing to run.")
        return 0

    git = git_state()
    if git["dirty"]:
        raise SystemExit("Tracked files have uncommitted changes. Commit them first, so the records name the code that ran.")
    load_dotenv(ROOT / ".env")
    session = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    used = {j.model for j in todo}
    adapters = {m: default_adapter(m, models[m]) for m in used}
    by_id = {c.id: c for c in configs}
    interfaces = {by_id[j.config].interface for j in todo}

    from harness.backends.driver import DriverBackend
    backends, fingerprint = {}, None
    with DriverBackend() as driver:
        backends["driver"] = driver
        mcp = None
        if "mcp" in interfaces:
            from harness.backends.mcp import McpBackend
            mcp = McpBackend()
            backends["mcp"] = mcp
            fingerprint = mcp.fingerprint()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        counts = Counter()
        try:
            counts = execute(todo, by_id, {q["id"]: q for q in questions}, args.qset, questions_sha, writer, session,
                             git, adapters, backends, fingerprint)
        except KeyboardInterrupt:
            print("Stopped. Finished episodes are saved; run the same command to resume.")
        finally:
            if mcp is not None:
                mcp.close()
            import anthropic
            writer._append(writer.folder / "sessions.jsonl", {
                "session": session, "started": started,
                "ended": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
                "git": git, "python": platform.python_version(), "anthropic": anthropic.__version__,
                "questions_sha256": questions_sha, "plan": len(jobs), "to_run": len(todo), "counts": dict(counts),
                "config_hashes": {c.id: c.config_hash for c in configs}})
    print("Session counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
