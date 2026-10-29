"""Build what the model sees at the start of an episode (guide, section 6 and Appendix B).

Everything before the question goes in the system prompt, in this order:

    [base prompt]
    [output note: driver or MCP]
    ### Schema            only if the schema is fixed
    ### Examples          only if examples are used
    ### Instructions      C4, C4w, C4p, C7t
    ### Available skill   name and description, in C5, C6, C7

The question is the first user message, as in both original scripts (Phase 1: the schema and skill text
were in the system prompt and the user message was only the question). In C5 the harness then adds a
skill load, as if the model had asked for it: an assistant tool call (fixed id "harness_load") and the
tool result holding the skill body.

Texts are used exactly as stored, with only trailing blank lines stripped (the skill body: blank lines at
both ends, see skills.py). Blocks are joined by one blank line; headers are identical in every
configuration.

Messages use one neutral format, translated for each API in harness/models/:

    {"role": "user", "text": str}
    {"role": "assistant", "text": str | None, "tool_calls": [{"id": str, "name": str, "arguments": dict}]}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}

Tool definitions are tools.py's job.

Usage (print the prompt for one configuration and question):
    python -m harness.context configurations/C5.yaml [P1]
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from harness.config import ROOT, Config, load
from harness.skills import read_skill, strip_blank_lines

BASE_PROMPT = ROOT / "prompts" / "base_prompt.txt"
OUTPUT_NOTES = {"driver": ROOT / "prompts" / "output_note_driver.txt",
                "mcp": ROOT / "prompts" / "output_note_mcp.txt"}
QUESTIONS = ROOT / "data" / "questions_original.jsonl"
HEADERS = {"schema": "### Schema", "examples": "### Examples",
           "instructions": "### Instructions", "skill": "### Available skill"}
LOAD_TOOL = "load_skill"
HARNESS_LOAD_ID = "harness_load"


@dataclass(frozen=True)
class Prompt:
    system: str
    messages: list[dict]
    blocks: dict[str, str] = field(default_factory=dict)     # block name -> text as placed (for T2)
    prompt_hash: str = ""                                    # system + messages, first 16 hex


def read_text(path: Path) -> str:
    """A prompt text exactly as stored, with trailing blank lines (and the final newline) stripped."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def build(config: Config, question: str) -> Prompt:
    blocks = {"base": read_text(BASE_PROMPT), "output_note": read_text(OUTPUT_NOTES[config.interface])}
    if config.schema is not None and config.schema_delivery == "fixed":
        blocks["schema"] = HEADERS["schema"] + "\n" + read_text(config.schema)
    if config.examples is not None:
        blocks["examples"] = HEADERS["examples"] + "\n" + read_text(config.examples)
    if config.instructions is not None:
        blocks["instructions"] = HEADERS["instructions"] + "\n" + read_text(config.instructions)
    skill = read_skill(config.skill) if config.skill is not None else None
    if skill is not None:
        blocks["skill"] = f"{HEADERS['skill']}\nname: {skill.name}\ndescription: {skill.description}"
    system = "\n\n".join(blocks.values())

    messages = [{"role": "user", "text": question}]
    if skill is not None and config.skill_loading == "harness":
        messages += [
            {"role": "assistant", "text": None,
             "tool_calls": [{"id": HARNESS_LOAD_ID, "name": LOAD_TOOL, "arguments": {"name": skill.name}}]},
            {"role": "tool", "tool_call_id": HARNESS_LOAD_ID, "name": LOAD_TOOL, "content": skill.body}]
    prompt_hash = hashlib.sha256(json.dumps([system, messages], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return Prompt(system=system, messages=messages, blocks=blocks, prompt_hash=prompt_hash)


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    """The question records of a question file (the header line is skipped)."""
    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in records if not r.get("_header")]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    config = load(argv[0])
    qid = argv[1] if len(argv) > 1 else "P1"
    question = next(q for q in load_questions() if q["id"] == qid)["question"]
    p = build(config, question)
    print(f"=== {config.id} / {qid}  prompt_hash {p.prompt_hash}\n=== SYSTEM\n{p.system}")
    for m in p.messages:
        print(f"=== {m['role'].upper()}")
        print(m.get("text") or m.get("content") or json.dumps(m["tool_calls"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
