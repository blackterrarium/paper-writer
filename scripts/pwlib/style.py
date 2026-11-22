"""Style profiles: resolution, rules, validation, legacy import, deterministic scan.

A style profile is a directory:

    style.md      prose guide, pasted into writing and review prompts
    rules.toml    machine-readable rules (schema below) used by the scan
    profile.toml  metadata: name (required), author, version, generator, created
    rubric.md     optional: judgment rubric for style-review Pass 2

rules.toml schema:

    [deterministic]            # each: "forbid" | "warn" | "allow"
    em_dash = "forbid"
    author_name_citations = "forbid"
    prose_semicolons = "warn"

    [phrases]
    banned = ["delve", "Moreover,"]
    avoided_transitions = ["Additionally,"]

    [swaps]                    # phrase (lower case) -> replacement; "" = delete (report only)
    "utilize" = "use"
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from .config import Config

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = PLUGIN_ROOT / "profiles" / "baseline"
LEGACY_STYLE = "guidelines/style.md"

DETERMINISTIC_RULES = ("em_dash", "author_name_citations", "prose_semicolons")
DETERMINISTIC_VALUES = ("forbid", "warn", "allow")

# Plugin-wide swap suggestions. Profiles extend or override these.
DEFAULT_SWAPS: dict[str, str] = {
    "delve": "examine", "delving": "examining", "delved": "examined", "delves": "examines",
    "utilize": "use", "utilizes": "uses", "utilizing": "using", "utilized": "used",
    "facilitate": "enable", "facilitates": "enables", "facilitating": "enabling", "facilitated": "enabled",
    "novel": "new",
    "plays a crucial role": "is central",
    "it is important to note that": "Note that",
    "it is worth noting that": "Note that",
    "it should be noted that": "Note that",
    "in recent years,": "", "interestingly,": "", "notably,": "", "importantly,": "",
    "remarkably,": "", "impressively,": "", "it appears that": "", "arguably,": "",
    "arguably": "", "to some extent": "", "one could argue that": "",
    "cutting-edge": "advanced", "groundbreaking": "significant",
}

DEFAULT_RULES: dict[str, Any] = {
    "deterministic": {k: "allow" for k in DETERMINISTIC_RULES},
    "phrases": {"banned": [], "avoided_transitions": []},
    "swaps": dict(DEFAULT_SWAPS),
}


class StyleError(Exception):
    pass


# ---------- resolution ----------


def user_profiles_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "paper-writer" / "profiles"


def resolve(cfg: Config) -> dict[str, Any]:
    """Locate the active profile and its files.

    Order: project `style.path`, then user-level `style.profile`, then a legacy
    `guidelines/style.md` in the project, then the bundled baseline profile.
    """
    style = cfg.get("style")
    notes: list[str] = []
    if style["path"]:
        d, source = Path(cfg.resolve(style["path"])), "project"
        if not (d / "style.md").is_file():
            raise StyleError(f"style.path {d} has no style.md")
    elif style["profile"]:
        d, source = user_profiles_dir() / style["profile"], "user"
        if not (d / "style.md").is_file():
            raise StyleError(f"style profile '{style['profile']}' not found at {d}")
    elif Path(cfg.resolve(LEGACY_STYLE)).is_file():
        d, source = Path(cfg.resolve(LEGACY_STYLE)).parent, "legacy"
        notes.append(f"using legacy {LEGACY_STYLE}; rules are derived from its headings. "
                     "Run `pw.py style import-legacy` to create rules.toml.")
    else:
        d, source = BASELINE_DIR, "baseline"
        notes.append("no style profile configured: using the plugin baseline. Output will not match "
                     "any particular author's voice. Set [style] in paper-writer.toml.")

    rubric = d / "rubric.md"
    if not rubric.is_file():
        rubric = BASELINE_DIR / "rubric.md"
        if source != "baseline":
            notes.append("profile has no rubric.md: style-review uses the baseline rubric.")

    overrides_md = overrides_toml = None
    if style["overrides"]:
        p = Path(cfg.resolve(style["overrides"]))
        if not p.is_file():
            raise StyleError(f"style.overrides {p} does not exist")
        overrides_md = p
        if p.with_suffix(".toml").is_file():
            overrides_toml = p.with_suffix(".toml")

    rules = d / "rules.toml"
    return {
        "source": source,
        "dir": str(d),
        "style_md": str(d / "style.md"),
        "rules_toml": str(rules) if rules.is_file() else None,
        "rubric_md": str(rubric),
        "overrides_md": str(overrides_md) if overrides_md else None,
        "overrides_toml": str(overrides_toml) if overrides_toml else None,
        "notes": notes,
    }


# ---------- rules ----------


def _dedupe_ci(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for s in items:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def merge(base: dict, over: dict) -> dict:
    """Lists are unioned (case-insensitive, base order first), tables merge, scalars replace."""
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge(out[k], v)
        elif k in out and isinstance(out[k], list) and isinstance(v, list):
            out[k] = _dedupe_ci([*out[k], *v])
        else:
            out[k] = v
    return out


def load_rules(resolved: dict) -> dict:
    if resolved["rules_toml"]:
        profile_rules = tomllib.loads(Path(resolved["rules_toml"]).read_text(encoding="utf-8"))
    elif resolved["source"] == "legacy":
        profile_rules = import_legacy(Path(resolved["style_md"]).read_text(encoding="utf-8"))
    else:
        profile_rules = {}
    rules = merge(DEFAULT_RULES, profile_rules)
    if resolved["overrides_toml"]:
        rules = merge(rules, tomllib.loads(Path(resolved["overrides_toml"]).read_text(encoding="utf-8")))
    rules["swaps"] = {k.lower(): v for k, v in rules["swaps"].items()}
    return rules


def check_rules(rules: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a rules mapping."""
    errors: list[str] = []
    warnings: list[str] = []
    for k in rules:
        if k not in DEFAULT_RULES:
            warnings.append(f"rules: unknown table [{k}]")
    det = rules.get("deterministic", {})
    if not isinstance(det, dict):
        errors.append("rules: [deterministic] must be a table")
        det = {}
    for k, v in det.items():
        if k not in DETERMINISTIC_RULES:
            warnings.append(f"rules: unknown deterministic rule '{k}'")
        elif v not in DETERMINISTIC_VALUES:
            errors.append(f"rules: deterministic.{k} must be one of {DETERMINISTIC_VALUES}, got {v!r}")
    phrases = rules.get("phrases", {})
    for k in ("banned", "avoided_transitions"):
        v = phrases.get(k, [])
        if not isinstance(v, list) or not all(isinstance(s, str) and s.strip() for s in v):
            errors.append(f"rules: phrases.{k} must be a list of non-empty strings")
    swaps = rules.get("swaps", {})
    if not isinstance(swaps, dict) or not all(isinstance(v, str) for v in swaps.values()):
        errors.append("rules: [swaps] must map strings to strings")
        swaps = {}
    banned = {s.lower().rstrip(",") for k in ("banned", "avoided_transitions")
              for s in phrases.get(k, []) if isinstance(s, str)}
    for src, dst in swaps.items():
        if dst and dst.lower().rstrip(",") in banned:
            errors.append(f"rules: swap '{src}' -> '{dst}' replaces one banned phrase with another")
    return errors, warnings


