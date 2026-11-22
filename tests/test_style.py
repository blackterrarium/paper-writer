import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pwlib import style  # noqa: E402
from pwlib.config import Config  # noqa: E402

LEGACY_GUIDE = """# Writing Style Guide

## 5. Transitions and Connectors

### Transitions the author avoids
- "Moreover," (rare: prefer "Furthermore")
- "That said," (absent: use However)

### Section-boundary transitions
- "Next, we" (this is allowed, not banned)

## 11. Anti-Patterns (What to Avoid)

### Filler phrases to never use
- "It is important to note that" (use "Note that" instead)
- **"delve"** / "landscape" / "a wide range of"
- "As shown in..." (wildcard)
- "ok" (too short, dropped)

### Hedging patterns to never use
- "may potentially"
- "Moreover," (duplicate across sections)

### Enthusiasm patterns to never use
- "groundbreaking" / "Revolutionary"
"""


def write_profile(d: Path, rules: str, name: str = "me", rubric: bool = True) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "style.md").write_text("# Guide\n\nWrite well.\n")
    (d / "rules.toml").write_text(rules)
    (d / "profile.toml").write_text(f'name = "{name}"\n')
    if rubric:
        (d / "rubric.md").write_text("1. **Clarity** — be clear.\n")
    return d


# ---------- legacy import ----------


def test_import_legacy_follows_original_algorithm():
    r = style.import_legacy(LEGACY_GUIDE)
    assert r["phrases"]["banned"] == [
        "It is important to note that", "delve", "landscape", "a wide range of", "As shown in",
        "may potentially", "Moreover,", "groundbreaking", "Revolutionary",
    ]
    # Parenthetical annotations ("Furthermore", "Note that") are not extracted as banned.
    assert "Furthermore" not in r["phrases"]["banned"]
    # Transitions already banned elsewhere are not repeated.
    assert r["phrases"]["avoided_transitions"] == ["That said,"]
    assert set(r["deterministic"].values()) == {"forbid"}


def test_rules_toml_roundtrip():
    r = style.import_legacy(LEGACY_GUIDE)
    r["swaps"] = {"utilize": "use", 'say "hi"': "x"}
    assert tomllib.loads(style.rules_to_toml(r, header="# hi")) == r


# ---------- validation ----------


def test_baseline_profile_is_valid():
    errors, warnings = style.validate(style.BASELINE_DIR)
    assert errors == [] and warnings == []


def test_validate_reports_problems(tmp_path):
    d = write_profile(tmp_path / "p", '[deterministic]\nem_dash = "never"\n[phrases]\nbanned = ["", 3]\n'
                      '[swaps]\n"utilize" = "leverage"\n', rubric=False)
    (d / "rules.toml").write_text((d / "rules.toml").read_text().replace('banned = ["", 3]', 'banned = ["leverage"]'))
    errors, warnings = style.validate(d)
    assert any("em_dash must be one of" in e for e in errors)
    assert any("replaces one banned phrase with another" in e for e in errors)
    assert any("rubric.md is missing" in w for w in warnings)

    (d / "profile.toml").write_text("author = 'x'\n")
    (d / "style.md").write_text("  \n")
    errors, _ = style.validate(d)
    assert "profile.toml: 'name' is required" in errors
    assert "style.md is missing or empty" in errors


# ---------- resolution + merge ----------


def test_resolution_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    r = style.resolve(Config.load())
    assert r["source"] == "baseline" and r["dir"] == str(style.BASELINE_DIR)

    (tmp_path / "guidelines").mkdir()
    (tmp_path / "guidelines" / "style.md").write_text(LEGACY_GUIDE)
    r = style.resolve(Config.load())
    assert r["source"] == "legacy" and r["rules_toml"] is None
    assert r["rubric_md"] == str(style.BASELINE_DIR / "rubric.md")
    assert style.load_rules(r)["phrases"]["banned"][0] == "It is important to note that"

    write_profile(tmp_path / "xdg" / "paper-writer" / "profiles" / "eve", '[phrases]\nbanned = ["eve-phrase"]\n')
    (tmp_path / "paper-writer.toml").write_text('[style]\nprofile = "eve"\n')
    r = style.resolve(Config.load())
    assert r["source"] == "user" and r["rubric_md"].endswith("eve/rubric.md")

    write_profile(tmp_path / "style", '[phrases]\nbanned = ["local"]\n')
    (tmp_path / "paper-writer.toml").write_text('[style]\nprofile = "eve"\npath = "style"\n')
    assert style.resolve(Config.load())["source"] == "project"

    (tmp_path / "paper-writer.toml").write_text('[style]\nprofile = "nobody"\n')
    with pytest.raises(style.StyleError, match="not found"):
        style.resolve(Config.load())


