"""Per-project configuration: paper-writer.toml.

The config file is found by walking up from the current directory. Every key
has a default, so a project without a config file gets the historical layout.
"""

from __future__ import annotations

import copy
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

CONFIG_NAME = "paper-writer.toml"

# Defaults reproduce the layout the skills used before configuration existed.
# `/paper-writer:init` writes `vault = "vault"` for new projects.
DEFAULTS: dict[str, Any] = {
    "paths": {
        "paper_dir": "paper",
        "main_tex": "paper/main.tex",
        "bib": "paper/ref.bib",
        "vault": "vault/paper-writer",
        "outline_dir": "outline",
        "design_dir": "design/design-details",
        "name_commands": "guidelines/name-commands.md",
    },
    "paper": {
        "field": "computer systems and networking",
        "target_venues": ["SIGCOMM", "ASPLOS", "OSDI"],
    },
    "venues": {
        "preferred_tier": ["SIGCOMM", "OSDI", "NSDI", "SOSP", "ASPLOS", "MobiCom", "CoNEXT", "EuroSys"],
    },
    "style": {
        "profile": "",    # name of a profile under the user-level profiles directory
        "path": "",       # or: a profile directory inside the project
        "overrides": "",  # optional per-project style-overrides.md (a sibling .toml is picked up too)
    },
}


class ConfigError(Exception):
    pass


def find_config(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        candidate = d / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def _merge_known(base: dict, override: dict, where: str, warnings: list[str]) -> None:
    for key, value in override.items():
        if key not in base:
            warnings.append(f"unknown config key: {where}{key}")
            continue
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{where}{key} must be a table")
            _merge_known(base[key], value, f"{where}{key}.", warnings)
        else:
            expected = type(base[key])
            if not isinstance(value, expected):
                raise ConfigError(f"{where}{key} must be {expected.__name__}, got {type(value).__name__}")
            if expected is list and not all(isinstance(v, str) for v in value):
                raise ConfigError(f"{where}{key} must be a list of strings")
            base[key] = value


class Config:
    """Resolved configuration for one project."""

    def __init__(self, data: dict, root: Path, file: Path | None, warnings: list[str]):
        self.data = data
        self.root = root
        self.file = file
        self.warnings = warnings

    @classmethod
    def load(cls, start: Path | None = None) -> "Config":
        file = find_config(start)
        data = copy.deepcopy(DEFAULTS)
        warnings: list[str] = []
        if file:
            try:
                raw = tomllib.loads(file.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"{file}: {e}") from e
            _merge_known(data, raw, "", warnings)
            root = file.parent
        else:
            root = (start or Path.cwd()).resolve()
        return cls(data, root, file, warnings)

    def get(self, dotted: str) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(dotted)
            node = node[part]
        return node

    def path(self, key: str) -> str:
        """A `[paths]` entry, relative when the project root is the cwd, else absolute."""
        return self.resolve(self.get(f"paths.{key}"))

    def resolve(self, rel: str) -> str:
        p = Path(os.path.expanduser(rel))
        if p.is_absolute():
            return str(p)
        if self.root == Path.cwd().resolve():
            return str(p)
        return str(self.root / p)

    def dump(self) -> dict:
        out = copy.deepcopy(self.data)
        out["paths"] = {k: self.resolve(v) for k, v in out["paths"].items()}
        out["project_root"] = str(self.root)
        out["config_file"] = str(self.file) if self.file else None
        return out

    def emit_warnings(self) -> None:
        for w in self.warnings:
            print(f"warning: {w}", file=sys.stderr)