def validate(profile_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    d = Path(profile_dir)
    style_md = d / "style.md"
    if not style_md.is_file() or not style_md.read_text(encoding="utf-8").strip():
        errors.append("style.md is missing or empty")
    meta = d / "profile.toml"
    if not meta.is_file():
        errors.append("profile.toml is missing")
    else:
        try:
            m = tomllib.loads(meta.read_text(encoding="utf-8"))
            if not isinstance(m.get("name"), str) or not m["name"].strip():
                errors.append("profile.toml: 'name' is required")
        except tomllib.TOMLDecodeError as e:
            errors.append(f"profile.toml: {e}")
    rules = d / "rules.toml"
    if not rules.is_file():
        errors.append("rules.toml is missing")
    else:
        try:
            e2, w2 = check_rules(tomllib.loads(rules.read_text(encoding="utf-8")))
            errors += e2
            warnings += w2
        except tomllib.TOMLDecodeError as e:
            errors.append(f"rules.toml: {e}")
    if not (d / "rubric.md").is_file():
        warnings.append("rubric.md is missing: style-review will use the baseline rubric")
    return errors, warnings


# ---------- legacy import ----------

LEGACY_BANNED_HEADINGS = (
    "### Filler phrases to never use",
    "### Hedging patterns to never use",
    "### Enthusiasm patterns to never use",
)
LEGACY_TRANSITION_HEADING = "### Transitions the author avoids"


def _bullets_under(text: str, heading: str) -> list[str]:
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.strip() == heading:
            inside = True
            continue
        if inside and line.startswith("#"):
            break
        if inside and line.lstrip().startswith("- "):
            out.append(line.strip())
    return out


def _phrases_from_bullet(bullet: str) -> list[str]:
    s = bullet[2:] if bullet.startswith("- ") else bullet
    s = s.replace("`", "").replace("**", "").replace("*", "")
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    out = []
    for cand in re.findall(r'"([^"]*)"', s):
        cand = re.sub(r"(\.\.\.|…)$", "", cand).strip()
        if len(cand) >= 3:
            out.append(cand)
    return out


def import_legacy(style_md: str) -> dict:
    """Derive rules from a style guide written in the original heading format."""
    banned: list[str] = []
    for h in LEGACY_BANNED_HEADINGS:
        for b in _bullets_under(style_md, h):
            banned += _phrases_from_bullet(b)
    transitions: list[str] = []
    for b in _bullets_under(style_md, LEGACY_TRANSITION_HEADING):
        transitions += _phrases_from_bullet(b)
    banned = _dedupe_ci(banned)
    seen = {p.lower() for p in banned}
    transitions = [t for t in _dedupe_ci(transitions) if t.lower() not in seen]
    return {
        "deterministic": {k: "forbid" for k in DETERMINISTIC_RULES},
        "phrases": {"banned": banned, "avoided_transitions": transitions},
    }


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rules_to_toml(rules: dict, header: str = "") -> str:
    lines = [header.rstrip()] if header else []
    for table in ("deterministic", "phrases", "swaps"):
        if table not in rules:
            continue
        lines += ["", f"[{table}]"]
        for k, v in rules[table].items():
            key = k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else _toml_str(k)
            if isinstance(v, list):
                lines.append(f"{key} = [")
                lines += [f"  {_toml_str(x)}," for x in v]
                lines.append("]")
            else:
                lines.append(f"{key} = {_toml_str(v)}")
    return "\n".join(lines).lstrip("\n") + "\n"


# ---------- deterministic scan ----------

AUTHOR_CITE_RE = re.compile(
    r"\b[A-Z][a-z]+(?: and [A-Z][a-z]+)?(?: et al\.?)?\s+(?:show|shows|demonstrate|demonstrates|"
    r"propose|proposes|argue|argues|find|finds|report|reports|prove|proves|claim|claims|observe|observes)\b"
)
AUTHOR_CITE_STOPWORDS = set(
    "We Our Us I The This These Those That Here There Thus Hence However Note Observe Recall Consider "
    "Suppose Let It They One Some Many Most All Both Either Neither Such What When Where Why How Which "
    "Who First Second Third Next Finally Still Yet Also Again".split()
)
DASH_RE = re.compile(r"---|--|—")


def prose_view(tex: str) -> list[str]:
    """Line-preserving prose view of a LaTeX file (one output line per input line)."""
    out: list[str] = []
    in_verbatim = False
    for line in tex.split("\n"):
        if re.search(r"\\begin\{(verbatim|lstlisting|minted)\}", line):
            in_verbatim = True
        if in_verbatim:
            out.append("")
            if re.search(r"\\end\{(verbatim|lstlisting|minted)\}", line):
                in_verbatim = False
            continue
        line = re.sub(r"(?<!\\)%.*$", "", line)
        line = re.sub(r"\\(cite|ref|eqref|label|cref|Cref|citep|citet|autoref|nameref)\{[^}]*\}", "", line)
        line = re.sub(r"\\(textbf|textit|emph|textsc|textrm|textsf|texttt)\{([^}]*)\}", r"\2", line)
        line = re.sub(r"\\[a-zA-Z]+\*?\s*\{[^}]*\}", "", line)
        line = re.sub(r"\\[a-zA-Z]+\*?", "", line)
        line = re.sub(r"\\\\", "", line)
        line = re.sub(r"\$[^$]*\$", "", line)
        out.append(line)
    return out


def _context(line: str, start: int, end: int, words: int = 4) -> str:
    before = line[:start].split()[-words:]
    after = line[end:].split()[:words]
    return " ".join([*before, line[start:end], *after]).strip()


def _case_like(src: str, repl: str) -> str:
    """Capitalize the replacement if the original starts upper case, else lower-case it."""
    if not repl:
        return repl
    first = repl[:1].upper() if src[:1].isupper() else repl[:1].lower()
    return first + repl[1:]


def _phrase_re(phrase: str) -> re.Pattern:
    left = r"\b" if phrase[:1].isalnum() else ""
    right = r"\b" if phrase[-1:].isalnum() else ""
    return re.compile(left + re.escape(phrase) + right, re.IGNORECASE)


def scan(tex: str, rules: dict) -> dict:
    lines = prose_view(tex)
    det = rules["deterministic"]
    swaps = rules["swaps"]
    findings: list[dict] = []

    def add(rule: str, n: int, line: str, m: re.Match, fix: str | None, level: str) -> None:
        findings.append({
            "rule": rule, "line": n, "col": m.start() + 1, "original": m.group(0),
            "context": _context(line, m.start(), m.end()), "suggested_fix": fix, "level": level,
        })

    phrases = _dedupe_ci([*rules["phrases"]["banned"], *rules["phrases"]["avoided_transitions"]])
    patterns = [(p, _phrase_re(p)) for p in phrases]
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        taken: list[tuple[int, int]] = []
        for phrase, rx in sorted(patterns, key=lambda x: -len(x[0])):
            for m in rx.finditer(line):
                if any(m.start() < e and s < m.end() for s, e in taken):
                    continue  # a longer phrase already covers this span
                taken.append((m.start(), m.end()))
                key = m.group(0).lower()
                fix = swaps.get(key)
                fix = None if fix is None else ("(delete)" if fix == "" else _case_like(m.group(0), fix))
                add("banned-word", n, line, m, fix, "forbid")
        if det["em_dash"] != "allow":
            for m in DASH_RE.finditer(line):
                nxt = line[m.end():].lstrip()[:1]
                add("em-dash", n, line, m, ". " if nxt.isupper() else ", ", det["em_dash"])
        if det["author_name_citations"] != "allow":
            for m in AUTHOR_CITE_RE.finditer(line):
                if m.group(0).split()[0] in AUTHOR_CITE_STOPWORDS:
                    continue
                add("author-cite", n, line, m, "remove attributive clause", det["author_name_citations"])
        if det["prose_semicolons"] != "allow":
            for m in re.finditer(r"; ", line):
                add("semicolon", n, line, m, "split into two sentences", det["prose_semicolons"])

    findings.sort(key=lambda f: (f["line"], f["rule"], f["col"]))
    summary = {r: 0 for r in ("banned-word", "em-dash", "author-cite", "semicolon")}
    for f in findings:
        summary[f["rule"]] += 1
    return {"summary": summary, "total": len(findings), "findings": findings}