def test_overrides_merge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_profile(tmp_path / "style", '[deterministic]\nem_dash = "forbid"\n'
                  '[phrases]\nbanned = ["delve", "novel"]\n[swaps]\n"novel" = "new"\n')
    (tmp_path / "overrides.md").write_text("This paper allows semicolons.\n")
    (tmp_path / "overrides.toml").write_text('[deterministic]\nprose_semicolons = "allow"\nem_dash = "warn"\n'
                                             '[phrases]\nbanned = ["DELVE", "leverage"]\n[swaps]\n"Novel" = "fresh"\n')
    (tmp_path / "paper-writer.toml").write_text('[style]\npath = "style"\noverrides = "overrides.md"\n')
    r = style.resolve(Config.load())
    assert r["overrides_md"] == "overrides.md" and r["overrides_toml"] == "overrides.toml"
    rules = style.load_rules(r)
    assert rules["deterministic"] == {"em_dash": "warn", "author_name_citations": "allow", "prose_semicolons": "allow"}
    assert rules["phrases"]["banned"] == ["delve", "novel", "leverage"]  # union, case-insensitive
    assert rules["swaps"]["novel"] == "fresh"  # override wins; keys lower-cased
    assert rules["swaps"]["utilize"] == "use"  # plugin default survives


# ---------- scan ----------

SAMPLE = r"""\section{Intro}
Moreover, we delve into it --- it is important to note that latency grows.
Smith et al. show that queues build up; this is a problem \cite{x}.
% Interestingly, comments are ignored
We use a scheme—Acme—to fix it, with $a; b$ in math. However we proceed.
\begin{verbatim}
delve; --- inside verbatim
\end{verbatim}
Interestingly, Han and Lee propose a fix.
"""

ALL_FORBID = {
    "deterministic": {k: "forbid" for k in style.DETERMINISTIC_RULES},
    "phrases": {"banned": ["delve", "It is important to note that", "Interestingly,", "note that"],
                "avoided_transitions": ["Moreover,"]},
    "swaps": {"moreover,": "Furthermore,"},
}


def rules_with(extra: dict) -> dict:
    return style.merge(style.DEFAULT_RULES, extra)


def test_prose_view_preserves_lines():
    view = style.prose_view(SAMPLE)
    assert len(view) == len(SAMPLE.split("\n"))
    assert view[3] == "" and view[6] == ""  # comment line and verbatim body blanked
    assert "\\cite" not in view[2] and "$" not in view[4]


def test_scan_finds_each_rule():
    out = style.scan(SAMPLE, rules_with(ALL_FORBID))
    assert out["summary"] == {"banned-word": 4, "em-dash": 3, "author-cite": 2, "semicolon": 1}
    by = {(f["line"], f["original"]): f for f in out["findings"]}
    assert by[(2, "Moreover,")]["suggested_fix"] == "Furthermore,"
    assert by[(2, "delve")]["suggested_fix"] == "examine"
    # The longer phrase wins over the "note that" it contains.
    assert by[(2, "it is important to note that")]["suggested_fix"] == "note that"
    assert (2, "note that") not in by
    assert by[(9, "Interestingly,")]["suggested_fix"] == "(delete)"
    assert by[(2, "---")]["suggested_fix"] == ", "
    assert [f["suggested_fix"] for f in out["findings"] if f["original"] == "—"] == [". ", ", "]
    assert {f["original"] for f in out["findings"] if f["rule"] == "author-cite"} == {
        "Smith et al. show", "Han and Lee propose"}
    assert all(f["line"] not in (4, 6, 7, 8) for f in out["findings"])


def test_scan_respects_allow_and_warn():
    rules = rules_with({**ALL_FORBID, "deterministic": {"em_dash": "allow", "author_name_citations": "warn",
                                                         "prose_semicolons": "allow"}})
    out = style.scan(SAMPLE, rules)
    assert out["summary"]["em-dash"] == 0 and out["summary"]["semicolon"] == 0
    assert {f["level"] for f in out["findings"] if f["rule"] == "author-cite"} == {"warn"}


def test_author_cite_stopwords():
    out = style.scan("However we show this. The results show that. Recall that we prove it.\n",
                     rules_with({"deterministic": {"author_name_citations": "forbid"}}))
    assert out["summary"]["author-cite"] == 0
