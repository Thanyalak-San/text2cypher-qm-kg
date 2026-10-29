"""Read a skill folder: its name, description and body (guide, Appendix A, "Skills").

SKILL.md starts with a YAML header between two `---` lines. Only `name` and `description` are offered to
the model (the `### Available skill` block); other header fields, such as the generic skill's `triggers`,
are never shown. The body is everything after the header, given without the header and with blank lines
stripped at both ends, so the generic skill's body is the same text in C4 (prompts/skill_body.txt) and
when loaded (C5, C6).

A skill with more files (the domain skill, C7) also lets the model read them and run its scripts:
- `read_file`: any file in the skill folder except SKILL.md (its body comes from load_skill), by name.
- `run_script`: a `.py` file in the skill folder, run with the given text on its standard input, in a
  separate Python process. The database is set explicitly (`NEO4J_DATABASE`), so a script that talks to
  Neo4j (validate.py runs EXPLAIN, read-only) uses the study database and never the server's default.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    folder: Path


def strip_blank_lines(text: str) -> str:
    """Remove blank lines at both ends; leave every other character as stored."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def read_skill(folder: Path) -> Skill:
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{folder}/SKILL.md: no YAML header")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError(f"{folder}/SKILL.md: YAML header is not closed") from None
    header = yaml.safe_load("\n".join(lines[1:end])) or {}
    for k in ("name", "description"):
        if not isinstance(header.get(k), str) or not header[k].strip():
            raise ValueError(f"{folder}/SKILL.md: header has no {k}")
    return Skill(name=header["name"].strip(), description=" ".join(header["description"].split()),
                 body=strip_blank_lines("\n".join(lines[end + 1:])), folder=folder)


NO_FILE = "No file with that name in the skill."
NO_SCRIPT = "No script with that name in the skill."
SCRIPT_TIMEOUT_S = 60


def skill_files(skill: Skill) -> dict[str, Path]:
    """Readable files by their path inside the skill folder (SKILL.md and caches left out)."""
    return {f.relative_to(skill.folder).as_posix(): f for f in sorted(skill.folder.rglob("*"))
            if f.is_file() and f.name != "SKILL.md" and "__pycache__" not in f.parts}


def _clean(name: str) -> str:
    return name.strip().removeprefix("./")


def read_file(skill: Skill, name: str) -> tuple[str, bool]:
    """(file text, found). The name may be given with or without a leading './'."""
    f = skill_files(skill).get(_clean(name))
    return (f.read_text(encoding="utf-8"), True) if f else (NO_FILE, False)


def run_script(skill: Skill, name: str, text: str, database: str) -> tuple[str, bool]:
    """(what the script printed, found). Runs `python <script>` with `text` on standard input."""
    f = skill_files(skill).get(_clean(name))
    if f is None or f.suffix != ".py":
        return NO_SCRIPT, False
    env = {**os.environ, "NEO4J_DATABASE": database, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        p = subprocess.run([sys.executable, str(f)], input=text, capture_output=True, text=True, encoding="utf-8",
                           cwd=skill.folder, env=env, timeout=SCRIPT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"The script did not finish within {SCRIPT_TIMEOUT_S} seconds.", True
    out = p.stdout.strip()
    if p.stderr.strip():
        out += ("\n" if out else "") + p.stderr.strip()
    return out or f"(no output; exit status {p.returncode})", True
