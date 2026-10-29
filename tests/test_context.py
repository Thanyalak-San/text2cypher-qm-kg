"""Tests for harness/context.py: the prompt part of T2 (guide, Appendix C).

Builds the prompt for the first question under every configuration and compares neighbours: each pair
may differ only in the blocks listed in PAIRS. Also checks the block order (Appendix B), that texts are
placed as stored, and that the generic skill body is the same text in C4 (instructions) and C5 (harness
load). The tool list is checked once tools.py exists. No database or API is needed.

Usage:
    python tests/test_context.py [--dump DIR]     # --dump writes each configuration's full prompt to DIR
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C, context as X                 # noqa: E402
from harness.skills import read_skill, strip_blank_lines      # noqa: E402

failures = 0
ORDER = ["base", "output_note", "schema", "examples", "instructions", "skill"]
# (a, b, blocks that may differ; "messages" = what follows the question)
PAIRS = [("C0", "C1", {"schema", "examples"}),
         ("C1", "C2", {"schema"}),
         ("C2", "C3", {"output_note"}),
         ("C3", "C4", {"instructions"}),
         ("C4", "C4w", {"instructions"}),
         ("C4", "C4p", {"instructions"}),
         ("C4", "C7t", {"instructions"}),
         ("C3", "C5", {"skill", "messages"}),
         ("C5", "C6", {"messages"}),
         ("C6", "C7", {"skill"}),
         ("C7", "C7f", {"messages"}),
         ("C5", "C7f", {"skill", "messages"}),
         ("C3", "C3n", {"examples"}),
         ("C6", "C6n", {"examples"}),
         ("C7", "C7n", {"examples"}),
         ("pilot/C3n", "C3n", set()),
         ("pilot/C1", "C1", {"examples"}),
         ("pilot/C3", "C3", {"examples"}),
         ("pilot/C3", "pilot/C3n", {"examples"}),
         ("pilot/C3", "pilot/C4", {"instructions"}),
         ("pilot/C4", "pilot/C4n", {"examples"}),
         ("pilot/C3", "pilot/C5", {"skill", "messages"}),
         ("pilot/C5", "pilot/C5n", {"examples"})]


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def parts(p: X.Prompt) -> dict:
    return {**p.blocks, "messages": json.dumps(p.messages[1:], sort_keys=True)}


question = X.load_questions()[0]["question"]
paths = sorted(C.CONFIG_DIR.glob("C*.yaml")) + sorted((C.CONFIG_DIR / "pilot").glob("C*.yaml"))
known = set(C.load_models())
configs = {p.relative_to(C.CONFIG_DIR).with_suffix("").as_posix(): C.load(p, known) for p in paths}
prompts = {k: X.build(c, question) for k, c in configs.items()}

# neighbours differ only where expected
for a, b, allowed in PAIRS:
    if a not in prompts or b not in prompts:       # the pilot configurations are not in the public copy
        print(f"SKIP  T2 {a} vs {b}: configuration not found")
        continue
    pa, pb = parts(prompts[a]), parts(prompts[b])
    differ = {k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)}
    check(f"T2 {a} vs {b}: differ in {sorted(allowed)}", differ == allowed, f"differ in {sorted(differ)}")

# every configuration
generic = strip_blank_lines((ROOT / "prompts" / "skill_body.txt").read_text(encoding="utf-8"))
for k, p in prompts.items():
    c = configs[k]
    names = list(p.blocks)
    check(f"{k}: block order", names == [n for n in ORDER if n in names], str(names))
    check(f"{k}: system is the blocks joined by one blank line", p.system == "\n\n".join(p.blocks.values()))
    check(f"{k}: no block ends in a blank line or space",
          all(t == t.rstrip() for t in p.blocks.values()))
    check(f"{k}: first message is the question only", p.messages[0] == {"role": "user", "text": question})
    # few_shot_original.txt contains P1 word for word (example 1; the reason few_shot.txt replaced it),
    # so look for the question outside the examples block
    check(f"{k}: question not placed in the system prompt",
          all(question not in t for n, t in p.blocks.items() if n != "examples"))
    check(f"{k}: output note matches the interface",
          p.blocks["output_note"] == X.read_text(X.OUTPUT_NOTES[c.interface]))
    for field, header in (("schema", "### Schema"), ("examples", "### Examples"), ("instructions", "### Instructions")):
        path = getattr(c, field)
        if path is not None:
            check(f"{k}: {field} placed as stored", p.blocks[field] == header + "\n" + X.read_text(path))
    if c.skill is not None:
        s = read_skill(c.skill)
        check(f"{k}: skill block is name and description only",
              p.blocks["skill"] == f"### Available skill\nname: {s.name}\ndescription: {s.description}")
        check(f"{k}: skill body not in the system prompt", s.body not in p.system)
    check(f"{k}: harness load only when skill_loading is harness",
          (len(p.messages) == 3) == (c.skill_loading == "harness"), str(len(p.messages)))

# the generic skill: same body as instructions (C4) and when loaded (C5); header fields never shown
c5 = prompts["C5"].messages
check("C5: harness load calls load_skill with the real name and fixed id",
      c5[1]["tool_calls"] == [{"id": "harness_load", "name": "load_skill", "arguments": {"name": "neo4j-query"}}])
check("C5: tool result answers the harness load", c5[2]["tool_call_id"] == "harness_load")
check("C5: loaded body equals prompts/skill_body.txt", c5[2]["content"] == generic)
check("C4: instructions equal prompts/skill_body.txt", prompts["C4"].blocks["instructions"] == "### Instructions\n" + generic)
check("C5: SKILL.md header fields other than name/description not shown", "triggers" not in prompts["C5"].system)

# C7f: the harness loads the domain skill, as C5 loads the generic one
c7f = prompts["C7f"].messages
domain = read_skill(configs["C7f"].skill)
check("C7f: harness load calls load_skill with the domain skill's name and the fixed id",
      c7f[1]["tool_calls"] == [{"id": "harness_load", "name": "load_skill", "arguments": {"name": domain.name}}])
check("C7f: loaded body is the domain skill body", c7f[2]["content"] == domain.body)
check("prompt hashes differ across configurations with different prompts",
      len({p.prompt_hash for p in prompts.values()}) == len({(p.system, json.dumps(p.messages)) for p in prompts.values()}))

if "--dump" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--dump") + 1])
    out.mkdir(parents=True, exist_ok=True)
    for k, p in prompts.items():
        lines = [f"=== {k}  prompt_hash {p.prompt_hash}", "=== SYSTEM", p.system]
        for m in p.messages:
            lines += [f"=== {m['role'].upper()}", m.get("text") or m.get("content") or json.dumps(m["tool_calls"])]
        (out / f"{k.replace('/', '_')}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Prompts written to {out}")

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
