"""Make a readable page of a run folder's records, for checking by hand.

Reads episodes.jsonl and prompts.jsonl and writes view.html in the same folder (a local, self-contained
page; nothing is sent anywhere). One card per episode: identification, the query and its result, each
model call, the conversation, every other field, and the full prompt the model saw.

Usage:
    python scripts/view_run.py                                   # the newest run folder under runs/
    python scripts/view_run.py runs/smoke/20261022-174856-21c144   # a given run folder
"""

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ["config", "model", "qid", "run_idx", "failure", "n_calls", "n_requests", "tokens_in", "tokens_out",
        "ct_s", "row_count", "query_ok", "query_error", "skill_loaded", "request_limit_hit"]
SHOWN = set(MAIN) | {"question", "query", "columns", "rows_sample", "calls", "messages", "prompt_id"}
CALL_COLS = ["stop_reason", "cut_off", "input_tokens", "output_tokens", "cached_tokens", "model_returned",
             "api_version", "attempts", "retry_wait_s", "seconds", "request_id"]


def esc(v) -> str:
    return html.escape(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str))


def pre(v) -> str:
    text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2, default=str)
    return f"<pre>{html.escape(text)}</pre>"


def table(rows: list[list], head: list[str]) -> str:
    out = "<table><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr>"
    for r in rows:
        out += "<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>"
    return out + "</table>"


def message(m: dict) -> str:
    if m["role"] == "assistant":
        body = (pre(m["text"]) if m.get("text") else "") + "".join(
            f"<div class=tc>tool call <b>{esc(c['name'])}</b>{pre(c['arguments'])}</div>" for c in m.get("tool_calls", []))
        return f"<div class=msg><span class=role>assistant</span>{body}</div>"
    if m["role"] == "tool":
        return f"<div class=msg><span class=role>tool result ({esc(m['name'])})</span>{pre(m['content'])}</div>"
    return f"<div class=msg><span class=role>user</span>{pre(m['text'])}</div>"


def card(r: dict, prompt: dict | None) -> str:
    s = f"<section><h2>{esc(r['config'])} · {esc(r['qid'])} · run {r['run_idx']} · <span class=f>{esc(r['failure'])}</span></h2>"
    s += f"<p class=q>{esc(r['question'])}</p>"
    s += table([[r.get(k) if k != "ct_s" else round(r[k], 3) for k in MAIN]], MAIN)
    s += "<h3>Query</h3>" + pre(r["query"] or "(none)")
    if r.get("query_ok") is False:
        s += "<h3>Result</h3><p>Query failed:</p>" + pre(r["query_error"])
    elif r.get("columns") is not None:
        s += f"<h3>Result (first {len(r['rows_sample'])} of {r['row_count']} rows)</h3>"
        s += table(r["rows_sample"], r["columns"]) if r["row_count"] else "<p>(no rows)</p>"
    s += "<h3>Model calls</h3>" + table([[c.get(k) for k in CALL_COLS] for c in r["calls"]], CALL_COLS)
    s += "<h3>Conversation after the prompt</h3>" + "".join(message(m) for m in r["messages"])
    s += "<details><summary>All other fields</summary>" + pre({k: v for k, v in r.items() if k not in SHOWN}) + "</details>"
    if prompt:
        s += f"<details><summary>Prompt the model saw (prompt_id {esc(r['prompt_id'])})</summary>"
        s += "<h4>System</h4>" + pre(prompt["system"]) + "<h4>Messages before the first reply</h4>"
        s += "".join(message(m) for m in prompt["messages"]) + "<h4>Tools</h4>" + pre(prompt["tools"]) + "</details>"
    return s + "</section>"


STYLE = """
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--card:#fff;--line:#e7e5e4;--acc:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#e7e5e4;--mut:#a8a29e;--card:#292524;--line:#44403c;--acc:#f59e0b}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:16px}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:16px 0}
h2{font-size:16px;margin:0 0 4px} h3{font-size:13px;color:var(--mut);margin:14px 0 4px;text-transform:uppercase;letter-spacing:.04em}
.q{margin:0 0 8px;font-style:italic} .f{color:var(--acc)} .role{font-size:12px;color:var(--mut)}
table{border-collapse:collapse;font-size:12.5px;display:block;overflow-x:auto} th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top}
pre{margin:4px 0;padding:8px;background:var(--bg);border-radius:6px;white-space:pre-wrap;word-break:break-word;font:12.5px/1.45 ui-monospace,Consolas,monospace}
.msg{border-left:3px solid var(--line);padding-left:8px;margin:6px 0} .tc{margin-top:4px}
details{margin-top:10px} summary{cursor:pointer;color:var(--mut)}
"""


def newest_run() -> Path:
    runs = [f.parent for f in (ROOT / "runs").rglob("episodes.jsonl")]
    if not runs:
        raise SystemExit("No run folders with an episodes.jsonl under runs/.")
    return max(runs, key=lambda f: (f / "episodes.jsonl").stat().st_mtime)


def main(folder: Path) -> None:
    if not (folder / "episodes.jsonl").is_file():
        raise SystemExit(f"No episodes.jsonl in {folder}. Give a run folder, e.g. runs/smoke/<session name>, "
                         f"or no argument for the newest run.")
    episodes = [json.loads(l) for l in (folder / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    prompts = {}
    if (folder / "prompts.jsonl").exists():
        for l in (folder / "prompts.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                p = json.loads(l)
                prompts[p["prompt_id"]] = p
    body = "".join(card(r, prompts.get(r["prompt_id"])) for r in episodes)
    page = (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Run Records</title><style>{STYLE}</style></head><body><main>"
            f"<h1 style='font-size:18px'>{esc(folder.name)} · {len(episodes)} episode(s)</h1>{body}</main></body></html>")
    out = folder / "view.html"
    out.write_text(page, encoding="utf-8")
    print(f"Saved {out}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]) if len(sys.argv) == 2 else newest_run())
