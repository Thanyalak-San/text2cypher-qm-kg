"""Tests for harness/config.py (Phase 5).

Every real configuration in configurations/ must load; planted mistakes in copies of them must be
caught with a clear message. No database or API is needed.

Usage:
    python tests/test_config.py
"""

import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import config as C          # noqa: E402

failures = 0
KNOWN = set(C.load_models())
BASE = yaml.safe_load((C.CONFIG_DIR / "C7.yaml").read_text(encoding="utf-8"))


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    failures += not ok


def planted(name: str, changes: dict, expect: str, file_id: str | None = None) -> None:
    """Write a copy of C7 with `changes` applied; load() must fail with a message containing `expect`."""
    raw = {**BASE, **changes}
    for k, v in changes.items():
        if v is ...:
            raw.pop(k)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / f"{file_id or raw.get('id', 'X')}.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        try:
            C.load(path, KNOWN)
            check(name, False, "loaded without error")
        except ValueError as e:
            check(name, expect in str(e), f"message was: {e}")


# every real configuration loads
real = sorted(C.CONFIG_DIR.glob("C*.yaml"))
pilot = sorted((C.CONFIG_DIR / "pilot").glob("C*.yaml"))
for group in (real, pilot):
    if not group:                                   # the pilot configurations are not in the public copy
        print("SKIP  configurations in pilot/: folder not found")
        continue
    try:
        configs = C.load_all(group)
        check(f"{len(configs)} configurations in {group[0].parent.name}/ load", True)
    except ValueError as e:
        check(f"configurations in {group[0].parent.name}/ load", False, str(e))

c7 = C.load(C.CONFIG_DIR / "C7.yaml", KNOWN)
check("C7 fingerprints the skill files", any(k.endswith("validate.py") for k in c7.checksums))
check("C7 hash is stable", C.load(C.CONFIG_DIR / "C7.yaml", KNOWN).config_hash == c7.config_hash)
try:
    c7.id = "X"
    check("Config cannot be changed", False)
except AttributeError:
    check("Config cannot be changed", True)

# planted mistakes
planted("typo in a field name", {"instruction": None}, "unknown fields")
planted("missing field", {"max_calls": ...}, "missing fields")
planted("value outside its set", {"interface": "http"}, "interface must be one of")
planted("id differs from file name", {}, "does not match the file name", file_id="C99")
planted("non-positive limit", {"max_requests": 0}, "max_requests must be a positive")
planted("unknown model", {"models": ["claude", "llama"]}, "models not in models.yaml")
planted("skill without loading", {"skill_loading": "none"}, "skill and skill_loading must agree")
planted("loading without skill", {"skill": None}, "skill and skill_loading must agree")
planted("skill under the driver", {"interface": "driver"}, "cannot have a skill")
planted("schema on request without schema", {"schema": None, "schema_delivery": "on_request"}, "there is no schema")
planted("missing file", {"examples": "prompts/nope.txt"}, "not found")
planted("skill folder without SKILL.md", {"skill": "prompts"}, "has no SKILL.md")
planted("file field given a folder", {"instructions": "prompts"}, "is not a file")

print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
