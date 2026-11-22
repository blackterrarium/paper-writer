#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""pw: helper CLI for the paper-writer plugin.

Usage: pw.py <group> <command> [args...]

config
    dump                      Resolved config as JSON (paths, paper, venues, style,
                              project_root, config_file). Paths are relative to the
                              cwd when it is the project root, else absolute.
    get <dotted.key>          One value (strings bare, others as JSON), e.g. paths.bib

venue
    normalize <venue> [--year Y]   Short venue name (e.g. "SIGCOMM 2024"), empty if unknown
    is-target <venue>              "true"/"false": is the venue in paper-search scope
    list                           The venue table as JSON

style
    resolve                   Active profile and its files as JSON
    rules                     Merged rules (defaults + profile + overrides) as JSON
    scan <file.tex>           Deterministic style scan as JSON
    validate [<dir>]          Check a profile directory (default: the active profile)
    import-legacy <style.md> [--out rules.toml]
                              Derive rules.toml from an old-format style guide

init [options]                    Scaffold a project in the cwd (never overwrites files)
    --title T            \title for main.tex (default "System: A Descriptive Subtitle")
    --field F            paper.field
    --venues A,B,C       paper.target_venues
    --profile NAME       style.profile
    --vault DIR          paths.vault (default "vault")
    --template SRC       auto (CTAN, then local TeX) | ctan | tex | none
init allow-network [--print]      Add the skills' hosts to .claude/settings.json
                                  (--print: output the merged settings, write nothing)
init profiles                     User-level style profiles as JSON

vault [--vault DIR] <command>     Vault root: --vault, else $PAPER_VAULT_ROOT, else paths.vault
    load_tree | find_doi <doi> | list_paper_files | papers_under <topic>
    sanitize <title> | write_paper <json> | attach_paper <leaf-path> <title>
    add_subtopic <parent-path> <title> | create_topic <path> <desc> [--leaf]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwlib import style as stylelib  # noqa: E402
from pwlib import venues  # noqa: E402
from pwlib.config import Config, ConfigError  # noqa: E402
from pwlib.vault import Vault  # noqa: E402


def _usage(msg: str) -> int:
    print(f"usage: pw.py {msg}", file=sys.stderr)
    return 2


def _json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ---------- vault ----------


def vault_cli(cfg: Config, argv: list[str]) -> int:
    root = None
    if argv[:1] == ["--vault"]:
        if len(argv) < 2:
            return _usage("vault --vault DIR <command>")
        root, argv = argv[1], argv[2:]
    root = root or os.environ.get("PAPER_VAULT_ROOT") or cfg.path("vault")
    vault = Vault(root)
    if not argv:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]

    if cmd == "load_tree":
        _json(vault.load_topic_tree())
    elif cmd == "find_doi":
        if not args:
            return _usage("vault find_doi <doi>")
        p = vault.find_paper_by_doi(args[0])
        print(str(p) if p else "")
    elif cmd == "list_paper_files":
        for p in vault.list_paper_files():
            print(p)
    elif cmd == "papers_under":
        if not args:
            return _usage("vault papers_under <topic-title-or-path>")
        topic = args[0].rsplit("/", 1)[-1].removesuffix(".md")
        for p in vault.papers_under(topic):
            print(p)
    elif cmd == "sanitize":
        if not args:
            return _usage("vault sanitize <title>")
        print(Vault.sanitize_title(" ".join(args)))
    elif cmd == "write_paper":
        if not args:
            return _usage("vault write_paper <json-blob>")
        blob = json.loads(args[0])
        print(vault.write_paper_file(
            title=blob["title"],
            doi=blob.get("doi", ""),
            authors=blob.get("authors", ""),
            year=str(blob.get("year", "")),
            venue=blob.get("venue", ""),
            abstract=blob.get("abstract", ""),
            relevance=blob.get("relevance", ""),
        ))
    elif cmd in ("attach_paper", "add_subtopic"):
        if len(args) < 2:
            return _usage(f"vault {cmd} <topic-path> <title>")
        fn = vault.attach_paper if cmd == "attach_paper" else vault.add_subtopic
        print("modified" if fn(Path(args[0]), args[1]) else "unchanged")
    elif cmd == "create_topic":
        if len(args) < 2:
            return _usage("vault create_topic <path> <description> [--leaf]")
        leaf = "--leaf" in args
        desc = " ".join(a for a in args[1:] if a != "--leaf")
        print(Vault.create_topic_file(Path(args[0]), desc, leaf))
    else:
        return _usage(f"vault <command>  (unknown command: {cmd})")
    return 0


# ---------- config ----------


