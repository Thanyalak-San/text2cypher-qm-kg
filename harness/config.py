"""Read and check a configuration's settings file (guide, Phase 5).

A configuration is one YAML file in configurations/ (or configurations/pilot/). load() checks it and
returns a frozen Config: unknown or missing fields, values outside their allowed sets, combinations that
make no sense, and paths that do not exist are all reported before any API call is made. It also
fingerprints every file the configuration uses (SHA-256), so each episode can record exactly which
texts it ran with. Reading the texts and building the prompt is context.py's job.

Usage (check every configuration and print its hash):
    python -m harness.config
    python -m harness.config configurations/C7.yaml configurations/pilot/*.yaml
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "configurations"
MODELS_FILE = CONFIG_DIR / "models.yaml"

FIELDS = {"id", "description", "schema", "schema_delivery", "examples", "instructions",
          "skill", "skill_loading", "interface", "max_requests", "max_calls", "models"}
PATH_FIELDS = ("schema", "examples", "instructions", "skill")
ALLOWED = {"schema_delivery": {"fixed", "on_request"},
           "skill_loading": {"none", "harness", "model"},
           "interface": {"driver", "mcp"}}


@dataclass(frozen=True)
class Config:
    id: str
    description: str
    schema: Path | None
    schema_delivery: str
    examples: Path | None
    instructions: Path | None
    skill: Path | None
    skill_loading: str
    interface: str
    max_requests: int
    max_calls: int
    models: tuple[str, ...]
    source: Path                                              # the YAML file itself
    checksums: dict[str, str] = field(default_factory=dict, hash=False)   # relative path -> SHA-256
    config_hash: str = ""                                     # settings + checksums, first 16 hex


def load_models(path: Path = MODELS_FILE) -> dict:
    """Read the shared model settings (configurations/models.yaml)."""
    models = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(models, dict) or not models:
        raise ValueError(f"{path}: no models defined")
    return models


def _rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def _files(p: Path) -> list[Path]:
    """The file itself, or every file in a folder (skill folders), skipping caches."""
    if p.is_file():
        return [p]
    return sorted(f for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts)


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def problems(raw, path: Path, known_models: set[str]) -> list[str]:
    """Every problem with one configuration; an empty list means it is valid."""
    if not isinstance(raw, dict):
        return ["the file is not a YAML mapping"]
    out = []

    # fields and values
    if unknown := set(raw) - FIELDS:
        out.append(f"unknown fields: {sorted(unknown)}")
    if missing := FIELDS - set(raw):
        out.append(f"missing fields: {sorted(missing)}")
    for k, ok in ALLOWED.items():
        if k in raw and raw[k] not in ok:
            out.append(f"{k} must be one of {sorted(ok)}, not {raw[k]!r}")
    if "id" in raw and raw["id"] != path.stem:
        out.append(f"id {raw['id']!r} does not match the file name {path.stem!r}")
    for k in ("max_requests", "max_calls"):
        if k in raw and (not isinstance(raw[k], int) or isinstance(raw[k], bool) or raw[k] < 1):
            out.append(f"{k} must be a positive whole number")
    models = raw.get("models")
    if "models" in raw:
        if not isinstance(models, list) or not models:
            out.append("models must be a non-empty list")
        elif unknown := set(models) - known_models:
            out.append(f"models not in models.yaml: {sorted(unknown)}")
        elif len(set(models)) != len(models):
            out.append("models lists a model twice")

    # combinations
    if ("skill" in raw and "skill_loading" in raw
            and (raw["skill"] is None) != (raw["skill_loading"] == "none")):
        out.append("skill and skill_loading must agree (a skill needs harness or model loading; none needs no skill)")
    if raw.get("interface") == "driver":
        if raw.get("skill") is not None:
            out.append("the driver interface has no tools, so it cannot have a skill")
        if raw.get("schema_delivery") == "on_request":
            out.append("the driver interface has no tools, so the schema cannot be delivered on request")
    if raw.get("schema") is None and raw.get("schema_delivery") == "on_request":
        out.append("schema_delivery is on_request but there is no schema")

    # paths
    for k in PATH_FIELDS:
        v = raw.get(k)
        if v is None:
            continue
        if not isinstance(v, str):
            out.append(f"{k} must be a path or null")
            continue
        p = ROOT / v
        if not p.exists():
            out.append(f"{k}: {v} not found")
        elif k == "skill" and not (p / "SKILL.md").is_file():
            out.append(f"skill: {v} has no SKILL.md")
        elif k != "skill" and not p.is_file():
            out.append(f"{k}: {v} is not a file")
    return out


def load(path: str | Path, known_models: set[str] | None = None) -> Config:
    """Check one configuration file and return it as a frozen Config; raise ValueError if invalid."""
    path = Path(path).resolve()
    if known_models is None:
        known_models = set(load_models())
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if found := problems(raw, path, known_models):
        raise ValueError(f"{path.name}: " + "; ".join(found))

    paths = {k: (ROOT / raw[k] if raw[k] is not None else None) for k in PATH_FIELDS}
    checksums = {_rel(f): _sha256(f) for p in paths.values() if p is not None for f in _files(p)}
    config_hash = hashlib.sha256(
        json.dumps([raw, checksums], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return Config(
        id=raw["id"], description=raw["description"],
        schema=paths["schema"], schema_delivery=raw["schema_delivery"],
        examples=paths["examples"], instructions=paths["instructions"],
        skill=paths["skill"], skill_loading=raw["skill_loading"],
        interface=raw["interface"], max_requests=raw["max_requests"], max_calls=raw["max_calls"],
        models=tuple(raw["models"]), source=path, checksums=checksums, config_hash=config_hash)


def load_all(paths: list[str | Path]) -> list[Config]:
    """Load several configurations; ids must be unique among them (run a plan from one folder)."""
    known = set(load_models())
    configs = [load(p, known) for p in paths]
    ids = [c.id for c in configs]
    if dupes := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"duplicate configuration ids: {dupes}")
    return configs


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or sorted(CONFIG_DIR.glob("C*.yaml")) + sorted((CONFIG_DIR / "pilot").glob("C*.yaml"))
    try:
        known = set(load_models())
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f"models.yaml: {e}")
        return 1
    bad = 0
    for p in paths:
        try:
            c = load(p, known)
            print(f"OK   {_rel(c.source):<32} {c.id:<4} {c.config_hash}  {len(c.checksums)} file(s)  models: {', '.join(c.models)}")
        except (OSError, ValueError, yaml.YAMLError) as e:
            bad += 1
            print(f"FAIL {p}: {e}")
    print(f"{len(paths) - bad} of {len(paths)} configurations OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