def config_cli(cfg: Config, argv: list[str]) -> int:
    if argv[:1] == ["dump"]:
        _json(cfg.dump())
        return 0
    if argv[:1] == ["get"] and len(argv) == 2:
        key = argv[1]
        try:
            value = cfg.path(key[len("paths."):]) if key.startswith("paths.") else cfg.get(key)
        except KeyError:
            print(f"unknown config key: {key}", file=sys.stderr)
            return 2
        print(value if isinstance(value, str) else json.dumps(value))
        return 0
    return _usage("config dump | config get <dotted.key>")


# ---------- venue ----------


def venue_cli(argv: list[str]) -> int:
    if argv[:1] == ["normalize"] and len(argv) >= 2:
        year = None
        if "--year" in argv:
            i = argv.index("--year")
            year = argv[i + 1] if i + 1 < len(argv) else None
            argv = argv[:i] + argv[i + 2:]
        print(venues.short_name(" ".join(argv[1:]), year))
        return 0
    if argv[:1] == ["is-target"] and len(argv) >= 2:
        print("true" if venues.is_search_target(" ".join(argv[1:])) else "false")
        return 0
    if argv[:1] == ["list"]:
        _json([{"fragment": f, "short": s, "search_target": t} for f, s, t in venues.VENUES])
        return 0
    return _usage("venue normalize <venue> [--year Y] | venue is-target <venue> | venue list")


# ---------- style ----------


def style_cli(cfg: Config, argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "import-legacy":
        if len(argv) < 2:
            return _usage("style import-legacy <style.md> [--out rules.toml]")
        rules = stylelib.import_legacy(Path(argv[1]).read_text(encoding="utf-8"))
        n = len(rules["phrases"]["banned"]) + len(rules["phrases"]["avoided_transitions"])
        if n < 20:
            print(f"warning: extracted only {n} phrases; check the guide's heading format", file=sys.stderr)
        text = stylelib.rules_to_toml(rules, header=f"# Imported from {Path(argv[1]).name} by pw.py style import-legacy")
        if "--out" in argv:
            out = Path(argv[argv.index("--out") + 1])
            out.write_text(text, encoding="utf-8")
            print(out)
        else:
            sys.stdout.write(text)
        return 0
    if cmd == "validate":
        d = Path(argv[1]) if len(argv) > 1 else Path(stylelib.resolve(cfg)["dir"])
        errors, warnings = stylelib.validate(d)
        for w in warnings:
            print(f"warning: {w}")
        for e in errors:
            print(f"error: {e}")
        print(f"{d}: {'INVALID' if errors else 'OK'}")
        return 1 if errors else 0

    resolved = stylelib.resolve(cfg)
    for note in resolved["notes"]:
        print(f"note: {note}", file=sys.stderr)
    if cmd == "resolve":
        _json(resolved)
    elif cmd == "rules":
        _json(stylelib.load_rules(resolved))
    elif cmd == "scan":
        if len(argv) < 2:
            return _usage("style scan <file.tex>")
        tex = Path(argv[1]).read_text(encoding="utf-8")
        _json(stylelib.scan(tex, stylelib.load_rules(resolved)))
    else:
        return _usage("style resolve | rules | scan <file.tex> | validate [<dir>] | import-legacy <style.md>")
    return 0


def init_cli(argv: list[str]) -> int:
    from pwlib import init as initlib
    root = Path.cwd()
    try:
        if argv[:1] == ["allow-network"]:
            _json(initlib.allow_network(root, write="--print" not in argv[1:]))
            return 0
        if argv[:1] == ["profiles"]:
            _json(initlib.list_profiles())
            return 0
        opts = {"--title": "title", "--field": "field", "--venues": "target_venues",
                "--profile": "profile", "--vault": "vault", "--template": "template"}
        kw: dict = {}
        i = 0
        while i < len(argv):
            flag = argv[i]
            if flag not in opts or i + 1 >= len(argv):
                return _usage("init [--title T] [--field F] [--venues A,B] [--profile P] "
                              "[--vault DIR] [--template auto|ctan|tex|none] | init allow-network [--print] | init profiles")
            val = argv[i + 1]
            kw[opts[flag]] = [v.strip() for v in val.split(",") if v.strip()] if flag == "--venues" else val
            i += 2
        _json(initlib.init_project(root, **kw))
    except initlib.InitError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    group, rest = argv[0], argv[1:]
    try:
        if group == "venue":
            return venue_cli(rest)
        if group == "init":
            return init_cli(rest)
        cfg = Config.load()
        cfg.emit_warnings()
        if group == "vault":
            return vault_cli(cfg, rest)
        if group == "config":
            return config_cli(cfg, rest)
        if group == "style":
            return style_cli(cfg, rest)
    except (ConfigError, stylelib.StyleError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return _usage("<config|venue|style|vault|init> ...")


if __name__ == "__main__":
    sys.exit(main())
